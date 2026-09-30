"""
Modbus 读写往返测试

测试范围：
  1. Server 启动后 Client 能否连接
  2. Client 读取的寄存器值是否与 DeviceModel 一致
  3. Client 写入控制命令后 DeviceModel 状态是否改变
  4. 心跳计数是否递增

运行方式：
    pytest tests/test_modbus_roundtrip.py -v

注意：
    本测试会实际启动 Modbus TCP Server（异步），测试完成后自动关闭。
    使用 AsyncModbusTcpClient（pymodbus 3.15 推荐）。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.config.settings import CONFIG
from app.simulator.device_model import DeviceModel, DeviceState
from app.simulator.modbus_server import VirtualPlcServer
from app.simulator.register_map import decode_float, decode_status_word

# 使用非标准端口避免与系统服务冲突
TEST_PORT = 15020


async def _server_client():
    """
    启动 Server，返回 (server, pymodbus_client, model) 元组。
    测试结束后自动关闭。
    """
    from pymodbus.client import AsyncModbusTcpClient

    model = DeviceModel(CONFIG["simulator"])
    server = VirtualPlcServer(model)
    await server.start(host="127.0.0.1", port=TEST_PORT)

    # 给 Server 一点启动时间
    await asyncio.sleep(0.3)

    client = AsyncModbusTcpClient("127.0.0.1", port=TEST_PORT)
    await client.connect()

    return server, client, model


@pytest.mark.asyncio(loop_scope="function")
class TestModbusConnection:
    async def test_client_can_connect(self):
        server, client, _ = await _server_client()
        try:
            assert client.connected
        finally:
            client.close()
            await server.stop()


@pytest.mark.asyncio(loop_scope="function")
class TestModbusRead:
    async def test_read_initial_registers(self):
        """初始状态（STOPPED）读取寄存器"""
        server, client, model = await _server_client()
        try:
            # 等待至少一个 tick
            await asyncio.sleep(0.3)

            rr = await client.read_holding_registers(address=0, count=10)
            assert rr is not None
            assert not rr.isError()

            values = rr.registers
            assert len(values) == 10

            # 初始状态：转速应为 0
            assert decode_float(values[2], 1.0) == 0.0  # MOTOR_SPEED

            # 状态字：应无运行、无故障、无启动
            status = decode_status_word(values[5])
            assert status["running"] is False
            assert status["fault"] is False
            assert status["starting"] is False
        finally:
            client.close()
            await server.stop()

    async def test_heartbeat_increments(self):
        """心跳计数应随 tick 递增"""
        server, client, _ = await _server_client()
        try:
            await asyncio.sleep(0.3)
            rr1 = await client.read_holding_registers(address=9, count=1)
            hb1 = rr1.registers[0]

            await asyncio.sleep(0.5)
            rr2 = await client.read_holding_registers(address=9, count=1)
            hb2 = rr2.registers[0]

            assert hb2 > hb1, f"心跳未递增: {hb1} -> {hb2}"
        finally:
            client.close()
            await server.stop()


@pytest.mark.asyncio(loop_scope="function")
class TestModbusWrite:
    async def test_write_start_command(self):
        """写入启动命令后设备应进入 STARTING 状态"""
        server, client, model = await _server_client()
        try:
            # 等待初始 tick
            await asyncio.sleep(0.3)

            # 写入启动命令（40009 = 地址 8）
            wr = await client.write_register(address=8, value=1)
            assert wr is not None
            assert not wr.isError()

            # 等待命令被消费、设备状态更新
            await asyncio.sleep(0.5)

            # 读取状态字
            rr = await client.read_holding_registers(address=5, count=1)
            status = decode_status_word(rr.registers[0])
            assert status["starting"] is True or status["running"] is True
        finally:
            client.close()
            await server.stop()

    async def test_write_target_speed(self):
        """写入目标转速后应生效"""
        server, client, model = await _server_client()
        try:
            # 先启动设备
            await client.write_register(address=8, value=1)
            await asyncio.sleep(0.5)

            # 写入目标转速 1200 RPM（40008 = 地址 7）
            await client.write_register(address=7, value=1200)
            await asyncio.sleep(0.3)

            # 读取目标转速寄存器
            rr = await client.read_holding_registers(address=7, count=1)
            assert rr.registers[0] == 1200
        finally:
            client.close()
            await server.stop()

    async def test_command_consumed_and_cleared(self):
        """控制命令被消费后应自动清零"""
        server, client, _ = await _server_client()
        try:
            await asyncio.sleep(0.3)

            # 写入启动命令
            await client.write_register(address=8, value=1)
            await asyncio.sleep(0.3)

            # 读取控制命令寄存器，应为 0
            rr = await client.read_holding_registers(address=8, count=1)
            assert rr.registers[0] == 0, "控制命令未被清零"
        finally:
            client.close()
            await server.stop()
