# 运营项目部任务进度追踪 - 每周自动推送脚本

param()

$DWS = "C:\Users\shen.gang\.local\bin\dws.exe"
$PYTHON = "python"
$REPORT_SCRIPT = "C:\Users\shen.gang\.codex\skills\task-track-feedback\scripts\generate_report.py"
$DATA_FILE = "D:\Claw\SNS\records_latest.json"

$PeriodEnd = Get-Date -Format "yyyy-MM-dd"
$PeriodStart = (Get-Date).AddDays(-7).ToString("yyyy-MM-dd")

Write-Host "统计周期: $PeriodStart ~ $PeriodEnd"

try {
    # Step 1: 读取AI表格
    Write-Host "正在读取AI表格数据..."
    $records = & $DWS aitable record query --base-id 14lgGw3P8vLpM1ZbSQ44ZXx1V5daZ90D --table-id pqp1USn --all --format json 2>$null
    if (-not $records) {
        throw "读取AI表格失败(返回为空)"
    }
    $records | Set-Content -Path $DATA_FILE -Encoding UTF8 -NoNewline
    Write-Host "AI表格数据已保存 ($((Get-Item $DATA_FILE).Length) bytes)"

    # Step 2: 生成报表
    Write-Host "正在生成报表..."
    $md = (& $PYTHON $REPORT_SCRIPT $DATA_FILE.Replace('\','/') $PeriodStart $PeriodEnd 2>$null) -join "`n"
    if (-not $md -or $md.Length -lt 50) {
        throw "生成报表失败(内容过短)"
    }
    Write-Host "报表已生成 ($($md.Length) 字符)"

    # Step 3: 发送到群
    Write-Host "正在发送到群: 运营项目部工作群..."
    $result = & $DWS chat message send --group "cidnnV0AnEXEkDJIO+gSCPS0A==" --title "运营项目部任务进度追踪($PeriodStart~$PeriodEnd)" --text $md --format json 2>$null
    Write-Host "发送结果: $result"
} catch {
    Write-Error "执行失败: $_"
    exit 1
}

Write-Host "完成！"
