"""
Modbus TCP Server —— 虚拟 PLC 的通信接口

基于 pymodbus 3.15.0 实现，将 DeviceModel 的数据暴露为 Modbus Holding Register。

设计要点：
  1. 每个 tick（200ms）更新一次寄存器值，保持数据新鲜
  2. 40009 控制命令寄存器被消费后自动清零
  3. 40008 目标转速写入后立即生效（通过 DeviceModel.set_target_speed）
  4. 心跳计数（40010）每 tick 自增，用于上位机通信活性检测
  5. 所有寄存器定义来自 register_map.py，避免硬编码

重要说明：
  本模型为简化模型，用于产生具有工业过程特征的仿真数据，
  不代表任何真实设备的精确动力学模型。
"""

import asyncio
import logging
from typing import Optional

from pymodbus.server import ModbusTcpServer
from pymodbus.simulator import SimData, SimDevice, DataType

from app.config.settings import CONFIG
from app.simulator.device_model import DeviceModel, DeviceState, FaultCode
from app.simulator.register_map import (
    encode_float,
    encode_status_word,
    ControlCommand,
    CONTROL_CMD_NAMES,
)

# 配置 pymodbus 日志级别（减少控制台噪音）
logging.getLogger("pymodbus").setLevel(logging.WARNING)


class VirtualPlcServer:
    """
    虚拟 PLC Modbus TCP Server

    职责：
      - 维护 Modbus 寄存器数据存储
      - 周期性 tick 更新寄存器（从 DeviceModel 读取最新数据）
      - 处理控制命令写入（40009）并调用 DeviceModel 对应操作
      - 处理目标转速写入（40008）
    """

    def __init__(self, device_model: DeviceModel):
        self._model = device_model
        self._tick_ms = CONFIG["simulator"]["tick_interval_ms"]
        self._slave_id = CONFIG["modbus"]["slave_id"]

        # 使用 pymodbus 3.15 推荐的 SimData/SimDevice API
        # 10 个 holding register，地址 0-9，初始值 0，类型 uint16
        self._sim_data = SimData(
            address=0,
            count=10,
            values=[0] * 10,
            datatype=DataType.UINT16,
        )
        self._device = SimDevice(
            id=self._slave_id,
            simdata=[self._sim_data],
        )

        self._server: Optional[ModbusTcpServer] = None
        self._server_task: Optional[asyncio.Task] = None
        self._tick_task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    async def start(self, host: str = "0.0.0.0", port: int = 5020):
        """启动 Modbus TCP Server 和 tick 循环。"""
        if self._running:
            return
        self._running = True

        # 创建并启动 Modbus TCP Server
        self._server = ModbusTcpServer(
            context=self._device,
            address=(host, port),
        )
        await self._server.listen()
        self._server_task = asyncio.create_task(self._server.serve_forever(background=True))

        # 启动 tick 循环（更新寄存器 + 处理控制命令）
        self._tick_task = asyncio.create_task(self._tick_loop())

        print(f"[Modbus Server] 已启动于 {host}:{port} (slave_id={self._slave_id})")

    async def stop(self):
        """停止 Server 和 tick 循环。"""
        if not self._running:
            return
        self._running = False

        if self._tick_task:
            self._tick_task.cancel()
            try:
                await self._tick_task
            except asyncio.CancelledError:
                pass

        if self._server:
            await self._server.shutdown()
            self._server_task = None

        print("[Modbus Server] 已停止。")

    # ------------------------------------------------------------------
    # 内部 tick 循环
    # ------------------------------------------------------------------

    async def _tick_loop(self):
        """周期性 tick：更新设备模型、刷新寄存器、处理控制命令。"""
        try:
            while self._running:
                # 1. 执行设备模型 tick
                snapshot = self._model.tick()

                # 2. 检查是否有控制命令写入（40009）
                await self._process_control_command()

                # 3. 检查是否有目标转速写入（40008）
                await self._process_target_speed()

                # 4. 将最新快照写入寄存器
                await self._update_registers(snapshot)

                await asyncio.sleep(self._tick_ms / 1000.0)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[Modbus Server] tick 循环异常: {e}")
            raise

    # ------------------------------------------------------------------
    # 寄存器更新
    # ------------------------------------------------------------------

    async def _update_registers(self, snap):
        """将 DeviceSnapshot 编码后写入 Holding Register。"""
        values = [
            encode_float(snap.temperature, 10.0),          # 40001
            encode_float(snap.pressure, 10.0),             # 40002
            encode_float(snap.motor_speed, 1.0),           # 40003
            encode_float(snap.current, 10.0),              # 40004
            encode_float(snap.voltage, 10.0),              # 40005
            encode_status_word(
                running=(snap.state == DeviceState.RUNNING),
                fault=(snap.state == DeviceState.FAULT),
                starting=(snap.state == DeviceState.STARTING),
            ),                                              # 40006
            snap.fault_code.value,                          # 40007
            encode_float(snap.target_speed, 1.0),          # 40008
            0,                                              # 40009（控制命令消费后清零）
            snap.heartbeat,                                 # 40010
        ]
        # 使用 SimCore 的 async_setValues 写入寄存器
        await self._server.context.async_setValues(
            self._slave_id, 3, 0, values
        )

    # ------------------------------------------------------------------
    # 控制命令处理
    # ------------------------------------------------------------------

    async def _process_control_command(self):
        """
        读取 40009 控制命令寄存器，执行对应操作后清零。
        """
        vals = await self._server.context.async_getValues(
            self._slave_id, 3, 8, 1
        )
        cmd_raw = vals[0]  # 地址 8 = 40009
        if cmd_raw == 0:
            return

        cmd = ControlCommand(cmd_raw) if cmd_raw in (1, 2, 3, 4) else ControlCommand.NONE
        cmd_name = CONTROL_CMD_NAMES.get(cmd_raw, f"UNKNOWN({cmd_raw})")
        print(f"[Modbus Server] 收到控制命令: {cmd_name}")

        if cmd == ControlCommand.START:
            self._model.start()
        elif cmd == ControlCommand.STOP:
            self._model.stop()
        elif cmd == ControlCommand.INJECT_FAULT:
            self._model.inject_fault()
        elif cmd == ControlCommand.CLEAR_FAULT:
            self._model.clear_fault()

        # 消费后清零
        await self._server.context.async_setValues(
            self._slave_id, 6, 8, [0]
        )

    async def _process_target_speed(self):
        """
        读取 40008 目标转速寄存器，如果与当前目标不同则更新。
        """
        vals = await self._server.context.async_getValues(
            self._slave_id, 3, 7, 1
        )
        raw = vals[0]  # 地址 7 = 40008
        new_speed = raw  # scale=1.0，无需解码

        if new_speed != int(self._model._target_speed) and new_speed > 0:
            # 只在 RUNNING/STARTING 状态有效
            if self._model.state in (DeviceState.STARTING, DeviceState.RUNNING):
                self._model.set_target_speed(float(new_speed))
                print(f"[Modbus Server] 目标转速更新: {new_speed} RPM")
