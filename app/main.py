"""
上位机监控软件入口（Phase 3 控制台验证版）

运行方式：
    1. 先启动模拟器：python -m app.simulator.main
    2. 再启动本程序：python -m app.main

Phase 3 功能：
    - 连接 Modbus TCP Server
    - 周期性采集数据
    - 控制台打印实时数据

注意：本模型为简化模型，用于产生具有工业过程特征的仿真数据，
      不代表任何真实设备的精确动力学模型。
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QCoreApplication

from app.config.settings import CONFIG
from app.communication.modbus_client import PlcModbusClient
from app.acquisition.acquisition_worker import AcquisitionWorker, SensorSnapshot


def on_data_ready(snapshot: SensorSnapshot):
    """数据到达回调"""
    ts = snapshot.timestamp.strftime("%H:%M:%S.%f")[:-3]
    print(
        f"[{ts}] "
        f"T={snapshot.temperature:6.1f}℃ "
        f"P={snapshot.pressure:7.1f}kPa "
        f"RPM={snapshot.motor_speed:7.1f} "
        f"I={snapshot.current:5.1f}A "
        f"V={snapshot.voltage:6.1f}V "
        f"Run={snapshot.running} Fault={snapshot.fault} "
        f"Comm={snapshot.comm_status}"
    )


def on_comm_status_changed(status: str):
    """通信状态变化回调"""
    print(f"[通信状态] {status}")


def main():
    app = QCoreApplication(sys.argv)

    print("=" * 70)
    print("  PLC 工业数据采集与监控仿真系统 - Phase 3 控制台验证")
    print("=" * 70)
    print("  注意：本模型为简化模型，用于产生具有工业过程特征的仿真数据。")
    print("        不代表任何真实设备的精确动力学模型。")
    print("=" * 70)
    print()

    # 创建采集线程
    client = PlcModbusClient()
    worker = AcquisitionWorker(client=client)
    worker.data_ready.connect(on_data_ready)
    worker.comm_status_changed.connect(on_comm_status_changed)

    print("[Main] 启动采集线程...")
    worker.start()

    print("[Main] 按 Ctrl+C 停止。")
    print()

    try:
        while worker.isRunning():
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[Main] 用户中断，正在停止...")
    finally:
        worker.stop()
        print("[Main] 已退出。")


if __name__ == "__main__":
    main()
