"""
SQLite 数据库管理器

职责：
  1. 数据库连接管理（单连接，存储线程专用）
  2. 自动建表（sensor_data / alarm_records / system_events）
  3. 批量写入（sensor_data / alarm_records / system_events）
  4. 手动清空历史数据

设计要点：
  - 数据库连接只在存储线程中使用，不跨线程共享
  - 批量写入：每 N 条或每 T 秒 commit 一次
  - 使用参数化查询防止 SQL 注入
  - 时间戳使用 ISO8601 格式（含毫秒）
"""

import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.config.settings import CONFIG

logger = logging.getLogger(__name__)


class DatabaseManager:
    """
    SQLite 数据库管理器

    参数：
      db_path: 数据库文件路径，默认从配置读取
    """

    def __init__(self, db_path: str = None):
        self._db_path = db_path or CONFIG["database"]["path"]
        self._conn: Optional[sqlite3.Connection] = None
        self._ensure_directory()

    def _ensure_directory(self):
        """确保数据库目录存在。"""
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)

    def connect(self):
        """建立数据库连接。"""
        if self._conn is None:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            logger.info(f"[Database] 已连接到 {self._db_path}")

    def close(self):
        """关闭数据库连接。"""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("[Database] 连接已关闭")

    def init_tables(self):
        """初始化数据库表结构（如果不存在）。"""
        self.connect()
        cursor = self._conn.cursor()

        # sensor_data：传感器实时/历史数据
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sensor_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                temperature REAL,
                pressure REAL,
                motor_speed REAL,
                current REAL,
                voltage REAL,
                run_status INTEGER
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_sensor_ts ON sensor_data(timestamp)
        """)

        # alarm_records：报警记录
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alarm_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                alarm_type TEXT NOT NULL,
                value REAL,
                level TEXT NOT NULL,
                status TEXT NOT NULL,
                acknowledged INTEGER NOT NULL DEFAULT 0,
                recovered_at TEXT,
                acknowledged_at TEXT
            )
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_alarm_ts ON alarm_records(timestamp)
        """)

        # system_events：系统事件日志
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS system_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                source TEXT,
                message TEXT
            )
        """)

        self._conn.commit()
        logger.info("[Database] 表结构初始化完成")

    # ------------------------------------------------------------------
    # 写入方法
    # ------------------------------------------------------------------

    def insert_sensor_data(
        self,
        timestamp: datetime,
        temperature: float,
        pressure: float,
        motor_speed: float,
        current: float,
        voltage: float,
        run_status: int,
    ) -> int:
        """
        插入一条传感器数据。
        返回插入的行 ID。
        """
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO sensor_data (timestamp, temperature, pressure, motor_speed, current, voltage, run_status)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            timestamp.isoformat(),
            temperature,
            pressure,
            motor_speed,
            current,
            voltage,
            run_status,
        ))
        return cursor.lastrowid

    def insert_alarm_record(
        self,
        timestamp: datetime,
        alarm_type: str,
        value: float,
        level: str,
        status: str = "ACTIVE",
    ) -> int:
        """
        插入一条报警记录。
        返回插入的行 ID。
        """
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO alarm_records (timestamp, alarm_type, value, level, status)
            VALUES (?, ?, ?, ?, ?)
        """, (
            timestamp.isoformat(),
            alarm_type,
            value,
            level,
            status,
        ))
        return cursor.lastrowid

    def update_alarm_recovered(self, alarm_id: int, recovered_at: datetime):
        """更新报警记录为已恢复状态。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE alarm_records
            SET status = 'RECOVERED', recovered_at = ?
            WHERE id = ?
        """, (recovered_at.isoformat(), alarm_id))

    def update_alarm_acknowledged(self, alarm_id: int, acknowledged_at: datetime):
        """更新报警记录为已确认状态。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE alarm_records
            SET acknowledged = 1, acknowledged_at = ?
            WHERE id = ?
        """, (acknowledged_at.isoformat(), alarm_id))

    def update_alarm_recovered_by_type(self, alarm_type: str, recovered_at: datetime) -> int:
        """按报警类型更新最近一条活动报警为已恢复状态。返回影响的行数。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE alarm_records
            SET status = 'RECOVERED', recovered_at = ?
            WHERE id = (
                SELECT id FROM alarm_records
                WHERE alarm_type = ? AND status = 'ACTIVE'
                ORDER BY timestamp DESC
                LIMIT 1
            )
        """, (recovered_at.isoformat(), alarm_type))
        return cursor.rowcount

    def update_alarm_acknowledged_by_type(self, alarm_type: str, acknowledged_at: datetime) -> int:
        """按报警类型更新最近一条活动报警为已确认状态。返回影响的行数。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            UPDATE alarm_records
            SET acknowledged = 1, acknowledged_at = ?
            WHERE id = (
                SELECT id FROM alarm_records
                WHERE alarm_type = ? AND status = 'ACTIVE'
                ORDER BY timestamp DESC
                LIMIT 1
            )
        """, (acknowledged_at.isoformat(), alarm_type))
        return cursor.rowcount

    def insert_system_event(
        self,
        timestamp: datetime,
        event_type: str,
        source: str,
        message: str,
    ) -> int:
        """
        插入一条系统事件。
        返回插入的行 ID。
        """
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("""
            INSERT INTO system_events (timestamp, event_type, source, message)
            VALUES (?, ?, ?, ?)
        """, (
            timestamp.isoformat(),
            event_type,
            source,
            message,
        ))
        return cursor.lastrowid

    def commit(self):
        """手动提交事务。"""
        if self._conn:
            self._conn.commit()

    # ------------------------------------------------------------------
    # 查询方法
    # ------------------------------------------------------------------

    def query_sensor_data(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """
        查询传感器历史数据。
        返回字典列表。
        """
        self.connect()
        cursor = self._conn.cursor()
        sql = "SELECT * FROM sensor_data WHERE 1=1"
        params = []

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def query_alarm_records(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        status: Optional[str] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """查询报警记录。"""
        self.connect()
        cursor = self._conn.cursor()
        sql = "SELECT * FROM alarm_records WHERE 1=1"
        params = []

        if start_time:
            sql += " AND timestamp >= ?"
            params.append(start_time.isoformat())
        if end_time:
            sql += " AND timestamp <= ?"
            params.append(end_time.isoformat())
        if status:
            sql += " AND status = ?"
            params.append(status)

        sql += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def query_system_events(
        self,
        limit: int = 100,
    ) -> list[dict]:
        """查询系统事件。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute(
            "SELECT * FROM system_events ORDER BY timestamp DESC LIMIT ?",
            (limit,),
        )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # 维护方法
    # ------------------------------------------------------------------

    def clear_sensor_data(self):
        """清空传感器历史数据。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM sensor_data")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='sensor_data'")
        self._conn.commit()
        logger.info("[Database] 已清空 sensor_data")

    def clear_alarm_records(self):
        """清空报警记录。"""
        self.connect()
        cursor = self._conn.cursor()
        cursor.execute("DELETE FROM alarm_records")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name='alarm_records'")
        self._conn.commit()
        logger.info("[Database] 已清空 alarm_records")

    def get_stats(self) -> dict:
        """获取数据库统计信息。"""
        self.connect()
        cursor = self._conn.cursor()
        stats = {}
        for table in ["sensor_data", "alarm_records", "system_events"]:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            stats[table] = cursor.fetchone()[0]
        return stats
