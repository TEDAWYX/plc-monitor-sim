"""
DatabaseWriterThread 单元测试

测试范围：
  1. 批量传感器数据写入
  2. 报警插入 / 恢复 / 确认写入
  3. 系统事件写入
  4. DatabaseManager 按类型更新方法

运行方式：
    pytest tests/test_db_writer_thread.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import datetime

from app.database.db_manager import DatabaseManager
from app.database.db_writer_thread import DatabaseWriterThread


class TestDbManagerByTypeUpdates:
    """测试 DatabaseManager 新增的按类型更新方法"""

    @pytest.fixture
    def db(self, tmp_path):
        db_path = str(tmp_path / "test.db")
        manager = DatabaseManager(db_path)
        manager.init_tables()
        yield manager
        manager.close()

    def test_update_alarm_recovered_by_type(self, db):
        """按类型恢复最近一条活动报警"""
        ts = datetime.now()
        db.insert_alarm_record(
            timestamp=ts, alarm_type="TEMP_HIGH", value=85.0,
            level="ALARM", status="ACTIVE"
        )
        db.commit()

        recovered = datetime.now()
        rows_affected = db.update_alarm_recovered_by_type("TEMP_HIGH", recovered)
        assert rows_affected == 1
        db.commit()

        rows = db.query_alarm_records()
        assert rows[0]["status"] == "RECOVERED"
        assert rows[0]["recovered_at"] is not None

    def test_update_alarm_acknowledged_by_type(self, db):
        """按类型确认最近一条活动报警"""
        ts = datetime.now()
        db.insert_alarm_record(
            timestamp=ts, alarm_type="PRESSURE_HIGH", value=550.0,
            level="ALARM", status="ACTIVE"
        )
        db.commit()

        ack = datetime.now()
        rows_affected = db.update_alarm_acknowledged_by_type("PRESSURE_HIGH", ack)
        assert rows_affected == 1
        db.commit()

        rows = db.query_alarm_records()
        assert rows[0]["acknowledged"] == 1
        assert rows[0]["acknowledged_at"] is not None

    def test_update_only_affects_active_alarm(self, db):
        """按类型更新只影响 ACTIVE 状态的报警，不影响已恢复的记录"""
        ts = datetime.now()
        db.insert_alarm_record(
            timestamp=ts, alarm_type="TEMP_HIGH", value=85.0,
            level="ALARM", status="RECOVERED"
        )
        db.commit()

        rows_affected = db.update_alarm_acknowledged_by_type("TEMP_HIGH", datetime.now())
        assert rows_affected == 0


class TestDatabaseWriterThreadFlush:
    """测试 DatabaseWriterThread._flush 批量写入逻辑（不启动 QThread）"""

    @pytest.fixture
    def writer(self, tmp_path):
        db_path = str(tmp_path / "writer_test.db")
        w = DatabaseWriterThread(db_path=db_path)
        w._db.connect()
        w._db.init_tables()
        yield w
        w._db.close()

    def test_flush_sensor_data(self, writer):
        """批量写入传感器数据"""
        ts = datetime.now()
        writer._buffer = [
            {"op": "sensor", "data": {
                "timestamp": ts,
                "temperature": 72.5,
                "pressure": 350.0,
                "motor_speed": 1200.0,
                "current": 12.5,
                "voltage": 380.0,
                "run_status": 1,
            }},
        ]
        writer._flush()

        rows = writer._db.query_sensor_data(limit=10)
        assert len(rows) == 1
        assert rows[0]["temperature"] == 72.5
        assert rows[0]["run_status"] == 1

    def test_flush_alarm_insert_and_recover(self, writer):
        """写入报警并恢复"""
        ts = datetime.now()
        writer._buffer = [
            {"op": "alarm_insert", "data": {
                "timestamp": ts,
                "alarm_type": "TEMP_HIGH",
                "value": 85.0,
                "level": "ALARM",
                "status": "ACTIVE",
            }},
        ]
        writer._flush()

        alarms = writer._db.query_alarm_records()
        assert len(alarms) == 1
        assert alarms[0]["status"] == "ACTIVE"

        # 恢复
        writer._buffer = [
            {"op": "alarm_recover", "alarm_type": "TEMP_HIGH", "recovered_at": datetime.now()},
        ]
        writer._flush()

        alarms = writer._db.query_alarm_records()
        assert alarms[0]["status"] == "RECOVERED"

    def test_flush_system_event(self, writer):
        """写入系统事件"""
        writer._buffer = [
            {"op": "event", "data": {
                "timestamp": datetime.now(),
                "event_type": "INFO",
                "source": "test",
                "message": "测试事件",
            }},
        ]
        writer._flush()

        events = writer._db.query_system_events(limit=10)
        assert len(events) == 1
        assert events[0]["message"] == "测试事件"
        assert events[0]["event_type"] == "INFO"

    def test_flush_unknown_op_ignored(self, writer):
        """未知操作类型应被忽略，不抛异常"""
        writer._buffer = [
            {"op": "unknown_op", "data": {}},
        ]
        writer._flush()  # 不应抛异常
        assert len(writer._db.query_sensor_data(limit=10)) == 0


class TestDatabaseWriterThreadLifecycle:
    """测试 DatabaseWriterThread 启动/停止生命周期"""

    def test_start_and_stop(self, tmp_path):
        """线程能正常启动和停止，且退出前 flush 剩余数据"""
        db_path = str(tmp_path / "lifecycle.db")
        writer = DatabaseWriterThread(db_path=db_path)
        writer.start()
        assert writer.isRunning()

        # 推几条数据
        writer.enqueue({"op": "event", "data": {
            "timestamp": datetime.now(),
            "event_type": "INFO",
            "source": "test",
            "message": "lifecycle test",
        }})

        # stop() 内部会 wait() 并 flush 剩余数据
        writer.stop()

        # 验证数据已写入（证明线程确实完成工作并退出）
        db = DatabaseManager(db_path)
        db.connect()
        events = db.query_system_events(limit=10)
        assert len(events) >= 1
        db.close()
