"""
数据采集线程（QThread）

职责：
  1. 周期性（默认 500ms）通过 Modbus Client 读取寄存器
  2. 数据校验（范围检查）
  3. 加时间戳
  4. 通过 Qt signals 推送数据快照到 GUI
  5. 通信状态监控（心跳检测）

设计要点：
  - 继承 QThread，与 GUI 主线程分离
  - 使用 Qt signals/slots 跨线程通信
  - 采集周期可配置
  - 线程安全退出（通过 _running 标志位）

注意（V1.1.1）：
  PlcModbusClient 已改为同步接口（内部自带后台事件循环），
  本线程直接调用即可，不再自行创建/关闭 asyncio 事件循环。
"""

import logging
from dataclasses import dataclass
from datetime import datetime

from PySide6.QtCore import QThread, Signal

from app.config.settings import CONFIG
from app.communication.modbus_client import PlcModbusClient
from app.simulator.register_map import (
    decode_float,
    decode_status_word,
    REGISTER_BY_ADDRESS,
)

logger = logging.getLogger(__name__)


@dataclass
class SensorSnapshot:
    """传感器数据快照（带时间戳）"""
    timestamp: datetime
    temperature: float      # ℃
    pressure: float         # kPa
    motor_speed: float      # RPM
    current: float          # A
    voltage: float          # V
    running: bool
    fault: bool
    starting: bool
    fault_code: int
    heartbeat: int
    comm_status: str        # "OK" / "ERROR" / "DISCONNECTED"


class AcquisitionWorker(QThread):
    """
    数据采集工作线程

    Signals:
      data_ready(SensorSnapshot): 新数据快照可用
      comm_status_changed(str): 通信状态变化
    """

    data_ready = Signal(SensorSnapshot)
    comm_status_changed = Signal(str)

    def __init__(self, client: PlcModbusClient = None, period_ms: int = None):
        super().__init__()
        self._client = client or PlcModbusClient()
        self._period_ms = period_ms or CONFIG["acquisition"]["period_ms"]
        self._running = False
        self._comm_status = "DISCONNECTED"

    def run(self):
        """线程主循环：周期性采集。"""
        self._running = True
        logger.info("[Acquisition] 采集线程启动")

        try:
            while self._running:
                snapshot = self._acquire_once()
                if snapshot:
                    self.data_ready.emit(snapshot)

                    # 通信状态变化时发射信号
                    new_status = snapshot.comm_status
                    if new_status != self._comm_status:
                        self._comm_status = new_status
                        self.comm_status_changed.emit(new_status)

                self.msleep(self._period_ms)
        finally:
            # 线程退出前断开连接并关闭后台事件循环
            try:
                self._client.disconnect()
                self._client.shutdown()
            except Exception as e:
                logger.warning(f"[Acquisition] 客户端清理异常: {e}")

        logger.info("[Acquisition] 采集线程停止")

    def stop(self):
        """请求线程停止（线程安全）。"""
        self._running = False
        self.wait(2000)  # 最多等待 2 秒

    # ------------------------------------------------------------------
    # 单次采集
    # ------------------------------------------------------------------

    def _acquire_once(self) -> SensorSnapshot | None:
        """执行一次采集。返回 SensorSnapshot，失败返回 None。"""
        # 1. 确保连接（同步接口，内部自动重连）
        if not self._client.is_connected:
            if not self._client.connect():
                return self._make_error_snapshot("DISCONNECTED")

        # 2. 读取寄存器
        registers = self._client.read_all_registers()
        if registers is None:
            return self._make_error_snapshot("ERROR")

        # 3. 解码数据
        try:
            temperature = decode_float(registers[0], 10.0)
            pressure = decode_float(registers[1], 10.0)
            motor_speed = decode_float(registers[2], 1.0)
            current = decode_float(registers[3], 10.0)
            voltage = decode_float(registers[4], 10.0)
            status = decode_status_word(registers[5])
            fault_code = registers[6]
            heartbeat = registers[9]
        except (IndexError, ValueError) as e:
            logger.error(f"[Acquisition] 数据解码错误: {e}")
            return self._make_error_snapshot("ERROR")

        # 4. 数据校验（范围检查）
        if not self._validate_data(temperature, pressure, motor_speed, current, voltage):
            logger.warning("[Acquisition] 数据校验失败，丢弃本次数据")
            return self._make_error_snapshot("ERROR")

        # 5. 心跳检测
        if not self._client.check_communication_health(heartbeat):
            return self._make_error_snapshot("ERROR")

        return SensorSnapshot(
            timestamp=datetime.now(),
            temperature=temperature,
            pressure=pressure,
            motor_speed=motor_speed,
            current=current,
            voltage=voltage,
            running=status["running"],
            fault=status["fault"],
            starting=status["starting"],
            fault_code=fault_code,
            heartbeat=heartbeat,
            comm_status="OK",
        )

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _make_error_snapshot(self, status: str) -> SensorSnapshot:
        """生成错误状态的快照。"""
        return SensorSnapshot(
            timestamp=datetime.now(),
            temperature=0.0,
            pressure=0.0,
            motor_speed=0.0,
            current=0.0,
            voltage=0.0,
            running=False,
            fault=False,
            starting=False,
            fault_code=0,
            heartbeat=0,
            comm_status=status,
        )

    def _validate_data(
        self,
        temperature: float,
        pressure: float,
        motor_speed: float,
        current: float,
        voltage: float,
    ) -> bool:
        """
        数据范围校验。
        使用宽松的物理上限，主要过滤明显的异常值。
        """
        # 温度：-50 ~ 200℃
        if not (-50.0 <= temperature <= 200.0):
            return False
        # 压力：0 ~ 1000 kPa
        if not (0.0 <= pressure <= 1000.0):
            return False
        # 转速：0 ~ 2000 RPM
        if not (0.0 <= motor_speed <= 2000.0):
            return False
        # 电流：0 ~ 100 A
        if not (0.0 <= current <= 100.0):
            return False
        # 电压：0 ~ 500 V
        if not (0.0 <= voltage <= 500.0):
            return False
        return True
