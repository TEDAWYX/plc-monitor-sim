"""
数据库后台写入线程（QThread）

职责：
  1. 通过 Queue 接收写入操作（传感器数据 / 报警 / 系统事件）
  2. 批量写入 SQLite（每 N 条或每 T 秒 flush）
  3. 解耦采集/GUI 线程与数据库 IO，避免阻塞界面

设计要点：
  - 继承 QThread，在独立线程中运行
  - 使用标准库 queue.Queue（线程安全）
  - 批量写入减少磁盘 IO 压力
  - 启动时自动建表
  - 停止前 flush 剩余数据
"""

import logging
import queue
import time
from datetime import datetime

from PySide6.QtCore import QThread

from app.database.db_manager import DatabaseManager

logger = logging.getLogger(__name__)


class DatabaseWriterThread(QThread):
    """
    数据库后台写入线程

    参数：
      db_path: 数据库文件路径，None 则使用配置默认值
      batch_size: 批量写入阈值（默认从配置读取，否则 10）
      flush_interval_sec: 定时 flush 间隔（默认从配置读取，否则 2.0）
    """

    def __init__(
        self,
        db_path: str = None,
        batch_size: int = None,
        flush_interval_sec: float = None,
    ):
        super().__init__()
        self._db = DatabaseManager(db_path)
        # 若外部未传，则从配置读取（兼容 V1.0 的 database.batch_size / flush_interval_s）
        from app.config.settings import CONFIG

        self._batch_size = batch_size or CONFIG.get("database", {}).get("batch_size", 10)
        self._flush_interval_sec = flush_interval_sec or CONFIG.get("database", {}).get("flush_interval_s", 2.0)
        self._queue: queue.Queue[dict] = queue.Queue()
        self._buffer: list[dict] = []
        self._running = False

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def enqueue(self, operation: dict):
        """
        将写入操作加入队列（线程安全，可从任意线程调用）。

        operation 格式：
          {"op": "sensor", "data": {
              "timestamp": datetime, "temperature": float, ...
          }}
          {"op": "alarm_insert", "data": {
              "timestamp": datetime, "alarm_type": str,
              "value": float, "level": str, "status": str
          }}
          {"op": "alarm_recover", "alarm_type": str, "recovered_at": datetime}
          {"op": "alarm_ack", "alarm_type": str, "acknowledged_at": datetime}
          {"op": "event", "data": {
              "timestamp": datetime, "event_type": str,
              "source": str, "message": str
          }}
        """
        self._queue.put(operation)

    def stop(self):
        """请求停止线程，并等待剩余数据 flush 完成。"""
        self._running = False
        self.wait(3000)
        # 若队列仍有数据，在主线程做最后一次 flush
        self._flush()
        self._db.close()

    # ------------------------------------------------------------------
    # 线程主循环
    # ------------------------------------------------------------------

    def run(self):
        self._running = True
        self._db.connect()
        self._db.init_tables()
        logger.info("[DBWriter] 存储线程启动")

        last_flush = time.time()

        while self._running:
            # 非阻塞批量取数据
            got_data = False
            while len(self._buffer) < self._batch_size:
                try:
                    op = self._queue.get_nowait()
                    self._buffer.append(op)
                    got_data = True
                except queue.Empty:
                    break

            # 判断是否需要 flush
            now = time.time()
            need_flush = self._buffer and (
                len(self._buffer) >= self._batch_size
                or now - last_flush >= self._flush_interval_sec
            )

            if need_flush:
                self._flush()
                last_flush = now

            if not got_data:
                self.msleep(50)

        # 退出前 flush 剩余数据
        self._flush()
        self._db.close()
        logger.info("[DBWriter] 存储线程停止")

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _flush(self):
        """将缓冲区中的数据批量写入数据库。"""
        if not self._buffer:
            return

        count = len(self._buffer)
        try:
            for op in self._buffer:
                op_type = op.get("op")
                if op_type == "sensor":
                    self._db.insert_sensor_data(**op["data"])
                elif op_type == "alarm_insert":
                    self._db.insert_alarm_record(**op["data"])
                elif op_type == "alarm_recover":
                    self._db.update_alarm_recovered_by_type(
                        alarm_type=op["alarm_type"],
                        recovered_at=op["recovered_at"],
                    )
                elif op_type == "alarm_ack":
                    self._db.update_alarm_acknowledged_by_type(
                        alarm_type=op["alarm_type"],
                        acknowledged_at=op["acknowledged_at"],
                    )
                elif op_type == "event":
                    self._db.insert_system_event(**op["data"])
                else:
                    logger.warning(f"[DBWriter] 未知操作类型: {op_type}")
            self._db.commit()
            logger.debug(f"[DBWriter] 批量写入 {count} 条")
        except Exception as e:
            logger.error(f"[DBWriter] 批量写入失败: {e}")
        finally:
            self._buffer.clear()
