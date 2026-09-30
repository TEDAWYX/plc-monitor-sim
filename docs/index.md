# PLC 工业数据采集与监控仿真系统 —— 文档索引

> **版本**: V1.0  
> **日期**: 2026-09-11

---

## 快速导航

| 文档 | 说明 | 适用读者 |
|------|------|----------|
| [README.md](../README.md) | 项目总览、功能介绍、运行方法 | 所有人 |
| [design.md](design.md) | 系统设计文档、架构、技术决策 | 开发者、答辩评委 |
| [api_reference.md](api_reference.md) | API 参考、类/方法详细说明 | 开发者 |
| [user_manual.md](user_manual.md) | 用户手册、操作指南 | 使用者 |
| [troubleshooting.md](troubleshooting.md) | 故障排除、常见问题 | 使用者、开发者 |
| [deployment_guide.md](deployment_guide.md) | 部署指南、答辩准备 | 部署者、答辩者 |
| [phase_summary.md](phase_summary.md) | Phase 开发总结、踩坑经验 | 开发者 |
| [CHANGELOG.md](CHANGELOG.md) | 更新日志、版本规划 | 所有人 |

---

## 文档说明

### 对于使用者

如果你是第一次使用本系统，建议按以下顺序阅读：

1. [README.md](../README.md) —— 了解项目概况
2. [user_manual.md](user_manual.md) —— 学习如何操作
3. [troubleshooting.md](troubleshooting.md) —— 遇到问题时查阅

### 对于开发者

如果你需要理解或修改代码，建议按以下顺序阅读：

1. [README.md](../README.md) —— 了解项目概况
2. [design.md](design.md) —— 理解系统架构和设计决策
3. [api_reference.md](api_reference.md) —— 查阅 API 细节
4. [phase_summary.md](phase_summary.md) —— 了解开发历程和踩坑经验

### 对于答辩/演示

如果你需要准备答辩或演示，建议阅读：

1. [README.md](../README.md) —— 项目总览
2. [design.md](design.md) —— 技术亮点
3. [deployment_guide.md](deployment_guide.md) —— 演示脚本和注意事项

---

## 项目结构

```
plc-monitor-sim/
├── app/                    # 主应用代码
├── tests/                  # 单元测试（67 个）
├── data/                   # 运行时数据
├── docs/                   # 文档目录（本目录）
│   ├── index.md            # 文档索引（本文件）
│   ├── design.md           # 设计文档
│   ├── api_reference.md    # API 参考
│   ├── user_manual.md      # 用户手册
│   ├── troubleshooting.md  # 故障排除
│   ├── deployment_guide.md # 部署指南
│   ├── phase_summary.md    # Phase 总结
│   └── CHANGELOG.md        # 更新日志
├── screenshots/            # 项目截图
├── requirements.txt        # 依赖清单
├── README.md               # 项目说明
├── LICENSE                 # MIT 许可证
└── .gitignore              # Git 忽略规则
```

---

## 快速开始

```bash
# 1. 安装依赖
cd plc-monitor-sim
pip install -r requirements.txt

# 2. 运行测试
python -m pytest tests/ -v

# 3. 启动模拟器（终端 1）
python -m app.simulator.main

# 4. 启动上位机（终端 2）
python -m app.gui.main_window
```

---

_本文档为 V1.0 文档索引。_
