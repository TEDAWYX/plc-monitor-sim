# 项目运行截图说明

## 如何获取截图

### 1. 启动系统

**终端1 - 启动模拟器：**
```bash
cd C:\Users\barye\WorkBuddy\20260908202900\plc-monitor-sim
python -m app.simulator.main
```

等待看到：
```
[Modbus Server] 已启动于 127.0.0.1:5020 (slave_id=1)
>>> [自动演示] 启动设备
```

**终端2 - 启动上位机：**
```bash
cd C:\Users\barye\WorkBuddy\20260908202900\plc-monitor-sim
python -m app.gui.main_window
```

### 2. 操作并截图

#### monitor.png - 实时监控页面
1. 等待上位机启动后，默认显示"实时监控"页面
2. 观察数值显示（温度、压力、转速、电流、电压）
3. 观察右侧状态灯（绿色=通信正常，设备运行中）
4. 按 PrtScn 或 Win+Shift+S 截图，保存为 `monitor.png`

#### trend.png - 趋势曲线页面
1. 点击顶部"趋势曲线"标签页
2. 等待曲线开始绘制（约10秒）
3. 观察温度、压力、转速三条曲线
4. 截图保存为 `trend.png`

#### control.png - 设备控制页面
1. 点击顶部"设备控制"标签页
2. 可以看到启动/停止按钮、转速设定滑块、故障注入按钮
3. 截图保存为 `control.png`

#### alarm.png - 报警记录页面
1. 先在"设备控制"页点击"注入故障"按钮
2. 等待约5秒
3. 点击顶部"报警记录"标签页
4. 观察活动报警列表（应该有过温报警）
5. 截图保存为 `alarm.png`

#### history.png - 历史查询页面
1. 点击顶部"历史查询"标签页
2. 选择时间范围（默认显示最近1小时）
3. 点击"查询"按钮
4. 观察数据表格和"导出CSV"按钮
5. 截图保存为 `history.png`

### 3. 截图要求

- 分辨率：至少 1280x720
- 格式：PNG
- 文件大小：每张控制在 500KB 以内
- 确保界面清晰、字体可读

### 4. 快速截图脚本（可选）

如果需要批量截图，可以使用以下PowerShell脚本：

```powershell
# 需要手动切换页面，每次按任意键截图
$i = 1
$names = @("monitor", "trend", "control", "alarm", "history")
foreach ($name in $names) {
    Write-Host "请切换到 $name 页面，然后按任意键截图..."
    $null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
    Add-Type -AssemblyName System.Windows.Forms
    $screenshot = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds
    $bitmap = New-Object System.Drawing.Bitmap($screenshot.Width, $screenshot.Height)
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $graphics.CopyFromScreen($screenshot.Location, [System.Drawing.Point]::Empty, $screenshot.Size)
    $path = "C:\Users\barye\WorkBuddy\20260908202900\plc-monitor-sim\screenshots\$name.png"
    $bitmap.Save($path, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Host "已保存: $path"
}
```

## 截图用途

- GitHub README 展示
- 简历附件
- 软件著作权申请材料
- 面试时演示说明
