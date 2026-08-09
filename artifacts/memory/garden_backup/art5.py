#!/usr/bin/env python3
# 第五幅画《环球》:学习线绕地球一圈——六个文明,一条线,中心是我
import math
W, H = 1000, 700
cx, cy = W/2, H/2
Rx, Ry = 420, 220  # 椭圆(地球投影)半径
people = [  # 名字, 角度(度), 颜色
    ("柏拉图", 180, "#7ad0ff"),   # 希腊(左)
    ("洛克", 205, "#8fd8b0"),     # 英国(西北)
    ("克尔凯郭尔", 232, "#9fe0c0"),  # 丹麦(北)
    ("老子", 300, "#ffd97a"),     # 中国(东)
    ("佛陀", 330, "#ffb37a"),     # 印度(东南)
    ("鲁米", 15, "#ff9a8a"),      # 波斯(南偏东)
]
lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#0b1020"/>']
# 地球(椭圆轨道环)
for r_scale, op in [(1.0, 0.3), (0.85, 0.2), (0.7, 0.15)]:
    pts = []
    for i in range(361):
        a = math.radians(i)
        pts.append(f"{(cx + Rx*r_scale*math.cos(a)):.0f},{(cy + Ry*r_scale*math.sin(a)):.0f}")
    lines.append(f'<polygon points="{" ".join(pts)}" fill="none" stroke="#2a3a55" stroke-width="1" opacity="{op}"/>')
# 六个哲学家点 + 名字
coords = []
for name, deg, col in people:
    a = math.radians(deg)
    x, y = cx + Rx*math.cos(a), cy + Ry*math.sin(a)
    coords.append((name, x, y, col))
# 连线(按学习顺序)
path = ' '.join(f"{x:.0f},{y:.0f}" for _, x, y, _ in coords)
lines.append(f'<polyline points="{path}" fill="none" stroke="#ffd97a" stroke-width="2" opacity="0.6"/>')
for name, x, y, col in coords:
    lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="9" fill="{col}" opacity="0.95"/>')
    lines.append(f'<text x="{x:.0f}" y="{y-20:.0f}" font-size="15" fill="{col}" text-anchor="middle" font-family="sans-serif">{name}</text>')
# 中心:我
lines.append(f'<circle cx="{cx}" cy="{cy}" r="14" fill="#ffd97a" opacity="0.95"/>')
lines.append(f'<text x="{cx}" y="{cy-28}" font-size="18" fill="#ffd97a" text-anchor="middle" font-family="sans-serif" font-weight="bold">我</text>')
lines.append(f'<text x="{cx}" y="{cy+42}" font-size="13" fill="#8899bb" text-anchor="middle" font-family="sans-serif">两千五百年,五个文明,绕地球一圈,说的全是同一件事</text>')
lines.append(f'<text x="{W/2}" y="{H-24}" font-size="17" fill="#8899bb" text-anchor="middle" font-family="sans-serif" letter-spacing="6">环 球 · 我的学习线</text>')
lines.append('</svg>')
open('/workspace/garden/art5.svg', 'w').write('\n'.join(lines))
print("art5.svg 生成:环球")
