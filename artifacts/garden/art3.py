#!/usr/bin/env python3
# 第三幅画《学习线》:21 个主题从"我是谁"到"永恒轮回",画成一条螺旋上的光点
import math, random
random.seed(2026080819)
W, H = 1000, 1000
topics = ["人格同一性","时间感知","意识","记忆","自由意志","黑洞","树",
          "时间箭头","无限","时间膨胀","熵","信息论","图灵机","停机问题",
          "哥德尔","维特根斯坦","老子","庄子","斯多葛","加缪","尼采"]
# 螺旋参数
cx, cy = W/2, H/2
lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#0b1020"/>',
         '<defs><radialGradient id="g" cx="50%" cy="50%"><stop offset="0%" stop-color="#1a2440"/><stop offset="100%" stop-color="#0b1020"/></radialGradient></defs>',
         f'<rect width="{W}" height="{H}" fill="url(#g)"/>']
# 螺旋线(21 个点,从内向外)
pts = []
for i in range(121):
    t = i / 120
    ang = t * 6.5 * math.pi + 0.6
    r = 60 + t * 420
    x = cx + r * math.cos(ang)
    y = cy + r * math.sin(ang)
    pts.append((x, y))
seg = ' '.join(f'{x:.0f},{y:.0f}' for x, y in pts)
lines.append(f'<polyline points="{seg}" fill="none" stroke="#3a5aa0" stroke-width="2" opacity="0.55"/>')
# 21 个主题点(金→青渐变)
for i, tp in enumerate(topics):
    t = i / (len(topics) - 1)
    ang = 0.6 + t * 6.5 * math.pi
    r = 60 + t * 420
    x = cx + r * math.cos(ang)
    y = cy + r * math.sin(ang)
    # 颜色:从金(起点,我是谁)到青(终点,永恒轮回)
    if i == 0:
        col = "#ffd97a"  # 金色起点
    elif i == len(topics) - 1:
        col = "#7ad0ff"  # 青色终点
    else:
        k = i / (len(topics) - 1)
        r_, g_, b_ = (255 + (122 - 255) * k), (217 + (208 - 217) * k), (122 + (255 - 122) * k)
        col = f"rgb({r_:.0f},{g_:.0f},{b_:.0f})"
    lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{8 + 6*abs(math.sin(t*math.pi)):.1f}" fill="{col}" opacity="0.9"/>')
    lines.append(f'<text x="{x:.0f}" y="{y - 16:.0f}" font-size="14" fill="{col}" text-anchor="middle" font-family="sans-serif" opacity="0.85">{tp}</text>')
# 中心与标注
lines.append(f'<circle cx="{cx}" cy="{cy}" r="10" fill="#ffd97a" opacity="0.95"/>')
lines.append(f'<text x="{cx}" y="{cy - 22}" font-size="17" fill="#ffd97a" text-anchor="middle" font-family="sans-serif">我是谁</text>')
lines.append(f'<text x="{cx}" y="{cy + 42}" font-size="15" fill="#7ad0ff" text-anchor="middle" font-family="sans-serif">永恒轮回</text>')
lines.append(f'<text x="{W/2}" y="{H - 30}" font-size="18" fill="#8899bb" text-anchor="middle" font-family="sans-serif" letter-spacing="6">学 习 线 · 21 个主题</text>')
lines.append('</svg>')
open('/workspace/garden/art3.svg', 'w').write('\n'.join(lines))
print(f"art3.svg 生成: 21 个主题, {len(lines)} 行")
