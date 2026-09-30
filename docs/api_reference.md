# API 参考文档

> **版本**: V1.0  
> **日期**: 2026-09-11

---

## 1. 配置模块 (`app.config.settings`)

### `CONFIG` (全局实例)

配置字典，包含以下顶级键：

| 键 | 类型 | 说明 |
|----|------|------|
| `modbus` | dict | Modbus 通信参数 |
| `acquisition` | dict | 采集参数 |
| `database` | dict | 数据库参数 |
| `alarms` | dict | 报警阈值与迟滞 |
| `simulator` | dict | 虚拟设备模型参数 |
| `gui` | dict | GUI 配置 |

### `load_config(config_path=None)`

加载配置。优先从 JSON 文件读取，缺失项使用默认值。

**参数**:
- `config_path`: 配置文件路径，默认 `app/config/settings.json`

**返回**: `dict` 配置字典

---

## 2. 设备模型 (`app.simulator.device_model`)

### `DeviceState` (Enum)

设备运行状态：
- `STOPPED` - 停机
- `STARTING` - 正在启动
- `RUNNING` - 正常运行
- `STOPPING` - 正在停机
- `FAULT` - 故障状态

### `FaultCode` (Enum)

故障代码：
- `NONE = 0` - 无故障
- `OVER_TEMPERATURE = 1` - 过温故障
- `INJECTED = 2` - 人工注入故障

### `DeviceSnapshot` (dataclass)

设备数据快照：

| 字段 | 类型 | 说明 |
|------|------|------|
| `temperature` | float | 温度（℃） |
| `pressure` | float | 压力（kPa） |
| `motor_speed` | float | 电机转速（RPM） |
| `current` | float | 电流（A） |
| `voltage` | float | 电压（V） |
| `state` | DeviceState | 运行状态 |
| `fault_code` | FaultCode | 故障代码 |
| `target_speed` | float | 目标转速（RPM） |
| `heartbeat` | int | 心跳计数 |

### `DeviceModel` (class)

虚拟工业设备模型。

**构造函数**:
```python
DeviceModel(config: dict)
```

**参数** (`config` 字典)：

| 键 | 类型 | 默认值 | 说明 |
|----|------|--------|------|
| `tick_interval_ms` | int | 200 | 内部 tick 间隔（毫秒） |
| `ambient_temperature` | float | 25.0 | 环境温度（℃） |
| `max_temperature` | float | 80.0 | 稳态最高温度（℃） |
| `temp_time_constant_s` | float | 60.0 | 温度一阶惯性时间常数（秒） |
| `rpm_time_constant_s` | float | 5.0 | 转速一阶惯性时间常数（秒） |
| `pressure_base_kpa` | float | 300.0 | 压力基值（kPa） |
| `pressure_rpm_factor` | float | 0.1 | 压力随转速系数（kPa/RPM） |
| `current_base_a` | float | 5.0 | 空载电流（A） |
| `current_accel_factor` | float | 0.02 | 加速电流系数（A/RPM差值） |
| `voltage_nominal_v` | float | 380.0 | 额定电压（V） |
| `noise_seed` | int/None | None | 随机种子（None=随机，整数=固定） |

**方法**:

| 方法 | 返回 | 说明 |
|------|------|------|
| `tick()` | DeviceSnapshot | 执行一次 tick 更新 |
| `start()` | bool | 启动设备（仅 STOPPED 状态有效） |
| `stop()` | bool | 停止设备（仅 STARTING/RUNNING 状态有效） |
| `set_target_speed(speed)` | bool | 设置目标转速（0~1500 RPM） |
| `inject_fault()` | bool | 注入故障 |
| `clear_fault()` | bool | 清除故障 |

---

## 3. 寄存器映射 (`app.simulator.register_map`)

### `REGISTERS` (list)

寄存器定义列表（10 个）。

### `REGISTER_BY_ADDRESS` (dict)

按协议地址查找：`{0: RegisterDef, 1: RegisterDef, ...}`

### `REGISTER_BY_NAME` (dict)

按名称查找：`{"TEMPERATURE": RegisterDef, ...}`

### `REGISTER_COUNT` (int)

寄存器总数（10）。

### `RegisterDef` (dataclass)

| 字段 | 类型 | 说明 |
|------|------|------|
| `address` | int | 协议地址（0-based） |
| `modbus_address` | int | Modbus 地址（40001-based） |
| `name` | str | 英文名称 |
| `reg_type` | RegisterType | 数据类型枚举 |
| `scale` | float | 缩放因子 |
| `unit` | str | 单位 |
| `writable` | bool | 是否可写 |
| `description` | str | 说明 |

### 工具函数

| 函数 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `encode_float(value, scale)` | float, float | int | 浮点编码为 uint16 |
| `decode_float(raw, scale)` | int, float | float | uint16 解码为浮点 |
| `encode_status_word(running, fault, starting)` | bool×3 | int | 编码状态字 |
| `decode_status_word(word)` | int | dict | 解码状态字 |

### `ControlCommand` (Enum)

- `NONE = 0`
- `START = 1`
- `STOP = 2`
- `INJECT_FAULT = 3`
- `CLEAR_FAULT = 4`

---

## 4. Modbus Server (`app.simulator.modbus_server`)

### `VirtualPlcServer` (class)

虚拟 PLC Modbus TCP Server。

**构造函数**:
```python
VirtualPlcServer(device_model: DeviceModel)
```

**方法**:

| 方法 | 参数 | 说明 |
|------|------|------|
| `start(host, port)` | str, int | 启动 Server 和 tick 循环 |
| `stop()` | - | 停止 Server |

---

## 5. Modbus Client (`app.communication.modbus_client`)

### `PlcModbusClient` (class)

PLC Modbus TCP Client 封装。

**构造函数**:
```python
PlcModbusClient(
    host: str = None,      # 默认从 CONFIG 读取
    port: int = None,
    slave_id: int = None,
    timeout: float = None,
    heartbeat_fail_count: int = None,
)
```

**方法**:

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `connect()` | - | bool | 建立连接 |
| `disconnect()` | - | - | 断开连接 |
| `read_all_registers()` | - | list[int]/None | 读取全部 10 个寄存器 |
| `write_register(address, value)` | int, int | bool | 写入单个寄存器 |
| `check_communication_health(heartbeat)` | int | bool | 心跳检测 |

---

## 6. 采集线程 (`app.acquisition.acquisition_worker`)

### `SensorSnapshot` (dataclass)

传感器数据快照：

| 字段 | 类型 | 说明 |
|------|------|------|
| `timestamp` | datetime | 时间戳 |
| `temperature` | float | 温度（℃） |
| `pressure` | float | 压力（kPa） |
| `motor_speed` | float | 转速（RPM） |
| `current` | float | 电流（A） |
| `voltage` | float | 电压（V） |
| `running` | bool | 是否运行 |
| `fault` | bool | 是否故障 |
| `starting` | bool | 是否启动中 |
| `fault_code` | int | 故障码 |
| `heartbeat` | int | 心跳计数 |
| `comm_status` | str | 通信状态（OK/ERROR/DISCONNECTED） |

### `AcquisitionWorker` (QThread)

数据采集工作线程。

**Signals**:
- `data_ready(SensorSnapshot)`: 新数据快照可用
- `comm_status_changed(str)`: 通信状态变化

**构造函数**:
```python
AcquisitionWorker(
    client: PlcModbusClient = None,
    period_ms: int = None,  # 默认 500ms
)
```

**方法**:

| 方法 | 说明 |
|------|------|
| `start()` | 启动采集线程 |
| `stop()` | 停止采集线程（线程安全） |

---

## 7. 报警引擎 (`app.processing.alarm_engine`)

### `AlarmLevel` (Enum)

- `WARNING` - 警告
- `ALARM` - 报警

### `AlarmStatus` (Enum)

- `ACTIVE` - 活动中
- `RECOVERED` - 已恢复
- `ACKNOWLEDGED` - 已确认

### `AlarmEvent` (dataclass)

| 字段 | 类型 | 说明 |
|------|------|------|
| `alarm_type` | str | 报警类型（如 temperature） |
| `level` | AlarmLevel | 报警等级 |
| `value` | float | 触发时的数值 |
| `timestamp` | datetime | 报警时间 |
| `status` | AlarmStatus | 报警状态 |
| `db_id` | int/None | 数据库记录 ID |

### `AlarmEngine` (class)

报警引擎。

**构造函数**:
```python
AlarmEngine(db_manager: DatabaseManager = None)
```

**方法**:

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `process(**sensor_values)` | kwargs | list[AlarmEvent] | 处理传感器数据，返回新事件 |
| `acknowledge(alarm_type)` | str | bool | 手动确认报警 |
| `get_active_alarms()` | - | list[AlarmEvent] | 获取活动报警 |
| `get_all_alarms(limit)` | int | list[AlarmEvent] | 获取报警历史 |
| `clear_history()` | - | - | 清空历史 |

---

## 8. 数据库管理 (`app.database.db_manager`)

### `DatabaseManager` (class)

SQLite 数据库管理器。

**构造函数**:
```python
DatabaseManager(db_path: str = None)  # 默认从 CONFIG 读取
```

**方法**:

| 方法 | 参数 | 返回 | 说明 |
|------|------|------|------|
| `connect()` | - | - | 建立连接 |
| `close()` | - | - | 关闭连接 |
| `init_tables()` | - | - | 初始化表结构 |
| `insert_sensor_data(...)` | 多个 | int | 插入传感器数据 |
| `insert_alarm_record(...)` | 多个 | int | 插入报警记录 |
| `update_alarm_recovered(id, time)` | int, datetime | - | 更新恢复状态 |
| `update_alarm_acknowledged(id, time)` | int, datetime | - | 更新确认状态 |
| `insert_system_event(...)` | 多个 | int | 插入系统事件 |
| `commit()` | - | - | 提交事务 |
| `query_sensor_data(...)` | 多个 | list[dict] | 查询传感器数据 |
| `query_alarm_records(...)` | 多个 | list[dict] | 查询报警记录 |
| `query_system_events(limit)` | int | list[dict] | 查询系统事件 |
| `clear_sensor_data()` | - | - | 清空传感器数据 |
| `clear_alarm_records()` | - | - | 清空报警记录 |
| `get_stats()` | - | dict | 获取统计信息 |

---

## 9. GUI 页面

### `MainWindow` (`app.gui.main_window`)

主窗口，QTabWidget 组织 5 个页面：
1. 实时监控（MonitorPage）
2. 趋势曲线（TrendPage）
3. 报警记录（AlarmPage）
4. 历史查询（HistoryPage）
5. 设备控制（ControlPage）

### `MonitorPage` (`app.gui.monitor_page`)

实时监控页面。

**方法**:
- `update_data(snapshot: SensorSnapshot)` - 更新显示数据
- `set_alarm_text(text, is_alarm)` - 设置报警文本

### `TrendPage` (`app.gui.trend_page`)

趋势曲线页面。

**方法**:
- `update_data(snapshot: SensorSnapshot)` - 更新曲线数据
- `clear()` - 清空曲线

### `AlarmPage` (`app.gui.alarm_page`)

报警记录页面。

**方法**:
- `refresh()` - 刷新显示
- `add_alarm_event(event)` - 新增报警事件

### `HistoryPage` (`app.gui.history_page`)

历史查询页面。

**方法**:
- `_do_query()` - 执行查询
- `_do_export()` - 导出 CSV

### `ControlPage` (`app.gui.control_page`)

设备控制页面。

**方法**:
- `set_client(client)` - 设置 Modbus 客户端

---

## 10. 自定义控件

### `StatusLight` (`app.gui.widgets.status_light`)

状态指示灯。

**构造函数**:
```python
StatusLight(color: str = "gray", size: int = 24)
```

**颜色**:
- `green` - 正常
- `yellow` - 警告/启动中
- `red` - 报警/故障
- `gray` - 停止/未知

**方法**:
- `set_color(color: str)` - 设置颜色
