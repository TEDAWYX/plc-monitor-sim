# Phase 开发总结

> **项目**: PLC 工业数据采集与监控仿真系统 V1.0  
> **日期**: 2026-09-11  
> **作者**: Barye

---

## Phase 1：项目骨架与配置系统

**目标**：搭建项目目录结构，实现配置中心。

**完成内容**：
- 创建 `app/` 包结构（config, simulator, communication, acquisition, processing, database, gui, utils）
- 实现 `app/config/settings.py`：
  - `DEFAULT_CONFIG` 字典，包含 Modbus、采集、数据库、报警、模拟器、GUI 配置
  - `load_config()` 支持从 JSON 文件覆盖默认值
  - `_deep_update()` 递归更新字典
  - `CONFIG` 全局实例

**关键设计**：
- 配置集中管理，避免硬编码散落各处
- 支持 JSON 覆盖，便于用户自定义
- 报警阈值和迟滞参数统一在配置中定义

**测试**：无（配置模块在后续测试中覆盖）

---

## Phase 2：虚拟设备模型与 Modbus Server

**目标**：实现虚拟工业设备模型和 Modbus TCP Server。

**完成内容**：
1. `app/simulator/device_model.py`：
   - `DeviceState` 五状态枚举（STOPPED/STARTING/RUNNING/STOPPING/FAULT）
   - `FaultCode` 故障代码枚举
   - `DeviceSnapshot` 数据快照 dataclass
   - `DeviceModel` 核心模型：
     - 一阶惯性物理模型（转速、温度）
     - 独立 `random.Random(seed)` 支持可重复测试
     - 启动/停止/转速设定/故障注入/清除故障接口
     - 状态机守卫（拒绝非法状态转换）

2. `app/simulator/register_map.py`：
   - 10 个 Holding Register 定义（唯一事实来源）
   - `encode_float`/`decode_float` 编解码工具
   - `encode_status_word`/`decode_status_word` 状态字工具
   - `ControlCommand` 枚举

3. `app/simulator/modbus_server.py`：
   - `VirtualPlcServer` 基于 pymodbus 3.15 `SimDevice`/`SimData` 新 API
   - 周期性 tick 更新寄存器（200ms）
   - 处理控制命令写入（消费后自动清零）
   - 处理目标转速写入

4. `app/simulator/main.py`：模拟器独立启动入口

**关键设计**：
- 一阶惯性公式：`k = 1 - exp(-dt/τ)`，`value += (target - value) * k`
- 独立随机数生成器支持固定 seed 实现可重复测试
- 寄存器映射作为唯一事实来源，避免 Server/Client 硬编码不一致

**踩坑经验**：
- pymodbus 3.15 `ModbusSlaveContext` 被标记 deprecated，需使用 `SimDevice`/`SimData` 新 API
- 同步 `ModbusTcpClient` 无法与异步 `ModbusTcpServer` 通信，测试和 Client 均需改用 `AsyncModbusTcpClient`

**测试**：`tests/test_device_model.py`（22 个测试）、`tests/test_register_map.py`（14 个测试）

---

## Phase 3：Modbus Client 与采集线程

**目标**：实现 Modbus TCP Client 和数据采集线程。

**完成内容**：
1. `app/communication/modbus_client.py`：
   - `PlcModbusClient` 基于 `AsyncModbusTcpClient`
   - 连接/断开管理
   - 读取全部寄存器（`read_all_registers`）
   - 写入单个寄存器（`write_register`）
   - 心跳检测（`check_communication_health`）
   - 自动重连（`_ensure_connected`）

2. `app/acquisition/acquisition_worker.py`：
   - `SensorSnapshot` 数据快照 dataclass（带时间戳和通信状态）
   - `AcquisitionWorker` 继承 `QThread`：
     - 周期性采集（默认 500ms）
     - 数据校验（范围检查）
     - 心跳检测
     - 通过 Qt signals 推送数据

3. `app/main.py`：控制台验证入口（无 GUI）

**关键设计**：
- Client 全异步，避免阻塞 GUI 线程
- 采集线程与 GUI 线程分离，通过 signals/slots 通信
- 通信异常不抛异常，返回错误状态快照

**踩坑经验**：
- QThread 的 `run()` 是同步的，调用 async 方法需要创建 `asyncio.new_event_loop()`
- 每次 async 调用后需关闭循环，避免资源泄漏

**测试**：`tests/test_modbus_client.py`（5 个测试）、`tests/test_modbus_roundtrip.py`（6 个测试）

---

## Phase 4：数据库设计

**目标**：实现 SQLite 数据库管理。

**完成内容**：
- `app/database/db_manager.py`：
  - `DatabaseManager` 类：
    - 三表结构：`sensor_data`、`alarm_records`、`system_events`
    - 自动建表（`init_tables`）
    - 批量写入（`insert_sensor_data`、`insert_alarm_record`、`insert_system_event`）
    - 更新操作（`update_alarm_recovered`、`update_alarm_acknowledged`）
    - 查询操作（`query_sensor_data`、`query_alarm_records`、`query_system_events`）
    - 维护操作（`clear_sensor_data`、`clear_alarm_records`、`get_stats`）

**关键设计**：
- 时间戳使用 ISO8601 格式（含毫秒）
- 参数化查询防止 SQL 注入
- 索引优化时间范围查询

**测试**：`tests/test_database.py`（9 个测试）

---

## Phase 5：报警系统

**目标**：实现报警引擎。

**完成内容**：
- `app/processing/alarm_engine.py`：
  - `AlarmLevel` 枚举（WARNING/ALARM）
  - `AlarmStatus` 枚举（ACTIVE/RECOVERED/ACKNOWLEDGED）
  - `AlarmEvent` dataclass
  - `AlarmEngine` 类：
    - `process(**sensor_values)`：处理传感器数据，判断报警
    - `acknowledge(alarm_type)`：手动确认报警
    - `get_active_alarms()`：获取活动报警
    - 迟滞机制：超过 high_limit 报警，回落到 (high_limit - hysteresis) 以下恢复
    - 只允许升级（WARNING → ALARM），不允许自动降级

**关键设计**：
- 每个报警类型独立跟踪状态
- 有活动报警时优先检查恢复条件
- 报警记录持久化到数据库

**踩坑经验**：
- 报警迟滞逻辑曾出现错误：ALARM→WARNING 降级时未正确处理
- 修复：重构 `_check_alarm`，有活动报警时优先检查恢复条件，再处理新报警；只允许升级不允许降级

**测试**：`tests/test_alarm_engine.py`（10 个测试）

---

## Phase 6：实时监控页面

**目标**：实现 GUI 主监控页面。

**完成内容**：
- `app/gui/main_window.py`：
  - `MainWindow` 主窗口，QTabWidget 组织页面
  - 协调采集线程、报警引擎、数据库
  - 窗口关闭时优雅停止采集线程

- `app/gui/monitor_page.py`：
  - `MonitorPage` 实时监控页面
  - 大字体显示温度/压力/转速/电流/电压
  - 状态指示灯（运行/故障/通信）
  - 当前报警信息

- `app/gui/widgets/status_light.py`：
  - `StatusLight` 自定义圆形指示灯控件
  - 支持 green/yellow/red/gray 四种颜色

**关键设计**：
- 使用 QGridLayout 清晰对齐传感器数据
- 状态灯直观显示设备状态
- 数值变化时颜色提示

---

## Phase 7：趋势曲线页面

**目标**：实现实时趋势曲线。

**完成内容**：
- `app/gui/trend_page.py`：
  - `TrendPage` 趋势曲线页面
  - 使用 pyqtgraph 绘制温度/压力/转速曲线
  - 环形缓冲（`deque(maxlen=500)`）
  - 可显隐控制（QCheckBox）
  - 相对时间显示（秒）

**关键设计**：
- 环形缓冲防止内存无限增长
- 可显隐不同曲线，便于观察
- 自动 Y 轴范围调整

---

## Phase 8：报警记录页面

**目标**：实现报警记录页面。

**完成内容**：
- `app/gui/alarm_page.py`：
  - `AlarmPage` 报警记录页面
  - 活动报警列表（QTableWidget）
  - 报警历史列表
  - 确认按钮（每行一个）
  - 不同等级用不同颜色标识（ALARM=红色，WARNING=黄色）

**关键设计**：
- 活动报警和历史报警分开显示
- 确认操作更新报警引擎状态
- 刷新按钮手动刷新显示

---

## Phase 9：历史查询与 CSV 导出页面

**目标**：实现历史数据查询和 CSV 导出。

**完成内容**：
- `app/gui/history_page.py`：
  - `HistoryPage` 历史查询页面
  - QDateTimeEdit 选择时间范围
  - 查询结果表格显示
  - CSV 导出（使用 pandas）
  - 导出文件包含 UTF-8 BOM，支持 Excel 直接打开

**关键设计**：
- 时间范围查询使用 ISO8601 字符串比较
- 导出使用 `utf-8-sig` 编码，兼容 Excel
- 默认保存到桌面

---

## Phase 10：设备控制页面

**目标**：实现设备控制页面。

**完成内容**：
- `app/gui/control_page.py`：
  - `ControlPage` 设备控制页面
  - 启动/停止设备按钮
  - 目标转速设定（QSpinBox，0~1500 RPM）
  - 故障注入/清除按钮
  - 操作确认提示（QMessageBox）
  - 状态提示标签

**关键设计**：
- 控制命令通过 Modbus 写入虚拟 PLC
- 操作前有确认提示，防止误操作
- 按钮样式区分功能（绿色=启动，红色=停止，黄色=故障）

---

## Phase 11：README 与项目文档

**目标**：编写项目文档。

**完成内容**：
- `README.md`：
  - 项目介绍、功能列表
  - 系统架构图（ASCII）
  - 技术栈表格
  - Modbus 寄存器表
  - 数据库设计
  - 运行方法（详细步骤）
  - 测试方法（全部 67 个测试）
  - 项目截图说明
  - 后续版本规划（V1.1~V1.5）
  - 目录结构

- `docs/design.md`：详细设计文档
  - 系统架构详解
  - 关键技术决策（为什么用新 API、为什么用 AsyncClient 等）
  - 物理模型说明
  - 测试策略
  - 已知限制

- `docs/api_reference.md`：API 参考文档
  - 所有公共类、方法、函数的详细说明

- `requirements.txt` 更新：
  - 添加 `pytest-asyncio` 依赖
  - 更新版本说明（推荐 Python 3.11~3.12）

- `app/utils/__init__.py`：创建空工具包

---

## 测试汇总

| 测试文件 | 测试数 | 覆盖范围 |
|----------|--------|----------|
| `test_device_model.py` | 22 | 状态机、物理特征、可重复性、边界 |
| `test_register_map.py` | 14 | 寄存器定义、编解码、状态字、命令枚举 |
| `test_modbus_roundtrip.py` | 6 | Server/Client 集成、读写、心跳 |
| `test_modbus_client.py` | 5 | 连接、读写、心跳检测、自动重连 |
| `test_database.py` | 9 | 建表、CRUD、时间范围查询、维护 |
| `test_alarm_engine.py` | 10 | 报警产生、迟滞、确认、升级、多类型 |
| `test_csv_exporter.py` | 1 | CSV 导出格式 |
| **总计** | **67** | |

---

## 踩坑经验汇总

1. **pymodbus 3.15 API 变更**：`ModbusSlaveContext`/`ModbusServerContext` 被标记 deprecated，新 API 使用 `SimDevice`/`SimData`/`ModbusTcpServer`
2. **同步 Client 无法连接异步 Server**：`ModbusTcpClient`（同步）无法与 `ModbusTcpServer`（异步）通信，需改用 `AsyncModbusTcpClient`
3. **报警迟滞逻辑**：有活动报警时应优先检查恢复条件，再处理新报警；只允许升级不允许降级
4. **QThread 中调用 async 方法**：需在 `run()` 中创建 `asyncio.new_event_loop()`，用 `loop.run_until_complete()` 执行，完成后关闭
5. **Modbus Client 写入测试失败**：写入目标转速前设备需处于 STARTING/RUNNING 状态，否则 `set_target_speed` 返回 False
6. **shutdown 后重复 cancel task**：`server.shutdown()` 已停止 serve_forever，再 `task.cancel()` 引发 RuntimeError，需移除多余 cancel
7. **roundtrip 测试四舍五入误差**：`encode_float(72.35, 10)` = 724 → `decode_float(724, 10)` = 72.4，测试用例改用 72.3 避免边界

---

## 文件清单

```
plc-monitor-sim/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config/
│   │   └── settings.py
│   ├── simulator/
│   │   ├── device_model.py
│   │   ├── register_map.py
│   │   ├── modbus_server.py
│   │   └── main.py
│   ├── communication/
│   │   └── modbus_client.py
│   ├── acquisition/
│   │   └── acquisition_worker.py
│   ├── processing/
│   │   └── alarm_engine.py
│   ├── database/
│   │   └── db_manager.py
│   ├── gui/
│   │   ├── main_window.py
│   │   ├── monitor_page.py
│   │   ├── trend_page.py
│   │   ├── alarm_page.py
│   │   ├── history_page.py
│   │   ├── control_page.py
│   │   └── widgets/
│   │       └── status_light.py
│   └── utils/
│       └── __init__.py
├── tests/
│   ├── __init__.py
│   ├── test_device_model.py
│   ├── test_register_map.py
│   ├── test_modbus_roundtrip.py
│   ├── test_modbus_client.py
│   ├── test_database.py
│   ├── test_alarm_engine.py
│   └── test_csv_exporter.py
├── data/
├── docs/
│   ├── design.md
│   └── api_reference.md
├── screenshots/
│   └── .gitkeep
├── requirements.txt
├── README.md
└── .gitignore
```

**代码统计**：
- Python 源文件：25 个（`.py`）
- 测试文件：7 个
- 总测试数：67 个
- 文档文件：3 个（README, design, api_reference）
