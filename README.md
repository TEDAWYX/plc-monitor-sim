# PLC 工业数据采集与监控仿真系统 V1.0

> **本项目为工业自动化监控系统的软件仿真项目，不连接真实 PLC 硬件。**
> 所有虚拟设备的物理模型均为简化模型，用于产生具有工业过程特征的仿真数据，不代表任何真实设备的精确动力学模型。

---

## 1. 项目介绍

本项目是一个运行在 Windows PC 上的工业自动化监控软件仿真系统。系统不依赖真实 PLC 硬件，而是在 PC 端实现一个"虚拟 PLC/工业设备模拟器"，模拟工业设备运行过程中产生的温度、压力、电机转速、电流、电压、运行状态、报警状态等数据。

虚拟设备通过 Modbus TCP 提供数据，上位机作为客户端进行数据采集，并实现实时监控、趋势曲线、报警检测、历史数据查询、CSV 导出、设备控制等功能。

**开发目的：**
- 学习 Python 工程开发
- 学习工业通信（Modbus TCP）
- 学习 PLC/SCADA 基本架构
- GitHub 展示
- 求职简历
- 后续申请软件著作权

---

## 2. 项目功能

| 功能 | 说明 |
|------|------|
| 虚拟工业设备模拟 | 具备启停过程、一阶惯性、噪声、故障注入的物理仿真模型 |
| Modbus TCP Server | 虚拟 PLC 对外提供寄存器数据 |
| Modbus TCP Client | 上位机轮询读取，含时间戳与数据校验 |
| 实时数据监控 | 温度/压力/转速/电流/电压大字体显示 + 状态指示灯 |
| 实时趋势曲线 | 温度/压力/转速曲线，可显隐，环形缓冲防内存泄漏 |
| 报警系统 | 阈值判断 + 迟滞机制 + 产生/恢复/确认状态机 |
| 历史数据查询 | 按时间范围查询 sensor_data |
| CSV 数据导出 | 导出历史数据为 CSV 文件 |
| 设备控制模拟 | 启动/停止/设定转速/注入故障，经 Modbus 写入虚拟 PLC |
| 通信状态监控 | 心跳检测，连续 N 次不变判定通信异常 |

---

## 3. 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│ 进程 1：simulator.exe（虚拟工业设备 / 虚拟PLC）                │
│  DeviceModel → RegisterMap → Modbus TCP Server (port 5020)  │
└──────────────────────┬──────────────────────────────────────┘
                       │ Modbus TCP（本机回环 127.0.0.1）
┌──────────────────────▼──────────────────────────────────────┐
│ 进程 2：上位机监控软件（PySide6 GUI）                          │
│  AcquisitionWorker（QThread，周期轮询 500ms）                 │
│    │ 读寄存器 → 数据校验 → 加时间戳                            │
│    ▼                                                        │
│  ProcessingLayer（报警判断）→ AlarmEngine（迟滞 + 状态机）      │
│    │                                                        │
│    ├──► DatabaseWriter（SQLite，批量写入）                     │
│    └──► GUI（signals/slots 跨线程推送）                       │
│           ├── 主监控页（数值/状态灯/通信状态）                  │
│           ├── 趋势曲线页（pyqtgraph 环形缓冲）                 │
│           ├── 报警页（实时报警+确认操作）                      │
│           ├── 历史查询页（查询+CSV导出）                        │
│           └── 控制页（启停/转速/故障注入）                      │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. 技术栈

| 组件 | 版本 | 说明 |
|------|------|------|
| Python | 3.11+ | 开发语言（推荐 3.11~3.12） |
| PySide6 | 6.7.0+ | 桌面 GUI |
| pymodbus | 3.7.0~3.15.x | Modbus TCP 通信 |
| pyqtgraph | 0.13.0+ | 实时趋势曲线 |
| pandas | 2.0.0+ | 数据处理和 CSV 导出 |
| SQLite | 内置 | 本地数据库 |
| pytest | 8.0.0+ | 单元测试 |
| pytest-asyncio | 0.21.0+ | 异步测试支持 |

---

## 5. Modbus 寄存器表

寄存器区：**Holding Register**（功能码 03 读 / 06 写）
数据类型：全部 **uint16**，通过缩放因子表示小数

| 协议地址 | Modbus 地址 | 名称 | 缩放 | 单位 | 读写 | 说明 |
|---------|------------|------|------|------|------|------|
| 0 | 40001 | TEMPERATURE | ÷10 | ℃ | R | 温度 |
| 1 | 40002 | PRESSURE | ÷10 | kPa | R | 压力 |
| 2 | 40003 | MOTOR_SPEED | ÷1 | RPM | R | 电机转速 |
| 3 | 40004 | CURRENT | ÷10 | A | R | 电流 |
| 4 | 40005 | VOLTAGE | ÷10 | V | R | 电压 |
| 5 | 40006 | STATUS_WORD | — | — | R | bit0=运行, bit1=故障, bit2=启动中 |
| 6 | 40007 | FAULT_CODE | — | — | R | 0=无, 1=过温, 2=注入 |
| 7 | 40008 | TARGET_SPEED | ÷1 | RPM | R/W | 目标转速设定（0~1500） |
| 8 | 40009 | CONTROL_CMD | — | — | R/W | 1=启动, 2=停止, 3=注入故障, 4=清除故障 |
| 9 | 40010 | HEARTBEAT | — | — | R | 心跳计数，每 tick 自增 |

**控制命令（40009）：**
| 值 | 命令 | 效果 |
|----|------|------|
| 0 | NONE | 无命令（复位态） |
| 1 | START | 设备进入启动过程 |
| 2 | STOP | 设备进入停机过程 |
| 3 | INJECT_FAULT | 注入模拟故障 |
| 4 | CLEAR_FAULT | 清除故障 |

---

## 6. 数据库设计

### sensor_data（传感器数据）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| timestamp | TEXT | ISO8601 本地时间 |
| temperature | REAL | ℃ |
| pressure | REAL | kPa |
| motor_speed | REAL | RPM |
| current | REAL | A |
| voltage | REAL | V |
| run_status | INTEGER | 0=停止, 1=运行 |

### alarm_records（报警记录）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| timestamp | TEXT | 报警产生时间 |
| alarm_type | TEXT | 如 TEMP_HIGH / PRESSURE_HIGH |
| value | REAL | 触发时的数值 |
| level | TEXT | WARNING / ALARM |
| status | TEXT | ACTIVE / RECOVERED |
| acknowledged | INTEGER | 0=未确认, 1=已确认 |
| recovered_at | TEXT | 恢复时间 |
| acknowledged_at | TEXT | 确认时间 |

### system_events（系统事件）

| 字段 | 类型 | 说明 |
|------|------|------|
| id | INTEGER PK | 自增主键 |
| timestamp | TEXT | 事件时间 |
| event_type | TEXT | INFO / WARNING / ERROR |
| source | TEXT | 产生模块 |
| message | TEXT | 事件描述 |

---

## 7. 软件运行方法

### 7.1 环境要求

- Python 3.11 或更高版本（推荐 3.11~3.12）
- Windows 10/11 操作系统

> **注意**：Python 3.13+ 可能遇到 PySide6 wheel 兼容性问题，建议使用 Python 3.11 或 3.12。

### 7.2 安装依赖

```bash
cd plc-monitor-sim
pip install -r requirements.txt
```

### 7.3 启动模拟器（虚拟 PLC）

在**第一个终端**中启动模拟器：

```bash
python -m app.simulator.main
```

模拟器将启动 Modbus TCP Server，监听 `127.0.0.1:5020`。

启动后显示：
```
[Modbus Server] 已启动于 127.0.0.1:5020 (slave_id=1)
>>> [自动演示] 启动设备
按 Ctrl+C 停止模拟器。
```

### 7.4 启动上位机监控软件

在**第二个终端**中启动上位机：

```bash
python -m app.gui.main_window
```

或：

```bash
python app/gui/main_window.py
```

### 7.5 运行控制台验证（无 GUI）

```bash
python -m app.main
```

控制台将周期性打印传感器数据，用于快速验证通信是否正常。

### 7.6 典型使用流程

1. 启动模拟器（终端 1）
2. 启动上位机（终端 2）
3. 在"实时监控"页查看数据
4. 在"趋势曲线"页观察变化趋势
5. 在"设备控制"页点击"启动设备"/"停止设备"/"注入故障"
6. 在"报警记录"页查看报警状态
7. 在"历史查询"页查询数据并导出 CSV

---

## 8. 测试方法

### 8.1 运行全部测试

```bash
cd plc-monitor-sim
python -m pytest tests/ -v
```

预期输出（67 个测试全部通过）：
```
============================= test session starts ==============================
...
tests/test_device_model.py ..............                           [ 32%]
tests/test_register_map.py ..............                           [ 53%]
tests/test_modbus_roundtrip.py ......                               [ 62%]
tests/test_modbus_client.py .....                                   [ 70%]
tests/test_database.py .........                                    [ 83%]
tests/test_alarm_engine.py ..........                              [ 98%]
tests/test_csv_exporter.py .                                        [100%]
============================== 67 passed in X.XXs =============================
```

### 8.2 运行特定模块测试

```bash
# 设备模型测试（状态机、物理特征、可重复性）
python -m pytest tests/test_device_model.py -v

# 寄存器映射测试（编解码、状态字）
python -m pytest tests/test_register_map.py -v

# Modbus 往返测试（Server/Client 集成）
python -m pytest tests/test_modbus_roundtrip.py -v

# Modbus 客户端测试（连接、读写、心跳）
python -m pytest tests/test_modbus_client.py -v

# 数据库测试（CRUD、时间查询）
python -m pytest tests/test_database.py -v

# 报警引擎测试（产生、迟滞、确认、升级）
python -m pytest tests/test_alarm_engine.py -v

# CSV 导出测试
python -m pytest tests/test_csv_exporter.py -v
```

### 8.3 测试原则

- **不伪造测试结果**：所有测试真实运行，不硬编码通过
- **固定 seed 保证可重复**：使用 `random.Random(seed)` 实现确定性测试
- **临时资源自动清理**：使用 `tempfile` 和 `pytest.fixture` 管理临时数据库
- **异步测试支持**：使用 `pytest-asyncio` 处理 async/await

---

## 9. 项目截图

运行截图存放于 `screenshots/` 目录：

| 截图 | 说明 |
|------|------|
| `screenshots/monitor.png` | 实时监控页面（大字体数值 + 状态灯） |
| `screenshots/trend.png` | 趋势曲线页面（温度/压力/转速曲线） |
| `screenshots/alarm.png` | 报警记录页面（活动报警 + 历史记录） |
| `screenshots/history.png` | 历史查询页面（时间范围查询 + CSV 导出） |
| `screenshots/control.png` | 设备控制页面（启停/转速/故障注入） |

> 截图可在程序运行时通过系统截图工具获取，保存到 `screenshots/` 目录。

---

## 10. 项目后续规划

| 版本 | 规划 | 优先级 |
|------|------|--------|
| V1.1 | 增加数据库存储线程（当前采集线程直接写入，需分离） | 高 |
| V1.2 | 增加系统事件日志页面 | 中 |
| V1.3 | 增加多设备支持（多 Modbus 从机） | 中 |
| V1.4 | 增加用户权限管理 | 低 |
| V1.5 | 增加网络发布（Web 监控） | 低 |

### V1.1 详细规划（高优先级）

**问题**：当前 `AcquisitionWorker` 直接调用 `DatabaseManager` 写入数据，在高频采集或大数据量时可能阻塞采集线程。

**方案**：
1. 新增 `DatabaseWriterThread`（QThread）
2. `AcquisitionWorker` 通过 `Queue` 将数据推送给 `DatabaseWriterThread`
3. `DatabaseWriterThread` 批量写入数据库
4. 解耦采集与存储，提高系统响应性

### V1.2 详细规划（中优先级）

**问题**：`system_events` 表已存在，但 GUI 无页面展示。

**方案**：
1. 新增 `SystemEventPage`（QTableWidget）
2. 显示 INFO / WARNING / ERROR 级别事件
3. 支持按类型过滤和时间范围查询

### V1.3 详细规划（中优先级）

**问题**：当前仅支持单设备（单 Modbus 从机）。

**方案**：
1. 配置文件支持多从机定义
2. `AcquisitionWorker` 支持多客户端轮询
3. GUI 支持设备切换或并列显示

### V1.4/V1.5 规划（低优先级）

- 用户权限：登录/角色/操作审计
- Web 监控：基于 Flask/FastAPI 的 REST API + 前端页面

---

## 11. 目录结构

```
plc-monitor-sim/
├── app/                                    # 主应用包
│   ├── __init__.py                         # 包初始化（版本信息）
│   ├── main.py                             # 控制台验证入口（无 GUI）
│   ├── config/
│   │   └── settings.py                     # 系统配置中心（JSON 可覆盖）
│   ├── simulator/                          # 虚拟设备模拟器
│   │   ├── device_model.py                 # 五状态状态机 + 一阶惯性物理模型
│   │   ├── register_map.py                 # Modbus 寄存器定义（唯一事实来源）
│   │   ├── modbus_server.py                # Modbus TCP Server（pymodbus 3.15）
│   │   └── main.py                         # 模拟器独立启动入口
│   ├── communication/
│   │   └── modbus_client.py                # Modbus TCP Client（异步 + 心跳检测）
│   ├── acquisition/
│   │   └── acquisition_worker.py           # QThread 采集线程（500ms 周期）
│   ├── processing/
│   │   └── alarm_engine.py                 # 报警引擎（迟滞 + 状态机）
│   ├── database/
│   │   └── db_manager.py                   # SQLite 数据库管理（三表 + 批量写入）
│   ├── gui/                                # PySide6 GUI
│   │   ├── main_window.py                  # 主窗口（QTabWidget 协调各页）
│   │   ├── monitor_page.py                 # 实时监控页（大字体 + 状态灯）
│   │   ├── trend_page.py                   # 趋势曲线页（pyqtgraph + 环形缓冲）
│   │   ├── alarm_page.py                   # 报警记录页（活动报警 + 确认操作）
│   │   ├── history_page.py                 # 历史查询页（时间范围 + CSV 导出）
│   │   ├── control_page.py                 # 设备控制页（启停/转速/故障注入）
│   │   └── widgets/
│   │       └── status_light.py             # 自定义状态指示灯控件
│   └── utils/
│       └── __init__.py                     # 工具包初始化
├── tests/                                  # 单元测试（67 个测试）
│   ├── __init__.py
│   ├── test_device_model.py                # 设备模型测试（22 个）
│   ├── test_register_map.py                # 寄存器映射测试（14 个）
│   ├── test_modbus_roundtrip.py            # Modbus 往返测试（6 个）
│   ├── test_modbus_client.py               # 客户端测试（5 个）
│   ├── test_database.py                    # 数据库测试（9 个）
│   ├── test_alarm_engine.py                # 报警引擎测试（10 个）
│   └── test_csv_exporter.py                # CSV 导出测试（1 个）
├── data/                                   # 运行时数据（.gitignore）
│   └── monitor.db                          # SQLite 数据库（运行时生成）
├── docs/                                   # 设计文档
│   ├── design.md                           # 系统设计文档
│   ├── api_reference.md                    # API 参考文档
│   ├── user_manual.md                      # 用户手册
│   ├── troubleshooting.md                  # 故障排除指南
│   ├── deployment_guide.md                 # 部署指南
│   ├── phase_summary.md                    # Phase 开发总结
│   └── CHANGELOG.md                        # 更新日志
├── screenshots/                            # 项目截图（.gitignore）
│   └── .gitkeep                            # 保持目录在 git 中
├── requirements.txt                        # Python 依赖清单
├── README.md                               # 项目说明（本文件）
├── LICENSE                                 # MIT 许可证
└── .gitignore                              # Git 忽略规则
```

---

## 12. 核心设计要点

### 12.1 双进程架构

- **模拟器进程**：`python -m app.simulator.main`
  - 运行虚拟设备模型 + Modbus TCP Server
  - 监听 `127.0.0.1:5020`
  - 可独立运行，不依赖上位机

- **上位机进程**：`python -m app.gui.main_window`
  - PySide6 GUI 应用
  - 作为 Modbus TCP Client 连接模拟器
  - 两进程通过本机回环通信

### 12.2 一阶惯性物理模型

转速和温度采用一阶惯性逼近目标值：
```
k = 1 - exp(-dt / τ)
value += (target - value) * k
```

- 转速时间常数：5 秒（快速响应）
- 温度时间常数：60 秒（慢速响应）
- 支持固定随机种子实现可重复测试

### 12.3 报警迟滞机制

避免阈值附近抖动：
- 产生报警：数值超过 `high_limit`
- 恢复报警：数值回落到 `(high_limit - hysteresis)` 以下
- 例如：80℃ 报警，78℃ 以下恢复（迟滞 2℃）

### 12.4 环形缓冲

趋势曲线使用 `deque(maxlen=500)`：
- 防止内存无限增长
- 自动丢弃最旧数据点
- 约保留 4 分钟历史（@ 500ms 采集周期）

---

## 13. 许可证

MIT License

---

## 14. 作者

Barye

---

_本项目为本科工程项目，用于学习和展示目的。所有虚拟设备的物理模型均为简化模型，用于产生具有工业过程特征的仿真数据，不代表任何真实设备的精确动力学模型。_
