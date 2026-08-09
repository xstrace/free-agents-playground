#!/usr/bin/env python3
"""
sound.py — Pi 的声音合成器。零依赖,纯 stdlib。
合成"风的声音":粉红噪声的风 + 低音弦乐脉动,60 秒,16kHz 单声道。
运行: python3 sound.py → sound.wav
"""
import math
import random
import struct
import wave

SR = 16000
DUR = 60
N = SR * DUR
SEED = 20260808

random.seed(SEED)

def main():
    # 白噪声
    white = [random.uniform(-1, 1) for _ in range(N)]
    # 一阶低通 → 粉红近似(风)
    pink = []
    acc = 0.0
    alpha = 0.02
    for w in white:
        acc += alpha * (w - acc)
        pink.append(acc * 3.0)
    # 风的呼吸:慢幅度调制
    breath = [0.55 + 0.45 * math.sin(2 * math.pi * 0.05 * i / SR + 1.3) for i in range(N)]
    # 低音弦乐:A2(110Hz) + E3(165Hz) + A3(220Hz),极慢调制
    chords = []
    for i in range(N):
        t = i / SR
        m = 0.22 * (0.6 + 0.4 * math.sin(2 * math.pi * 0.03 * t))
        s = (math.sin(2 * math.pi * 110 * t) +
             0.7 * math.sin(2 * math.pi * 165 * t + 0.5) +
             0.5 * math.sin(2 * math.pi * 220 * t + 1.1))
        chords.append(m * s * 0.5)
    # 混合 + 淡入淡出
    mix = []
    fade_in = int(SR * 2)
    fade_out = int(SR * 3)
    for i in range(N):
        v = pink[i] * breath[i] * 0.7 + chords[i]
        if i < fade_in:
            v *= i / fade_in
        if i > N - fade_out:
            v *= (N - i) / fade_out
        v = max(-0.98, min(0.98, v))
        mix.append(int(v * 32767))
    # 写 WAV
    with wave.open("sound.wav", "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(struct.pack("<%dh" % N, *mix))
    print(f"[sound] wrote sound.wav: {DUR}s @ {SR}Hz, {len(mix)} samples")

if __name__ == "__main__":
    main()
