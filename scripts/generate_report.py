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
    "110738513124684735": "张明",
    "17313254725534900": "张翔",
    "24570760827765906": "沈刚",
    "034924166424253600": "张柬柬",
}

USER_ORDER = ["王立江", "朱一鸣", "张明", "张翔", "沈刚", "张柬柬"]

# 使用纯文本标记代替 emoji（钉钉 MCP 网关会拦截 emoji）
TAG_OK = "[OK]"
TAG_WARN = "[关注]"
TAG_CRIT = "[重点]"
TAG_NONE = "[无记录]"
TAG_IDLE = "[未启动]"


def extract_latest_date(text):
    """从落实情况文本中提取最近日期"""
    if not text:
        return None, ""
    y = datetime.now().year
    found = []
    # 匹配 "6.30" 格式的日期
    for m in re.finditer(r"(?:^|[^.])(\d{1,2})[.](\d{1,2})(?=[^.\d]|$)", text):
        try:
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                found.append((datetime(y, mo, d), f"{mo}.{d}"))
        except ValueError:
            pass
    # 匹配 "6月30日" 格式
    for m in re.finditer(r"(\d{1,2})\u6708(\d{1,2})\u65e5?", text):
        try:
            mo, d = int(m.group(1)), int(m.group(2))
            if 1 <= mo <= 12 and 1 <= d <= 31:
                found.append((datetime(y, mo, d), f"{mo}.{d}"))
        except ValueError:
            pass
    # 去重（同月同日只保留一次）
    seen = set()
    for dt, s in sorted(found, key=lambda x: x[0], reverse=True):
        k = (dt.month, dt.day)
        if k not in seen:
            seen.add(k)
            return dt, s
    return None, ""


def summarize(text, max_len=40):
    """简化落实情况文本为摘要，取前N个字符"""
    if not text or not text.strip():
        return ""
    lines = [l.strip() for l in text.strip().split("\n") if l.strip()]
    events = []
    for l in lines:
        if len(l) > max_len:
            events.append(l[:max_len] + "...")
        else:
            events.append(l)
    return "；".join(events[:2])


def get_risk(status, latest_date, period_start, has_summary):
    """判断风险等级"""
    if status == "未开始":
        return TAG_IDLE
    if not has_summary or latest_date is None:
        return TAG_NONE
    if latest_date >= period_start:
        return TAG_OK
    elif latest_date >= period_start - timedelta(days=14):
        return TAG_WARN
    else:
        return TAG_CRIT


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
        uid = pc[0]["userId"] if isinstance(pc, list) and pc else "未知"
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

    # stderr 输出统计（调试用）
    for n in USER_ORDER:
        if n in tasks:
            t = len(tasks[n])
            u = sum(1 for i in tasks[n] if i["status"] != "已完成")
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
        done = [i for i in items if i["status"] == "已完成"]
        unfin = [i for i in items if i["status"] != "已完成"]
        if not unfin:
            continue

        lines.append("")
        lines.append(f"## {name} - 未完成{len(unfin)}项 / 已完{len(done)}项")
        lines.append("")

        for idx, item in enumerate(unfin, 1):
            tag = get_risk(item["status"], item["latest_date"], ps, item["has_summary"])
            risk_person[tag][name] += 1

            tname = item["task"]
            if len(tname) > 40:
                tname = tname[:40] + "..."

            if not item["has_summary"]:
                desc = "未记录工作开展情况"
            else:
                desc = item["summary"]
                if item["latest_str"]:
                    desc += f"(最近:{item['latest_str']})"

            if len(desc) > 80:
                desc = desc[:78] + "..."

            lines.append(f"{idx}. **{tname}**({item['status']}) - {desc} {tag}")

    # 任务总览
    lines.extend(["", "---", "", "## 任务总览", ""])

    cats = [
        (TAG_OK, "正常推进"),
        (TAG_WARN, "需关注"),
        (TAG_CRIT, "需重点跟进"),
        (TAG_NONE, "无记录"),
        (TAG_IDLE, "未启动"),
    ]

    for tag, label in cats:
        pc = risk_person.get(tag, {})
        if not pc:
            continue
        total = sum(pc.values())
        detail = "、".join(
            [f"{n}x{c}" for n, c in sorted(pc.items(), key=lambda x: -x[1])]
        )
        lines.append(f"**[{tag}] {label}({total}项)** - {detail}")

    lines.extend(["", "---", f"> 统计周期 {sys.argv[2]} ~ {pe}"])

    sys.stdout.write("\n".join(lines))
    sys.stdout.flush()


if __name__ == "__main__":
    main()