# -*- coding: utf-8 -*-
"""gen_tesla_textures.py — Tesla Model 3 贴图 (numpy+PIL, 系统 python3)
运行: python3 assets/tesla/gen_tesla_textures.py
产出: textures/{side,front,rear,wheel}.png
UV 约定 (与 build_tesla.py 一致):
  侧  右 u=(2.345-x)/4.69  左 u=(x+2.345)/4.69, v=z/1.44   (车头 u=0)
  前  u=(y+0.925)/1.85   后 u=(0.925-y)/1.85, v=z/1.44
  轮帽 u=0.5+(x-xc)/0.6 v=0.5+(z-zc)/0.6; 胎面 u=角度/2π v=0.9
侧面轮廓 (世界 x,z): 鼻顶(2.345,1.00) 车顶前(0.85,1.42) 车顶后(-0.70,1.44) 尾(-2.345,1.18)
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261025)
FONT = "/usr/share/fonts/truetype/hw/NotoSansSC-VF.ttf"
L, W, H = 4.69, 1.85, 1.44

WHITE = np.array([0.93, 0.94, 0.95])
BLACK = np.array([0.05, 0.05, 0.06])
GLASS = np.array([0.07, 0.10, 0.14])
GLASS_L = np.array([0.30, 0.42, 0.52])
RED = np.array([0.75, 0.08, 0.06])


def rect(dr, px, py, xa, xb, za, zb, fill=None, outline=None, width=1):
    """PIL rectangle 归一化: 传世界坐标 x∈[xa,xb] z∈[za,zb]"""
    x0, x1 = min(px(xa), px(xb)), max(px(xa), px(xb))
    y0, y1 = min(py(za), py(zb)), max(py(za), py(zb))
    dr.rectangle([x0, y0, x1, y1], fill=fill, outline=outline, width=width)


def save(img, name):
    Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8)) \
        .save(os.path.join(OUT, name))
    print("saved", name)


def paint(h, w):
    img = base = np.tile(np.linspace(1.0, 0.0, h)[:, None, None] *
                         (WHITE * 0.15) + WHITE * 0.88, (1, w, 1))
    img = base + rng.random((h, w, 1)) * 0.01 - 0.005
    return img


def side():
    h, w = 1024, 2048
    px = lambda x: int((2.345 - x) / L * w)   # 车头 u=0 (右侧视角)
    py = lambda z: int((1 - z / H) * h)
    img = paint(h, w)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    # 窗区 (前窗 + 后窗, B 柱 x 0.05..0.16 车身色) — 侧面 z 上限 1.30/1.38
    win_front = [(px(1.02), py(1.03)), (px(0.78), py(1.27)),
                 (px(0.16), py(1.29)), (px(0.16), py(1.03))]
    win_rear = [(px(0.05), py(1.03)), (px(0.05), py(1.29)),
                (px(-0.62), py(1.30)), (px(-0.92), py(1.03))]
    for poly in (win_front, win_rear):
        dr.polygon(poly, fill=tuple(int(v) for v in (GLASS * 255)))
    # 玻璃斜反光 (只在窗内)
    mask_im = Image.new("L", (w, h), 0)
    for poly in (win_front, win_rear):
        ImageDraw.Draw(mask_im).polygon(poly, fill=255)
    m = np.asarray(mask_im, bool)
    xs = np.linspace(2.345, -2.345, w)
    for off, amp in ((0.0, 0.16), (0.13, 0.09)):
        s = (xs[None, :] / L * 1.6 + np.arange(h)[:, None] / h * 0.9 - off) % 1.0
        band = np.exp(-((s - 0.85) / 0.035) ** 2) * amp
        img = img + np.where(m[:, :, None], band[:, :, None] * GLASS_L, 0.0)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    # beltline 镀铬 + 下裙板 + 折线
    dr.line([(0, py(1.03)), (w, py(1.03))], fill=(200, 205, 210), width=3)
    rect(dr, px, py, -2.345, 2.345, 0.44, 0.30,
         fill=tuple(int(v) for v in (BLACK * 255)))
    dr.line([(0, py(0.60)), (w, py(0.60))], fill=(150, 152, 155), width=2)
    # 门缝 (A/B/C 柱) + 门把手
    for xs_, wd in ((0.98, 2), (0.08, 3), (-0.90, 2)):
        dr.line([(px(xs_), py(1.02)), (px(xs_), py(0.44))],
                fill=(60, 62, 65), width=wd)
    for hx in (0.70, -0.52):
        dr.rectangle([px(hx) - 26, py(0.99), px(hx) + 26, py(0.955)],
                     fill=(40, 42, 45))
    # 轮拱暗腔 (轴心 x=±1.45, z=0.33, r≈0.43)
    for wx in (1.45, -1.45):
        cx, cy = px(wx), py(0.33)
        rx, ry = int(0.44 * w / L), int(0.44 * h / H)
        dr.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(12, 12, 14))
    save(np.asarray(im, dtype=np.float64) / 255, "side.png")


def front():
    h, w = 1024, 1024
    px = lambda y: int((y + W / 2) / W * w)
    py = lambda z: int((1 - z / H) * h)
    img = paint(h, w)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    # 前风挡 (斜面 z1.20..1.44 归 front 贴图, y±0.745)
    rect(dr, px, py, -0.745, 0.745, 1.44, 1.20,
         fill=tuple(int(v) for v in (GLASS * 255)))
    rect(dr, px, py, -0.76, 0.76, 1.44, 1.20, None,
         outline=(215, 218, 222), width=3)
    # 贯穿式 LED 前灯
    rect(dr, px, py, -0.86, 0.86, 0.91, 0.845, None,
         outline=(30, 30, 32), width=2)
    rect(dr, px, py, -0.84, 0.84, 0.90, 0.855, fill=(235, 245, 255))
    # 黑色下区 + 进气口 + 车牌
    rect(dr, px, py, -0.90, 0.90, 0.52, 0.30,
         fill=tuple(int(v) for v in (BLACK * 255)))
    rect(dr, px, py, -0.55, 0.55, 0.44, 0.40, fill=(25, 25, 28))
    rect(dr, px, py, -0.24, 0.24, 0.47, 0.33,
         fill=(245, 245, 240), outline=(30, 30, 30))
    f = ImageFont.truetype(FONT, 30)
    s = "京A·D3888"
    dr.text(((w - dr.textlength(s, font=f)) / 2, py(0.455) - 28), s,
            font=f, fill=(20, 20, 20))
    save(np.asarray(im, dtype=np.float64) / 255, "front.png")


def rear():
    h, w = 1024, 1024
    px = lambda y: int((W / 2 - y) / W * w)
    py = lambda z: int((1 - z / H) * h)
    img = paint(h, w)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    # 后风挡 (斜面 z1.32..1.44 归 rear 贴图, y±0.745)
    rect(dr, px, py, -0.745, 0.745, 1.44, 1.32,
         fill=tuple(int(v) for v in (GLASS * 255)))
    rect(dr, px, py, -0.76, 0.76, 1.44, 1.32, None,
         outline=(215, 218, 222), width=3)
    # 尾灯 (L 形红 + 中央暗带)
    for sgn in (-1, 1):
        rect(dr, px, py, sgn * 0.40, sgn * 0.86, 0.92, 0.84,
             fill=tuple(int(v) for v in (RED * 255)))
        rect(dr, px, py, sgn * 0.80, sgn * 0.86, 0.84, 0.62,
             fill=tuple(int(v) for v in (RED * 0.85)))
    rect(dr, px, py, -0.38, 0.38, 0.90, 0.875, fill=(25, 25, 27))
    # 黑色下区 (扩散器) + 车牌
    rect(dr, px, py, -0.90, 0.90, 0.50, 0.30,
         fill=tuple(int(v) for v in (BLACK * 255)))
    rect(dr, px, py, -0.24, 0.24, 0.46, 0.32,
         fill=(245, 245, 240), outline=(30, 30, 30))
    f = ImageFont.truetype(FONT, 30)
    s = "京A·D3888"
    dr.text(((w - dr.textlength(s, font=f)) / 2, py(0.445) - 28), s,
            font=f, fill=(20, 20, 20))
    save(np.asarray(im, dtype=np.float64) / 255, "rear.png")


def roof():
    """顶面 (nz 主导): 投影 u=(y+0.925)/1.85, v=(x+2.345)/4.69
    顶面 x∈[-1.145,1.045] z≈1.42..1.44 y∈±0.745 → v∈[0.259,0.719] u∈[0.068,0.932]
    画全景玻璃顶 + 白边框"""
    h, w = 512, 1024
    img = paint(h, w)
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    px = lambda x: int((x + 2.345) / L * w)
    py = lambda y: int((y + W / 2) / W * h)
    gl = tuple(int(v) for v in (GLASS * 255))
    # 全景玻璃顶 (x -1.145..1.045, y ±0.745)
    dr.rectangle([px(-1.145), py(-0.745), px(1.045), py(0.745)], fill=gl)
    dr.rectangle([px(-1.145), py(-0.745), px(1.045), py(0.745)],
                 outline=(215, 218, 222), width=3)
    # 玻璃反光
    xs = np.linspace(-2.345, 2.345, w)
    s = (xs[None, :] / L * 1.2 + np.arange(h)[:, None] / h * 0.5) % 1.0
    band = np.exp(-((s - 0.85) / 0.06) ** 2) * 0.10
    img = np.asarray(im, dtype=np.float64) / 255
    dark = (img.sum(axis=2, keepdims=True) < 0.5)
    img = img + band[:, :, None] * GLASS_L * dark
    save(img, "roof.png")


def wheel():
    n = 512
    cy = cx = n // 2
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / (n / 2)
    img = np.zeros((n, n, 3))
    img += 0.04
    band = np.zeros((n, n), bool)
    band[0:84, :] = True
    u = X / n
    block = ((u * 24) % 1.0) < 0.55
    img[band & block] = 0.20
    img[band & ~block] = 0.05
    img[(r < 0.5)] = 0.10
    img[(r > 0.40) & (r < 0.50)] = 0.12
    img[(r < 0.40)] = 0.58
    ang = np.arctan2(Y - cy, X - cx)
    # 涡轮 5 辐
    spoke = ((r < 0.40) &
             (np.abs((((ang / (2 * np.pi)) * 5 + 0.05 * r) % 1.0) - 0.5) > 0.36) &
             (r > 0.12))
    img[spoke] = 0.28
    for i in range(5):
        a = i * 2 * np.pi / 5 + 0.4
        bx, by = cx + 0.22 * (n / 2) * np.cos(a), cy + 0.22 * (n / 2) * np.sin(a)
        m = (X - bx) ** 2 + (Y - by) ** 2 < (0.032 * (n / 2)) ** 2
        img[m] = 0.85
    img[r < 0.10] = 0.42
    img[r < 0.05] = 0.22
    Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8)) \
        .save(os.path.join(OUT, "wheel.png"))
    print("saved wheel.png")


side()
front()
rear()
roof()
wheel()
print("TEXTURES_DONE ->", OUT)
