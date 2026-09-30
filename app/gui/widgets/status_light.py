"""
状态指示灯控件

一个简单的圆形指示灯，用于显示设备运行状态。
颜色：
  - 绿色：正常/运行
  - 黄色：警告/启动中
  - 红色：报警/故障
  - 灰色：停止/未知
"""

from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt
from PySide6.QtGui import QPainter, QBrush, QColor


class StatusLight(QWidget):
    """
    状态指示灯

    参数：
      color: 初始颜色（"green", "yellow", "red", "gray"）
      size: 指示灯直径（像素）
    """

    COLOR_MAP = {
        "green": QColor("#00C851"),
        "yellow": QColor("#FFBB33"),
        "red": QColor("#FF4444"),
        "gray": QColor("#9E9E9E"),
    }

    def __init__(self, color: str = "gray", size: int = 24, parent=None):
        super().__init__(parent)
        self._color_name = color
        self._size = size
        self.setFixedSize(size, size)
        self.setToolTip(self._get_tooltip())

    def set_color(self, color: str):
        """设置指示灯颜色。"""
        if color in self.COLOR_MAP:
            self._color_name = color
            self.setToolTip(self._get_tooltip())
            self.update()

    def _get_tooltip(self) -> str:
        tooltips = {
            "green": "正常",
            "yellow": "警告/启动中",
            "red": "报警/故障",
            "gray": "停止/未知",
        }
        return tooltips.get(self._color_name, "未知")

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        color = self.COLOR_MAP.get(self._color_name, self.COLOR_MAP["gray"])
        brush = QBrush(color)
        painter.setBrush(brush)
        painter.setPen(Qt.NoPen)

        # 绘制圆形
        margin = 2
        painter.drawEllipse(margin, margin, self._size - margin * 2, self._size - margin * 2)

        painter.end()
