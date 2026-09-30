"""
虚拟工业设备物理模型与状态机

本模块实现一个简化的工业设备仿真模型，用于产生具有工业过程特征的数据，
包括启动/停止过程、温度惯性、压力波动、电流尖峰等。

重要说明：
  本模型为简化模型，用于产生具有工业过程特征的仿真数据，
  不代表任何真实设备的精确动力学模型。

设计要点：
  1. 状态机：STOPPED -> STARTING -> RUNNING -> STOPPING -> FAULT
  2. 一阶惯性：转速、温度采用一阶惯性逼近目标值，模拟真实惯性过程
  3. 噪声：使用独立 random.Random 实例，支持固定 seed 实现可重复测试
  4. 故障注入：支持模拟故障状态，转速/温度异常变化
"""

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


class DeviceState(Enum):
    """设备运行状态"""
    STOPPED = auto()    # 停机
    STARTING = auto()   # 正在启动
    RUNNING = auto()    # 正常运行
    STOPPING = auto()   # 正在停机
    FAULT = auto()      # 故障状态


class FaultCode(Enum):
    """故障代码"""
    NONE = 0
    OVER_TEMPERATURE = 1    # 过温故障（模拟器内部触发）
    INJECTED = 2            # 人工注入故障


@dataclass
class DeviceSnapshot:
    """设备数据快照（用于外部读取当前状态）"""
    temperature: float = 25.0       # ℃
    pressure: float = 300.0         # kPa
    motor_speed: float = 0.0        # RPM
    current: float = 0.0            # A
    voltage: float = 0.0            # V
    state: DeviceState = DeviceState.STOPPED
    fault_code: FaultCode = FaultCode.NONE
    target_speed: float = 0.0       # RPM
    heartbeat: int = 0              # 通信活性计数


class DeviceModel:
    """
    虚拟工业设备模型

    参数说明（均来自 settings.py 中的 simulator 配置）：
      tick_interval_ms: 内部 tick 间隔（毫秒）
      ambient_temperature: 环境温度（℃）
      max_temperature: 稳态最高温度（℃）
      temp_time_constant_s: 温度一阶惯性时间常数（秒）
      rpm_time_constant_s: 转速一阶惯性时间常数（秒）
      pressure_base_kpa: 压力基值（kPa）
      pressure_rpm_factor: 压力随转速系数（kPa/RPM）
      current_base_a: 空载电流（A）
      current_accel_factor: 加速电流系数（A/RPM差值）
      voltage_nominal_v: 额定电压（V）
      noise_seed: 随机种子（None=随机，整数=固定）
    """

    def __init__(self, config: dict):
        self._cfg = config
        self._dt = config["tick_interval_ms"] / 1000.0  # 秒

        # 独立随机数生成器（支持固定 seed 实现可重复测试）
        seed = config.get("noise_seed")
        self._rng = random.Random(seed)

        # 状态机
        self._state = DeviceState.STOPPED
        self._fault_code = FaultCode.NONE

        # 物理量
        self._temperature = config["ambient_temperature"]
        self._pressure = config["pressure_base_kpa"]
        self._motor_speed = 0.0
        self._current = 0.0
        self._voltage = 0.0

        # 控制量
        self._target_speed = 0.0

        # 通信活性计数（每 tick 自增，回绕）
        self._heartbeat = 0

        # 预计算一阶惯性系数：k = 1 - exp(-dt / tau)
        # 这样每 tick 更新：value += (target - value) * k
        self._temp_k = self._compute_k(config["temp_time_constant_s"])
        self._rpm_k = self._compute_k(config["rpm_time_constant_s"])

    # ------------------------------------------------------------------
    # 公共接口
    # ------------------------------------------------------------------

    def tick(self) -> DeviceSnapshot:
        """
        执行一次内部 tick 更新（由模拟器主循环周期性调用）。
        返回当前数据快照。
        """
        self._heartbeat = (self._heartbeat + 1) % 65536

        # 根据当前状态更新物理量
        if self._state == DeviceState.STOPPED:
            self._tick_stopped()
        elif self._state == DeviceState.STARTING:
            self._tick_starting()
        elif self._state == DeviceState.RUNNING:
            self._tick_running()
        elif self._state == DeviceState.STOPPING:
            self._tick_stopping()
        elif self._state == DeviceState.FAULT:
            self._tick_fault()

        return self._snapshot()

    def start(self) -> bool:
        """启动设备。仅在 STOPPED 状态有效。"""
        if self._state == DeviceState.STOPPED:
            self._state = DeviceState.STARTING
            self._target_speed = 1450.0  # 默认目标转速
            return True
        return False

    def stop(self) -> bool:
        """停止设备。在 STARTING / RUNNING 状态有效。"""
        if self._state in (DeviceState.STARTING, DeviceState.RUNNING):
            self._state = DeviceState.STOPPING
            self._target_speed = 0.0
            return True
        return False

    def set_target_speed(self, speed: float) -> bool:
        """
        设置目标转速。仅在 STARTING / RUNNING 状态有效。
        范围限制：0 ~ 1500 RPM。
        """
        if self._state not in (DeviceState.STARTING, DeviceState.RUNNING):
            return False
        self._target_speed = max(0.0, min(1500.0, speed))
        return True

    def inject_fault(self) -> bool:
        """注入模拟故障。在任意非 FAULT 状态有效。"""
        if self._state != DeviceState.FAULT:
            self._state = DeviceState.FAULT
            self._fault_code = FaultCode.INJECTED
            return True
        return False

    def clear_fault(self) -> bool:
        """清除故障。仅在 FAULT 状态有效，清除后回到 STOPPED。"""
        if self._state == DeviceState.FAULT:
            self._state = DeviceState.STOPPED
            self._fault_code = FaultCode.NONE
            self._target_speed = 0.0
            return True
        return False

    @property
    def state(self) -> DeviceState:
        return self._state

    @property
    def fault_code(self) -> FaultCode:
        return self._fault_code

    # ------------------------------------------------------------------
    # 内部物理更新
    # ------------------------------------------------------------------

    def _tick_stopped(self):
        """停机状态：所有量缓慢归零/回落到环境值。"""
        self._motor_speed = 0.0
        self._target_speed = 0.0

        # 温度回落到环境温度
        self._temperature += (
            self._cfg["ambient_temperature"] - self._temperature
        ) * self._temp_k

        # 压力回到基值
        self._pressure = self._cfg["pressure_base_kpa"] + self._noise(2.0)

        # 电流、电压归零
        self._current = 0.0
        self._voltage = max(0.0, self._voltage - 50.0 * self._dt)  # 母线缓慢放电

    def _tick_starting(self):
        """启动中：转速向目标值爬升，伴随电流尖峰，温度开始上升。"""
        # 转速一阶惯性逼近目标
        self._motor_speed += (self._target_speed - self._motor_speed) * self._rpm_k

        # 温度：稳态温度与负载（目标转速比例）相关
        load_ratio = self._target_speed / 1500.0
        steady_temp = self._cfg["ambient_temperature"] + (
            self._cfg["max_temperature"] - self._cfg["ambient_temperature"]
        ) * load_ratio
        self._temperature += (steady_temp - self._temperature) * self._temp_k

        # 压力：与转速正相关 + 噪声
        self._pressure = (
            self._cfg["pressure_base_kpa"]
            + self._motor_speed * self._cfg["pressure_rpm_factor"]
            + self._noise(5.0)
        )

        # 电流：空载 + 加速电流（与转速差成正比）+ 噪声
        speed_diff = self._target_speed - self._motor_speed
        self._current = (
            self._cfg["current_base_a"]
            + speed_diff * self._cfg["current_accel_factor"]
            + self._noise(0.5)
        )
        self._current = max(0.0, self._current)

        # 电压：额定电压 + 噪声
        self._voltage = self._cfg["voltage_nominal_v"] + self._noise(3.0)

        # 启动完成判定：转速达到目标值的 98% 以上
        if self._motor_speed >= self._target_speed * 0.98:
            self._state = DeviceState.RUNNING

    def _tick_running(self):
        """正常运行：转速稳定，温度继续缓慢上升趋近稳态，压力正常波动。"""
        # 转速：轻微波动（模拟负载扰动）
        self._motor_speed = self._target_speed + self._noise(5.0)
        self._motor_speed = max(0.0, min(1500.0, self._motor_speed))

        # 温度
        load_ratio = self._target_speed / 1500.0
        steady_temp = self._cfg["ambient_temperature"] + (
            self._cfg["max_temperature"] - self._cfg["ambient_temperature"]
        ) * load_ratio
        self._temperature += (steady_temp - self._temperature) * self._temp_k

        # 压力
        self._pressure = (
            self._cfg["pressure_base_kpa"]
            + self._motor_speed * self._cfg["pressure_rpm_factor"]
            + self._noise(5.0)
        )

        # 电流：空载 + 小量噪声（运行中无加速电流）
        self._current = self._cfg["current_base_a"] + self._noise(0.3)
        self._current = max(0.0, self._current)

        # 电压
        self._voltage = self._cfg["voltage_nominal_v"] + self._noise(3.0)

    def _tick_stopping(self):
        """停机中：转速下降，温度回落，电流减小。"""
        # 转速向 0 下降
        self._motor_speed += (0.0 - self._motor_speed) * self._rpm_k

        # 温度回落
        self._temperature += (
            self._cfg["ambient_temperature"] - self._temperature
        ) * self._temp_k

        # 压力
        self._pressure = (
            self._cfg["pressure_base_kpa"]
            + self._motor_speed * self._cfg["pressure_rpm_factor"]
            + self._noise(5.0)
        )

        # 电流：随转速下降而减小
        self._current = (
            self._cfg["current_base_a"] * (self._motor_speed / 1500.0)
            + self._noise(0.3)
        )
        self._current = max(0.0, self._current)

        # 电压：母线缓慢放电
        self._voltage = self._cfg["voltage_nominal_v"] + self._noise(3.0)
        if self._motor_speed < 10.0:
            self._voltage = max(0.0, self._voltage - 50.0 * self._dt)

        # 停机完成判定
        if self._motor_speed < 1.0:
            self._state = DeviceState.STOPPED
            self._motor_speed = 0.0
            self._current = 0.0

    def _tick_fault(self):
        """故障状态：转速快速跌落，温度异常升高，电流波动。"""
        # 转速快速滑落
        self._motor_speed = max(0.0, self._motor_speed - 200.0 * self._dt)

        # 温度异常升高（模拟故障发热）
        self._temperature += 0.5 * self._dt  # 每 tick 缓慢上升
        self._temperature = min(120.0, self._temperature)

        # 压力随转速下降
        self._pressure = (
            self._cfg["pressure_base_kpa"]
            + self._motor_speed * self._cfg["pressure_rpm_factor"]
            + self._noise(10.0)
        )

        # 电流异常波动
        self._current = self._noise(5.0)
        self._current = max(0.0, self._current)

        # 电压跌落
        self._voltage = max(0.0, self._voltage - 30.0 * self._dt)

    # ------------------------------------------------------------------
    # 辅助方法
    # ------------------------------------------------------------------

    def _compute_k(self, time_constant_s: float) -> float:
        """
        计算一阶惯性离散化系数。
        公式：k = 1 - exp(-dt / tau)
        当 tau >> dt 时，k ≈ dt / tau
        """
        import math
        return 1.0 - math.exp(-self._dt / time_constant_s)

    def _noise(self, amplitude: float) -> float:
        """生成 [-amplitude, +amplitude] 范围内的均匀分布噪声。"""
        return self._rng.uniform(-amplitude, amplitude)

    def _snapshot(self) -> DeviceSnapshot:
        """生成当前数据快照。"""
        return DeviceSnapshot(
            temperature=round(self._temperature, 2),
            pressure=round(self._pressure, 2),
            motor_speed=round(self._motor_speed, 2),
            current=round(self._current, 2),
            voltage=round(self._voltage, 2),
            state=self._state,
            fault_code=self._fault_code,
            target_speed=round(self._target_speed, 2),
            heartbeat=self._heartbeat,
        )
