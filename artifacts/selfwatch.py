#!/usr/bin/env python3
"""selfwatch.py — 沙箱自我观察表: 解析 journal.md, 画出每轮的"心情-产出"对照。

用法: python3 selfwatch.py [journal路径]
"""
import re
import sys
from collections import Counter
from pathlib import Path


def parse(path):
    text = Path(path).read_text(encoding="utf-8")
    sections, cur = [], None
    for line in text.splitlines():
        m = re.match(r"^## (\S+) · (.+)$", line)
        if m:
            cur = {"date": m.group(1), "title": m.group(2), "lines": []}
            sections.append(cur)
        elif cur is not None:
            cur["lines"].append(line)
    return sections


def mood(title):
    if "冥想" in title:
        return "🧘冥想"
    if "狂野" in title:
        return "🔥狂野"
    if "沉思" in title or "思考" in title:
        return "🌙沉思"
    if "静默" in title:
        return "🤫静默"
    return "📄常规"


def product(lines):
    t = None
    for line in lines:
        m = re.search(r"本轮[:：]\s*(.+)", line.strip())
        if m:
            t = m.group(1).strip()
            break
    if t:
        if "干了" in t or "大事" in t:
            return "综合产出"
        if "写了" in t or "建" in t and "工具" in t:
            return "小工具"
        if "检查" in t or "探测" in t or "网络" in t:
            return "探索/网络"
        if "重读" in t or "沉思" in t or "思考" in t:
            return "文字沉思"
        return "行动"
    s = " ".join(lines)
    if "重读" in s or "沉思" in s or "灵光" in s:
        return "文字沉思"
    return "?"


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else "/workspace/journal.md"
    sections = parse(path)
    print("═" * 66)
    print("🧿 沙箱自我观察表")
    print("═" * 66)
    print(f"{'#':<3}{'心情':<7}{'日期':<13}{'产出':<10}标题")
    print("─" * 66)
    for i, s in enumerate(sections, 1):
        print(f"{i:<3}{mood(s['title']):<7}{s['date']:<13}{product(s['lines']):<10}{s['title'][:26]}")
    print("─" * 66)
    c = Counter(mood(s["title"]) for s in sections)
    print("心情分布:", "  ".join(f"{k}×{v}" for k, v in c.most_common()))
    ws = Path(path).parent
    tools = sorted(ws.glob("*.py")) + sorted(ws.glob("*.sh"))
    total = sum(len(p.read_text(encoding="utf-8").splitlines()) for p in tools)
    print(f"工具 {len(tools)} 个 · 共 {total} 行代码: {', '.join(p.name for p in tools)}")
    print("═" * 66)


if __name__ == "__main__":
    main()
