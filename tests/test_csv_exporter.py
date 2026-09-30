"""
CSV 导出测试

测试范围：
  1. pandas DataFrame 导出为 CSV
  2. 文件编码和格式

运行方式：
    pytest tests/test_csv_exporter.py -v
"""

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
import pandas as pd


class TestCsvExport:
    def test_export_sensor_data(self):
        """导出传感器数据为 CSV"""
        data = {
            "timestamp": ["2026-09-10T10:00:00", "2026-09-10T10:00:01"],
            "temperature": [72.3, 73.1],
            "pressure": [350.1, 351.2],
            "motor_speed": [1450.0, 1450.0],
            "current": [12.5, 12.6],
            "voltage": [380.0, 380.1],
            "run_status": [1, 1],
        }
        df = pd.DataFrame(data)

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name

        df.to_csv(path, index=False, encoding="utf-8-sig")

        # 读取验证
        df_read = pd.read_csv(path)
        assert len(df_read) == 2
        assert df_read["temperature"][0] == 72.3

        Path(path).unlink(missing_ok=True)
