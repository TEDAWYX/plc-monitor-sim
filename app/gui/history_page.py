"""
历史数据查询与 CSV 导出页面

功能：
  - 按时间范围查询 sensor_data
  - 显示查询结果表格
  - 导出为 CSV 文件

设计要点：
  - 使用 QTableWidget 显示数据
  - 导出操作有用户提示（文件路径、记录数）
  - 使用 pandas 处理 CSV 导出
"""

from datetime import datetime, timedelta
from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QDateTimeEdit, QGroupBox, QHeaderView, QMessageBox,
    QFileDialog,
)
from PySide6.QtCore import Qt

import pandas as pd

from app.database.db_manager import DatabaseManager


class HistoryPage(QWidget):
    """历史数据查询与导出页面"""

    def __init__(self, db_manager: DatabaseManager = None, parent=None):
        super().__init__(parent)
        self._db = db_manager or DatabaseManager()
        self._db.init_tables()
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # === 标题 ===
        title = QLabel("历史数据查询")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # === 查询条件 ===
        query_group = QGroupBox("查询条件")
        query_layout = QHBoxLayout(query_group)

        query_layout.addWidget(QLabel("开始时间:"))
        self._start_edit = QDateTimeEdit()
        self._start_edit.setDateTime(datetime.now() - timedelta(hours=1))
        self._start_edit.setCalendarPopup(True)
        query_layout.addWidget(self._start_edit)

        query_layout.addWidget(QLabel("结束时间:"))
        self._end_edit = QDateTimeEdit()
        self._end_edit.setDateTime(datetime.now())
        self._end_edit.setCalendarPopup(True)
        query_layout.addWidget(self._end_edit)

        self._query_btn = QPushButton("查询")
        self._query_btn.clicked.connect(self._do_query)
        query_layout.addWidget(self._query_btn)

        self._export_btn = QPushButton("导出 CSV")
        self._export_btn.clicked.connect(self._do_export)
        query_layout.addWidget(self._export_btn)

        query_layout.addStretch()
        main_layout.addWidget(query_group)

        # === 数据表格 ===
        self._table = QTableWidget()
        self._table.setColumnCount(7)
        self._table.setHorizontalHeaderLabels([
            "时间", "温度(℃)", "压力(kPa)", "转速(RPM)", "电流(A)", "电压(V)", "运行状态"
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.setSelectionBehavior(QTableWidget.SelectRows)
        self._table.setAlternatingRowColors(True)
        main_layout.addWidget(self._table)

        # === 统计信息 ===
        self._stats_label = QLabel("共 0 条记录")
        main_layout.addWidget(self._stats_label)

    def _do_query(self):
        """执行查询。"""
        start = self._start_edit.dateTime().toPython()
        end = self._end_edit.dateTime().toPython()

        rows = self._db.query_sensor_data(start_time=start, end_time=end, limit=5000)
        self._display_results(rows)

    def _display_results(self, rows: list[dict]):
        """显示查询结果。"""
        self._table.setRowCount(len(rows))

        for i, row in enumerate(rows):
            self._table.setItem(i, 0, QTableWidgetItem(str(row["timestamp"])))
            self._table.setItem(i, 1, QTableWidgetItem(f"{row['temperature']:.1f}"))
            self._table.setItem(i, 2, QTableWidgetItem(f"{row['pressure']:.1f}"))
            self._table.setItem(i, 3, QTableWidgetItem(f"{row['motor_speed']:.0f}"))
            self._table.setItem(i, 4, QTableWidgetItem(f"{row['current']:.1f}"))
            self._table.setItem(i, 5, QTableWidgetItem(f"{row['voltage']:.1f}"))
            self._table.setItem(i, 6, QTableWidgetItem("运行" if row["run_status"] else "停止"))

        self._stats_label.setText(f"共 {len(rows)} 条记录")
        self._last_query_results = rows

    def _do_export(self):
        """导出 CSV。"""
        if not hasattr(self, "_last_query_results") or not self._last_query_results:
            QMessageBox.information(self, "提示", "请先查询数据")
            return

        # 选择保存路径
        default_name = f"industrial_monitor_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path, _ = QFileDialog.getSaveFileName(
            self,
            "导出 CSV",
            str(Path.home() / "Desktop" / default_name),
            "CSV Files (*.csv)",
        )
        if not path:
            return

        try:
            df = pd.DataFrame(self._last_query_results)
            # 选择需要的列并重命名
            columns = {
                "timestamp": "timestamp",
                "temperature": "temperature",
                "pressure": "pressure",
                "motor_speed": "motor_speed",
                "current": "current",
                "voltage": "voltage",
                "run_status": "run_status",
            }
            df = df[[c for c in columns.keys() if c in df.columns]]
            df.to_csv(path, index=False, encoding="utf-8-sig")

            QMessageBox.information(
                self,
                "导出成功",
                f"已导出 {len(df)} 条记录到:\n{path}",
            )
        except Exception as e:
            QMessageBox.critical(self, "导出失败", f"错误: {e}")
