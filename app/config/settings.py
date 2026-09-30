"""
系统配置模块

所有可配置参数集中定义，支持从 JSON 文件覆盖默认值。
报警阈值和迟滞参数均在此配置，便于统一调整。
"""

import json
import os
from pathlib import Path

# 项目根目录（plc-monitor-sim/）
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# 默认配置
DEFAULT_CONFIG = {
    # --- Modbus 通信 ---
    "modbus": {
        "host": "127.0.0.1",
        "port": 5020,
        "slave_id": 1,
    },

    # --- 采集参数 ---
    "acquisition": {
        "period_ms": 500,           # 采集周期（毫秒）
        "timeout_s": 5.0,           # Modbus 连接超时（秒）
        "heartbeat_fail_count": 3,  # 连续几次心跳不变判定通信异常
    },

    # --- 数据库 ---
    "database": {
        "path": str(PROJECT_ROOT / "data" / "monitor.db"),
        "batch_size": 4,            # 批量写入条数（500ms×4 = 2秒）
        "flush_interval_s": 2.0,    # 最大 flush 间隔（秒）
    },

    # --- 报警阈值与迟滞（hysteresis） ---
    # 迟滞机制说明：
    #   当数值超过 high_limit 时产生报警；
    #   当数值回落到 (high_limit - hysteresis) 以下时才恢复报警。
    #   这样可避免模拟噪声导致报警状态在阈值附近频繁切换。
    "alarms": {
        "temperature": {
            "warning_high": 75.0,
            "alarm_high": 80.0,
            "hysteresis": 2.0,      # 例如 80℃ 报警，78℃ 以下恢复
        },
        "pressure": {
            "warning_high": 450.0,
            "warning_low": 300.0,
            "alarm_high": 520.0,
            "alarm_low": 280.0,
            "hysteresis": 5.0,
        },
        "current": {
            "warning_high": 20.0,
            "alarm_high": 25.0,
            "hysteresis": 1.0,
        },
        "voltage": {
            "warning_high": 400.0,
            "warning_low": 360.0,
            "alarm_high": 420.0,
            "alarm_low": 340.0,
            "hysteresis": 2.0,
        },
        "motor_speed": {
            # 运行中转速异常低（非零但远低于目标）
            "alarm_low": 100.0,
            "hysteresis": 10.0,
        },
    },

    # --- 虚拟设备模型参数 ---
    # 注意：以下参数仅用于产生具有工业过程特征的仿真数据，
    # 不代表任何真实设备的精确动力学模型。
    "simulator": {
        "tick_interval_ms": 200,    # 模拟器内部 tick 间隔
        "ambient_temperature": 25.0, # 环境温度（℃）
        "max_temperature": 80.0,    # 稳态最高温度（℃）
        "temp_time_constant_s": 60.0,  # 温度一阶惯性时间常数（秒）
        "rpm_time_constant_s": 5.0,    # 转速一阶惯性时间常数（秒）
        "pressure_base_kpa": 300.0,    # 压力基值（kPa）
        "pressure_rpm_factor": 0.1,    # 压力随转速系数（kPa/RPM）
        "current_base_a": 5.0,         # 空载电流（A）
        "current_accel_factor": 0.02,  # 加速电流系数（A/RPM差值）
        "voltage_nominal_v": 380.0,    # 额定电压（V）
        "noise_seed": None,            # None=随机，整数=固定种子（测试用）
    },

    # --- GUI ---
    "gui": {
        "trend_max_points": 500,    # 趋势曲线最大保留点数（环形缓冲）
        "update_interval_ms": 500,  # GUI 刷新间隔
    },
}


def load_config(config_path: str | None = None) -> dict:
    """
    加载配置。优先从 JSON 文件读取，缺失项使用默认值。
    """
    if config_path is None:
        config_path = PROJECT_ROOT / "app" / "config" / "settings.json"
    else:
        config_path = Path(config_path)

    config = dict(DEFAULT_CONFIG)

    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            _deep_update(config, user_config)
        except (json.JSONDecodeError, OSError) as e:
            print(f"[Config] 读取配置文件失败，使用默认配置。错误：{e}")

    return config


def _deep_update(base: dict, override: dict) -> None:
    """递归更新字典，不覆盖整个子字典。"""
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_update(base[key], value)
        else:
            base[key] = value


# 全局配置实例（首次导入时加载）
CONFIG = load_config()
