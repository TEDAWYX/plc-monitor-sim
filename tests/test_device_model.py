"""
DeviceModel 单元测试

测试范围：
  1. 状态机流转
  2. 启动/停止过程的一阶惯性特征
  3. 温度随运行时间上升、停机回落
  4. 固定 seed 下数据可重复
  5. 故障注入与清除
  6. 边界条件（非法状态转换、转速范围限制）

运行方式：
    cd plc-monitor-sim
    pytest tests/test_device_model.py -v
"""

import pytest
import sys
from pathlib import Path

# 确保 app 包在路径中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.simulator.device_model import DeviceModel, DeviceState, FaultCode


# ---------------------------------------------------------------------------
# 测试辅助
# ---------------------------------------------------------------------------

def make_model(seed: int | None = 42, **overrides) -> DeviceModel:
    """构造一个测试用的 DeviceModel，默认固定 seed 保证可重复。"""
    config = {
        "tick_interval_ms": 200,
        "ambient_temperature": 25.0,
        "max_temperature": 80.0,
        "temp_time_constant_s": 60.0,
        "rpm_time_constant_s": 5.0,
        "pressure_base_kpa": 300.0,
        "pressure_rpm_factor": 0.1,
        "current_base_a": 5.0,
        "current_accel_factor": 0.02,
        "voltage_nominal_v": 380.0,
        "noise_seed": seed,
    }
    config.update(overrides)
    return DeviceModel(config)


def run_ticks(model: DeviceModel, n: int) -> list:
    """连续运行 n 个 tick，返回所有快照。"""
    return [model.tick() for _ in range(n)]


# ---------------------------------------------------------------------------
# 状态机测试
# ---------------------------------------------------------------------------

class TestStateMachine:
    def test_initial_state_is_stopped(self):
        model = make_model()
        assert model.state == DeviceState.STOPPED
        assert model.fault_code == FaultCode.NONE

    def test_start_from_stopped(self):
        model = make_model()
        assert model.start() is True
        assert model.state == DeviceState.STARTING

    def test_start_from_running_is_rejected(self):
        model = make_model()
        model.start()
        # 强制进入 RUNNING（直接 tick 很多轮）
        for _ in range(200):
            model.tick()
        assert model.state == DeviceState.RUNNING
        assert model.start() is False  # 重复启动应被拒绝

    def test_stop_from_running(self):
        model = make_model()
        model.start()
        for _ in range(200):
            model.tick()
        assert model.state == DeviceState.RUNNING
        assert model.stop() is True
        assert model.state == DeviceState.STOPPING

    def test_stop_from_stopped_is_rejected(self):
        model = make_model()
        assert model.stop() is False

    def test_full_start_stop_cycle(self):
        model = make_model()
        # 启动
        model.start()
        assert model.state == DeviceState.STARTING
        # tick 直到运行
        for _ in range(200):
            model.tick()
        assert model.state == DeviceState.RUNNING
        # 停止
        model.stop()
        assert model.state == DeviceState.STOPPING
        # tick 直到停机
        for _ in range(200):
            model.tick()
        assert model.state == DeviceState.STOPPED

    def test_inject_fault_from_running(self):
        model = make_model()
        model.start()
        for _ in range(200):
            model.tick()
        assert model.state == DeviceState.RUNNING
        assert model.inject_fault() is True
        assert model.state == DeviceState.FAULT
        assert model.fault_code == FaultCode.INJECTED

    def test_clear_fault_returns_to_stopped(self):
        model = make_model()
        model.start()
        for _ in range(200):
            model.tick()
        model.inject_fault()
        assert model.state == DeviceState.FAULT
        assert model.clear_fault() is True
        assert model.state == DeviceState.STOPPED
        assert model.fault_code == FaultCode.NONE

    def test_inject_fault_when_already_fault_is_rejected(self):
        model = make_model()
        model.start()
        for _ in range(200):
            model.tick()
        model.inject_fault()
        assert model.inject_fault() is False


# ---------------------------------------------------------------------------
# 物理模型特征测试
# ---------------------------------------------------------------------------

class TestPhysicalCharacteristics:
    def test_rpm_smooth_ramp_up(self):
        """
        启动过程中，转速应从 0 平滑爬升，不能出现瞬间跳变。
        相邻 tick 之间的转速变化量应小于一个合理上限。
        """
        model = make_model()
        model.start()
        prev_rpm = 0.0
        max_delta = 0.0
        for _ in range(100):
            snap = model.tick()
            delta = abs(snap.motor_speed - prev_rpm)
            max_delta = max(max_delta, delta)
            prev_rpm = snap.motor_speed
        # 200ms tick，5s 时间常数，最大单步变化约 50 RPM（保守估计）
        assert max_delta < 60.0, f"转速跳变过大：{max_delta}"

    def test_rpm_reaches_target(self):
        """启动完成后，转速应接近目标值（1450 RPM）。"""
        model = make_model()
        model.start()
        for _ in range(300):
            snap = model.tick()
        assert snap.motor_speed >= 1400.0, f"转速未达标：{snap.motor_speed}"

    def test_temperature_rises_during_running(self):
        """运行过程中温度应持续上升（或至少不下降）。"""
        model = make_model()
        model.start()
        temps = []
        for _ in range(300):
            snap = model.tick()
            temps.append(snap.temperature)
        # 取前 100 个 tick 的平均 vs 后 100 个 tick 的平均
        early_avg = sum(temps[:100]) / 100
        late_avg = sum(temps[-100:]) / 100
        assert late_avg > early_avg, f"温度未上升：早期 {early_avg}，后期 {late_avg}"

    def test_temperature_falls_after_stop(self):
        """停机后温度应回落。"""
        model = make_model()
        model.start()
        for _ in range(300):
            model.tick()
        temp_before_stop = model.tick().temperature
        model.stop()
        for _ in range(100):
            model.tick()
        temp_after_stop = model.tick().temperature
        assert temp_after_stop < temp_before_stop, (
            f"温度未回落：停机前 {temp_before_stop}，停机后 {temp_after_stop}"
        )

    def test_pressure_correlates_with_rpm(self):
        """压力应与转速正相关（粗略验证）。"""
        model = make_model()
        # 停机时压力
        snap_stop = model.tick()
        # 运行后压力
        model.start()
        for _ in range(300):
            snap_run = model.tick()
        assert snap_run.pressure > snap_stop.pressure + 50, (
            f"运行压力未显著高于停机压力：{snap_run.pressure} vs {snap_stop.pressure}"
        )

    def test_current_spike_during_start(self):
        """启动过程中电流应有尖峰（高于空载电流）。"""
        model = make_model()
        model.start()
        max_current = 0.0
        for _ in range(100):
            snap = model.tick()
            max_current = max(max_current, snap.current)
        assert max_current > 6.0, f"启动电流未出现尖峰：{max_current}"

    def test_voltage_nominal_when_running(self):
        """运行中电压应在额定值附近。"""
        model = make_model()
        model.start()
        for _ in range(300):
            snap = model.tick()
        assert 370.0 <= snap.voltage <= 390.0, f"电压异常：{snap.voltage}"


# ---------------------------------------------------------------------------
# 可重复性测试
# ---------------------------------------------------------------------------

class TestReproducibility:
    def test_fixed_seed_produces_identical_sequence(self):
        """固定 seed 下，两次运行应产生完全相同的序列。"""
        model1 = make_model(seed=12345)
        model2 = make_model(seed=12345)

        model1.start()
        model2.start()

        seq1 = run_ticks(model1, 500)
        seq2 = run_ticks(model2, 500)

        for i, (a, b) in enumerate(zip(seq1, seq2)):
            assert a.temperature == b.temperature, f"tick {i} 温度不同"
            assert a.pressure == b.pressure, f"tick {i} 压力不同"
            assert a.motor_speed == b.motor_speed, f"tick {i} 转速不同"
            assert a.current == b.current, f"tick {i} 电流不同"
            assert a.voltage == b.voltage, f"tick {i} 电压不同"
            assert a.state == b.state, f"tick {i} 状态不同"

    def test_different_seed_produces_different_noise(self):
        """不同 seed 应产生不同的噪声序列（至少压力不同）。"""
        model1 = make_model(seed=111)
        model2 = make_model(seed=222)

        model1.start()
        model2.start()

        pressures1 = [m.tick().pressure for m in [model1] for _ in range(50)]
        pressures2 = [m.tick().pressure for m in [model2] for _ in range(50)]

        # 重新构造（上面的写法有问题，修正如下）
        m1 = make_model(seed=111)
        m2 = make_model(seed=222)
        m1.start()
        m2.start()
        p1 = [m1.tick().pressure for _ in range(50)]
        p2 = [m2.tick().pressure for _ in range(50)]

        assert p1 != p2, "不同 seed 产生了相同压力序列"


# ---------------------------------------------------------------------------
# 边界与异常测试
# ---------------------------------------------------------------------------

class TestEdgeCases:
    def test_target_speed_clamped(self):
        """目标转速应被限制在 0~1500 范围内。"""
        model = make_model()
        model.start()
        for _ in range(200):
            model.tick()
        # 设置超限值
        model.set_target_speed(2000)
        assert model._target_speed == 1500.0
        model.set_target_speed(-100)
        assert model._target_speed == 0.0

    def test_set_speed_in_stopped_is_rejected(self):
        model = make_model()
        assert model.set_target_speed(1000) is False

    def test_heartbeat_increments_and_wraps(self):
        """心跳计数应递增并在 65535 后回绕到 0。"""
        model = make_model()
        # 先 tick 到接近回绕
        for _ in range(65530):
            model.tick()
        snap = model.tick()
        assert snap.heartbeat == 65531
        for _ in range(4):
            snap = model.tick()
        assert snap.heartbeat == 65535
        snap = model.tick()
        assert snap.heartbeat == 0

    def test_fault_state_values_are_abnormal(self):
        """故障状态下应有异常特征：温度升高、转速跌落。"""
        model = make_model()
        model.start()
        for _ in range(300):
            model.tick()
        rpm_before = model.tick().motor_speed
        temp_before = model.tick().temperature

        model.inject_fault()
        for _ in range(50):
            snap = model.tick()

        assert snap.motor_speed < rpm_before * 0.5, "故障后转速未显著跌落"
        assert snap.temperature > temp_before, "故障后温度未上升"
