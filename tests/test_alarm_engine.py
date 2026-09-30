"""
AlarmEngine 单元测试

测试范围：
  1. 报警产生（超过阈值）
  2. 迟滞恢复（回落到阈值以下减去迟滞量）
  3. 报警确认
  4. 报警等级变化（WARNING → ALARM）
  5. 多类型报警独立跟踪

运行方式：
    pytest tests/test_alarm_engine.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.processing.alarm_engine import AlarmEngine, AlarmLevel, AlarmStatus


class TestAlarmGeneration:
    def test_temperature_high_alarm(self):
        """温度超过报警阈值应产生报警"""
        engine = AlarmEngine()
        events = engine.process(temperature=85.0)

        assert len(events) == 1
        assert events[0].alarm_type == "temperature"
        assert events[0].level == AlarmLevel.ALARM
        assert events[0].status == AlarmStatus.ACTIVE

    def test_temperature_warning(self):
        """温度超过警告阈值但未达报警阈值"""
        engine = AlarmEngine()
        events = engine.process(temperature=76.0)

        assert len(events) == 1
        assert events[0].level == AlarmLevel.WARNING

    def test_no_alarm_when_normal(self):
        """正常温度不应产生报警"""
        engine = AlarmEngine()
        events = engine.process(temperature=50.0)

        assert len(events) == 0

    def test_pressure_low_alarm(self):
        """压力低于报警阈值应产生报警"""
        engine = AlarmEngine()
        events = engine.process(pressure=250.0)

        assert len(events) == 1
        assert events[0].alarm_type == "pressure"
        assert events[0].level == AlarmLevel.ALARM


class TestAlarmHysteresis:
    def test_alarm_recovery_with_hysteresis(self):
        """
        迟滞恢复测试：
        1. 温度 85℃ 产生报警（阈值 80，迟滞 2）
        2. 温度 79℃ 不应恢复（需要 ≤ 78）
        3. 温度 77℃ 应恢复
        """
        engine = AlarmEngine()

        # 产生报警（WARNING，因为 85 > 80 alarm_high，所以是 ALARM）
        events = engine.process(temperature=85.0)
        assert len(events) == 1
        assert events[0].status == AlarmStatus.ACTIVE
        assert events[0].level.value == "ALARM"

        # 79℃：79 > 75 warning_high，所以 current_level = WARNING
        # 但 active_event.level = ALARM，current_level = WARNING
        # 由于不允许降级，所以无变化
        events = engine.process(temperature=79.0)
        assert len(events) == 0  # 无状态变化
        assert len(engine.get_active_alarms()) == 1

        # 77℃：77 < 75 warning_high，所以 current_level = None
        # 检查恢复：threshold = alarm_high - hysteresis = 80 - 2 = 78
        # 77 <= 78，应恢复
        events = engine.process(temperature=77.0)
        assert len(events) == 1
        assert events[0].status == AlarmStatus.RECOVERED
        assert len(engine.get_active_alarms()) == 0

    def test_no_recovery_without_hysteresis_cross(self):
        """未跨过迟滞边界不应恢复"""
        engine = AlarmEngine()
        engine.process(temperature=85.0)

        # 80.5℃ 仍高于 80-2=78
        events = engine.process(temperature=80.5)
        assert len(events) == 0
        assert len(engine.get_active_alarms()) == 1


class TestAlarmAcknowledge:
    def test_acknowledge_active_alarm(self):
        """确认活动报警"""
        engine = AlarmEngine()
        engine.process(temperature=85.0)

        result = engine.acknowledge("temperature")
        assert result is not None
        assert result.alarm_type == "temperature"

        # 确认后应从活动列表移除
        assert len(engine.get_active_alarms()) == 0

    def test_acknowledge_nonexistent_alarm(self):
        """确认不存在的报警应失败"""
        engine = AlarmEngine()
        result = engine.acknowledge("temperature")
        assert result is None


class TestAlarmLevelChange:
    def test_warning_to_alarm_escalation(self):
        """报警升级：WARNING → ALARM"""
        engine = AlarmEngine()

        # 先产生 WARNING
        events = engine.process(temperature=76.0)
        assert events[0].level == AlarmLevel.WARNING

        # 升级到 ALARM
        events = engine.process(temperature=85.0)
        assert len(events) == 1
        assert events[0].level == AlarmLevel.ALARM


class TestMultipleAlarmTypes:
    def test_multiple_independent_alarms(self):
        """多种报警类型应独立跟踪"""
        engine = AlarmEngine()

        events = engine.process(temperature=85.0, pressure=550.0)
        assert len(events) == 2

        active = engine.get_active_alarms()
        assert len(active) == 2

        # 恢复温度报警
        engine.process(temperature=70.0)
        active = engine.get_active_alarms()
        assert len(active) == 1
        assert active[0].alarm_type == "pressure"
