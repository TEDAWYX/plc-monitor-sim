# 部署指南

> **版本**: V1.0  
> **日期**: 2026-09-11  
> **适用场景**: 本科工程答辩、GitHub 展示、求职简历演示

---

## 1. 部署前准备

### 1.1 环境检查清单

| 检查项 | 要求 | 验证命令 |
|--------|------|----------|
| 操作系统 | Windows 10/11 | `winver` |
| Python 版本 | 3.11 ~ 3.12 | `python --version` |
| pip 版本 | 最新 | `pip --version` |
| 磁盘空间 | > 500 MB | 资源管理器 |
| 内存 | > 4 GB | 任务管理器 |

### 1.2 推荐 Python 版本

- **推荐**: Python 3.11.9 或 3.12.4
- **避免**: Python 3.13+（PySide6 兼容性问题）
- **开发环境**: Python 3.14.2（已验证可用，但非推荐）

---

## 2. 安装步骤

### 2.1 方式一：直接安装（推荐）

1. 克隆或解压项目到本地目录：
   ```bash
   cd C:\Users\YourName\Projects
   # 或解压 zip 文件
   ```

2. 进入项目目录：
   ```bash
   cd plc-monitor-sim
   ```

3. 创建虚拟环境（可选但推荐）：
   ```bash
   python -m venv venv
   venv\Scripts\activate
   ```

4. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

5. 验证安装：
   ```bash
   python -m pytest tests/ -v
   ```
   预期：67 个测试全部通过

### 2.2 方式二：使用 conda

```bash
# 创建环境
conda create -n plc-monitor python=3.11

# 激活环境
conda activate plc-monitor

# 安装依赖
pip install -r requirements.txt

# 验证
python -m pytest tests/ -v
```

### 2.3 方式三：便携部署（无 Python 环境）

如需在没有 Python 环境的机器上运行，可使用 PyInstaller 打包：

```bash
# 安装 PyInstaller
pip install pyinstaller

# 打包模拟器
pyinstaller --onefile --name simulator app/simulator/main.py

# 打包上位机
pyinstaller --onefile --name monitor app/gui/main_window.py
```

> **注意**：PyInstaller 打包需要处理资源文件和路径问题，建议先测试再部署。

---

## 3. 运行系统

### 3.1 开发模式运行

**终端 1 - 启动模拟器**：
```bash
python -m app.simulator.main
```

**终端 2 - 启动上位机**：
```bash
python -m app.gui.main_window
```

### 3.2 演示模式运行

为答辩或演示优化：

1. 提前启动模拟器，让设备运行一段时间
2. 启动上位机，展示实时监控页面
3. 切换到趋势曲线页面展示数据变化
4. 在控制页面注入故障，展示报警系统
5. 在历史查询页面导出 CSV，展示数据持久化

### 3.3 后台运行模拟器

如需模拟器在后台运行（无控制台窗口）：

```bash
pythonw -m app.simulator.main
```

> **注意**：`pythonw` 不显示控制台，适合后台服务。

---

## 4. 配置调整

### 4.1 修改 Modbus 端口

如 5020 端口被占用：

编辑 `app/config/settings.json`：
```json
{
  "modbus": {
    "port": 5021
  }
}
```

### 4.2 调整采集周期

如需更快或更慢的采集：

```json
{
  "acquisition": {
    "period_ms": 1000
  }
}
```

### 4.3 修改报警阈值

```json
{
  "alarms": {
    "temperature": {
      "warning_high": 70.0,
      "alarm_high": 75.0,
      "hysteresis": 3.0
    }
  }
}
```

---

## 5. 答辩/演示准备

### 5.1 演示脚本

**开场（1 分钟）**：
1. 介绍项目背景：工业自动化监控系统仿真
2. 展示系统架构图（双进程、Modbus TCP 通信）
3. 说明技术栈（Python、PySide6、pymodbus、SQLite）

**功能演示（5 分钟）**：
1. 启动模拟器，展示控制台输出
2. 启动上位机，展示实时监控页面
   - 大字体数值显示
   - 状态指示灯（运行/故障/通信）
3. 切换到趋势曲线页面
   - 展示温度、压力、转速曲线
   - 演示显隐控制
4. 在控制页面操作
   - 点击"停止设备"，观察转速下降
   - 点击"启动设备"，观察启动过程
   - 点击"注入故障"，观察报警
5. 切换到报警记录页面
   - 展示活动报警
   - 点击"确认"按钮
6. 切换到历史查询页面
   - 选择时间范围查询
   - 导出 CSV 文件
   - 用 Excel 打开展示

**技术亮点（2 分钟）**：
1. 一阶惯性物理模型（可讲解公式）
2. 报警迟滞机制（避免抖动）
3. 环形缓冲（防止内存泄漏）
4. 67 个单元测试（展示测试通过率）

**收尾（1 分钟）**：
1. 总结项目收获
2. 展示后续规划（V1.1~V1.5）
3. 回答提问

### 5.2 演示注意事项

1. **提前启动**：演示前 5 分钟启动模拟器，让数据积累
2. **双终端**：准备两个终端窗口，分别运行模拟器和上位机
3. **备份计划**：如 GUI 出现问题，使用控制台验证：`python -m app.main`
4. **截图备用**：准备关键页面的截图，防止现场演示出错

### 5.3 常见问题应对

**Q: 为什么使用 Modbus TCP？**
A: Modbus 是工业领域最常用的通信协议，学习价值高。本项目使用 TCP  variant，可在单机上模拟，无需硬件。

**Q: 虚拟设备的物理模型准确吗？**
A: 本模型为简化模型，用于产生具有工业过程特征的仿真数据。一阶惯性模型是工业控制中常用的近似方法。

**Q: 如何保证代码质量？**
A: 项目包含 67 个单元测试，覆盖状态机、物理特征、通信、数据库、报警等核心功能。所有测试均真实运行，不伪造结果。

**Q: 后续有什么规划？**
A: V1.1 计划分离数据库存储线程；V1.2 增加系统事件日志页面；V1.3 支持多设备；V1.4 增加用户权限；V1.5 增加 Web 监控。

---

## 6. GitHub 展示

### 6.1 README 优化

确保 README.md 包含：
- 项目介绍（1-2 句话）
- 功能列表（表格）
- 系统架构图（ASCII 或图片）
- 技术栈（表格）
- 运行方法（代码块）
- 测试方法（代码块）
- 目录结构（树形）
- 截图（如有）

### 6.2 代码规范

- 所有 Python 文件包含模块文档字符串
- 关键函数包含参数和返回说明
- 中文注释（适合国内展示）
- 统一的代码风格（PEP 8）

### 6.3 提交历史

建议的 git 提交历史：
```
feat: Phase 1 - 项目骨架与配置系统
feat: Phase 2 - 虚拟设备模型与 Modbus Server
feat: Phase 3 - Modbus Client 与采集线程
feat: Phase 4 - 数据库设计
feat: Phase 5 - 报警系统
feat: Phase 6 - 实时监控页面
feat: Phase 7 - 趋势曲线页面
feat: Phase 8 - 报警记录页面
feat: Phase 9 - 历史查询与 CSV 导出
feat: Phase 10 - 设备控制页面
docs: Phase 11 - README 与项目文档
test: 完善单元测试（67 个测试）
```

---

## 7. 软件著作权申请

### 7.1 准备材料

1. **源代码**：完整项目代码（去除了 `__pycache__` 和 `.pyc` 文件）
2. **设计文档**：`docs/design.md`
3. **用户手册**：`docs/user_manual.md`
4. **测试报告**：运行 `pytest tests/ -v` 的输出截图
5. **软件说明**：项目功能、技术特点、创新点

### 7.2 代码整理

申请前整理代码：

```bash
# 删除编译文件
find . -type d -name __pycache__ -exec rm -rf {} +
find . -name "*.pyc" -delete

# 删除运行时数据
rm -f data/*.db data/*.csv

# 删除日志
rm -f *.log

# 打包
zip -r plc-monitor-sim-v1.0.zip plc-monitor-sim/ -x "*.git*" "*__pycache__*" "*.pyc"
```

### 7.3 注意事项

1. 代码需包含版权声明（LICENSE 文件）
2. 确保代码可运行（提供 requirements.txt）
3. 文档需与代码版本一致
4. 保留开发历史（git log）

---

## 8. 维护与更新

### 8.1 日常维护

- 定期清理 `data/monitor.db`（防止文件过大）
- 更新依赖版本（`pip list --outdated`）
- 运行测试确保系统完整（`pytest tests/ -v`）

### 8.2 版本发布

发布新版本时：
1. 更新 `app/__init__.py` 中的 `__version__`
2. 更新 `docs/CHANGELOG.md`
3. 更新 `README.md` 中的版本信息
4. 打 git tag：`git tag v1.1.0`
5. 打包发布

---

## 9. 故障快速排查

| 问题 | 快速检查 | 解决 |
|------|----------|------|
| 模拟器启动失败 | `netstat -ano \| findstr 5020` | 更换端口 |
| 上位机闪退 | 检查模拟器是否已启动 | 先启动模拟器 |
| 通信异常 | 检查防火墙设置 | 允许 Python 通过防火墙 |
| 测试失败 | `pip install -r requirements.txt` | 重新安装依赖 |
| 趋势曲线空白 | 检查复选框是否勾选 | 勾选数据类型 |

---

_本指南对应系统版本 V1.0。_
