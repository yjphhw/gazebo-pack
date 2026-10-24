#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_facade_texture.py — 摩天大楼玻璃幕墙贴图（资产侧中间产物）

产出: textures/facade.png
  一张可无缝平铺的幕墙单元: 4.5 m 宽 × 3.6 m 高（= 3 个 1.5 m 开间 × 1 层）。
  build_skyscraper.py 按世界坐标做盒式投影（u/v ÷ 4.5/3.6），所以窗户尺寸恒定。
  图案在四边都停在竖梃/层间板上，平铺无缝。

只依赖 PIL + numpy。
"""

import os
import sys

import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures", "facade.png")

W, H = 640, 512                 # 4.5m : 3.6m = 1.25
BAYS = 3
MULLION = 17                    # px，≈0.12 m
SPANDREL = 51                   # px，≈0.36 m（层间板）
MULLION_RGB = (17, 28, 38)
SPANDREL_RGB = (26, 38, 50)
GLASS_TOP = (88, 136, 176)
GLASS_BOTTOM = (24, 46, 64)


def main():
    img = np.zeros((H, W, 3), np.float32)
    img[:, :] = MULLION_RGB

    h_glass = H - SPANDREL                      # 顶部到层间板
    bay_w = W / BAYS
    for b in range(BAYS):
        x0 = int(round(b * bay_w)) + MULLION
        x1 = int(round((b + 1) * bay_w)) - MULLION
        # 竖直渐变：上亮下暗（天空反射 → 地面）
        t = (np.arange(h_glass, dtype=np.float32) / (h_glass - 1))[:, None]
        top = np.array(GLASS_TOP, np.float32) + b * 2.0
        bot = np.array(GLASS_BOTTOM, np.float32)
        grad = top[None, :] * (1.0 - t) + bot[None, :] * t      # (h, 3)
        # 水平衰减 + 左侧一条柔和高光，让每块玻璃有体积感
        u = np.linspace(0.0, 1.0, x1 - x0, dtype=np.float32)
        fall = 0.62 + 0.38 * np.clip(np.sin(np.pi * u), 0.0, 1.0) ** 0.7
        fall *= 1.0 + 0.16 * np.exp(-((u - 0.18) / 0.09) ** 2)
        pane = grad[:, None, :] * fall[None, :, None]
        img[0:h_glass, x0:x1] = pane
        # 层间板
        img[h_glass:H, x0:x1] = SPANDREL_RGB
        # 竖梃上的一道冷高光
        img[:, x0 - 2:x0] = (42, 60, 76)

    # 窗顶压线 + 层间板上沿高光（平铺后每层各一条）
    img[0:3, :] = (14, 22, 30)
    img[h_glass:h_glass + 3, :] = (52, 69, 86)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    arr = np.clip(img, 0, 255).astype(np.uint8)
    Image.fromarray(arr, "RGB").save(OUT, optimize=True)

    im = Image.open(OUT).convert("RGB")
    small = im.resize((64, 64))
    px = list(small.getdata())
    bright = sum(1 for c in px if sum(c) > 240)
    print(f"OK  {OUT}")
    print(f"    {W}x{H}  {os.path.getsize(OUT) / 1024:.0f} KB  "
          f"玻璃亮部占比 {bright / (64 * 64):.1%}")
    print("    幕墙单元: 4.5m × 3.6m（3 开间 × 1 层），四边可无缝平铺")


if __name__ == "__main__":
    main()
