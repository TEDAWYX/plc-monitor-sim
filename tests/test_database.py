"""
DatabaseManager 单元测试

测试范围：
  1. 建表
  2. 插入/查询 sensor_data
  3. 插入/更新 alarm_records
  4. 插入 system_events
  5. 清空数据
  6. 统计信息

运行方式：
    pytest tests/test_database.py -v

注意：使用内存数据库或临时文件，测试结束后自动清理。
"""

import sys
import tempfile
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from app.database.db_manager import DatabaseManager


@pytest.fixture
def db():
    """创建临时数据库，测试结束后删除。"""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    manager = DatabaseManager(db_path=db_path)
    manager.init_tables()

    yield manager

    manager.close()
    Path(db_path).unlink(missing_ok=True)


class TestDatabaseInit:
    def test_tables_created(self, db):
        """建表后应能查询到表结构"""
        db.connect()
        cursor = db._conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        assert "sensor_data" in tables
        assert "alarm_records" in tables
        assert "system_events" in tables


class TestSensorData:
    def test_insert_and_query(self, db):
        """插入 sensor_data 后能查询到"""
        now = datetime.now()
        row_id = db.insert_sensor_data(
            timestamp=now,
            temperature=72.3,
            pressure=350.1,
            motor_speed=1450.0,
            current=12.5,
            voltage=380.0,
            run_status=1,
        )
        assert row_id > 0
        db.commit()

        rows = db.query_sensor_data()
        assert len(rows) == 1
        assert rows[0]["temperature"] == 72.3
        assert rows[0]["motor_speed"] == 1450.0

    def test_query_by_time_range(self, db):
        """按时间范围查询"""
        t1 = datetime(2026, 9, 10, 10, 0, 0)
        t2 = datetime(2026, 9, 10, 11, 0, 0)
        t3 = datetime(2026, 9, 10, 12, 0, 0)

        db.insert_sensor_data(t1, 10, 100, 0, 0, 0, 0)
        db.insert_sensor_data(t2, 20, 200, 0, 0, 0, 0)
        db.insert_sensor_data(t3, 30, 300, 0, 0, 0, 0)
        db.commit()

        rows = db.query_sensor_data(start_time=t2, end_time=t2)
        assert len(rows) == 1
        assert rows[0]["temperature"] == 20.0


class TestAlarmRecords:
    def test_insert_and_query(self, db):
        """插入报警记录后能查询到"""
        now = datetime.now()
        row_id = db.insert_alarm_record(
            timestamp=now,
            alarm_type="TEMP_HIGH",
            value=85.0,
            level="ALARM",
        )
        assert row_id > 0
        db.commit()

        rows = db.query_alarm_records()
        assert len(rows) == 1
        assert rows[0]["alarm_type"] == "TEMP_HIGH"
        assert rows[0]["status"] == "ACTIVE"

    def test_update_recovered(self, db):
        """更新报警恢复状态"""
        now = datetime.now()
        row_id = db.insert_alarm_record(now, "PRESSURE_HIGH", 550.0, "ALARM")
        db.commit()

        db.update_alarm_recovered(row_id, datetime.now())
        db.commit()

        rows = db.query_alarm_records()
        assert rows[0]["status"] == "RECOVERED"
        assert rows[0]["recovered_at"] is not None

    def test_update_acknowledged(self, db):
        """更新报警确认状态"""
        now = datetime.now()
        row_id = db.insert_alarm_record(now, "DEVICE_FAULT", 1.0, "ALARM")
        db.commit()

        db.update_alarm_acknowledged(row_id, datetime.now())
        db.commit()

        rows = db.query_alarm_records()
        assert rows[0]["acknowledged"] == 1
        assert rows[0]["acknowledged_at"] is not None


class TestSystemEvents:
    def test_insert_and_query(self, db):
        """插入系统事件后能查询到"""
        now = datetime.now()
        row_id = db.insert_system_event(
            timestamp=now,
            event_type="INFO",
            source="test",
            message="test message",
        )
        assert row_id > 0
        db.commit()

        rows = db.query_system_events()
        assert len(rows) == 1
        assert rows[0]["message"] == "test message"


class TestMaintenance:
    def test_clear_data(self, db):
        """清空数据后应为空"""
        db.insert_sensor_data(datetime.now(), 1, 2, 3, 4, 5, 0)
        db.insert_alarm_record(datetime.now(), "TEST", 1.0, "WARNING")
        db.commit()

        db.clear_sensor_data()
        db.clear_alarm_records()

        assert len(db.query_sensor_data()) == 0
        assert len(db.query_alarm_records()) == 0

    def test_get_stats(self, db):
        """统计信息应正确"""
        db.insert_sensor_data(datetime.now(), 1, 2, 3, 4, 5, 0)
        db.insert_alarm_record(datetime.now(), "TEST", 1.0, "WARNING")
        db.insert_system_event(datetime.now(), "INFO", "test", "msg")
        db.commit()

        stats = db.get_stats()
        assert stats["sensor_data"] == 1
        assert stats["alarm_records"] == 1
        assert stats["system_events"] == 1
