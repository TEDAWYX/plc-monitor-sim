"""
设备控制页面

功能：
  - 启动设备
  - 停止设备
  - 设置目标转速
  - 模拟故障注入
  - 清除故障

设计要点：
  - 控制命令通过 Modbus 写入虚拟 PLC
  - 按钮状态根据通信状态启用/禁用
  - 操作有确认提示
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QGroupBox, QSpinBox, QMessageBox,
)
from PySide6.QtCore import Qt

from app.communication.modbus_client import PlcModbusClient


class ControlPage(QWidget):
    """设备控制页面"""

    def __init__(self, client: PlcModbusClient = None, parent=None):
        super().__init__(parent)
        self._client = client
        self._setup_ui()

    def _setup_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(16, 16, 16, 16)
        main_layout.setSpacing(16)

        # === 标题 ===
        title = QLabel("设备控制")
        title_font = title.font()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title.setFont(title_font)
        title.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title)

        # === 启停控制 ===
        run_group = QGroupBox("启停控制")
        run_layout = QHBoxLayout(run_group)

        self._start_btn = QPushButton("启动设备")
        self._start_btn.setStyleSheet("background-color: #00C851; color: white; font-size: 14px; padding: 8px;")
        self._start_btn.clicked.connect(self._on_start)
        run_layout.addWidget(self._start_btn)

        self._stop_btn = QPushButton("停止设备")
        self._stop_btn.setStyleSheet("background-color: #FF4444; color: white; font-size: 14px; padding: 8px;")
        self._stop_btn.clicked.connect(self._on_stop)
        run_layout.addWidget(self._stop_btn)

        main_layout.addWidget(run_group)

        # === 转速设定 ===
        speed_group = QGroupBox("目标转速设定")
        speed_layout = QHBoxLayout(speed_group)

        speed_layout.addWidget(QLabel("目标转速:"))
        self._speed_spin = QSpinBox()
        self._speed_spin.setRange(0, 1500)
        self._speed_spin.setValue(1450)
        self._speed_spin.setSuffix(" RPM")
        speed_layout.addWidget(self._speed_spin)

        self._set_speed_btn = QPushButton("设定转速")
        self._set_speed_btn.clicked.connect(self._on_set_speed)
        speed_layout.addWidget(self._set_speed_btn)

        speed_layout.addStretch()
        main_layout.addWidget(speed_group)

        # === 故障模拟 ===
        fault_group = QGroupBox("故障模拟")
        fault_layout = QHBoxLayout(fault_group)

        self._inject_btn = QPushButton("注入故障")
        self._inject_btn.setStyleSheet("background-color: #FFBB33; color: black; font-size: 14px; padding: 8px;")
        self._inject_btn.clicked.connect(self._on_inject_fault)
        fault_layout.addWidget(self._inject_btn)

        self._clear_fault_btn = QPushButton("清除故障")
        self._clear_fault_btn.clicked.connect(self._on_clear_fault)
        fault_layout.addWidget(self._clear_fault_btn)

        main_layout.addWidget(fault_group)

        # === 状态提示 ===
        self._status_label = QLabel("就绪")
        self._status_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(self._status_label)

        main_layout.addStretch()

    def set_client(self, client: PlcModbusClient):
        """设置 Modbus 客户端。"""
        self._client = client

    def _on_start(self):
        """启动设备。"""
        if not self._client:
            QMessageBox.warning(self, "错误", "Modbus 客户端未初始化")
            return

        reply = QMessageBox.question(
            self,
            "确认启动",
            "确定要启动设备吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._send_command(1, "启动")

    def _on_stop(self):
        """停止设备。"""
        if not self._client:
            QMessageBox.warning(self, "错误", "Modbus 客户端未初始化")
            return

        reply = QMessageBox.question(
            self,
            "确认停止",
            "确定要停止设备吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._send_command(2, "停止")

    def _on_set_speed(self):
        """设定目标转速。"""
        if not self._client:
            QMessageBox.warning(self, "错误", "Modbus 客户端未初始化")
            return

        speed = self._speed_spin.value()
        self._send_write(7, speed, f"目标转速设定为 {speed} RPM")

    def _on_inject_fault(self):
        """注入故障。"""
        if not self._client:
            QMessageBox.warning(self, "错误", "Modbus 客户端未初始化")
            return

        reply = QMessageBox.warning(
            self,
            "确认注入故障",
            "注入故障将模拟设备异常状态，确定要继续吗？",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply == QMessageBox.Yes:
            self._send_command(3, "故障注入")

    def _on_clear_fault(self):
        """清除故障。"""
        if not self._client:
            QMessageBox.warning(self, "错误", "Modbus 客户端未初始化")
            return

        self._send_command(4, "清除故障")

    def _send_command(self, cmd: int, name: str):
        """发送控制命令。"""
        import asyncio

        async def do_send():
            ok = await self._client.write_register(8, cmd)
            if ok:
                self._status_label.setText(f"{name} 命令已发送")
            else:
                self._status_label.setText(f"{name} 命令发送失败")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(do_send())
            loop.close()
        except Exception as e:
            self._status_label.setText(f"发送异常: {e}")

    def _send_write(self, address: int, value: int, name: str):
        """发送写入命令。"""
        import asyncio

        async def do_send():
            ok = await self._client.write_register(address, value)
            if ok:
                self._status_label.setText(f"{name} 成功")
            else:
                self._status_label.setText(f"{name} 失败")

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(do_send())
            loop.close()
        except Exception as e:
            self._status_label.setText(f"发送异常: {e}")
