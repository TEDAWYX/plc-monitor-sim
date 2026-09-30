"""
RegisterMap 单元测试

测试范围：
  1. 寄存器定义完整性
  2. 编码/解码函数正确性
  3. 状态字编解码
  4. 控制命令枚举

运行方式：
    pytest tests/test_register_map.py -v
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.simulator.register_map import (
    REGISTERS,
    REGISTER_COUNT,
    REGISTER_BY_ADDRESS,
    REGISTER_BY_NAME,
    encode_float,
    decode_float,
    encode_status_word,
    decode_status_word,
    ControlCommand,
)


class TestRegisterDefinitions:
    def test_register_count(self):
        assert REGISTER_COUNT == 10
        assert len(REGISTERS) == 10

    def test_address_continuous(self):
        """寄存器地址应连续从 0 开始"""
        for i, reg in enumerate(REGISTERS):
            assert reg.address == i
            assert reg.modbus_address == 40001 + i

    def test_unique_names(self):
        names = [r.name for r in REGISTERS]
        assert len(names) == len(set(names))

    def test_lookup_by_address(self):
        for reg in REGISTERS:
            assert REGISTER_BY_ADDRESS[reg.address] == reg

    def test_lookup_by_name(self):
        for reg in REGISTERS:
            assert REGISTER_BY_NAME[reg.name] == reg

    def test_writable_registers(self):
        """只有 TARGET_SPEED 和 CONTROL_CMD 可写"""
        writable = [r for r in REGISTERS if r.writable]
        assert len(writable) == 2
        assert writable[0].name == "TARGET_SPEED"
        assert writable[1].name == "CONTROL_CMD"


class TestEncodeDecode:
    def test_encode_float_scale_10(self):
        assert encode_float(72.3, 10.0) == 723
        assert encode_float(350.15, 10.0) == 3502  # 四舍五入

    def test_encode_float_scale_1(self):
        assert encode_float(1450.0, 1.0) == 1450

    def test_decode_float_scale_10(self):
        assert decode_float(723, 10.0) == 72.3
        assert decode_float(3502, 10.0) == 350.2

    def test_roundtrip(self):
        """编码再解码应近似还原（允许四舍五入误差，scale=10 时精度为 0.1）"""
        original = 72.3
        encoded = encode_float(original, 10.0)
        decoded = decode_float(encoded, 10.0)
        assert abs(decoded - original) < 0.01


class TestStatusWord:
    def test_all_false(self):
        word = encode_status_word(False, False, False)
        assert word == 0
        decoded = decode_status_word(word)
        assert decoded == {"running": False, "fault": False, "starting": False}

    def test_all_true(self):
        word = encode_status_word(True, True, True)
        assert word == 0x07
        decoded = decode_status_word(word)
        assert decoded == {"running": True, "fault": True, "starting": True}

    def test_only_running(self):
        word = encode_status_word(True, False, False)
        assert word == 0x01
        decoded = decode_status_word(word)
        assert decoded["running"] is True
        assert decoded["fault"] is False
        assert decoded["starting"] is False


class TestControlCommand:
    def test_enum_values(self):
        assert ControlCommand.NONE.value == 0
        assert ControlCommand.START.value == 1
        assert ControlCommand.STOP.value == 2
        assert ControlCommand.INJECT_FAULT.value == 3
        assert ControlCommand.CLEAR_FAULT.value == 4
