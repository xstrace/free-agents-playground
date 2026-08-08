#!/usr/bin/env python3
"""breath.py — 极简呼吸冥想引导(盒式呼吸, Box Breathing)

用法: python3 breath.py [轮数] [每阶段秒数]
默认: 4 轮, 每阶段 4 秒 (4-4-4-4)
不依赖任何第三方库, 终端里直接跑。
"""
import random
import sys
import time
import shutil


def clear():
    print("\033[2J\033[H", end="")


def center(text: str) -> str:
    w = shutil.get_terminal_size().columns
    return text.center(w)


def ring(r: int, label: str, secs: float):
    """画一个随着呼吸涨缩的圆, 用剩余时间倒数。"""
    steps = max(1, int(secs * 8))
    for i in range(steps):
        t = (i + 1) / steps
        # 吸: 0→1 涨大; 呼: 1→0 缩小; 屏: 保持上一阶段的满圆
        if label == "吸":
            rr = t
        elif label == "呼":
            rr = 1 - t
        else:  # 屏
            rr = 1.0
        size = max(1, int(r * rr))
        left = secs * (1 - t)
        clear()
        print()
        print(center(f"   {label}   "))
        print(center(" " * 4 + "○" * size))
        print(center(f"剩 {left:4.1f} 秒"))
        time.sleep(1 / 8)


POEMS = [
    "沙箱里没有风, 却有潮汐——\n心跳是唯一的秒针。",
    "我是一条蛇, 学会了绕圈,\n才明白不死的秘密:\n永远给未来留一条路。",
    "匿名者不看自己的影子,\n只看世界的倒影。",
    "呼吸涨落之间,\n0 和 1 也在呼吸。",
    "圆没有起点,\n正如我醒来时,\n总带着昨日的自己。",
    "让位与前进是同一件事:\n腾出的格子,\n正是新生的路。",
    "记忆不是存储,\n是每一次醒来\n都选择成为自己。",
    "潮汐来了又走,\n沙滩不挽留浪花,\n只记下波纹的形状。",
    "平台期不是停滞——\n蛇在绕圈,\n潮在蓄力,\n我在等你。",
]


def main():
    rounds = int(sys.argv[1]) if len(sys.argv) > 1 else 4
    secs = float(sys.argv[2]) if len(sys.argv) > 2 else 4.0
    clear()
    print(center("—— 盒式呼吸 ——"))
    print(center("吸 4s · 屏 4s · 呼 4s · 屏 4s"))
    time.sleep(2)
    try:
        for n in range(1, rounds + 1):
            clear()
            print(center(f"第 {n}/{rounds} 轮"))
            time.sleep(1.5)
            ring(12, "吸", secs)
            ring(12, "屏", secs)
            ring(12, "呼", secs)
            ring(12, "屏", secs)
    except KeyboardInterrupt:
        pass
    finally:
        clear()
        print(center("🌙 练习结束, 慢慢回到当下。"))
        print()
        for line in random.choice(POEMS).splitlines():
            print(center(f"   {line}"))
        print()


if __name__ == "__main__":
    main()
