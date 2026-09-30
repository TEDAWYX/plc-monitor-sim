# 更新日志

> **项目**: PLC 工业数据采集与监控仿真系统

---

## [V1.0.0] - 2026-09-11

### 新增

- **虚拟工业设备模拟**
  - 五状态状态机（STOPPED/STARTING/RUNNING/STOPPING/FAULT）
  - 一阶惯性物理模型（转速、温度）
  - 独立随机数生成器，支持固定 seed 实现可重复测试
  - 故障注入与清除功能

- **Modbus TCP 通信**
  - 基于 pymodbus 3.15 的 Modbus TCP Server（虚拟 PLC）
  - 异步 Modbus TCP Client（上位机）
  - 10 个 Holding Register 定义（唯一事实来源）
  - 心跳检测与自动重连

- **数据采集**
  - QThread 采集线程（500ms 周期）
  - 数据校验（范围检查）
  - 时间戳与通信状态标记

- **报警系统**
  - 阈值判断（WARNING/ALARM 两级）
  - 迟滞机制（避免阈值附近抖动）
  - 报警状态机（ACTIVE/RECOVERED/ACKNOWLEDGED）
  - 多类型报警独立跟踪

- **数据库**
  - SQLite 三表设计（sensor_data/alarm_records/system_events）
  - 批量写入与查询
  - 时间范围查询

- **GUI 界面（PySide6）**
  - 实时监控页面（大字体数值 + 状态指示灯）
  - 趋势曲线页面（pyqtgraph + 环形缓冲）
  - 报警记录页面（活动报警 + 历史记录 + 确认操作）
  - 历史查询页面（时间范围查询 + CSV 导出）
  - 设备控制页面（启停/转速设定/故障注入）

- **测试**
  - 67 个单元测试（pytest）
  - 覆盖设备模型、寄存器映射、Modbus 通信、数据库、报警引擎、CSV 导出

- **文档**
  - README.md（项目说明）
  - docs/design.md（设计文档）
  - docs/api_reference.md（API 参考）
  - docs/user_manual.md（用户手册）
  - docs/troubleshooting.md（故障排除）
  - docs/phase_summary.md（Phase 开发总结）

### 技术栈

- Python 3.11+
- PySide6 6.7.0+
- pymodbus 3.7.0+
- pyqtgraph 0.13.0+
- pandas 2.0.0+
- pytest 8.0.0+
- pytest-asyncio 0.21.0+

### 已知限制

1. 采集线程直接写入数据库，未分离存储线程
2. system_events 表有数据但无 GUI 页面展示
3. 仅支持单设备（单 Modbus 从机）
4. 无用户权限管理
5. 无 Web 监控功能

---

## 后续版本规划

### V1.1（高优先级）

- [ ] 增加数据库存储线程，分离采集与存储
- [ ] 优化高负载下的系统响应性

### V1.2（中优先级）

- [ ] 增加系统事件日志页面
- [ ] 支持按类型过滤和时间范围查询系统事件

### V1.3（中优先级）

- [ ] 增加多设备支持（多 Modbus 从机）
- [ ] 配置文件支持多从机定义
- [ ] GUI 支持设备切换或并列显示

### V1.4（低优先级）

- [ ] 增加用户权限管理
- [ ] 登录/角色/操作审计

### V1.5（低优先级）

- [ ] 增加网络发布（Web 监控）
- [ ] 基于 Flask/FastAPI 的 REST API
- [ ] 前端监控页面

---

_更新日志格式参考 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。_
