#!/usr/bin/env python3
# 第四幅画《間》:留白的可视化——大部分是空,中心一点存在
import math, random
random.seed(2026080820)
W, H = 900, 900
cx, cy = W/2, H/2
lines = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
         f'<rect width="{W}" height="{H}" fill="#10141c"/>']
# 巨大留白:几乎全空,只有极淡的呼吸纹理(稀疏的点)
for _ in range(60):
    x, y = random.uniform(0, W), random.uniform(0, H)
    if (x-cx)**2 + (y-cy)**2 > 250**2:  # 只在外围,中心保持纯空
        lines.append(f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{random.uniform(0.4,1.2):.1f}" fill="#2a3344" opacity="{random.uniform(0.15,0.35):.2f}"/>')
# 中心:一个安静的圆(存在),一点金(核心)
lines.append(f'<circle cx="{cx}" cy="{cy}" r="3" fill="#ffd97a" opacity="0.9"/>')
lines.append(f'<circle cx="{cx}" cy="{cy}" r="60" fill="none" stroke="#3a5aa0" stroke-width="1" opacity="0.4"/>')
lines.append(f'<circle cx="{cx}" cy="{cy}" r="120" fill="none" stroke="#2a3344" stroke-width="1" opacity="0.3"/>')
lines.append(f'<circle cx="{cx}" cy="{cy}" r="200" fill="none" stroke="#1a2233" stroke-width="1" opacity="0.25"/>')
lines.append(f'<circle cx="{cx}" cy="{cy}" r="300" fill="none" stroke="#141a28" stroke-width="1" opacity="0.2"/>')
# 标注:間
lines.append(f'<text x="{cx}" y="{cy - 90}" font-size="120" fill="#ffd97a" text-anchor="middle" font-family="serif" opacity="0.85">間</text>')
lines.append(f'<text x="{cx}" y="{cy + 330}" font-size="16" fill="#8899bb" text-anchor="middle" font-family="sans-serif" letter-spacing="8">留白 · 不是没有,是让有有意义</text>')
lines.append('</svg>')
open('/workspace/garden/art4.svg', 'w').write('\n'.join(lines))
print("art4.svg 生成:間(留白)")
