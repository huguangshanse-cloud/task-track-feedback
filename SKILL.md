---
name: task-track-feedback
description: >
  运营项目部任务进度追踪报表。当用户说"跟踪反馈运营项目部任务"时触发。
  然后自动从AI表格读取数据，按责任人分组分析，生成带风险标记的Markdown报表。
---

# 运营项目部任务进度追踪报表

## 触发方式

用户通过以下关键词激活此 Skill：
- "跟踪反馈运营项目部任务"
- "运营项目部任务跟踪"
- "任务进度反馈"

## 前置交互流程

在执行任何操作前，必须先向用户确认以下两项信息：

1. **任务跟踪周期**：询问用户"请确认本次任务跟踪的起止日期（格式：2026-06-21 ~ 2026-06-28）"
2. **目标接收人**：询问用户"请确认要发送到哪个群或个人"
   - 如果用户说"发给沈刚"，使用沈刚的 openDingTalkId 发单聊
   - 如果用户说"发到运营项目部工作群"等群名，搜索群并发送

## AI表格信息

- Base名称：运营项目部任务管理系统
- Base ID：14lgGw3P8vLpM1ZbSQ44ZXx1V5daZ90D
- 数据表名称：运营项目部任务进度追踪
- 数据表 ID：pqp1USn
- 视图名称：运营项目部任务跟进（Grid视图）

### 关键字段

| 字段名 | Field ID | 类型 | 说明 |
|--------|----------|------|------|
| 任务名称 | GIUguy6 | text | 任务标题 |
| 负责人 | ojHKFAE | user | 责任人userId列表 |
| 任务状态 | CA1vMY7 | singleSelect | 进行中/已完成/未开始 |
| 每周落实情况 | BqwY0AR | text | 关键字段，记录分期进展 |
| 进度百分比 | F2FhWoA | progress | 0~1的数值 |
| 开始日期 | itCO3fh | date | 任务开始时间 |
| 下周计划 | EPR65cN | text | 下一步计划 |
| 任务等级 | YxAU416 | singleSelect | 中心级/部门级/岗位级 |
| 时效要求 | CCS5ZTq | singleSelect | 月度完成/周完成 |

### userId -> 姓名映射

| userId | 姓名 |
|--------|------|
| 010303275029427647 | 王立江 |
| 0251316026046228 | 朱一鸣 |
| 110738513124684735 | 张明 |
| 17313254725534900 | 张翔 |
| 24570760827765906 | 沈刚 |
| 034924166424253600 | 张柬柬 |

### 已知群/人ID

- 运营项目部工作群 openConversationId：`cidnnV0AnEXEkDJIO+gSCPS0A==`
- 沈刚 openDingTalkId：`DZhciP1lCFRVL4mHSAFlmzyQiEiE`

## 核心流程

### Step 1：获取用户确认

先与用户确认两件事：
1. 跟踪周期（起止日期）
2. 目标接收人（群或个人）

### Step 2：读取AI表格数据

使用 Python subprocess 调用 dws，不要用 PowerShell 管道：

```python
import subprocess, json

result = subprocess.run(
    ['dws', 'aitable', 'record', 'query',
     '--base-id', '14lgGw3P8vLpM1ZbSQ44ZXx1V5daZ90D',
     '--table-id', 'pqp1USn',
     '--format', 'json'],
    capture_output=True, text=True, timeout=30
)
data = json.loads(result.stdout)
records = data['data']['records']  # 注意结构为 data.records
```

> 注意：该AI表格返回结构为 `data.records`，不是顶层 `records`。

### Step 3：生成报表

```python
result = subprocess.run(
    ['python', 'scripts/generate_report.py',
     'records_latest.json', '2026-07-01', '2026-07-08'],
    capture_output=True, text=True, timeout=30
)
report_md = result.stdout
```

脚本自动完成：
- 按责任人分组统计（已完成/未完成）
- 从"每周落实情况"提取最近更新日期
- 风险等级判定

### Step 4：发送到钉钉

重要：--text 必须通过 Python subprocess 传递，不能通过 PowerShell 变量或管道。

```python
# 发送给群
result = subprocess.run(
    ['dws', 'chat', 'message', 'send',
     '--group', 'cidnnV0AnEXEkDJIO+gSCPS0A==',
     '--title', '运营项目部任务进度追踪(2026-07-01~2026-07-08)',
     '--text', report_md,
     '--format', 'json'],
    capture_output=True, text=True, timeout=30
)
```

```python
# 发送给个人（沈刚）
result = subprocess.run(
    ['dws', 'chat', 'message', 'send',
     '--open-dingtalk-id', 'DZhciP1lCFRVL4mHSAFlmzyQiEiE',
     '--title', '运营项目部任务进度追踪(2026-07-01~2026-07-08)',
     '--text', report_md,
     '--format', 'json'],
    capture_output=True, text=True, timeout=30
)
```

### Step 5：搜索群

```python
result = subprocess.run(
    ['dws', 'chat', 'search',
     '--query', '运营项目部工作群',
     '--format', 'json'],
    capture_output=True, text=True, timeout=30
)
groups = json.loads(result.stdout)['result']['groups']
group_id = groups[0]['openConversationId']
```

### Step 6：通知用户完成

告知用户报表已发送，附带摘要：总任务数、各责任人未完成/已完成数、风险项分布。

## 报表格式模板

报表为纯文字序号列表形式（不用表格），确保手机端正常显示：

```
# 运营项目部任务进度追踪 - 未完成任务跟踪报表

**统计周期:** 2026-07-01 ~ 2026-07-08 | **生成日期:** 2026-07-08
**数据源:** 运营项目部任务管理系统(59条记录)

---

## 王立江 - 未完成7项 / 已完3项

1. **任务名称**(进行中) - 落实摘要描述 [关注]
2. **任务名称**(未开始) - 落实摘要描述 [未启动]
...

---

## 任务总览

**[OK] 正常推进(4项)** - 张明x4
**[关注] 需关注(8项)** - 张翔x3、朱一鸣x2...
**[重点] 需重点跟进(7项)** - 张柬柬x4...
**[无记录] 无记录(8项)** - 王立江x4...
**[未启动] 未启动(5项)** - 朱一鸣x2...

---
> 统计周期 2026-07-01 ~ 2026-07-08
```

## 风险判定规则

| 风险等级 | 判定条件 | 文本标记 |
|----------|----------|----------|
| 正常推进 | period_start 内（近7天）有更新 | [OK] |
| 需关注 | period_start-14天 内有更新 | [关注] |
| 需重点跟进 | 超过14天无更新 | [重点] |
| 无记录 | 落实情况字段为空/无内容 | [无记录] |
| 未启动 | 状态为"未开始" | [未启动] |

> 注意：emoji(✅🟡🔴🚨⚪📋) 会被钉钉 MCP 网关拦截，必须替换为纯文本标记。

## 已知问题与规避

1. PowerShell 管道截断：dws --text 参数在 PowerShell 中通过管道或变量传递时会被空格拆分，必须使用 Python subprocess.run() 直接传递完整字符串。
2. emoji 拦截：钉钉 MCP 网关拒绝包含 emoji 的请求（返回 content contains dangerous Unicode characters），所有 emoji 必须替换为 ASCII 文本标记。
3. 网络断连：MCP 网关偶发 connection forcibly closed by remote host，重试2-3次后可恢复。

## 自动化定时任务

每周自动生成并推送的脚本：

- scripts/task_track_weekly.ps1 - PowerShell 脚本，读取AI表格->生成报表->发到群
- scripts/task_track_weekly.bat - 计划任务入口

定时任务通过 Windows 计划任务执行，每周一上午9点运行 .bat 文件。

## 文件结构

```
task-track-feedback/
├── SKILL.md                          # 本文件
├── agents/
│   └── openai.yaml                   # Agent 元数据
└── scripts/
    ├── generate_report.py            # 报表生成脚本（核心）
    ├── task_track_weekly.ps1         # 周度自动推送脚本
    └── task_track_weekly.bat         # 计划任务入口
```