"""
Modbus TCP Client 封装

基于 pymodbus 3.15.0 AsyncModbusTcpClient 实现。

职责：
  1. 与虚拟 PLC 建立/断开连接
  2. 读取 Holding Register（功能码 03）
  3. 写入 Holding Register（功能码 06）
  4. 心跳检测：连续 N 次心跳不变判定通信异常
  5. 连接状态管理：连接/断开/异常

设计要点：
  - 使用异步客户端（AsyncModbusTcpClient），避免阻塞 GUI 线程
  - 所有方法均为 async，由调用方（采集线程）在异步上下文中执行
  - 通信异常不抛异常到上层，而是返回 None 并记录日志
"""

import asyncio
import logging
from typing import Optional

from pymodbus.client import AsyncModbusTcpClient

from app.config.settings import CONFIG
from app.simulator.register_map import REGISTER_COUNT

logger = logging.getLogger(__name__)


class PlcModbusClient:
    """
    PLC Modbus TCP Client 封装

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

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """建立连接。返回是否成功。"""
        if self._connected and self._client and self._client.connected:
            return True

        try:
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

    async def disconnect(self):
        """断开连接。"""
        if self._client:
            self._client.close()
            self._client = None
        self._connected = False
        self._last_heartbeat = None
        self._heartbeat_stale_count = 0
        logger.info("[Modbus Client] 已断开连接")

    @property
    def is_connected(self) -> bool:
        return self._connected and self._client is not None and self._client.connected

    # ------------------------------------------------------------------
    # 寄存器读写
    # ------------------------------------------------------------------

    async def read_all_registers(self) -> Optional[list[int]]:
        """
        读取全部 10 个 Holding Register（地址 0-9）。
        返回寄存器值列表，失败返回 None。
        """
        if not await self._ensure_connected():
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

    async def write_register(self, address: int, value: int) -> bool:
        """
        写入单个 Holding Register。
        返回是否成功。
        """
        if not await self._ensure_connected():
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
    # 通信状态检测
    # ------------------------------------------------------------------

    async def check_communication_health(self, current_heartbeat: int) -> bool:
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

    async def _ensure_connected(self) -> bool:
        """确保已连接，未连接则尝试重连。"""
        if self.is_connected:
            return True
        return await self.connect()
