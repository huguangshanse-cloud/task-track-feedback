#!/usr/bin/env python3
"""
运营项目部任务进度追踪 — 报表生成脚本

从AI表格读取任务数据，按责任人分组，分析近N天内是否有更新，
生成钉钉友好的Markdown报表。

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

USER_DEPT = {
    "王立江": "项目部",
    "朱一鸣": "营运部",
    "张鹏明": "营运部",
    "张翔": "项目部",
    "沈刚": "营运部",
    "张柬柬": "营运部",
}


def extract_all_dates(text):
    """从文本中提取所有日期，返回 [(datetime, str), ...] 按日期降序排列"""
    if not text:
        return []

    current_year = datetime.now().year
    found = []

    # 模式1: 6.28 / 6/28 格式（注意不能匹配版本号如 5.16 中的纯数字）
    # 要求前面是空白或中文标点，后面是中文/空白/标点
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
        return dates[0]  # (datetime, str)
    return None, ""


def summarize_weekly(text):
    """将落实情况文本简化为摘要（取前3条关键事件）"""
    if not text or not text.strip():
        return ""

    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]
    events = []
    for line in lines:
        if len(line) > 50:
            line = line[:48] + "…"
        events.append(line)

    return "；".join(events[:3])


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

    # 生成Markdown
    lines = []
    lines.append("# 运营项目部任务进度追踪 — 未完成任务跟踪报表\n")
    lines.append(f"**统计周期：** {period_start_str} ~ {period_end_str}")
    lines.append(f"**生成日期：** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**数据源：** 运营项目部任务管理系统（自动获取，{len(records)}条记录）\n")
    lines.append("---")

    risk_map = {}
    all_done_tasks = defaultdict(list)  # 记录已完成任务以便备注

    for name in USER_ORDER:
        if name not in tasks:
            continue
        items = tasks[name]
        dept = USER_DEPT.get(name, "")
        done = [i for i in items if i["status"] == "已完成"]
        unfinished = [i for i in items if i["status"] != "已完成"]

        if done:
            all_done_tasks[name] = done

        if not unfinished:
            continue

        lines.append(f"\n## 📋 {name}（{dept}）— 未完成{len(unfinished)}项\n")
        lines.append("| 任务 | 状态 | 开展情况 | 标记 |")
        lines.append("|------|------|----------|------|")

        for item in unfinished:
            task_short = item["task"]
            if len(task_short) > 28:
                task_short = task_short[:26] + "…"

            status = item["status"]
            marker = get_risk_marker(status, item["latest_date"], period_start, item["has_summary"])

            if not item["has_summary"]:
                status_text = "未记录工作开展情况"
            else:
                status_text = item["summary"]
                if item["latest_str"]:
                    status_text += f"（最近：{item['latest_str']}）"

            if len(status_text) > 78:
                status_text = status_text[:76] + "…"

            lines.append(f"| {task_short} | {status} | {status_text} | {marker} |")
            risk_map.setdefault(marker, []).append(f"{item['task'][:40]}…" if len(item['task']) > 40 else item['task'])

        # 备注已完成任务
        if done:
            done_names = "、".join([d['task'][:20] + "…" if len(d['task']) > 20 else d['task'] for d in done])
            lines.append(f"\n> ✅ **已完成无需跟踪：** {done_names}")

    # 整体风险总览
    lines.append("\n\n---\n")
    lines.append("## 📊 整体风险总览\n")

    categories = [
        ("✅", "近7天有更新（正常推进）"),
        ("🟡", "近14天无更新（需关注）"),
        ("🔴", "超14天无更新（需重点跟进）"),
        ("🚨", "无任何工作开展记录"),
        ("⚪", "未启动"),
    ]

    for key, desc in categories:
        items = risk_map.get(key, [])
        if items:
            lines.append(f"**{desc}：{len(items)}项**")
            # 按责任人分组展示
            for i in items[:6]:
                lines.append(f"- {i}")
            if len(items) > 6:
                lines.append(f"- … 共{len(items)}项")
            lines.append("")

    lines.append("---")
    lines.append(f"> 📌 统计周期 {period_start_str} ~ {period_end_str} | 数据来源：运营项目部任务管理系统")

    print("\n".join(lines))


if __name__ == "__main__":
    main()
