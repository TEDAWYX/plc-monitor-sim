# PLC 工业数据采集与监控仿真系统 —— 设计文档

> **版本**: V1.0  
> **日期**: 2026-09-11  
> **作者**: Barye

---

## 1. 项目概述

本项目是一个运行在 Windows PC 上的工业自动化监控软件仿真系统，用于本科工程实践。系统不依赖真实 PLC 硬件，而是通过软件模拟虚拟工业设备，并通过 Modbus TCP 协议进行数据通信。

**核心目标**:
- 学习 Python 工程化开发
- 理解工业通信协议（Modbus TCP）
- 掌握 SCADA 系统基本架构
- 为 GitHub 展示、求职简历、软件著作权申请提供项目支撑

---

## 2. 系统架构

### 2.1 双进程架构

```
┌─────────────────────────────────────────────────────────────┐
│ 进程 1：虚拟 PLC / 工业设备模拟器                              │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────┐  │
│  │ DeviceModel │───►│ RegisterMap │───►│ Modbus TCP      │  │
│  │ (物理模型)   │    │ (寄存器映射) │    │ Server (5020)   │  │
│  └─────────────┘    └─────────────┘    └─────────────────┘  │
└──────────────────────┬──────────────────────────────────────┘
                       │ Modbus TCP（本机回环 127.0.0.1）
┌──────────────────────▼──────────────────────────────────────┐
│ 进程 2：上位机监控软件（PySide6 GUI）                          │
│  ┌─────────────────────────────────────────────────────────┐│
│  │ AcquisitionWorker（QThread，500ms 周期轮询）              ││
│  │   ├── 读寄存器 → 数据校验 → 加时间戳                      ││
│  │   └── 通信状态检测（心跳）                                ││
│  └─────────────────────────────────────────────────────────┘│
│                            │                                │
│  ┌─────────────────────────▼─────────────────────────────┐  │
│  │ Processing Layer                                        │  │
│  │   ├── AlarmEngine（报警判断 + 迟滞 + 状态机）            │  │
│  │   └── DatabaseWriter（SQLite 持久化）                   │  │
│  └─────────────────────────────────────────────────────────┘  │
│                            │                                │
│  ┌─────────────────────────▼─────────────────────────────┐  │
│  │ GUI Layer（PySide6 + signals/slots 跨线程）             │  │
│  │   ├── MonitorPage（实时监控页）                          │  │
│  │   ├── TrendPage（趋势曲线，pyqtgraph）                   │  │
│  │   ├── AlarmPage（报警记录 + 确认）                       │  │
│  │   ├── HistoryPage（历史查询 + CSV 导出）                 │  │
│  │   └── ControlPage（设备控制）                            │  │
│  └─────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块职责

| 模块 | 职责 | 对应文件 |
|------|------|----------|
| 配置中心 | 集中管理所有可配置参数，支持 JSON 覆盖 | `app/config/settings.py` |
| 设备模型 | 五状态状态机 + 一阶惯性物理仿真 | `app/simulator/device_model.py` |
| 寄存器映射 | Modbus 寄存器定义唯一事实来源 | `app/simulator/register_map.py` |
| Modbus Server | 虚拟 PLC 的 TCP 通信接口 | `app/simulator/modbus_server.py` |
| Modbus Client | 上位机异步通信客户端 | `app/communication/modbus_client.py` |
| 采集线程 | QThread 周期性轮询 + 数据校验 | `app/acquisition/acquisition_worker.py` |
| 报警引擎 | 阈值判断 + 迟滞 + 状态机 | `app/processing/alarm_engine.py` |
| 数据库 | SQLite 三表操作 + 批量写入 | `app/database/db_manager.py` |
| 主窗口 | 协调各模块，QTabWidget 组织页面 | `app/gui/main_window.py` |

---

## 3. 关键技术决策

### 3.1 为什么使用 pymodbus 3.15 的新 API？

pymodbus 3.15 将 `ModbusSlaveContext`/`ModbusServerContext` 标记为 deprecated，推荐使用 `SimDevice`/`SimData`/`SimCore` 新 API。新 API 的优势：
- 更简洁的异步接口（`async_getValues`/`async_setValues`）
- 内置的数据类型支持
- 与 `ModbusTcpServer` 更好的集成

### 3.2 为什么使用 AsyncModbusTcpClient？

同步的 `ModbusTcpClient` 无法与异步的 `ModbusTcpServer` 正常通信。使用异步客户端：
- 避免阻塞 GUI 线程
- 支持 asyncio 生态
- 与 pymodbus 3.15 Server 兼容

### 3.3 为什么采集线程中创建新的事件循环？

`AcquisitionWorker` 继承 `QThread`，其 `run()` 方法是同步的。而 `PlcModbusClient` 的方法是 async 的。解决方案：
- 在 `run()` 中每次调用 async 方法前创建 `asyncio.new_event_loop()`
- 用 `loop.run_until_complete()` 执行异步操作
- 完成后关闭循环

这是 QThread 与 asyncio 混用的常见模式。

### 3.4 报警迟滞机制设计

**问题**：如果数值在阈值附近波动，会导致报警状态频繁切换（抖动）。

**解决方案**：
- 产生报警：数值超过 `high_limit`
- 恢复报警：数值回落到 `(high_limit - hysteresis)` 以下
- 例如：温度报警阈值 80℃，迟滞 2℃，则 80℃ 报警，78℃ 以下恢复

**状态机**：
```
无报警 ──[value > limit]──► ACTIVE ──[value <= limit - hysteresis]──► RECOVERED
                              │
                              └──[人工确认]──► ACKNOWLEDGED
```

### 3.5 环形缓冲设计

趋势曲线使用 `collections.deque(maxlen=N)` 作为环形缓冲：
- 防止内存无限增长
- 自动丢弃最旧的数据点
- 默认最大 500 点（约 4 分钟 @ 500ms 采集周期）

---

## 4. Modbus 寄存器设计

### 4.1 寄存器表

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

### 4.2 控制命令

| 值 | 命令 | 效果 |
|----|------|------|
| 0 | NONE | 无命令（复位态） |
| 1 | START | 设备进入启动过程 |
| 2 | STOP | 设备进入停机过程 |
| 3 | INJECT_FAULT | 注入模拟故障 |
| 4 | CLEAR_FAULT | 清除故障 |

---

## 5. 数据库设计

### 5.1 表结构

**sensor_data**（传感器数据）
```sql
CREATE TABLE sensor_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    temperature REAL,
    pressure REAL,
    motor_speed REAL,
    current REAL,
    voltage REAL,
    run_status INTEGER
);
```

**alarm_records**（报警记录）
```sql
CREATE TABLE alarm_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    alarm_type TEXT NOT NULL,
    value REAL,
    level TEXT NOT NULL,
    status TEXT NOT NULL,
    acknowledged INTEGER NOT NULL DEFAULT 0,
    recovered_at TEXT,
    acknowledged_at TEXT
);
```

**system_events**（系统事件）
```sql
CREATE TABLE system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source TEXT,
    message TEXT
);
```

---

## 6. 物理模型说明

### 6.1 一阶惯性模型

转速和温度采用一阶惯性逼近目标值：

```
k = 1 - exp(-dt / τ)
value += (target - value) * k
```

其中：
- `dt`：tick 间隔（秒）
- `τ`：时间常数（秒）
- `k`：离散化系数

### 6.2 各物理量计算

| 物理量 | 计算方式 | 参数 |
|--------|----------|------|
| 转速 | 一阶惯性逼近目标转速 | `rpm_time_constant_s = 5.0` |
| 温度 | 一阶惯性逼近稳态温度（与负载相关） | `temp_time_constant_s = 60.0` |
| 压力 | 基值 + 转速 × 系数 + 噪声 | `pressure_base_kpa = 300.0`, `pressure_rpm_factor = 0.1` |
| 电流 | 空载 + 加速电流 + 噪声 | `current_base_a = 5.0`, `current_accel_factor = 0.02` |
| 电压 | 额定电压 + 噪声 | `voltage_nominal_v = 380.0` |

### 6.3 状态机

```
                    START
                     │
                     ▼
STOPPED ────────► STARTING ────────► RUNNING
   │                  │                  │
   │                  │                  │
   │ STOP             │                  │ STOP
   │                  │                  │
   ▼                  ▼                  ▼
   └────────────► STOPPING ◄────────────┘
   │
   │ INJECT_FAULT (任意非 FAULT 状态)
   ▼
 FAULT ────────► CLEAR_FAULT ────────► STOPPED
```

---

## 7. 测试策略

### 7.1 测试覆盖

| 测试文件 | 测试数 | 覆盖范围 |
|----------|--------|----------|
| `test_device_model.py` | 22 | 状态机、物理特征、可重复性、边界 |
| `test_register_map.py` | 14 | 寄存器定义、编解码、状态字、命令枚举 |
| `test_modbus_roundtrip.py` | 6 | Server/Client 集成、读写、心跳 |
| `test_modbus_client.py` | 5 | 连接、读写、心跳检测、自动重连 |
| `test_database.py` | 9 | 建表、CRUD、时间范围查询、维护 |
| `test_alarm_engine.py` | 10 | 报警产生、迟滞、确认、升级、多类型 |
| `test_csv_exporter.py` | 1 | CSV 导出格式 |

**总计：67 个测试**

### 7.2 测试原则

1. **不伪造测试结果**：所有测试真实运行，不硬编码通过
2. **固定 seed 保证可重复**：`random.Random(seed)` 支持确定性测试
3. **异步测试**：使用 `pytest-asyncio` 处理 async/await
4. **临时资源**：使用 `tempfile` 和 `pytest.fixture` 管理临时数据库

---

## 8. 已知限制与后续规划

### 8.1 V1.0 已知限制

1. 采集线程直接写入数据库，未分离存储线程（高负载时可能阻塞采集）
2. 系统事件日志有数据库表但无 GUI 页面
3. 单设备支持（仅一个 Modbus 从机）
4. 无用户权限管理
5. 无网络发布功能（Web 监控）

### 8.2 后续版本规划

| 版本 | 规划 |
|------|------|
| V1.1 | 增加数据库存储线程，分离采集与存储 |
| V1.2 | 增加系统事件日志页面 |
| V1.3 | 增加多设备支持（多 Modbus 从机） |
| V1.4 | 增加用户权限管理 |
| V1.5 | 增加网络发布（Web 监控） |

---

## 9. 开发环境

- **OS**: Windows 10/11
- **Python**: 3.11+（开发使用 3.14.2）
- **IDE**: VS Code / PyCharm
- **包管理**: pip + requirements.txt

---

## 10. 运行方法

```bash
# 1. 安装依赖
cd plc-monitor-sim
pip install -r requirements.txt

# 2. 启动模拟器（终端 1）
python -m app.simulator.main

# 3. 启动上位机（终端 2）
python -m app.gui.main_window

# 4. 运行测试
python -m pytest tests/ -v
```

---

_本文档为 V1.0 设计文档，用于项目理解和后续维护。_
