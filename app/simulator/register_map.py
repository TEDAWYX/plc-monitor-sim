"""
Modbus 寄存器映射表 —— 唯一事实来源

本模块定义虚拟 PLC 的所有寄存器地址、数据类型、缩放因子和读写属性。
上位机（Client）和模拟器（Server）必须引用同一套定义，避免硬编码不一致。

寄存器区：Holding Register（功能码 03 读 / 06 写）
数据类型：全部 uint16（16 位无符号整数），通过缩放因子表示小数

重要说明：
  本模型为简化模型，用于产生具有工业过程特征的仿真数据，
  不代表任何真实设备的精确动力学模型。
"""

from dataclasses import dataclass
from enum import Enum
from typing import Callable


class RegisterType(Enum):
    """寄存器数据类型"""
    TEMPERATURE = "temperature"      # ℃
    PRESSURE = "pressure"            # kPa
    MOTOR_SPEED = "motor_speed"      # RPM
    CURRENT = "current"              # A
    VOLTAGE = "voltage"              # V
    STATUS_WORD = "status_word"      # 位域
    FAULT_CODE = "fault_code"        # 枚举
    TARGET_SPEED = "target_speed"    # RPM（可写）
    CONTROL_CMD = "control_cmd"      # 枚举（可写）
    HEARTBEAT = "heartbeat"          # 通信活性计数


@dataclass(frozen=True)
class RegisterDef:
    """寄存器定义"""
    address: int                # 协议地址（0-based）
    modbus_address: int         # Modbus 地址（40001-based）
    name: str                   # 英文名称
    reg_type: RegisterType      # 数据类型
    scale: float                # 缩放因子（上位机读取后：value / scale）
    unit: str                   # 单位
    writable: bool              # 是否可写
    description: str            # 说明


# ---------------------------------------------------------------------------
# 寄存器定义列表（唯一事实来源）
# ---------------------------------------------------------------------------

REGISTERS: list[RegisterDef] = [
    RegisterDef(
        address=0,
        modbus_address=40001,
        name="TEMPERATURE",
        reg_type=RegisterType.TEMPERATURE,
        scale=10.0,
        unit="℃",
        writable=False,
        description="温度，缩放因子 10。例：723 → 72.3℃",
    ),
    RegisterDef(
        address=1,
        modbus_address=40002,
        name="PRESSURE",
        reg_type=RegisterType.PRESSURE,
        scale=10.0,
        unit="kPa",
        writable=False,
        description="压力，缩放因子 10。例：3501 → 350.1 kPa",
    ),
    RegisterDef(
        address=2,
        modbus_address=40003,
        name="MOTOR_SPEED",
        reg_type=RegisterType.MOTOR_SPEED,
        scale=1.0,
        unit="RPM",
        writable=False,
        description="电机转速，无缩放",
    ),
    RegisterDef(
        address=3,
        modbus_address=40004,
        name="CURRENT",
        reg_type=RegisterType.CURRENT,
        scale=10.0,
        unit="A",
        writable=False,
        description="电流，缩放因子 10",
    ),
    RegisterDef(
        address=4,
        modbus_address=40005,
        name="VOLTAGE",
        reg_type=RegisterType.VOLTAGE,
        scale=10.0,
        unit="V",
        writable=False,
        description="电压，缩放因子 10",
    ),
    RegisterDef(
        address=5,
        modbus_address=40006,
        name="STATUS_WORD",
        reg_type=RegisterType.STATUS_WORD,
        scale=1.0,
        unit="-",
        writable=False,
        description="状态字：bit0=运行，bit1=故障，bit2=正在启动",
    ),
    RegisterDef(
        address=6,
        modbus_address=40007,
        name="FAULT_CODE",
        reg_type=RegisterType.FAULT_CODE,
        scale=1.0,
        unit="-",
        writable=False,
        description="故障码：0=无，1=过温，2=注入故障",
    ),
    RegisterDef(
        address=7,
        modbus_address=40008,
        name="TARGET_SPEED",
        reg_type=RegisterType.TARGET_SPEED,
        scale=1.0,
        unit="RPM",
        writable=True,
        description="目标转速设定（0~1500），可写",
    ),
    RegisterDef(
        address=8,
        modbus_address=40009,
        name="CONTROL_CMD",
        reg_type=RegisterType.CONTROL_CMD,
        scale=1.0,
        unit="-",
        writable=True,
        description="控制命令：1=启动，2=停止，3=注入故障，4=清除故障。消费后自动清零",
    ),
    RegisterDef(
        address=9,
        modbus_address=40010,
        name="HEARTBEAT",
        reg_type=RegisterType.HEARTBEAT,
        scale=1.0,
        unit="-",
        writable=False,
        description="心跳计数，每 tick 自增，用于通信活性检测",
    ),
]

# 快速查找字典
REGISTER_BY_ADDRESS: dict[int, RegisterDef] = {r.address: r for r in REGISTERS}
REGISTER_BY_NAME: dict[str, RegisterDef] = {r.name: r for r in REGISTERS}

# 寄存器总数
REGISTER_COUNT = len(REGISTERS)


# ---------------------------------------------------------------------------
# 编码/解码工具函数
# ---------------------------------------------------------------------------

def encode_float(value: float, scale: float) -> int:
    """
    将浮点数值编码为 uint16 寄存器值。
    例：72.3℃ → 723（scale=10）
    """
    return int(round(value * scale))


def decode_float(raw: int, scale: float) -> float:
    """
    将 uint16 寄存器值解码为浮点数。
    例：723（scale=10）→ 72.3
    """
    return raw / scale


def encode_status_word(running: bool, fault: bool, starting: bool) -> int:
    """编码状态字"""
    word = 0
    if running:
        word |= 0x01
    if fault:
        word |= 0x02
    if starting:
        word |= 0x04
    return word


def decode_status_word(word: int) -> dict[str, bool]:
    """解码状态字"""
    return {
        "running": bool(word & 0x01),
        "fault": bool(word & 0x02),
        "starting": bool(word & 0x04),
    }


# ---------------------------------------------------------------------------
# 控制命令枚举
# ---------------------------------------------------------------------------

class ControlCommand(Enum):
    """控制命令枚举（写入 40009）"""
    NONE = 0
    START = 1
    STOP = 2
    INJECT_FAULT = 3
    CLEAR_FAULT = 4


# 命令名称映射（用于日志）
CONTROL_CMD_NAMES: dict[int, str] = {
    0: "NONE",
    1: "START",
    2: "STOP",
    3: "INJECT_FAULT",
    4: "CLEAR_FAULT",
}
