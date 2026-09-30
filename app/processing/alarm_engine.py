"""
报警引擎

职责：
  1. 根据配置的阈值和迟滞参数判断报警状态
  2. 报警状态机：产生 → 确认 → 恢复
  3. 支持多类型报警（温度、压力、电流、电压、转速）
  4. 报警记录持久化到数据库

设计要点：
  - 迟滞机制：超过 high_limit 产生报警，回落到 (high_limit - hysteresis) 以下才恢复
  - 状态机：ACTIVE → RECOVERED（自动）/ ACKNOWLEDGED（手动）
  - 每个报警类型独立跟踪当前状态
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Optional

from app.config.settings import CONFIG

logger = logging.getLogger(__name__)


class AlarmLevel(Enum):
    """报警等级"""
    WARNING = "WARNING"   # 警告
    ALARM = "ALARM"       # 报警


class AlarmStatus(Enum):
    """报警状态"""
    ACTIVE = "ACTIVE"           # 活动中
    RECOVERED = "RECOVERED"     # 已恢复
    ACKNOWLEDGED = "ACKNOWLEDGED"  # 已确认（保留状态）


@dataclass
class AlarmEvent:
    """报警事件"""
    alarm_type: str
    level: AlarmLevel
    value: float
    timestamp: datetime
    status: AlarmStatus = AlarmStatus.ACTIVE
    db_id: Optional[int] = None


class AlarmEngine:
    """
    报警引擎

    职责：
      1. 根据配置的阈值和迟滞参数判断报警状态
      2. 报警状态机：产生 → 确认 → 恢复
      3. 支持多类型报警（温度、压力、电流、电压、转速）

    注意：
      本引擎不再直接操作数据库。报警持久化由调用方（如 MainWindow）
      通过 DatabaseWriterThread 异步完成。
    """

    def __init__(self):
        self._config = CONFIG["alarms"]

        # 当前活动报警（alarm_type -> AlarmEvent）
        self._active_alarms: dict[str, AlarmEvent] = {}

        # 报警历史（用于 GUI 显示）
        self._alarm_history: list[AlarmEvent] = []

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def process(self, **sensor_values) -> list[AlarmEvent]:
        """
        处理一组传感器数据，判断报警状态变化。

        参数：
          sensor_values: 关键字参数，如 temperature=72.3, pressure=350.1

        返回：
          本次处理产生的新报警事件列表（产生或恢复）
        """
        new_events = []

        for alarm_type, value in sensor_values.items():
            if alarm_type not in self._config:
                continue

            cfg = self._config[alarm_type]
            event = self._check_alarm(alarm_type, value, cfg)
            if event:
                new_events.append(event)

        return new_events

    def acknowledge(self, alarm_type: str) -> Optional[AlarmEvent]:
        """
        手动确认报警。

        返回：
          被确认的报警事件（供调用方持久化），不存在则返回 None。
        """
        if alarm_type not in self._active_alarms:
            return None

        event = self._active_alarms[alarm_type]
        event.status = AlarmStatus.ACKNOWLEDGED

        logger.info(f"[Alarm] 报警已确认: {alarm_type}")
        return event

    def get_active_alarms(self) -> list[AlarmEvent]:
        """获取当前活动报警列表。"""
        return [
            event for event in self._active_alarms.values()
            if event.status == AlarmStatus.ACTIVE
        ]

    def get_all_alarms(self, limit: int = 100) -> list[AlarmEvent]:
        """获取报警历史。"""
        return self._alarm_history[-limit:]

    def clear_history(self):
        """清空报警历史。"""
        self._alarm_history.clear()
        self._active_alarms.clear()

    # ------------------------------------------------------------------
    # 内部报警判断
    # ------------------------------------------------------------------

    def _check_alarm(self, alarm_type: str, value: float, cfg: dict) -> Optional[AlarmEvent]:
        """
        检查单个报警类型的状态变化。
        返回新产生的报警事件，无变化返回 None。
        """
        warning_high = cfg.get("warning_high")
        warning_low = cfg.get("warning_low")
        alarm_high = cfg.get("alarm_high")
        alarm_low = cfg.get("alarm_low")
        hysteresis = cfg.get("hysteresis", 0.0)

        # 确定当前报警等级（如果有）
        current_level = None
        if alarm_high is not None and value > alarm_high:
            current_level = AlarmLevel.ALARM
        elif alarm_low is not None and value < alarm_low:
            current_level = AlarmLevel.ALARM
        elif warning_high is not None and value > warning_high:
            current_level = AlarmLevel.WARNING
        elif warning_low is not None and value < warning_low:
            current_level = AlarmLevel.WARNING

        # 检查是否有活动报警
        active_event = self._active_alarms.get(alarm_type)

        if active_event and active_event.status == AlarmStatus.ACTIVE:
            # 有活动报警时，优先检查恢复条件
            threshold = self._get_recovery_threshold(active_event, cfg)
            if threshold is not None and value <= threshold:
                # 报警恢复
                active_event.status = AlarmStatus.RECOVERED
                del self._active_alarms[alarm_type]
                self._persist_recovery(active_event)
                logger.info(f"[Alarm] 报警恢复: {alarm_type}={value:.1f}")
                return active_event

        if current_level:
            # 有报警条件
            if active_event is None:
                # 新报警产生
                event = AlarmEvent(
                    alarm_type=alarm_type,
                    level=current_level,
                    value=value,
                    timestamp=datetime.now(),
                    status=AlarmStatus.ACTIVE,
                )
                self._active_alarms[alarm_type] = event
                self._alarm_history.append(event)
                self._persist_alarm(event)
                logger.warning(
                    f"[Alarm] 报警产生: {alarm_type}={value:.1f} ({current_level.value})"
                )
                return event
            elif active_event.level != current_level:
                # 报警等级变化（如 WARNING → ALARM）
                # 只允许升级，不允许自动降级
                if current_level.value == "ALARM" and active_event.level.value == "WARNING":
                    active_event.level = current_level
                    active_event.value = value
                    logger.warning(
                        f"[Alarm] 报警升级: {alarm_type}={value:.1f} ({current_level.value})"
                    )
                    return active_event
                # 其他等级变化忽略（保持当前状态）
                return None

        return None

    def _get_recovery_threshold(self, event: AlarmEvent, cfg: dict) -> Optional[float]:
        """
        获取报警恢复阈值。
        根据报警类型和等级计算。
        恢复规则：
          - 高限报警：恢复到 alarm_high - hysteresis 以下
          - 低限报警：恢复到 alarm_low + hysteresis 以上
        """
        hysteresis = cfg.get("hysteresis", 0.0)

        # 优先使用 alarm 阈值（即使当前是 WARNING，也按原始触发阈值恢复）
        if cfg.get("alarm_high") is not None:
            return cfg["alarm_high"] - hysteresis
        if cfg.get("alarm_low") is not None:
            return cfg["alarm_low"] + hysteresis
        if cfg.get("warning_high") is not None:
            return cfg["warning_high"] - hysteresis
        if cfg.get("warning_low") is not None:
            return cfg["warning_low"] + hysteresis

        return None

    # ------------------------------------------------------------------
    # 持久化（V1.1 起不再直接操作数据库，由调用方异步完成）
    # ------------------------------------------------------------------

    def _persist_alarm(self, event: AlarmEvent):
        """报警产生时的内部回调（占位，持久化由调用方负责）。"""
        pass

    def _persist_recovery(self, event: AlarmEvent):
        """报警恢复时的内部回调（占位，持久化由调用方负责）。"""
        pass
