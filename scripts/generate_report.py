#!/usr/bin/env python3
"""
运营项目部任务进度追踪 — 报表生成脚本

从AI表格读取任务数据，按责任人分组，分析近N天内是否有更新，
生成钉钉友好的Markdown报表（纯文字序号列表，适配手机端）。

用法：
  python scripts/generate_report.py <all_records.json> <period_start> <period_end>

示例：
  python scripts/generate_report.py all_records.json 2026-06-21 2026-06-28
"""

import json
import sys
import re
from datetime import datetime, timedelta
from collections import defaultdict
from itertools import chain

# 责任人userId -> 姓名映射
USERS = {
    "010303275029427647": "王立江",
    "0251316026046228": "朱一鸣",
    "110738513124684735": "张鹏明",
    "17313254725534900": "张翔",
    "24570760827765906": "沈刚",
    "034924166424253600": "张柬柬",
}

USER_ORDER = ["王立江", "朱一鸣", "张鹏明", "张翔", "沈刚", "张柬柬"]


def extract_all_dates(text):
    """从文本中提取所有日期，返回 [(datetime, str), ...] 按日期降序排列"""
    if not text:
        return []

    current_year = datetime.now().year
    found = []

    # 模式1: 6.28 / 6/28 格式
    pattern1 = re.finditer(r'(?:^|[^.])(\d{1,2})[.](\d{1,2})(?=[^.\d]|$)', text)
    for m in pattern1:
        try:
            mon, day = int(m.group(1)), int(m.group(2))
            if 1 <= mon <= 12 and 1 <= day <= 31:
                dt = datetime(current_year, mon, day)
                found.append((dt, f"{mon}.{day}"))
        except ValueError:
            continue

    # 模式2: 6月28日 / 6月28
    pattern2 = re.finditer(r'(\d{1,2})月(\d{1,2})日?', text)
    for m in pattern2:
        try:
            mon, day = int(m.group(1)), int(m.group(2))
            if 1 <= mon <= 12 and 1 <= day <= 31:
                dt = datetime(current_year, mon, day)
                found.append((dt, f"{mon}.{day}"))
        except ValueError:
            continue

    # 去重并按日期降序
    seen = set()
    unique = []
    for dt, s in sorted(found, key=lambda x: x[0], reverse=True):
        key = (dt.month, dt.day)
        if key not in seen:
            seen.add(key)
            unique.append((dt, s))

    return unique


def extract_latest_date(text):
    """从落实情况文本中提取最近的日期"""
    dates = extract_all_dates(text)
    if dates:
        return dates[0]
    return None, ""


def summarize_weekly(text):
    """将落实情况文本简化为摘要（取前2条关键事件）"""
    if not text or not text.strip():
        return ""

    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    events = []
    for line in lines:
        if len(line) > 40:
            line = line[:38] + "…"
        events.append(line)

    return "；".join(events[:2])


def get_risk_marker(status, latest_date, period_start, has_summary):
    """判断风险标记"""
    if status == "未开始":
        return "⚪"

    if not has_summary:
        return "🚨"

    if latest_date is None:
        return "🚨"

    two_weeks_ago = period_start - timedelta(days=14)

    if latest_date >= period_start:
        return "✅"
    elif latest_date >= two_weeks_ago:
        return "🟡"
    else:
        return "🔴"


def build_task_line(idx, task_name, status, summary, latest_str, marker):
    """构建单条任务描述"""
    # 截取任务名
    name_display = task_name
    if len(name_display) > 50:
        name_display = name_display[:48] + "…"

    # 构建概况
    parts = []
    if not summary:
        parts.append("未记录工作开展情况")
    else:
        if latest_str:
            summary += f"（最近：{latest_str}）"
        parts.append(summary)

    # 如果概况太长
    desc = "；".join(parts)
    if len(desc) > 80:
        desc = desc[:78] + "…"

    return f"{idx}. **{name_display}**（{status}）— {desc} {marker}"


def build_summary_line(risk_map):
    """构建风险统计行"""
    categories = [
        ("✅", "正常推进"),
        ("🟡", "需关注"),
        ("🔴", "需重点跟进"),
        ("🚨", "无记录"),
        ("⚪", "未启动"),
    ]

    parts = []
    for key, label in categories:
        items = risk_map.get(key, [])
        if items:
            parts.append(f"**{label}（{len(items)}项）**")

    return " | ".join(parts)


def main():
    if len(sys.argv) < 4:
        print("用法: python generate_report.py <records.json> <period_start> <period_end>", file=sys.stderr)
        sys.exit(1)

    records_file = sys.argv[1]
    period_start_str = sys.argv[2]
    period_end_str = sys.argv[3]

    with open(records_file, "r", encoding="utf-8-sig") as f:
        raw = json.load(f)

    records = raw.get("records", [])
    if not records:
        records = raw.get("data", {}).get("records", [])

    period_start = datetime.strptime(period_start_str, "%Y-%m-%d")

    # 按责任人分析
    tasks = defaultdict(list)
    for rec in records:
        cells = rec.get("cells", {})
        task_name = (cells.get("GIUguy6") or "").strip()
        if not task_name:
            continue

        status_cell = cells.get("CA1vMY7") or {}
        status = status_cell.get("name", "") if isinstance(status_cell, dict) else ""

        person_cell = cells.get("ojHKFAE") or []
        uid = person_cell[0]["userId"] if isinstance(person_cell, list) and person_cell else "未知"
        name = USERS.get(uid, uid)

        weekly_text = cells.get("BqwY0AR") or ""
        latest_date, latest_str = extract_latest_date(weekly_text)
        summary = summarize_weekly(weekly_text)

        tasks[name].append({
            "task": task_name,
            "status": status,
            "summary": summary,
            "latest_date": latest_date,
            "latest_str": latest_str,
            "has_summary": bool(summary),
        })

    # 输出统计到stderr
    for name in USER_ORDER:
        if name in tasks:
            total = len(tasks[name])
            unfin = sum(1 for i in tasks[name] if i["status"] != "已完成")
            print(f"{name}: total={total} unfinished={unfin}", file=sys.stderr)

    # 生成Markdown（纯文字序号列表，无表格）
    lines = []
    lines.append("# 运营项目部任务进度追踪 — 未完成任务跟踪报表\n")
    lines.append(f"**统计周期：** {period_start_str} ~ {period_end_str} | **生成日期：** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**数据源：** 运营项目部任务管理系统（{len(records)}条记录）\n")
    lines.append("---")

    risk_map = {}

    for name in USER_ORDER:
        if name not in tasks:
            continue
        items = tasks[name]
        done = [i for i in items if i["status"] == "已完成"]
        unfinished = [i for i in items if i["status"] != "已完成"]

        if not unfinished:
            continue

        lines.append(f"\n## 📋 {name} — 未完成{len(unfinished)}项 / 已完{len(done)}项\n")

        for idx, item in enumerate(unfinished, 1):
            marker = get_risk_marker(item["status"], item["latest_date"], period_start, item["has_summary"])
            line = build_task_line(idx, item["task"], item["status"], item["summary"], item["latest_str"], marker)
            lines.append(line)

        risk_map.setdefault(marker, []).append(f"{item['task'][:30]}…" if len(item['task']) > 30 else item['task'])

    # 任务总览
    lines.append("\n---\n")
    lines.append("## 📋 任务总览\n")
    lines.append("| 状态 | 数量 | 说明 |")
    lines.append("|------|------|------|")

    # 按责任人统计各风险等级的数量
    person_risk_count = defaultdict(lambda: defaultdict(int))
    for name in USER_ORDER:
        if name not in tasks:
            continue
        items = tasks[name]
        unfinished = [i for i in items if i["status"] != "已完成"]
        for item in unfinished:
            marker = get_risk_marker(item["status"], item["latest_date"], period_start, item["has_summary"])
            person_risk_count[marker][name] += 1
            risk_map.setdefault(marker, []).append(name)

    categories = [
        ("✅", "正常推进"),
        ("🟡", "需关注"),
        ("🔴", "需重点跟进"),
        ("🚨", "无记录"),
        ("⚪", "未启动"),
    ]

    for key, label in categories:
        person_counts = person_risk_count.get(key, {})
        if not person_counts:
            continue
        total_count = sum(person_counts.values())
        detail = "、".join([f"{n}×{c}" for n, c in sorted(person_counts.items(), key=lambda x: -x[1])])
        lines.append(f"| {key} {label} | {total_count}项 | {detail} |")

    lines.append("")
    lines.append("---")
    lines.append(f"> 📌 统计周期 {period_start_str} ~ {period_end_str}")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
