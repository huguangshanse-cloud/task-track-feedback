#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运营项目部任务进度追踪 - 报表生成脚本

从AI表格读取任务数据，按责任人分组，分析近N天内是否有更新，
生成纯文字序号列表形式的Markdown报表（适配手机端）。

用法:
  python scripts/generate_report.py <records.json> <period_start> <period_end>

示例:
  python scripts/generate_report.py all_records.json 2026-06-21 2026-06-28
"""

import json
import sys
import re
from datetime import datetime, timedelta
from collections import defaultdict

# 修复 Windows 控制台编码问题
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

USERS = {
    "010303275029427647": "王立江",
    "0251316026046228": "朱一鸣",
    "110738513124684735": "张鹏明",
    "17313254725534900": "张翔",
    "24570760827765906": "沈刚",
    "034924166424253600": "张柬柬",
}

USER_ORDER = ["王立江", "朱一鸣", "张鹏明", "张翔", "沈刚", "张柬柬"]

EMOJI_CHECK = "\u2705"
EMOJI_WARN = "\U0001f7e1"
EMOJI_CRIT = "\U0001f534"
EMOJI_NONE = "\U0001f6a8"
EMOJI_IDLE = "\u26aa"


def extract_latest_date(text):
    """从落实情况文本中提取最近日期"""
    if not text:
        return None, ""
    y = datetime.now().year
    found = []
    for m in re.finditer(r"(?:^|[^.])(\d{1,2})[.](\d{1,2})(?=[^.\d]|$)", text):
        try:
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                found.append((datetime(y, mo, d), f"{mo}.{d}"))
        except ValueError:
            pass
    for m in re.finditer(r"(\d{1,2})\u6708(\d{1,2})\u65e5?", text):
        try:
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                found.append((datetime(y, mo, d), f"{mo}.{d}"))
        except ValueError:
            pass
    seen = set()
    for dt, s in sorted(found, key=lambda x: x[0], reverse=True):
        k = (dt.month, dt.day)
        if k not in seen:
            seen.add(k)
            return dt, s
    return None, ""


def summarize(text):
    """简化落实情况文本为摘要"""
    if not text or not text.strip():
        return ""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    events = [l[:35] + "\u2026" if len(l) > 35 else l for l in lines]
    return "\uff1b".join(events[:2])


def get_risk(status, latest_date, period_start, has_summary):
    """判断风险等级"""
    if status == "\u672a\u5f00\u59cb":
        return EMOJI_IDLE
    if not has_summary or latest_date is None:
        return EMOJI_NONE
    if latest_date >= period_start:
        return EMOJI_CHECK
    elif latest_date >= period_start - timedelta(days=14):
        return EMOJI_WARN
    else:
        return EMOJI_CRIT


def main():
    if len(sys.argv) < 4:
        print("usage: script <records.json> <period_start> <period_end>", file=sys.stderr)
        sys.exit(1)

    with open(sys.argv[1], "r", encoding="utf-8-sig") as f:
        raw = json.load(f)

    records = raw.get("records", [])
    if not records:
        records = raw.get("data", {}).get("records", [])

    ps = datetime.strptime(sys.argv[2], "%Y-%m-%d")
    pe = sys.argv[3]

    tasks = defaultdict(list)
    for rec in records:
        cells = rec.get("cells", {})
        tn = (cells.get("GIUguy6") or "").strip()
        if not tn:
            continue
        sc = cells.get("CA1vMY7") or {}
        st = sc.get("name", "") if isinstance(sc, dict) else ""
        pc = cells.get("ojHKFAE") or []
        uid = pc[0]["userId"] if isinstance(pc, list) and pc else "\u672a\u77e5"
        name = USERS.get(uid, uid)
        wt = cells.get("BqwY0AR") or ""
        ld, ls = extract_latest_date(wt)
        tasks[name].append({
            "task": tn,
            "status": st,
            "summary": summarize(wt),
            "latest_date": ld,
            "latest_str": ls,
            "has_summary": bool(summarize(wt)),
        })

    # stderr 输出统计
    for n in USER_ORDER:
        if n in tasks:
            t = len(tasks[n])
            u = sum(1 for i in tasks[n] if i["status"] != "\u5df2\u5b8c\u6210")
            print(f"{n}: total={t} unfin={u}", file=sys.stderr)

    # 生成 Markdown
    lines = [
        "# 运营项目部任务进度追踪 - 未完成任务跟踪报表",
        "",
        f"**统计周期:** {sys.argv[2]} ~ {pe} | **生成日期:** {datetime.now().strftime('%Y-%m-%d')}",
        f"**数据源:** 运营项目部任务管理系统({len(records)}条记录)",
        "",
        "---",
    ]

    risk_person = defaultdict(lambda: defaultdict(int))

    for name in USER_ORDER:
        if name not in tasks:
            continue
        items = tasks[name]
        done = [i for i in items if i["status"] == "\u5df2\u5b8c\u6210"]
        unfin = [i for i in items if i["status"] != "\u5df2\u5b8c\u6210"]
        if not unfin:
            continue

        lines.append("")
        lines.append(f"## {name} - 未完成{len(unfin)}项 / 已完{len(done)}项")
        lines.append("")

        for idx, item in enumerate(unfin, 1):
            m = get_risk(item["status"], item["latest_date"], ps, item["has_summary"])
            risk_person[m][name] += 1

            tname = item["task"][:40] + "\u2026" if len(item["task"]) > 40 else item["task"]
            if not item["has_summary"]:
                desc = "\u672a\u8bb0\u5f55\u5de5\u4f5c\u5f00\u5c55\u60c5\u51b5"
            else:
                desc = item["summary"]
                if item["latest_str"]:
                    desc += f"(\u6700\u8fd1:{item['latest_str']})"
            if len(desc) > 80:
                desc = desc[:78] + "\u2026"

            lines.append(f"{idx}. **{tname}**({item['status']}) - {desc} {m}")

    # 任务总览
    lines.extend(["", "---", "", "## 任务总览", ""])

    cats = [
        (EMOJI_CHECK, "\u6b63\u5e38\u63a8\u8fdb"),
        (EMOJI_WARN, "\u9700\u5173\u6ce8"),
        (EMOJI_CRIT, "\u9700\u91cd\u70b9\u8ddf\u8fdb"),
        (EMOJI_NONE, "\u65e0\u8bb0\u5f55"),
        (EMOJI_IDLE, "\u672a\u542f\u52a8"),
    ]

    for emoji, label in cats:
        pc = risk_person.get(emoji, {})
        if not pc:
            continue
        total = sum(pc.values())
        detail = "\u3001".join([f"{n}\u00d7{c}" for n, c in sorted(pc.items(), key=lambda x: -x[1])])
        lines.append(f"| {emoji} {label} | {total}\u9879 | {detail} |")

    lines.extend(["", "---", f"> \u7edf\u8ba1\u5468\u671f {sys.argv[2]} ~ {pe}"])

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


if __name__ == "__main__":
    main()
