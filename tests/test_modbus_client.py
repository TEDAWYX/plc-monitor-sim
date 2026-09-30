"""
PlcModbusClient 单元测试

测试范围：
  1. 连接/断开
  2. 读取寄存器
  3. 写入寄存器
  4. 心跳检测

运行方式：
    pytest tests/test_modbus_client.py -v

注意：需要先启动 Modbus Server（由测试自动启动和停止）。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.config.settings import CONFIG
from app.simulator.device_model import DeviceModel
from app.simulator.modbus_server import VirtualPlcServer
from app.communication.modbus_client import PlcModbusClient

TEST_PORT = 15050


async def _setup_server():
    """启动测试用的 Modbus Server"""
    model = DeviceModel(CONFIG["simulator"])
    server = VirtualPlcServer(model)
    await server.start(host="127.0.0.1", port=TEST_PORT)
    await asyncio.sleep(0.3)
    return server, model


@pytest.mark.asyncio(loop_scope="function")
class TestModbusClient:
    async def test_connect_and_disconnect(self):
        server, _ = await _setup_server()
        try:
            client = PlcModbusClient(port=TEST_PORT)
            result = await client.connect()
            assert result is True
            assert client.is_connected is True

            await client.disconnect()
            assert client.is_connected is False
        finally:
            await server.stop()

    async def test_read_registers(self):
        server, model = await _setup_server()
        try:
            client = PlcModbusClient(port=TEST_PORT)
            await client.connect()

            regs = await client.read_all_registers()
            assert regs is not None
            assert len(regs) == 10
            # 初始状态转速为 0
            assert regs[2] == 0
        finally:
            await server.stop()

    async def test_write_and_read_back(self):
        server, model = await _setup_server()
        try:
            client = PlcModbusClient(port=TEST_PORT)
            await client.connect()

            # 先启动设备（否则目标转速写入无效）
            await client.write_register(address=8, value=1)
            await asyncio.sleep(0.3)

            # 写入目标转速 1200（地址 7）
            ok = await client.write_register(address=7, value=1200)
            assert ok is True

            # 读取验证
            regs = await client.read_all_registers()
            assert regs[7] == 1200
        finally:
            await server.stop()

    async def test_heartbeat_detection(self):
        server, model = await _setup_server()
        try:
            client = PlcModbusClient(port=TEST_PORT, heartbeat_fail_count=3)
            await client.connect()

            # 正常心跳应递增
            assert await client.check_communication_health(1) is True
            assert await client.check_communication_health(2) is True
            assert await client.check_communication_health(3) is True

            # 连续 3 次相同应判定异常
            assert await client.check_communication_health(3) is True   # 第1次相同
            assert await client.check_communication_health(3) is True   # 第2次相同
            assert await client.check_communication_health(3) is False  # 第3次相同 → 异常
        finally:
            await server.stop()

    async def test_auto_reconnect(self):
        """断开连接后读取应自动尝试重连"""
        server, model = await _setup_server()
        try:
            client = PlcModbusClient(port=TEST_PORT)
            await client.connect()
            assert client.is_connected

            # 手动断开
            await client.disconnect()
            assert not client.is_connected

            # 读取应自动重连
            regs = await client.read_all_registers()
            assert regs is not None
            assert client.is_connected
        finally:
            await server.stop()
