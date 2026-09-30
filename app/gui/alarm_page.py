"""
报警记录页面

显示：
  - 实时报警列表（活动报警）
  - 报警历史记录
  - 报警确认按钮

设计要点：
  - 使用 QTableWidget 显示报警列表
  - 不同等级用不同颜色标识
  - 支持确认操作
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QTableWidget, QTableWidgetItem, QPushButton,
    QGroupBox, QHeaderView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor

from app.processing.alarm_engine import AlarmEngine, AlarmEvent, AlarmStatus, AlarmLevel


class AlarmPage(QWidget):
    """报警记录页面"""

    # 报警被确认时发射（alarm_type）
    alarm_acknowledged = Signal(str)

    def __init__(self, alarm_engine: AlarmEngine = None, parent=None):
        super().__init__(parent)
        self._alarm_engine = alarm_engine or AlarmEngine()
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)
        main_layout.setSpacing(12)

        # === 标题 ===
        title = QLabel("报警记录")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # === 活动报警区域 ===
        active_group = QGroupBox("当前活动报警")
        active_layout = QVBoxLayout(active_group)

        self._active_table = QTableWidget()
        self._active_table.setColumnCount(5)
        self._active_table.setHorizontalHeaderLabels([
            "时间", "报警类型", "报警值", "等级", "操作"
        ])
        self._active_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._active_table.setSelectionBehavior(QTableWidget.SelectRows)
        active_layout.addWidget(self._active_table)

        main_layout.addWidget(active_group)

        # === 报警历史区域 ===
        history_group = QGroupBox("报警历史")
        history_layout = QVBoxLayout(history_group)

        self._history_table = QTableWidget()
        self._history_table.setColumnCount(5)
        self._history_table.setHorizontalHeaderLabels([
            "时间", "报警类型", "报警值", "等级", "状态"
        ])
        self._history_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._history_table.setSelectionBehavior(QTableWidget.SelectRows)
        history_layout.addWidget(self._history_table)

        main_layout.addWidget(history_group)

        # === 按钮区域 ===
        btn_layout = QHBoxLayout()
        self._refresh_btn = QPushButton("刷新")
        self._refresh_btn.clicked.connect(self.refresh)
        btn_layout.addWidget(self._refresh_btn)

        self._clear_btn = QPushButton("清空历史")
        self._clear_btn.clicked.connect(self._clear_history)
        btn_layout.addWidget(self._clear_btn)

        btn_layout.addStretch()
        main_layout.addLayout(btn_layout)

    def refresh(self):
        """刷新报警显示。"""
        self._refresh_active_alarms()
        self._refresh_history()

    def _refresh_active_alarms(self):
        """刷新活动报警列表。"""
        alarms = self._alarm_engine.get_active_alarms()
        self._active_table.setRowCount(len(alarms))

        for i, alarm in enumerate(alarms):
            self._active_table.setItem(i, 0, QTableWidgetItem(
                alarm.timestamp.strftime("%H:%M:%S")
            ))
            self._active_table.setItem(i, 1, QTableWidgetItem(alarm.alarm_type))
            self._active_table.setItem(i, 2, QTableWidgetItem(f"{alarm.value:.1f}"))

            level_item = QTableWidgetItem(alarm.level.value)
            if alarm.level == AlarmLevel.ALARM:
                level_item.setBackground(QColor("#FF4444"))
                level_item.setForeground(QColor("white"))
            elif alarm.level == AlarmLevel.WARNING:
                level_item.setBackground(QColor("#FFBB33"))
            self._active_table.setItem(i, 3, level_item)

            # 确认按钮
            ack_btn = QPushButton("确认")
            ack_btn.clicked.connect(lambda checked, t=alarm.alarm_type: self._acknowledge(t))
            self._active_table.setCellWidget(i, 4, ack_btn)

    def _refresh_history(self):
        """刷新报警历史列表。"""
        alarms = self._alarm_engine.get_all_alarms(limit=50)
        self._history_table.setRowCount(len(alarms))

        for i, alarm in enumerate(alarms):
            self._history_table.setItem(i, 0, QTableWidgetItem(
                alarm.timestamp.strftime("%H:%M:%S")
            ))
            self._history_table.setItem(i, 1, QTableWidgetItem(alarm.alarm_type))
            self._history_table.setItem(i, 2, QTableWidgetItem(f"{alarm.value:.1f}"))

            level_item = QTableWidgetItem(alarm.level.value)
            if alarm.level == AlarmLevel.ALARM:
                level_item.setBackground(QColor("#FF4444"))
                level_item.setForeground(QColor("white"))
            elif alarm.level == AlarmLevel.WARNING:
                level_item.setBackground(QColor("#FFBB33"))
            self._history_table.setItem(i, 3, level_item)

            status_item = QTableWidgetItem(alarm.status.value)
            if alarm.status == AlarmStatus.ACTIVE:
                status_item.setForeground(QColor("red"))
            elif alarm.status == AlarmStatus.RECOVERED:
                status_item.setForeground(QColor("green"))
            self._history_table.setItem(i, 4, status_item)

    def _acknowledge(self, alarm_type: str):
        """确认报警。"""
        self._alarm_engine.acknowledge(alarm_type)
        self.alarm_acknowledged.emit(alarm_type)
        self.refresh()

    def _clear_history(self):
        """清空报警历史。"""
        self._alarm_engine.clear_history()
        self.refresh()

    def add_alarm_event(self, event: AlarmEvent):
        """外部调用：新增报警事件时刷新显示。"""
        self.refresh()
