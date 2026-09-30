"""
Modbus TCP Client 封装

基于 pymodbus 3.15.0 AsyncModbusTcpClient 实现。

职责：
  1. 与虚拟 PLC 建立/断开连接
  2. 读取 Holding Register（功能码 03）
  3. 写入 Holding Register（功能码 06）
  4. 心跳检测：连续 N 次心跳不变判定通信异常
  5. 连接状态管理：连接/断开/异常

设计要点（V1.1.1 修复）：
  - AsyncModbusTcpClient 的 transport 绑定在创建它的 asyncio 事件循环上。
    如果每次调用都新建事件循环（旧实现），循环关闭后 transport 随之失效，
    而 client.connected 状态残留为 True，导致
    'NoneType' object has no attribute 'send' 异常无限刷屏。
  - 修复方案：客户端内部持有一个常驻后台事件循环线程，
    所有协程统一调度到该循环执行（asyncio.run_coroutine_threadsafe）。
  - 对外暴露同步方法：采集线程（QThread）和 GUI 线程直接调用即可，
    无需各自管理事件循环，也天然规避了跨循环共享 client 的问题。
  - 通信异常不抛异常到上层，而是返回 None/False 并记录日志。
"""

import asyncio
import logging
import threading
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient

from app.config.settings import CONFIG
from app.simulator.register_map import REGISTER_COUNT

logger = logging.getLogger(__name__)


class PlcModbusClient:
    """
    PLC Modbus TCP Client 封装（同步接口）

    内部结构：
      - 一个常驻的后台事件循环线程（daemon），所有异步操作都调度到它上面
      - 同步方法内部通过 run_coroutine_threadsafe 提交协程并阻塞等待结果

    参数：
      host: Modbus Server IP
      port: Modbus Server 端口
      slave_id: 从机地址
      timeout: 连接超时（秒）
      heartbeat_fail_count: 连续几次心跳不变判定通信异常
    """

    def __init__(
        self,
        host: str = None,
        port: int = None,
        slave_id: int = None,
        timeout: float = None,
        heartbeat_fail_count: int = None,
    ):
        cfg = CONFIG["modbus"]
        acq = CONFIG["acquisition"]

        self._host = host or cfg["host"]
        self._port = port or cfg["port"]
        self._slave_id = slave_id or cfg["slave_id"]
        self._timeout = timeout or acq["timeout_s"]
        self._heartbeat_fail_count = heartbeat_fail_count or acq["heartbeat_fail_count"]

        self._client: Optional[AsyncModbusTcpClient] = None
        self._connected = False
        self._last_heartbeat: Optional[int] = None
        self._heartbeat_stale_count = 0

        # 常驻后台事件循环
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_lock = threading.Lock()

    # ------------------------------------------------------------------
    # 后台事件循环管理
    # ------------------------------------------------------------------

    def _ensure_loop(self):
        """确保后台事件循环线程已启动。"""
        with self._loop_lock:
            if self._loop is None or self._loop.is_closed():
                self._loop = asyncio.new_event_loop()
                self._loop_thread = threading.Thread(
                    target=self._loop.run_forever,
                    daemon=True,
                    name="ModbusClientEventLoop",
                )
                self._loop_thread.start()
                logger.info("[Modbus Client] 后台事件循环线程已启动")

    def _run_coro(self, coro, timeout: float = None):
        """将协程调度到后台事件循环执行，阻塞等待结果。"""
        self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        # 默认等待时间 = 通信超时 + 余量
        wait = timeout if timeout is not None else self._timeout + 5.0
        return future.result(wait)

    def shutdown(self):
        """停止后台事件循环线程（程序退出时调用）。"""
        with self._loop_lock:
            if self._loop is not None and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            if self._loop_thread is not None:
                self._loop_thread.join(timeout=2.0)
                self._loop_thread = None
            if self._loop is not None:
                self._loop.close()
                self._loop = None
            logger.info("[Modbus Client] 后台事件循环线程已停止")

    # ------------------------------------------------------------------
    # 连接管理（同步接口）
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """建立连接。返回是否成功。"""
        return self._run_coro(self._async_connect())

    def disconnect(self):
        """断开连接。"""
        self._run_coro(self._async_disconnect())

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.connected

    async def _async_connect(self) -> bool:
        """协程：建立连接。"""
        if self._connected and self._client and self._client.connected:
            return True

        try:
            # 复用已有 client 对象时先确保旧的断开
            if self._client is not None:
                self._client.close()

            self._client = AsyncModbusTcpClient(
                self._host,
                port=self._port,
                timeout=self._timeout,
            )
            await self._client.connect()
            self._connected = self._client.connected

            if self._connected:
                logger.info(f"[Modbus Client] 已连接到 {self._host}:{self._port}")
                self._last_heartbeat = None
                self._heartbeat_stale_count = 0
            else:
                logger.warning(f"[Modbus Client] 连接失败 {self._host}:{self._port}")

            return self._connected

        except Exception as e:
            logger.error(f"[Modbus Client] 连接异常: {e}")
            self._connected = False
            self._client = None
            return False

    async def _async_disconnect(self):
        """协程：断开连接。"""
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
        self._last_heartbeat = None
        self._heartbeat_stale_count = 0
        logger.info("[Modbus Client] 已断开连接")

    # ------------------------------------------------------------------
    # 寄存器读写（同步接口）
    # ------------------------------------------------------------------

    def read_all_registers(self) -> Optional[list[int]]:
        """
        读取全部 10 个 Holding Register（地址 0-9）。
        返回寄存器值列表，失败返回 None。
        """
        return self._run_coro(self._async_read_all_registers())

    def write_register(self, address: int, value: int) -> bool:
        """
        写入单个 Holding Register。
        返回是否成功。
        """
        return self._run_coro(self._async_write_register(address, value))

    async def _async_read_all_registers(self) -> Optional[list[int]]:
        """协程：读取全部寄存器。"""
        if not await self._async_ensure_connected():
            return None

        try:
            rr = await self._client.read_holding_registers(
                address=0, count=REGISTER_COUNT
            )
            if rr.isError():
                logger.warning(f"[Modbus Client] 读取寄存器错误: {rr}")
                return None
            return rr.registers
        except Exception as e:
            logger.error(f"[Modbus Client] 读取异常: {e}")
            self._connected = False
            return None

    async def _async_write_register(self, address: int, value: int) -> bool:
        """协程：写入单个寄存器。"""
        if not await self._async_ensure_connected():
            return False

        try:
            wr = await self._client.write_register(address=address, value=value)
            if wr.isError():
                logger.warning(f"[Modbus Client] 写入寄存器错误: {wr}")
                return False
            return True
        except Exception as e:
            logger.error(f"[Modbus Client] 写入异常: {e}")
            self._connected = False
            return False

    # ------------------------------------------------------------------
    # 通信状态检测（同步接口）
    # ------------------------------------------------------------------

    def check_communication_health(self, current_heartbeat: int) -> bool:
        """
        检测通信健康状态。
        连续 heartbeat_fail_count 次心跳不变 → 判定通信异常。
        返回 True=正常，False=异常。
        """
        if self._last_heartbeat is None:
            self._last_heartbeat = current_heartbeat
            self._heartbeat_stale_count = 0
            return True

        if current_heartbeat == self._last_heartbeat:
            self._heartbeat_stale_count += 1
            if self._heartbeat_stale_count >= self._heartbeat_fail_count:
                logger.warning(
                    f"[Modbus Client] 通信异常：心跳连续 {self._heartbeat_stale_count} 次未变化"
                )
                self._connected = False
                return False
        else:
            self._last_heartbeat = current_heartbeat
            self._heartbeat_stale_count = 0

        return True

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    async def _async_ensure_connected(self) -> bool:
        """确保已连接，未连接则尝试重连。"""
        if self.is_connected:
            return True
        return await self._async_connect()
