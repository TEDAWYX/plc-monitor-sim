# 故障排除指南

> **版本**: V1.0  
> **日期**: 2026-09-11

---

## 1. 安装问题

### 1.1 pip 安装依赖失败

**现象**:
```
ERROR: Could not find a version that satisfies the requirement PySide6>=6.7.0
```

**原因**: Python 版本不兼容（如 Python 3.13+）

**解决**:
1. 检查 Python 版本：`python --version`
2. 如为 3.13+，建议降级到 3.11 或 3.12
3. 或使用 conda 创建虚拟环境：
   ```bash
   conda create -n plc python=3.11
   conda activate plc
   pip install -r requirements.txt
   ```

### 1.2 pymodbus 安装后导入错误

**现象**:
```
ImportError: cannot import name 'SimDevice' from 'pymodbus.simulator'
```

**原因**: pymodbus 版本过低（< 3.7.0）

**解决**:
```bash
pip install --upgrade "pymodbus>=3.7.0,<4.0"
```

### 1.3 pyqtgraph 安装后报错

**现象**:
```
ImportError: No module named 'pyqtgraph'
```

**解决**:
```bash
pip install pyqtgraph>=0.13.0
```

---

## 2. 启动问题

### 2.1 模拟器启动报错：端口被占用

**现象**:
```
[Modbus Server] 启动失败: [WinError 10048] 通常每个套接字地址(协议/网络地址/端口)只允许使用一次
```

**原因**: 5020 端口被其他程序占用

**解决**:
1. 查找占用端口的进程：
   ```bash
   netstat -ano | findstr 5020
   ```
2. 结束占用进程，或修改配置使用其他端口：
   ```python
   # app/config/settings.py
   "modbus": {
       "port": 5021,  # 改为其他端口
   }
   ```

### 2.2 模拟器启动后无输出

**现象**: 执行命令后没有任何输出

**原因**: Python 模块路径问题

**解决**:
1. 确保在项目根目录（`plc-monitor-sim/`）执行
2. 检查 `app/simulator/main.py` 是否存在
3. 尝试使用完整路径：
   ```bash
   python -m app.simulator.main
   ```

### 2.3 上位机启动后窗口闪退

**现象**: 窗口出现后立即关闭

**原因**: 
1. 模拟器未启动，连接失败
2. PySide6 与 Python 版本不兼容
3. 缺少图形界面支持（如远程 SSH）

**解决**:
1. 先启动模拟器
2. 检查 PySide6 兼容性
3. 在本地图形环境运行，或使用控制台验证：
   ```bash
   python -m app.main
   ```

---

## 3. 通信问题

### 3.1 上位机显示"未连接"

**现象**: 通信状态灯灰色，显示"未连接"

**排查步骤**:
1. 检查模拟器是否已启动
2. 检查防火墙设置（允许 Python 通过防火墙）
3. 检查 IP 和端口配置是否一致
4. 测试网络连通性：
   ```bash
   telnet 127.0.0.1 5020
   ```

### 3.2 通信状态"异常"

**现象**: 通信状态灯红色，显示"通信异常"

**原因**: 心跳检测失败（连续多次心跳未变化）

**解决**:
1. 检查模拟器是否卡住（查看模拟器终端输出）
2. 重启模拟器
3. 增加心跳失败阈值：
   ```python
   "acquisition": {
       "heartbeat_fail_count": 5,  # 增加容错次数
   }
   ```

### 3.3 数据不更新

**现象**: 数值显示不变或全为 0

**排查步骤**:
1. 检查通信状态
2. 检查模拟器是否在运行（终端是否有 tick 输出）
3. 检查数据校验是否过滤了异常值
4. 查看日志输出是否有错误信息

---

## 4. 功能问题

### 4.1 趋势曲线不显示

**现象**: 趋势曲线页面空白

**解决**:
1. 检查"温度"/"压力"/"转速"复选框是否勾选
2. 等待几秒钟积累数据
3. 检查 pyqtgraph 是否安装正确
4. 尝试点击其他标签页再返回

### 4.2 报警不触发

**现象**: 设备运行中超阈值但不报警

**排查步骤**:
1. 检查设备是否处于运行状态（报警只在通信正常时检测）
2. 检查报警阈值配置
3. 检查报警引擎是否初始化（查看主窗口代码）
4. 尝试注入故障测试报警系统

### 4.3 历史查询无结果

**现象**: 查询后显示"共 0 条记录"

**原因**:
1. 数据库中无数据
2. 时间范围选择不正确
3. 数据库文件被删除

**解决**:
1. 确保系统已运行一段时间（数据需要积累）
2. 扩大时间范围（选择更早的开始时间）
3. 检查 `data/monitor.db` 是否存在

### 4.4 CSV 导出失败

**现象**: 点击"导出 CSV"报错

**解决**:
1. 确保已先执行查询
2. 检查磁盘空间
3. 检查是否有写入权限
4. 尝试保存到其他目录

### 4.5 控制命令无效

**现象**: 点击"启动设备"无反应

**排查步骤**:
1. 检查通信状态是否为"正常"
2. 检查设备当前状态（停止状态才能启动）
3. 查看模拟器终端是否有命令接收日志
4. 检查 Modbus 写入是否成功（查看状态栏提示）

---

## 5. 测试问题

### 5.1 测试运行缓慢

**现象**: `pytest` 执行时间很长

**原因**: 部分测试需要等待异步操作（如 Modbus 通信）

**解决**:
- 这是正常现象，Modbus 往返测试需要实际通信
- 如想加速，可单独运行非异步测试：
  ```bash
  pytest tests/test_device_model.py tests/test_register_map.py tests/test_database.py tests/test_alarm_engine.py -v
  ```

### 5.2 异步测试报错

**现象**:
```
pytest_asyncio.plugin.MultipleExceptions
```

**原因**: pytest-asyncio 版本不兼容

**解决**:
```bash
pip install --upgrade pytest-asyncio
```

### 5.3 测试端口冲突

**现象**: Modbus 测试报错端口被占用

**原因**: 测试使用的非标准端口（15020, 15050）被占用

**解决**:
1. 修改测试文件中的 `TEST_PORT` 为其他值
2. 或等待一段时间后重试（端口释放需要时间）

---

## 6. 性能问题

### 6.1 上位机卡顿

**现象**: GUI 界面响应缓慢

**原因**:
1. 数据库写入阻塞采集线程
2. 趋势曲线数据点过多
3. 系统资源不足

**解决**:
1. 减少趋势曲线保留点数：
   ```python
   "gui": {
       "trend_max_points": 200,
   }
   ```
2. 增加采集周期：
   ```python
   "acquisition": {
       "period_ms": 1000,
   }
   ```
3. 关闭不必要的页面

### 6.2 数据库文件过大

**现象**: `data/monitor.db` 文件体积很大

**解决**:
1. 定期清理历史数据：
   ```python
   from app.database.db_manager import DatabaseManager
   db = DatabaseManager()
   db.clear_sensor_data()
   db.clear_alarm_records()
   ```
2. 或手动删除 `data/monitor.db` 后重启

### 6.3 内存占用高

**现象**: Python 进程内存占用持续增长

**原因**: 趋势曲线数据积累（虽然有限制，但 pyqtgraph 可能缓存）

**解决**:
1. 定期清理趋势曲线（点击"清空"按钮，如已实现）
2. 重启上位机
3. 减少 `trend_max_points`

---

## 7. 配置问题

### 7.1 配置文件不生效

**现象**: 修改 `settings.json` 后配置未改变

**原因**:
1. JSON 格式错误
2. 文件路径不正确
3. 配置项名称错误

**解决**:
1. 验证 JSON 格式（使用在线 JSON 验证工具）
2. 确保文件位于 `app/config/settings.json`
3. 检查配置项名称是否与 `DEFAULT_CONFIG` 一致

### 7.2 如何恢复默认配置

**解决**:
1. 删除 `app/config/settings.json`
2. 重启程序，将使用 `DEFAULT_CONFIG`

---

## 8. 日志与调试

### 8.1 查看详细日志

**方法**: 在代码中添加日志输出

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### 8.2 调试 Modbus 通信

**方法**: 启用 pymodbus 调试日志

```python
# 在 modbus_server.py 或 modbus_client.py 中添加
logging.getLogger("pymodbus").setLevel(logging.DEBUG)
```

### 8.3 采集数据调试

**方法**: 使用控制台验证入口

```bash
python -m app.main
```

将实时打印采集到的数据，便于排查通信问题。

---

## 9. 已知限制

### 9.1 V1.0 已知问题

1. **采集线程直接写入数据库**：高负载时可能阻塞采集
2. **无系统事件日志页面**：`system_events` 表有数据但无 GUI 展示
3. **单设备支持**：仅支持一个 Modbus 从机
4. **无用户权限**：任何人可操作所有功能
5. **无 Web 监控**：仅支持本地桌面 GUI

### 9.2 不影响使用的警告

测试中可能出现的 `Task was destroyed but it is pending!` 警告：
- 这是 pytest-asyncio 清理时的正常现象
- 不影响测试结果
- 不影响实际运行

---

## 10. 获取进一步帮助

如以上方法无法解决问题：

1. 查看项目文档：`docs/` 目录
2. 运行测试确认系统完整性：`pytest tests/ -v`
3. 检查 Python 环境和依赖版本
4. 查看各模块的文档字符串（docstring）

---

_本指南对应系统版本 V1.0。_
