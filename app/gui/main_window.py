"""
主窗口

使用 QTabWidget 组织各功能页面：
  - 监控页（MonitorPage）
  - 趋势曲线页（Phase 6）
  - 报警页（Phase 7）
  - 历史查询页（Phase 8）
  - 控制页（Phase 9）

设计要点：
  - 主窗口负责协调采集线程和 GUI 页面
  - 使用 signals/slots 实现线程安全的数据传递
  - 窗口关闭时优雅停止采集线程
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QTabWidget,
    QStatusBar, QLabel, QMessageBox,
)
from PySide6.QtCore import Qt, Slot

from app.config.settings import CONFIG
from app.communication.modbus_client import PlcModbusClient
from app.acquisition.acquisition_worker import AcquisitionWorker, SensorSnapshot
from app.gui.monitor_page import MonitorPage
from app.gui.trend_page import TrendPage
from app.gui.alarm_page import AlarmPage
from app.gui.history_page import HistoryPage
from app.gui.control_page import ControlPage
from app.processing.alarm_engine import AlarmEngine, AlarmStatus
from app.database.db_manager import DatabaseManager
from app.database.db_writer_thread import DatabaseWriterThread


class MainWindow(QMainWindow):
    """
    主窗口

    Signals：
      无（直接连接 worker signals 到页面 slots）
    """

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PLC 工业数据采集与监控仿真系统 V1.0")
        self.setMinimumSize(900, 600)

        # V1.1 数据库后台写入线程（解耦采集与存储）
        self._db_writer = DatabaseWriterThread()
        self._db_writer.start()

        # 报警引擎（V1.1 不再直接操作数据库）
        self._alarm_engine = AlarmEngine()

        # 保留 DatabaseManager 供 HistoryPage 查询
        self._db = DatabaseManager()
        self._db.init_tables()

        # 创建中央部件
        central = QWidget()
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(8, 8, 8, 8)

        # 创建标签页
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # === 监控页 ===
        self._monitor_page = MonitorPage()
        self._tabs.addTab(self._monitor_page, "实时监控")

        # === 趋势曲线页 ===
        self._trend_page = TrendPage()
        self._tabs.addTab(self._trend_page, "趋势曲线")

        # === 报警记录页 ===
        self._alarm_page = AlarmPage(alarm_engine=self._alarm_engine)
        self._alarm_page.alarm_acknowledged.connect(self._on_alarm_acknowledged)
        self._tabs.addTab(self._alarm_page, "报警记录")

        # === 历史查询页 ===
        self._history_page = HistoryPage(db_manager=self._db)
        self._tabs.addTab(self._history_page, "历史查询")

        # === 设备控制页 ===
        self._control_page = ControlPage()
        self._tabs.addTab(self._control_page, "设备控制")

        # 状态栏
        self._status_bar = QStatusBar()
        self.setStatusBar(self._status_bar)
        self._status_label = QLabel("就绪")
        self._status_bar.addWidget(self._status_label)

        # 采集线程
        self._client = PlcModbusClient()
        self._worker = AcquisitionWorker(client=self._client)
        self._worker.data_ready.connect(self._on_data_ready)
        self._worker.comm_status_changed.connect(self._on_comm_status_changed)

        # 控制页面需要客户端
        self._control_page.set_client(self._client)

        # 启动采集
        self._worker.start()
        self._status_label.setText("采集线程已启动")

        # 记录启动事件
        self._db_writer.enqueue({
            "op": "event",
            "data": {
                "timestamp": datetime.now(),
                "event_type": "INFO",
                "source": "gui",
                "message": "上位机监控软件启动",
            }
        })

    # ------------------------------------------------------------------
    # Slots
    # ------------------------------------------------------------------

    @Slot(SensorSnapshot)
    def _on_data_ready(self, snapshot: SensorSnapshot):
        """数据到达：更新界面、推入存储队列、报警判断。"""
        self._monitor_page.update_data(snapshot)
        self._trend_page.update_data(snapshot)

        # V1.1 推传感器数据到存储队列（无论通信状态如何都记录）
        self._db_writer.enqueue({
            "op": "sensor",
            "data": {
                "timestamp": snapshot.timestamp,
                "temperature": snapshot.temperature,
                "pressure": snapshot.pressure,
                "motor_speed": snapshot.motor_speed,
                "current": snapshot.current,
                "voltage": snapshot.voltage,
                "run_status": 1 if snapshot.running else 0,
            }
        })

        if snapshot.comm_status == "OK":
            # 报警判断
            alarm_events = self._alarm_engine.process(
                temperature=snapshot.temperature,
                pressure=snapshot.pressure,
                motor_speed=snapshot.motor_speed,
                current=snapshot.current,
                voltage=snapshot.voltage,
            )
            for event in alarm_events:
                if event.status == AlarmStatus.ACTIVE:
                    # 新报警产生 → 推入库队列
                    self._db_writer.enqueue({
                        "op": "alarm_insert",
                        "data": {
                            "timestamp": event.timestamp,
                            "alarm_type": event.alarm_type,
                            "value": event.value,
                            "level": event.level.value,
                            "status": event.status.value,
                        }
                    })
                    self._alarm_page.add_alarm_event(event)
                elif event.status == AlarmStatus.RECOVERED:
                    # 报警恢复 → 推入库队列
                    self._db_writer.enqueue({
                        "op": "alarm_recover",
                        "alarm_type": event.alarm_type,
                        "recovered_at": datetime.now(),
                    })

            # 更新监控页报警文本
            active = self._alarm_engine.get_active_alarms()
            if active:
                alarm_texts = [f"{a.alarm_type}={a.value:.1f} ({a.level.value})" for a in active]
                self._monitor_page.set_alarm_text(
                    "当前报警: " + ", ".join(alarm_texts), is_alarm=True
                )
            else:
                self._monitor_page.set_alarm_text("无报警", is_alarm=False)

    @Slot(str)
    def _on_comm_status_changed(self, status: str):
        """通信状态变化：更新状态栏并记录系统事件。"""
        self._status_label.setText(f"通信状态: {status}")
        if status != "OK":
            self._db_writer.enqueue({
                "op": "event",
                "data": {
                    "timestamp": datetime.now(),
                    "event_type": "WARNING",
                    "source": "modbus_client",
                    "message": f"通信异常: {status}",
                }
            })

    @Slot(str)
    def _on_alarm_acknowledged(self, alarm_type: str):
        """报警被确认：推入存储队列。"""
        self._db_writer.enqueue({
            "op": "alarm_ack",
            "alarm_type": alarm_type,
            "acknowledged_at": datetime.now(),
        })

    # ------------------------------------------------------------------
    # 窗口事件
    # ------------------------------------------------------------------

    def closeEvent(self, event):
        """窗口关闭时停止采集线程和存储线程。"""
        reply = QMessageBox.question(
            self,
            "确认退出",
            "确定要退出程序吗？",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._status_label.setText("正在停止采集线程...")
            self._db_writer.enqueue({
                "op": "event",
                "data": {
                    "timestamp": datetime.now(),
                    "event_type": "INFO",
                    "source": "gui",
                    "message": "用户关闭程序",
                }
            })
            self._worker.stop()
            self._db_writer.stop()
            event.accept()
        else:
            event.ignore()


def main():
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    # 设置应用-wide 字体
    font = app.font()
    font.setPointSize(10)
    app.setFont(font)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
