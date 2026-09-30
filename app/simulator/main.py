"""
虚拟工业设备模拟器独立启动入口

运行方式：
    python -m app.simulator.main

Phase 2 更新：
    增加了 Modbus TCP Server，虚拟 PLC 可通过 Modbus 协议被上位机访问。
    默认监听 0.0.0.0:5020。

注意：
    本模型为简化模型，用于产生具有工业过程特征的仿真数据，
    不代表任何真实设备的精确动力学模型。
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from app.config.settings import CONFIG
from app.simulator.device_model import DeviceModel
from app.simulator.modbus_server import VirtualPlcServer


async def main():
    print("=" * 60)
    print("  虚拟工业设备模拟器 - Phase 2 (Modbus TCP Server)")
    print("=" * 60)
    print("  注意：本模型为简化模型，用于产生具有工业过程特征的仿真数据。")
    print("        不代表任何真实设备的精确动力学模型。")
    print("=" * 60)
    print()

    # 创建设备模型
    model = DeviceModel(CONFIG["simulator"])

    # 创建并启动 Modbus Server
    server = VirtualPlcServer(model)
    host = CONFIG["modbus"]["host"]
    port = CONFIG["modbus"]["port"]
    await server.start(host=host, port=port)

    print()
    print("  寄存器映射：")
    print("    40001 - 温度 (×10, ℃)")
    print("    40002 - 压力 (×10, kPa)")
    print("    40003 - 电机转速 (RPM)")
    print("    40004 - 电流 (×10, A)")
    print("    40005 - 电压 (×10, V)")
    print("    40006 - 状态字 (bit0=运行, bit1=故障, bit2=启动中)")
    print("    40007 - 故障码 (0=无, 1=过温, 2=注入)")
    print("    40008 - 目标转速 (RPM, 可写)")
    print("    40009 - 控制命令 (1=启动, 2=停止, 3=注入故障, 4=清除故障, 可写)")
    print("    40010 - 心跳计数 (通信活性检测)")
    print()
    print("  按 Ctrl+C 停止模拟器。")
    print()

    # 设备自动启动演示（可选，可在配置中关闭）
    print(">>> [自动演示] 启动设备")
    model.start()

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n用户中断，正在停止...")
    finally:
        await server.stop()
        print("模拟器已退出。")


if __name__ == "__main__":
    asyncio.run(main())
