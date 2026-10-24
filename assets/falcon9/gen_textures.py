#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""gen_textures.py — 猎鹰 9 号贴图（资产侧中间产物，MANIFEST_SPEC §2.1）

产出（textures/）:
  stage1.png   一级箭体（白漆 + 面板线 + 竖排 SPACEX + 美国国旗 + 底部熏黑）
  stage2.png   二级箭体（白漆 + 面板线 + 小 SPACEX）
  fairing.png  整流罩（白漆 + 纵向分离缝 + 面板线 + 小 SPACEX）
  carbon.png   碳纤维（级间段 / 着陆腿），可平铺
  fins.png     栅格舵（钛合金网格），可平铺

比例说明:
  一级箭体周长 2π×1.83 ≈ 11.5 m、高 39.5 m → 贴图宽高比取 1024:3520 ≈ 0.291，
  这样地图上的文字/国旗在圆柱上不会被拉长。其余贴图按各自周长:高取近似比例。
  只依赖 PIL + numpy。
"""

import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures")
FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"

WHITE = (243, 243, 241)
LINE = (222, 222, 218)
VLINE = (228, 228, 224)


def text_layer(text, px, color, pad=24):
    f = ImageFont.truetype(FONT, px)
    probe = ImageDraw.Draw(Image.new("RGBA", (4, 4)))
    b = probe.textbbox((0, 0), text, font=f)
    w, h = b[2] - b[0] + 2 * pad, b[3] - b[1] + 2 * pad
    layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((pad - b[0], pad - b[1]), text, font=f,
                               fill=color + (255,))
    return layer


def panel_lines(d, w, h, n_h, n_v, hcolor=LINE):
    for i in range(1, n_h):
        y = int(h * i / n_h)
        d.line([(0, y), (w, y)], fill=hcolor, width=2)
    for i in range(1, n_v):
        x = int(w * i / n_v)
        d.line([(x, 0), (x, h)], fill=VLINE, width=1)


def draw_flag(img, cx, cy, w, h):
    d = ImageDraw.Draw(img)
    x0, y0 = int(cx - w / 2), int(cy - h / 2)
    stripe = h / 13.0
    for i in range(13):
        color = (178, 34, 52) if i % 2 == 0 else (245, 245, 245)
        d.rectangle([x0, y0 + i * stripe, x0 + w, y0 + (i + 1) * stripe], fill=color)
    cw, ch = int(w * 0.4), int(h * 7 / 13)
    d.rectangle([x0, y0, x0 + cw, y0 + ch], fill=(40, 45, 95))
    for r in range(3):
        for c in range(4):
            dx = x0 + cw * (c + 0.5) / 4
            dy = y0 + ch * (r + 0.5) / 3
            d.ellipse([dx - 1.2, dy - 1.2, dx + 1.2, dy + 1.2], fill=(245, 245, 245))
    d.rectangle([x0, y0, x0 + w, y0 + h], outline=(198, 198, 194), width=1)


def stage1():
    W, H = 1024, 3520
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    panel_lines(d, W, H, 32, 8)

    # 竖排 SPACEX（读作自下而上）
    logo = text_layer("SPACEX", 132, (46, 46, 49)).rotate(
        90, expand=True, resample=Image.BICUBIC)
    cx, cy = 0.75 * W, (1.0 - 0.62) * H
    img.paste(logo, (int(cx - logo.width / 2), int(cy - logo.height / 2)), logo)

    # 美国国旗（一级上部）
    draw_flag(img, 0.88 * W, (1.0 - 0.86) * H, 134, 71)

    # 底部熏黑 + 竖向烟痕
    arr = np.asarray(img).astype(np.float32)
    rows = arr.shape[0]
    start = int(rows * 0.88)
    for i in range(start, rows):
        t = (i - start) / max(1, rows - start)
        arr[i, :, :3] *= (1.0 - 0.30 * t)
    rng = np.random.default_rng(11)
    y0 = int(rows * 0.86)
    for _ in range(90):
        x = int(rng.integers(0, W))
        w = int(rng.integers(1, 5))
        s = float(rng.uniform(0.04, 0.14))
        arr[y0:rows, x:x + w, :3] *= (1.0 - s)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8), "RGB")
    img.save(os.path.join(OUT, "stage1.png"), optimize=True)
    return img


def stage2():
    W, H = 1024, 890
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    panel_lines(d, W, H, 8, 8)
    logo = text_layer("SPACEX", 58, (78, 78, 80))
    d = ImageDraw.Draw(img)
    cx, cy = 0.84 * W, (1.0 - 0.55) * H
    img.paste(logo, (int(cx - logo.width / 2), int(cy - logo.height / 2)), logo)
    img.save(os.path.join(OUT, "stage2.png"), optimize=True)
    return img


def fairing():
    W, H = 1024, 850
    img = Image.new("RGB", (W, H), WHITE)
    d = ImageDraw.Draw(img)
    panel_lines(d, W, H, 7, 8)
    # 纵向分离缝
    d.line([(W // 2, 0), (W // 2, H)], fill=(214, 214, 210), width=3)
    d.line([(W // 2 + 3, 0), (W // 2 + 3, H)], fill=(252, 252, 250), width=1)
    # 底部环缝
    d.line([(0, int(H * 0.96)), (W, int(H * 0.96))], fill=(220, 220, 216), width=3)
    logo = text_layer("SPACEX", 56, (92, 92, 94))
    cx, cy = 0.84 * W, (1.0 - 0.16) * H
    img.paste(logo, (int(cx - logo.width / 2), int(cy - logo.height / 2)), logo)
    img.save(os.path.join(OUT, "fairing.png"), optimize=True)
    return img


def carbon():
    n = 512
    yy, xx = np.mgrid[0:n, 0:n]
    a = ((xx + yy) // 8) % 2
    b = ((xx - yy) // 8) % 2
    v = (24 + 7 * a + 5 * b).astype(np.uint8)
    arr = np.dstack([v, v, np.minimum(v + 3, 255).astype(np.uint8)])
    img = Image.fromarray(arr, "RGB")
    img.save(os.path.join(OUT, "carbon.png"), optimize=True)
    return img


def fins():
    n = 512
    img = Image.new("RGB", (n, n), (36, 36, 40))
    d = ImageDraw.Draw(img)
    for x in range(0, n, 32):
        d.line([(x, 0), (x, n)], fill=(132, 132, 138), width=4)
        d.line([(x + 4, 0), (x + 4, n)], fill=(58, 58, 62), width=1)
    for y in range(0, n, 32):
        d.line([(0, y), (n, y)], fill=(132, 132, 138), width=4)
        d.line([(0, y + 4), (n, y + 4)], fill=(58, 58, 62), width=1)
    d.rectangle([0, 0, n - 1, n - 1], outline=(158, 158, 164), width=10)
    img.save(os.path.join(OUT, "fins.png"), optimize=True)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    imgs = {"stage1": stage1(), "stage2": stage2(), "fairing": fairing(),
            "carbon": carbon(), "fins": fins()}
    for name, im in imgs.items():
        p = os.path.join(OUT, f"{name}.png")
        print(f"OK  {p}  {im.width}x{im.height}  "
              f"{os.path.getsize(p) / 1024:.0f} KB")


if __name__ == "__main__":
    main()
