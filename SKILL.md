---
name: task-track-feedback
description: 运营项目部任务进度追踪报表。当用户说"跟踪反馈运营项目部任务"时触发。执行流程：先与用户确认任务跟踪的起止日期（某年某月某日至某年某月某日），再确认要发送的目标钉钉群名称。然后自动从AI表格"运营项目部任务管理系统"读取数据，按责任人分组分析，生成带风险标记的Markdown报表，推送到指定钉钉群。
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
2. **目标钉钉群**：询问用户"请确认要发送到的钉钉群名称"

获取确认后才进行后续操作。

## AI表格信息

- Base名称：运营项目部任务管理系统
- Base ID：14lgGw3P8vLpM1ZbSQ44ZXx1V5daZ90D
- 数据表名称：运营项目部任务进度追踪
- 数据表 ID：pqp1USn
- 视图名称：运营项目部任务跟进（Grid视图）

### 关键字段

| 字段名 | Field ID | 类型 | 说明 |
|-------|---------|------|------|
| 任务名称 | GIUguy6 | text | 任务标题 |
| 负责人 | ojHKFAE | user | 责任人userId列表 |
| 任务状态 | CA1vMY7 | singleSelect | 进行中/已完成/未开始 |
| 每周落实情况 | BqwY0AR | text | 关键字段，记录分期进展 |
| 下周计划 | EPR65cN | text | 下一步计划 |
| 进度百分比 | F2FhWoA | progress | 0~1的数值 |
| 开始日期 | itCO3fh | date | 任务开始时间 |
| 任务等级 | YxAU416 | singleSelect | 中心级/部门级/岗位级 |
| 时效要求 | CCS5ZTq | singleSelect | 月度完成/周完成 |

### 负责人userId映射

| userId | 姓名 | 部门 |
|--------|------|------|
| 010303275029427647 | 王立江 | 项目部 |
| 0251316026046228 | 朱一鸣 | 营运部 |
| 110738513124684735 | 张鹏明 | 营运部 |
| 17313254725534900 | 张翔 | 项目部 |
| 24570760827765906 | 沈刚 | 营运部 |
| 034924166424253600 | 张柬柬 | 营运部 |

## 核心流程

### Step 1：获取用户确认

先与用户确认两件事：
1. 跟踪周期（起止日期）
2. 目标钉钉群

### Step 2：读取AI表格数据

```bash
# 拉取全部记录
dws aitable record query --base-id 14lgGw3P8vLpM1ZbSQ44ZXx1V5daZ90D --table-id pqp1USn --all --format json
```

将输出保存到临时JSON文件供脚本分析。

### Step 3：生成报表

使用脚本生成Markdown报表：

```bash
python scripts/generate_report.py <records.json> <period_start> <period_end>
```

脚本会自动：
- 按责任人分组
- 从"每周落实情况"字段提取各任务最新更新日期
- 判断风险等级（近7天有更新✅ / 近14天无更新🟡 / 超14天无更新🔴 / 无记录🚨 / 未启动⚪）
- 生成钉钉群友好的Markdown格式

### Step 4：搜索目标群并发送

```bash
# 搜索群
dws chat search --query "<群名关键词>" --format json

# 发送Markdown消息到群
dws chat message send --group <openConversationId> --title "运营项目部任务进度追踪报表" --text "<markdown内容>"
```

### Step 5：通知用户

告知用户报表已发送到指定钉钉群，并附上简要统计摘要（如总任务数、风险项等）。

## 资源

### scripts/generate_report.py
报表生成脚本。读取JSON格式的AI表格记录，分析各任务的最新更新日期，按责任人分组生成带风险标记的Markdown报表。
