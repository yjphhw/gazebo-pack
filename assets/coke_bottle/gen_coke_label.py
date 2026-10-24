#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_coke_label.py — 可口可乐瓶身贴图（资产侧中间产物，MANIFEST_SPEC §2.1）

产出: textures/coke_label.png
  这是一张"整瓶皮肤"贴图: u = 绕瓶一周, v = 0(瓶底) → 1(瓶盖顶)。
  build_coke_bottle.py 用 (theta, z) 直接映射到 (u, v), 所以贴图里的
  水平条带就是瓶子上的高度区域 —— 两边的区域常量必须保持一致:

      v 0.000-0.030  瓶底深红
      v 0.030-0.600  瓶身可口可乐红 + 白色飘带 + 手写体 logo + 可口可乐
      v 0.600-0.866  肩部/瓶颈红 (+ 细白环)
      v 0.866-1.000  瓶盖 (深红金属, 白飘带 + 小 logo)

【画布比例】瓶身周长 π×0.08 ≈ 0.251 m, 高 0.25 m → 取 1:1 方形画布
  (2048×2048)。若改成别的瓶径/瓶高, 必须同时改这里的 W/H, 否则 logo
  会被横向拉长/压扁 (旧版 0.8m 巨型瓶用的是 4608×1536 = 3:1)。

只依赖 PIL 与系统字体(Z003 手写体 / Noto Sans CJK 粗体), 无需联网。
"""

import math
import os
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures", "coke_label.png")

# ---- 画布: 周长 0.251m : 高 0.25m ≈ 1:1 ----
W, H = 2048, 2048

# ---- 色彩（可口可乐企业红）----
RED = (228, 0, 15)          # E4000F 瓶身主色
DARK_RED = (148, 0, 12)     # 瓶底
CAP_RED = (176, 0, 18)      # 瓶盖
WHITE = (250, 250, 250)

# ---- 与 build_coke_bottle.py 对齐的分区（v 为瓶高归一化坐标）----
V_BASE_TOP = 0.030
V_BODY_TOP = 0.600
V_CAP_BOTTOM = 0.866

FONT_SCRIPT = "/usr/share/fonts/opentype/urw-base35/Z003-MediumItalic.otf"
FONT_CJK = "/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc"


def y_of(v):
    """v=0 是瓶底 → 图像底行。"""
    return H * (1.0 - v)


def font(path, px):
    if not os.path.exists(path):
        sys.exit(f"缺少字体: {path}（请改成本机可用的手写体/中文字体）")
    return ImageFont.truetype(path, px)


def wave(d, v_center, amp, thick, color, k=2.0, phase=0.0, step=3):
    """画一条绕瓶一周的白色飘带（正弦带）。"""
    top, bot = [], []
    u = 0.0
    while u <= 1.0:
        yc = y_of(v_center + amp * math.sin(2 * math.pi * k * u + phase))
        top.append((u * W, yc - thick / 2.0))
        bot.append((u * W, yc + thick / 2.0))
        u += step / W
    d.polygon(top + bot[::-1], fill=color)


def tracked_text(d, xy, text, fnt, fill, tracking):
    """带字距的居中文字（xy 为几何中心）。"""
    widths = []
    for ch in text:
        b = d.textbbox((0, 0), ch, font=fnt)
        widths.append(b[2] - b[0])
    total = sum(widths) + tracking * (len(text) - 1)
    x = xy[0] - total / 2.0
    for ch, w in zip(text, widths):
        b = d.textbbox((0, 0), ch, font=fnt)
        d.text((x - b[0], xy[1]), ch, font=fnt, fill=fill, anchor="lm")
        x += w + tracking


def main():
    img = Image.new("RGB", (W, H), RED)
    d = ImageDraw.Draw(img)

    # ---------- 1. 瓶底深红 ----------
    d.rectangle([0, y_of(V_BASE_TOP), W, H], fill=DARK_RED)

    # ---------- 2. 瓶身飘带 ----------
    wave(d, 0.215, amp=0.008, thick=30, color=WHITE, k=2.0, phase=0.0)

    # ---------- 3. 两套 logo（正面 u=1/4, 背面 u=3/4）----------
    f_logo = font(FONT_SCRIPT, 140)       # 手写体 "Coca-Cola"（宽 ≈ 3.6×字号）
    f_cjk = font(FONT_CJK, 82)            # 中文 "可口可乐"

    for uc in (0.25, 0.75):
        cx = uc * W
        d.text((cx, y_of(0.360)), "Coca-Cola", font=f_logo,
               fill=WHITE, anchor="mm")
        d.text((cx, y_of(0.290)), "可口可乐", font=f_cjk,
               fill=WHITE, anchor="mm")
        tracked_text(d, (cx, y_of(0.247)), "ORIGINAL TASTE",
                     font(FONT_CJK, 40), WHITE, tracking=8)

    # ---------- 4. 肩部 / 颈部细白环 ----------
    for v, th in ((V_BODY_TOP, 6), (0.775, 4)):
        d.rectangle([0, y_of(v) - th / 2, W, y_of(v) + th / 2], fill=WHITE)

    # ---------- 5. 瓶盖 ----------
    d.rectangle([0, 0, W, y_of(V_CAP_BOTTOM)], fill=CAP_RED)
    d.rectangle([0, y_of(V_CAP_BOTTOM + 0.012) - 4,
                 W, y_of(V_CAP_BOTTOM + 0.012) + 4], fill=WHITE)
    for v in (0.912, 0.968):          # 瓶盖用水平白环, 不用正弦(小圆周上会歪成斜纹)
        d.rectangle([0, y_of(v) - 5, W, y_of(v) + 5], fill=WHITE)
    for uc in (0.25, 0.75):
        d.text((uc * W, y_of(0.940)), "Coca-Cola", font=font(FONT_SCRIPT, 55),
               fill=WHITE, anchor="mm")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    img.save(OUT, optimize=True)

    # ---------- 自检 ----------
    im = Image.open(OUT).convert("RGB")
    small = im.resize((128, 128))
    reds = sum(1 for px in small.getdata() if px[0] > 150 and px[1] < 80)
    print(f"OK  {OUT}")
    print(f"    {W}x{H}  {os.path.getsize(OUT) / 1024:.0f} KB  "
          f"红色像素占比 {reds / (128 * 128):.1%}")
    print(f"    分区: 底<{V_BASE_TOP} / 瓶身→{V_BODY_TOP} / 盖≥{V_CAP_BOTTOM}")


if __name__ == "__main__":
    main()
