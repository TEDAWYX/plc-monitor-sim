"""
主监控页面

显示：
  - 温度、压力、电机转速、电流、电压（大字体）
  - 运行状态指示灯
  - 通信状态
  - 当前报警信息

设计要点：
  - 使用 QGridLayout 布局，清晰对齐
  - 数值变化时颜色提示（正常/警告/报警）
  - 状态灯直观显示设备状态
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QGroupBox, QFrame,
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QFont

from app.gui.widgets.status_light import StatusLight
from app.acquisition.acquisition_worker import SensorSnapshot


class MonitorPage(QWidget):
    """主监控页面"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(16)
        main_layout.setContentsMargins(16, 16, 16, 16)

        # === 标题 ===
        title = QLabel("实时数据监控")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # === 传感器数值区域 ===
        sensor_group = QGroupBox("传感器数据")
        sensor_grid = QGridLayout(sensor_group)
        sensor_grid.setSpacing(12)

        self._value_labels = {}
        self._unit_labels = {}

        sensors = [
            ("temperature", "温度", "℃", 0, 0),
            ("pressure", "压力", "kPa", 0, 1),
            ("motor_speed", "电机转速", "RPM", 0, 2),
            ("current", "电流", "A", 1, 0),
            ("voltage", "电压", "V", 1, 1),
        ]

        for key, name, unit, row, col in sensors:
            frame = QFrame()
            frame.setFrameStyle(QFrame.StyledPanel | QFrame.Raised)
            frame_layout = QVBoxLayout(frame)
            frame_layout.setSpacing(4)
            frame_layout.setContentsMargins(12, 8, 12, 8)

            name_label = QLabel(name)
            name_label.setAlignment(Qt.AlignCenter)
            name_font = QFont()
            name_font.setPointSize(10)
            name_label.setFont(name_font)

            value_label = QLabel("--")
            value_label.setAlignment(Qt.AlignCenter)
            value_font = QFont()
            value_font.setPointSize(24)
            value_font.setBold(True)
            value_label.setFont(value_font)

            unit_label = QLabel(unit)
            unit_label.setAlignment(Qt.AlignCenter)
            unit_font = QFont()
            unit_font.setPointSize(9)
            unit_label.setFont(unit_font)

            frame_layout.addWidget(name_label)
            frame_layout.addWidget(value_label)
            frame_layout.addWidget(unit_label)

            sensor_grid.addWidget(frame, row, col)
            self._value_labels[key] = value_label

        # 占位，让网格对称
        sensor_grid.addWidget(QWidget(), 1, 2)

        main_layout.addWidget(sensor_group)

        # === 状态区域 ===
        status_group = QGroupBox("设备状态")
        status_layout = QHBoxLayout(status_group)
        status_layout.setSpacing(24)

        # 运行状态
        run_frame = QFrame()
        run_layout = QHBoxLayout(run_frame)
        run_layout.setSpacing(8)
        self._run_light = StatusLight("gray", size=32)
        self._run_label = QLabel("停止")
        run_layout.addWidget(self._run_light)
        run_layout.addWidget(self._run_label)
        status_layout.addWidget(run_frame)

        # 故障状态
        fault_frame = QFrame()
        fault_layout = QHBoxLayout(fault_frame)
        fault_layout.setSpacing(8)
        self._fault_light = StatusLight("gray", size=32)
        self._fault_label = QLabel("无故障")
        fault_layout.addWidget(self._fault_light)
        fault_layout.addWidget(self._fault_label)
        status_layout.addWidget(fault_frame)

        # 通信状态
        comm_frame = QFrame()
        comm_layout = QHBoxLayout(comm_frame)
        comm_layout.setSpacing(8)
        self._comm_light = StatusLight("gray", size=32)
        self._comm_label = QLabel("未连接")
        comm_layout.addWidget(self._comm_light)
        comm_layout.addWidget(self._comm_label)
        status_layout.addWidget(comm_frame)

        status_layout.addStretch()
        main_layout.addWidget(status_group)

        # === 报警信息区域 ===
        alarm_group = QGroupBox("当前报警")
        alarm_layout = QVBoxLayout(alarm_group)
        self._alarm_label = QLabel("无报警")
        self._alarm_label.setStyleSheet("color: green; font-size: 14px;")
        alarm_layout.addWidget(self._alarm_label)
        main_layout.addWidget(alarm_group)

        main_layout.addStretch()

    def update_data(self, snapshot: SensorSnapshot):
        """更新显示数据。"""
        # 更新数值
        self._value_labels["temperature"].setText(f"{snapshot.temperature:.1f}")
        self._value_labels["pressure"].setText(f"{snapshot.pressure:.1f}")
        self._value_labels["motor_speed"].setText(f"{snapshot.motor_speed:.0f}")
        self._value_labels["current"].setText(f"{snapshot.current:.1f}")
        self._value_labels["voltage"].setText(f"{snapshot.voltage:.1f}")

        # 更新运行状态
        if snapshot.fault:
            self._run_light.set_color("red")
            self._run_label.setText("故障")
        elif snapshot.running:
            self._run_light.set_color("green")
            self._run_label.setText("运行中")
        elif snapshot.starting:
            self._run_light.set_color("yellow")
            self._run_label.setText("启动中")
        else:
            self._run_light.set_color("gray")
            self._run_label.setText("停止")

        # 更新故障状态
        if snapshot.fault:
            self._fault_light.set_color("red")
            self._fault_label.setText(f"故障码: {snapshot.fault_code}")
        else:
            self._fault_light.set_color("gray")
            self._fault_label.setText("无故障")

        # 更新通信状态
        if snapshot.comm_status == "OK":
            self._comm_light.set_color("green")
            self._comm_label.setText("正常")
        elif snapshot.comm_status == "ERROR":
            self._comm_light.set_color("red")
            self._comm_label.setText("通信异常")
        else:
            self._comm_light.set_color("gray")
            self._comm_label.setText("未连接")

    def set_alarm_text(self, text: str, is_alarm: bool = False):
        """设置报警信息文本。"""
        self._alarm_label.setText(text)
        if is_alarm:
            self._alarm_label.setStyleSheet("color: red; font-size: 14px; font-weight: bold;")
        else:
            self._alarm_label.setStyleSheet("color: green; font-size: 14px;")
