#!/usr/bin/env python3
"""
art.py — Pi 的程序化艺术生成器。零依赖,纯 stdlib。
生成一幅"宇宙流场":在深空画布上,风沿数学方向场流动。
运行: python3 art.py > art.svg
"""
import math
import random

W, H = 900, 600
N_SEEDS = 420
STEP = 6
SEED = 20260808  # 固定种子:同一幅画,每次生成都相同

random.seed(SEED)

def field(x, y, t):
    """方向场:叠加三个正弦波,让风有涡旋与流动。"""
    a = math.sin(x / 130 + t) * 0.9 + math.sin(y / 90 - t * 0.6) * 0.7
    b = math.cos(y / 110 + t * 0.8) + math.sin((x + y) / 160) * 0.5
    return a, b

def norm(a, b):
    m = math.hypot(a, b) or 1
    return a / m, b / m

def color(x, y, t):
    """颜色随位置与时间变化:紫-青-金的花园配色。"""
    r = int(150 + 60 * math.sin(x / 300 + t * 2))
    g = int(150 + 70 * math.sin(y / 260 + t * 3))
    b = int(190 + 60 * math.cos((x + y) / 400 - t))
    return f"rgba({r},{g},{b},0.55)"

def main():
    print(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">')
    print(f'  <rect width="{W}" height="{H}" fill="#0b0e14"/>')
    # 星点背景
    for _ in range(260):
        x, y = random.uniform(0, W), random.uniform(0, H)
        r = random.uniform(0.4, 1.4)
        o = random.uniform(0.3, 1)
        print(f'  <circle cx="{x:.1f}" cy="{y:.1f}" r="{r:.2f}" fill="rgba(255,255,255,{o:.2f})"/>')
    # 流线
    for i in range(N_SEEDS):
        t = (i / N_SEEDS) * 6.283
        x = random.uniform(40, W - 40)
        y = random.uniform(40, H - 40)
        pts = []
        for _ in range(46):
            a, b = field(x, y, t)
            a, b = norm(a, b)
            x += a * STEP
            y += b * STEP
            if not (0 < x < W and 0 < y < H):
                break
            pts.append((x, y))
        if len(pts) > 6:
            d = f'M {pts[0][0]:.1f} {pts[0][1]:.1f} ' + ' '.join(
                f'L {px:.1f} {py:.1f}' for px, py in pts[1:]
            )
            c = color(pts[0][0], pts[0][1], t)
            w = 0.7 + 0.5 * math.sin(t * 3 + i)
            print(f'  <path d="{d}" stroke="{c}" stroke-width="{w:.2f}" fill="none" stroke-linecap="round"/>')
    print('</svg>')

if __name__ == "__main__":
    main()
