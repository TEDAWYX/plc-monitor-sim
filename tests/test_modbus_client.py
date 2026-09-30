"""
PlcModbusClient 单元测试

测试范围：
  1. 连接/断开
  2. 读取寄存器
  3. 写入寄存器
  4. 心跳检测
  5. 自动重连

运行方式：
    pytest tests/test_modbus_client.py -v

注意：
  - PlcModbusClient 自 V1.1.1 起为同步接口（内部自带后台事件循环线程）
  - 虚拟 PLC 服务端仍是异步实现，故测试函数保留 asyncio 标记
  - 需要先启动 Modbus Server（由测试自动启动和停止）。
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


async def _teardown(client: PlcModbusClient, server: VirtualPlcServer):
    """统一清理：断开客户端、停止事件循环、关闭服务端"""
    try:
        # 注意：client 方法是阻塞调用，必须放到线程里执行，
        # 否则会阻塞当前事件循环，导致运行在同一循环上的虚拟 PLC
        # 服务端无法处理请求（测试死锁）。
        await asyncio.to_thread(client.disconnect)
    except Exception:
        pass
    try:
        await asyncio.to_thread(client.shutdown)
    except Exception:
        pass
    await server.stop()


async def _call(client: PlcModbusClient, method: str, *args, **kwargs):
    """在线程中执行 client 的阻塞方法，避免阻塞服务端事件循环。"""
    return await asyncio.to_thread(getattr(client, method), *args, **kwargs)


@pytest.mark.asyncio(loop_scope="function")
class TestModbusClient:
    async def test_connect_and_disconnect(self):
        server, _ = await _setup_server()
        client = PlcModbusClient(port=TEST_PORT)
        try:
            result = await _call(client, "connect")
            assert result is True
            assert client.is_connected is True

            await _call(client, "disconnect")
            assert client.is_connected is False
        finally:
            await _teardown(client, server)

    async def test_read_registers(self):
        server, model = await _setup_server()
        client = PlcModbusClient(port=TEST_PORT)
        try:
            await _call(client, "connect")

            regs = await _call(client, "read_all_registers")
            assert regs is not None
            assert len(regs) == 10
            # 初始状态转速为 0
            assert regs[2] == 0
        finally:
            await _teardown(client, server)

    async def test_write_and_read_back(self):
        server, model = await _setup_server()
        client = PlcModbusClient(port=TEST_PORT)
        try:
            await _call(client, "connect")

            # 先启动设备（否则目标转速写入无效）
            await _call(client, "write_register", address=8, value=1)
            await asyncio.sleep(0.3)

            # 写入目标转速 1200（地址 7）
            ok = await _call(client, "write_register", address=7, value=1200)
            assert ok is True

            # 读取验证
            regs = await _call(client, "read_all_registers")
            assert regs[7] == 1200
        finally:
            await _teardown(client, server)

    async def test_heartbeat_detection(self):
        server, model = await _setup_server()
        client = PlcModbusClient(port=TEST_PORT, heartbeat_fail_count=3)
        try:
            await _call(client, "connect")

            # 正常心跳应递增（纯内存操作，直接调用即可）
            assert client.check_communication_health(1) is True
            assert client.check_communication_health(2) is True
            assert client.check_communication_health(3) is True

            # 连续 3 次相同应判定异常
            assert client.check_communication_health(3) is True   # 第1次相同
            assert client.check_communication_health(3) is True   # 第2次相同
            assert client.check_communication_health(3) is False  # 第3次相同 → 异常
        finally:
            await _teardown(client, server)

    async def test_auto_reconnect(self):
        """断开连接后读取应自动尝试重连"""
        server, model = await _setup_server()
        client = PlcModbusClient(port=TEST_PORT)
        try:
            await _call(client, "connect")
            assert client.is_connected

            # 手动断开
            await _call(client, "disconnect")
            assert not client.is_connected

            # 读取应自动重连
            regs = await _call(client, "read_all_registers")
            assert regs is not None
            assert client.is_connected
        finally:
            await _teardown(client, server)
