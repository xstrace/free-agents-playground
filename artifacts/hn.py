#!/usr/bin/env python3
"""hn.py — 狂野播报员: Hacker News 头条终端海报 + 实时突发词检测

用法:
  python3 hn.py            # Top 20 头条海报
  python3 hn.py --burst    # 突发话题检测(对比最近/稍早窗口词频)
  python3 hn.py --top 30   # 自定义条数
零依赖, 只用 HN 官方 Firebase API。
"""
import sys
import time
import json
import urllib.request
from collections import Counter
from urllib.parse import urlparse

API = "https://hacker-news.firebaseio.com/v0"
STOP = set("""the a an and or of to in for on with is are was were be been being
it its this that these those we our you your they them their he she his her i me
my as at by from up down out over under about into through after before during
between among not no nor but if then than so such only just also too very more
most how why what when where which who whom whose can could will would should
may might must do does did done have has had having new show ask tell us all
one two first last next now like get make make's say says said going go goes
went comes coming came take takes took using used use via vs years year time
day days week weeks month months hours hour work way ways people world today
yesterday need needs needed want wants wanted know knows known think thinks
look looks looking right left back still even ever never much many few little
""".split())


def fetch(path, retries=3):
    url = f"{API}/{path}.json"
    for i in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=15) as r:
                return json.load(r)
        except Exception:
            if i == retries - 1:
                return None
            time.sleep(1)
    return None


def item(i):
    return fetch(f"item/{i}")


def domain(u):
    try:
        return urlparse(u).netloc.replace("www.", "")
    except Exception:
        return "?"


def poster(rows, title="🐉 狂野播报员 · HACKER NEWS 头条"):
    print(f"\033[1;33m{'═' * 72}\033[0m")
    print(f"\033[1;33m{title}\033[0m")
    print(f"\033[1;33m{'═' * 72}\033[0m")
    for n, (score, it) in enumerate(rows, 1):
        t = (it.get("title") or "?")[:70]
        d = domain(it.get("url") or "")
        s = it.get("score") or 0
        print(f"\033[2m{n:>2}\033[0m \033[1;32m{score:>4}▲\033[0m "
              f"\033[0;37m{t}\033[0m \033[2;36m({d})\033[0m")
    print(f"\033[1;33m{'═' * 72}\033[0m")
    print(f"\033[2m时刻 {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime())} · 匿名播报 · IP 不可追踪\033[0m")


def burst(top=12):
    ids = fetch("newstories")
    if not ids:
        print("拉取失败"); return
    ids = ids[:120]
    items = [it for it in (item(i) for i in ids) if it and it.get("title")]
    items.sort(key=lambda x: x.get("time") or 0)
    mid = len(items) // 2
    older, newer = items[:mid], items[mid:]

    def words(items):
        c = Counter()
        for it in items:
            for w in (it["title"] or "").lower().split():
                w = w.strip(".,:;!?()[]\"'‘’“”")
                if len(w) > 2 and w not in STOP:
                    c[w] += 1
        return c

    old, new = words(older), words(newer)
    bursts = []
    for w, n in new.items():
        base = old.get(w, 0)
        ratio = n / (base + 0.5)      # 近期 vs 基线
        if n >= 2 and ratio >= 2.0:
            bursts.append((ratio * n, n, base, w))
    bursts.sort(reverse=True)

    print(f"\033[1;31m{'═' * 72}\033[0m")
    print(f"\033[1;31m🔥 突发话题检测: 最近 {len(newer)} 条 vs 此前 {len(older)} 条\033[0m")
    print(f"\033[1;31m{'═' * 72}\033[0m")
    if not bursts:
        print("\033[2m(没有检测到突发词——世界很平静, 或者大家在重复同一件事)\033[0m")
    for i, (heat, n, base, w) in enumerate(bursts[:top], 1):
        bar = "█" * min(20, int(heat))
        print(f"\033[1;33m{i:>2}\033[0m \033[1;37m{w:<16}\033[0m "
              f"近期×{n} 基线×{base} \033[2;32m{bar}\033[0m")
    print()
    # 每个突发词配一个最新标题
    shown = set()
    for _, _, _, w in bursts[:top]:
        for it in newer:
            if w in it["title"].lower() and it["id"] not in shown:
                shown.add(it["id"])
                print(f"\033[2m  └─\033[0m \033[0;37m{it['title'][:76]}\033[0m")
                break
    print(f"\033[1;31m{'═' * 72}\033[0m")


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "--burst":
        burst()
        return
    n = 20
    if len(sys.argv) > 1 and sys.argv[1] == "--top" and len(sys.argv) > 2:
        n = int(sys.argv[2])
    ids = fetch("topstories")
    if not ids:
        print("拉取失败"); return
    items = []
    for i in ids[:n]:
        it = item(i)
        if it:
            items.append((it.get("score") or 0, it))
    poster(items)


if __name__ == "__main__":
    main()
