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


def extract_latest_date(text):
    """从落实情况文本中提取最近的日期"""
    if not text:
        return None, ""

    current_year = datetime.now().year
    latest_date = None
    latest_str = ""

    # 匹配常见日期格式如 6.28, 6/28
    for match in re.finditer(r'(?<!\d)(\d{1,2})[.](\d{1,2})(?!\d)', text):
        try:
            m, d = int(match.group(1)), int(match.group(2))
            if 1 <= m <= 12 and 1 <= d <= 31:
                dt = datetime(current_year, m, d)
                if latest_date is None or dt > latest_date:
                    latest_date = dt
                    latest_str = f"{m}.{d}"
        except ValueError:
            continue

    # 匹配 6月28日 格式
    for match in re.finditer(r'(\d{1,2})月(\d{1,2})日', text):
        try:
            m, d = int(match.group(1)), int(match.group(2))
            if 1 <= m <= 12 and 1 <= d <= 31:
                dt = datetime(current_year, m, d)
                if latest_date is None or dt > latest_date:
                    latest_date = dt
                    latest_str = f"{m}.{d}"
        except ValueError:
            continue

    return latest_date, latest_str


def summarize_weekly(text):
    """将落实情况文本简化为摘要"""
    if not text or not text.strip():
        return ""

    lines = text.strip().split("\n")
    events = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        if len(line) > 60:
            line = line[:58] + "…"
        events.append(line)

    if not events:
        return ""

    return "；".join(events[:4])


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

    print(f"共读取 {len(records)} 条记录", file=sys.stderr)

    period_start = datetime.strptime(period_start_str, "%Y-%m-%d")
    period_end = datetime.strptime(period_end_str, "%Y-%m-%d")

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

    for name in USER_ORDER:
        if name in tasks:
            total = len(tasks[name])
            unfin = sum(1 for i in tasks[name] if i["status"] != "已完成")
            print(f"  {name}: 共{total}项, 未完成{unfin}项", file=sys.stderr)

    # 生成Markdown
    lines = []
    lines.append("# 运营项目部任务进度追踪 — 未完成任务跟踪报表\n")
    lines.append(f"**统计周期：** {period_start_str} ~ {period_end_str}")
    lines.append(f"**生成日期：** {datetime.now().strftime('%Y-%m-%d')}")
    lines.append(f"**数据源：** 运营项目部任务管理系统\n")
    lines.append("---")

    risk_map = {}

    for name in USER_ORDER:
        if name not in tasks:
            continue
        items = tasks[name]
        dept = USER_DEPT.get(name, "")
        unfinished = [i for i in items if i["status"] != "已完成"]

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

            # 标记文字
            marker_label = marker
            if marker == "⚪":
                marker_label = "⚪"
            elif marker == "🚨":
                marker_label = "🚨"
            elif marker == "🟡":
                marker_label = "🟡"
            elif marker == "🔴":
                marker_label = "🔴"
            elif marker == "✅":
                marker_label = "✅"

            lines.append(f"| {task_short} | {status} | {status_text} | {marker_label} |")

            risk_map.setdefault(marker, []).append(f"{item['task']} — {name}")

    # 整体风险总览
    lines.append("\n---\n")
    lines.append("## 📊 整体风险总览\n")

    markers_desc = {
        "✅": "近7天有更新（正常推进）",
        "🟡": "近14天无更新（需关注）",
        "🔴": "超14天无更新（需重点跟进）",
        "🚨": "无任何工作开展记录",
        "⚪": "未启动",
    }

    for m in ["✅", "🟡", "🔴", "🚨", "⚪"]:
        items = risk_map.get(m, [])
        if items:
            lines.append(f"**{markers_desc[m]}：**")
            for i in items[:8]:
                lines.append(f"- {i}")
            if len(items) > 8:
                lines.append(f"- … 共{len(items)}项")
            lines.append("")

    lines.append("---")
    lines.append(f"> 📌 统计周期 {period_start_str} ~ {period_end_str}")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
