"""
实时趋势曲线页面

使用 pyqtgraph 绘制实时趋势曲线：
  - 温度曲线
  - 压力曲线
  - 转速曲线

设计要点：
  - 环形缓冲：限制历史显示点数，避免内存无限增长
  - 可显隐：用户可以选择显示/隐藏不同曲线
  - 实时更新：通过 Qt signal 接收数据并刷新曲线
"""

import time
from collections import deque

import pyqtgraph as pg
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QCheckBox
from PySide6.QtCore import Qt

from app.config.settings import CONFIG
from app.acquisition.acquisition_worker import SensorSnapshot


class TrendPage(QWidget):
    """
    实时趋势曲线页面

    参数：
      max_points: 最大保留点数（环形缓冲），默认从配置读取
    """

    def __init__(self, max_points: int = None, parent=None):
        super().__init__(parent)
        self._max_points = max_points or CONFIG["gui"]["trend_max_points"]
        self._setup_ui()

        # 数据缓冲（环形）
        self._time_buffer = deque(maxlen=self._max_points)
        self._temp_buffer = deque(maxlen=self._max_points)
        self._pressure_buffer = deque(maxlen=self._max_points)
        self._speed_buffer = deque(maxlen=self._max_points)

        # 起始时间（用于相对时间显示）
        self._start_time = time.time()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(8, 8, 8, 8)

        # === 曲线显隐控制 ===
        control_layout = QHBoxLayout()

        self._cb_temp = QCheckBox("温度 (℃)")
        self._cb_temp.setChecked(True)
        self._cb_temp.stateChanged.connect(self._on_visibility_changed)
        control_layout.addWidget(self._cb_temp)

        self._cb_pressure = QCheckBox("压力 (kPa)")
        self._cb_pressure.setChecked(True)
        self._cb_pressure.stateChanged.connect(self._on_visibility_changed)
        control_layout.addWidget(self._cb_pressure)

        self._cb_speed = QCheckBox("转速 (RPM)")
        self._cb_speed.setChecked(True)
        self._cb_speed.stateChanged.connect(self._on_visibility_changed)
        control_layout.addWidget(self._cb_speed)

        control_layout.addStretch()
        main_layout.addLayout(control_layout)

        # === pyqtgraph 绘图区域 ===
        self._plot_widget = pg.PlotWidget()
        self._plot_widget.setLabel("left", "数值")
        self._plot_widget.setLabel("bottom", "时间 (s)")
        self._plot_widget.addLegend()
        self._plot_widget.setYRange(0, 500)  # 初始范围，后续自动调整
        self._plot_widget.enableAutoRange(axis="y")

        # 创建曲线
        self._curve_temp = self._plot_widget.plot(
            pen=pg.mkPen(color="#FF4444", width=2),
            name="温度",
        )
        self._curve_pressure = self._plot_widget.plot(
            pen=pg.mkPen(color="#33B5E5", width=2),
            name="压力",
        )
        self._curve_speed = self._plot_widget.plot(
            pen=pg.mkPen(color="#00C851", width=2),
            name="转速",
        )

        main_layout.addWidget(self._plot_widget)

    def _on_visibility_changed(self):
        """曲线显隐状态变化。"""
        self._curve_temp.setVisible(self._cb_temp.isChecked())
        self._curve_pressure.setVisible(self._cb_pressure.isChecked())
        self._curve_speed.setVisible(self._cb_speed.isChecked())

    def update_data(self, snapshot: SensorSnapshot):
        """更新曲线数据。"""
        # 计算相对时间（秒）
        t = time.time() - self._start_time

        self._time_buffer.append(t)
        self._temp_buffer.append(snapshot.temperature)
        self._pressure_buffer.append(snapshot.pressure)
        self._speed_buffer.append(snapshot.motor_speed)

        # 更新曲线
        if self._cb_temp.isChecked():
            self._curve_temp.setData(list(self._time_buffer), list(self._temp_buffer))
        if self._cb_pressure.isChecked():
            self._curve_pressure.setData(list(self._time_buffer), list(self._pressure_buffer))
        if self._cb_speed.isChecked():
            self._curve_speed.setData(list(self._time_buffer), list(self._speed_buffer))

    def clear(self):
        """清空曲线数据。"""
        self._time_buffer.clear()
        self._temp_buffer.clear()
        self._pressure_buffer.clear()
        self._speed_buffer.clear()
        self._curve_temp.clear()
        self._curve_pressure.clear()
        self._curve_speed.clear()
        self._start_time = time.time()
