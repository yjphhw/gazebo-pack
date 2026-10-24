# -*- coding: utf-8 -*-
"""gen_bus_textures.py — 程序化生成公交贴图 (系统 python3 跑, 需 numpy+PIL)
运行: python3 assets/bus/gen_bus_textures.py
产出: assets/bus/textures/{side_R,side_L,front,rear,wheel}.png
约定: 建模坐标 Z-up, 车头 +X, 车底 z=0; 尺寸 10.5(X) × 2.5(Y) × 3.05(Z)
      侧面 UV: 右(u=(5.25-x)/10.5) 左(u=(x+5.25)/10.5), v=z/3.05
      前面 UV: u=(y+1.25)/2.5, v=z/3.05;  后面: u=(1.25-y)/2.5
      车轮: 面(cap) u=0.5+(x-xc)/0.9 v=0.5+(z-zc)/0.9; 胎面 u=角度 v=0.836..1.0
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261024)
FONT = "/usr/share/fonts/truetype/hw/NotoSansSC-VF.ttf"

L, W, H = 10.5, 2.5, 3.05          # 长宽高
ZWIN_B, ZWIN_T = 1.72, 2.56        # 车窗 z 范围
BAND_B, BAND_T = 1.02, 1.58        # 蓝色腰线 z 范围
WHEELS = [(3.1, 0.45), (-3.1, 0.45)]  # (x, z 轴心)

BLUE = np.array([0.09, 0.33, 0.62])
BLUE_D = np.array([0.05, 0.20, 0.40])
WHITE = np.array([0.94, 0.95, 0.96])
DARK = np.array([0.13, 0.14, 0.15])
GLASS = np.array([0.10, 0.15, 0.22])
GLASS_L = np.array([0.28, 0.42, 0.55])
GREY_BUMPER = np.array([0.22, 0.23, 0.25])
RED = np.array([0.72, 0.12, 0.10])


def base_grad(h, w, top, bot):
    t = np.linspace(1.0, 0.0, h)[:, None]
    return np.tile(np.linspace(bot, top, h)[:, None, None] * np.ones((1, w, 3)), (h, 1, 1)) \
        if False else (bot[None, None, :] + (top - bot)[None, None, :] * t[:, :, None]) * \
        np.ones((h, w, 1))


def noise(h, w, amp=0.02):
    return rng.random((h, w, 1)) * amp - amp / 2


def rect(px_img, x0, x1, z0, z1, color, x_to_px, z_to_py):
    a, b = sorted((int(x_to_px(x0)), int(x_to_px(x1))))
    c, d = sorted((int(z_to_py(z0)), int(z_to_py(z1))))
    px_img[c:d, a:b] = color


def ell(x_to_px, z_to_py, cx, cz, rx, rz, img_h, img_w):
    """世界坐标椭圆 mask (True=内部)"""
    u = np.arange(img_w) / img_w
    v = np.arange(img_h) / img_h
    xs = np.linspace(5.25, -5.25, img_w)           # 侧面: px 左→右 = x +→-
    ys = np.linspace(H, 0.0, img_h)
    X, Y = np.meshgrid(xs, ys)
    return ((X - cx) / rx) ** 2 + ((Y - cz) / rz) ** 2 <= 1.0


def window_row(img, doors, x_to_px, z_to_py, h, w):
    """在 img 上画一排车窗: 深色玻璃+斜反光+白框"""
    for (x0, x1) in doors:
        rect(img, x0, x1, ZWIN_B, ZWIN_T, GLASS, x_to_px, z_to_py)
    # 斜反光 (只在车窗高度)
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    xs = np.linspace(5.25, -5.25, w)
    zs = np.linspace(H, 0.0, h)
    m = (xs[None, :] - (-1.5)) / 10.5 * 4 - (np.arange(h)[:, None] / h) * 1.6
    streak = np.clip(0.12 * np.exp(-(((m % 1.0) - 0.15) / 0.10) ** 2), 0, 0.12)
    winband = ((zs[:, None] > ZWIN_B - 0.05) & (zs[:, None] < ZWIN_T + 0.05))
    img = img + (streak * winband)[:, :, None]
    return img


def side(side):
    h, w = 1024, 2048
    # px: 左→右 = 车头→车尾 (两侧纹理各自方向不同, 用 x_to_px 统一)
    if side == "R":
        x_to_px = lambda x: int((5.25 - x) / L * w)
        doors = [(3.30, 4.35), (-0.75, 0.80)]      # 前双开门 + 中双开门 (右侧)
        wins = [(0.95, 1.95), (2.15, 3.15),
                (-4.95, -3.80), (-3.52, -2.37), (-2.09, -0.94)]
    else:
        x_to_px = lambda x: int((x + 5.25) / L * w)
        doors = [(3.40, 4.35)]                     # 仅驾驶门 (左侧)
        wins = [(0.30, 1.45), (1.65, 2.80),
                (-4.95, -3.80), (-3.52, -2.37), (-2.09, -0.94)]
    z_to_py = lambda z: int((1.0 - z / H) * h)

    img = base_grad(h, w, WHITE * 1.02, WHITE * 0.96)
    img = img + noise(h, w, 0.015)
    # 底部裙边 z<0.55 深灰; 保险杠区 (车头 x>4.8) 深灰+红线
    rect(img, -5.25, 5.25, 0.0, 0.55, GREY_BUMPER * 0.8, x_to_px, z_to_py)
    rect(img, 4.80, 5.25, 0.0, 0.55, GREY_BUMPER, x_to_px, z_to_py)
    rect(img, 4.80, 5.25, 0.50, 0.55, RED, x_to_px, z_to_py)
    rect(img, -5.25, -4.80, 0.50, 0.55, RED, x_to_px, z_to_py)
    # 轮拱暗腔 (与 3D 轮拱对齐: 轴心 x=±3.1 z=0.45 r=0.52)
    for wx, wz in WHEELS:
        m = ell(x_to_px, z_to_py, wx, 0.50, 0.56, 0.56, h, w)
        img[m] = DARK * 0.85
    # 腰线
    rect(img, -5.25, 5.25, BAND_B, BAND_T, BLUE, x_to_px, z_to_py)
    rect(img, -5.25, 5.25, BAND_T, BAND_T + 0.035, BLUE_D, x_to_px, z_to_py)
    # 车窗
    img = window_row(img, wins, x_to_px, z_to_py, h, w)
    # 车窗白框
    for (x0, x1) in wins:
        rect(img, x0, x1, ZWIN_B - 0.025, ZWIN_B, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x0, x1, ZWIN_T, ZWIN_T + 0.025, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x0, x0 + 0.025, ZWIN_B, ZWIN_T, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x1 - 0.025, x1, ZWIN_B, ZWIN_T, WHITE * 0.9, x_to_px, z_to_py)
    # 车门 (双扇: 中缝 + 玻璃 + 深色下板 + 门槛)
    for (x0, x1) in doors:
        rect(img, x0, x1, 0.55, ZWIN_T, WHITE * 0.98, x_to_px, z_to_py)
        rect(img, x0, x1, ZWIN_B, ZWIN_T, GLASS, x_to_px, z_to_py)
        xc = (x0 + x1) / 2
        rect(img, xc - 0.015, xc + 0.015, 0.55, ZWIN_T, DARK * 1.2, x_to_px, z_to_py)
        rect(img, x0, x1, ZWIN_B - 0.025, ZWIN_B, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x0, x1, ZWIN_T, ZWIN_T + 0.025, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x0, x0 + 0.03, ZWIN_B, ZWIN_T, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x1 - 0.03, x1, ZWIN_B, ZWIN_T, WHITE * 0.9, x_to_px, z_to_py)
        rect(img, x0 + 0.04, x1 - 0.04, 0.55, 0.72, DARK * 1.1, x_to_px, z_to_py)
    # 线路上方站牌 (门上方)
    for (x0, x1) in doors:
        rect(img, x0 + 0.05, x1 - 0.05, ZWIN_T + 0.06, ZWIN_T + 0.24,
             np.array([0.98, 0.93, 0.30]), x_to_px, z_to_py)
    # 车身细缝线 (腰线以下的装饰线)
    rect(img, -5.25, 5.25, 0.90, 0.92, DARK * 0.7, x_to_px, z_to_py)

    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    f_cn = ImageFont.truetype(FONT, 88)
    f_cn_s = ImageFont.truetype(FONT, 40)
    f_num = ImageFont.truetype(FONT, 120)
    # 腰线文字: 城市公交 CITY BUS
    def tx(world_x, z, s, font, fill):
        px = x_to_px(world_x)
        py = z_to_py(z)
        dr.text((px - dr.textlength(s, font=font) / 2, py - font.size), s,
                font=font, fill=fill)
    if side == "R":
        tx(-2.6, 1.52, "城市公交", f_cn, (255, 255, 255))
        tx(-2.6, 1.12, "CITY BUS", f_cn_s, (200, 220, 255))
    else:
        tx(-2.6, 1.52, "城市公交", f_cn, (255, 255, 255))
        tx(-2.6, 1.12, "CITY BUS", f_cn_s, (200, 220, 255))
    # 门上线路号 108
    for (x0, x1) in doors:
        s = "108"
        f = f_num
        px = x_to_px((x0 + x1) / 2)
        py = z_to_py(2.50)
        dr.text((px - dr.textlength(s, font=f) / 2, py - f.size), s,
                font=f, fill=(255, 235, 60))
    im.save(os.path.join(OUT, f"side_{side}.png"))
    print("saved side_%s.png" % side)


def front():
    h, w = 1024, 1024
    u_to_y = lambda u: -1.25 + u * W
    x_to_px = lambda y: int((y + 1.25) / W * w)     # u=(y+1.25)/2.5
    z_to_py = lambda z: int((1.0 - z / H) * h)
    img = base_grad(h, w, WHITE * 1.02, WHITE * 0.95)
    img = img + noise(h, w, 0.015)
    # 保险杠 (3D 保险杠 z 0.2..0.7, |y|<1.15)
    rect(img, -1.25, 1.25, 0.0, 0.55, GREY_BUMPER * 0.85, x_to_px, z_to_py)
    rect(img, -1.15, 1.15, 0.55, 0.70, GREY_BUMPER, x_to_px, z_to_py)
    rect(img, -1.15, 1.15, 0.70, 0.74, RED, x_to_px, z_to_py)
    # 挡风玻璃
    rect(img, -1.02, 1.02, 1.85, 2.78, GLASS, x_to_px, z_to_py)
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    u = xx / w
    slant = (u * 2.2 - (np.arange(h) / h) * 1.2 - 0.35)
    zs = np.linspace(H, 0.0, h)
    m = (np.abs(slant % 1.0 - 0.15) < 0.06) & \
        (zs[:, None] > 1.85) & (zs[:, None] < 2.78)
    img[m] = GLASS_L * 0.9
    # 玻璃框
    rect(img, -1.06, 1.06, 1.82, 1.86, DARK, x_to_px, z_to_py)
    rect(img, -1.06, 1.06, 2.78, 2.82, DARK, x_to_px, z_to_py)
    rect(img, -1.06, -1.02, 1.85, 2.78, DARK, x_to_px, z_to_py)
    rect(img, 1.02, 1.06, 1.85, 2.78, DARK, x_to_px, z_to_py)
    # LED 线路牌 (车顶折角内 z 2.72..2.78)
    rect(img, -0.90, 0.90, 2.72, 2.78, np.array([0.05, 0.05, 0.05]),
         x_to_px, z_to_py)
    # 大灯 (两侧): 先框后玻璃后高光
    for sy in (-1, 1):
        rect(img, sy * 0.55 - 0.32, sy * 0.55 + 0.32, 0.74, 1.00, DARK * 0.9,
             x_to_px, z_to_py)
        rect(img, sy * 0.55 - 0.28, sy * 0.55 + 0.28, 0.78, 0.96,
             np.array([0.85, 0.90, 0.97]), x_to_px, z_to_py)
        img[int(z_to_py(0.94)):int(z_to_py(0.84)),
            int(x_to_px(sy * 0.55 - 0.22)):int(x_to_px(sy * 0.55 + 0.22))] = \
            np.array([0.97, 0.99, 1.0])
    # 中缝 (前门合页线)
    rect(img, -0.012, 0.012, 0.70, 1.85, DARK * 0.8, x_to_px, z_to_py)

    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    f_led = ImageFont.truetype(FONT, 52)
    s = "108  市中心"
    px = w // 2 - dr.textlength(s, font=f_led) / 2
    dr.text((px, z_to_py(2.955) - 52), s, font=f_led, fill=(255, 210, 40))
    f_pl = ImageFont.truetype(FONT, 34)
    s = "京A·D8888"
    dr.rectangle([w // 2 - 95, z_to_py(0.42), w // 2 + 95, z_to_py(0.20)],
                 fill=(245, 245, 240), outline=(30, 30, 30))
    dr.text((w // 2 - dr.textlength(s, font=f_pl) / 2, z_to_py(0.40) - 34),
            s, font=f_pl, fill=(20, 20, 20))
    im.save(os.path.join(OUT, "front.png"))
    print("saved front.png")


def rear():
    h, w = 1024, 1024
    x_to_px = lambda y: int((1.25 - y) / W * w)    # u=(1.25-y)/2.5
    z_to_py = lambda z: int((1.0 - z / H) * h)
    img = base_grad(h, w, WHITE * 1.02, WHITE * 0.95)
    img = img + noise(h, w, 0.015)
    rect(img, -1.25, 1.25, 0.0, 0.55, GREY_BUMPER * 0.85, x_to_px, z_to_py)
    rect(img, -1.15, 1.15, 0.55, 0.70, GREY_BUMPER, x_to_px, z_to_py)
    # 后窗
    rect(img, -0.95, 0.95, 1.70, 2.55, GLASS, x_to_px, z_to_py)
    yy, xx = np.meshgrid(np.arange(h), np.arange(w), indexing="ij")
    slant = ((xx / w) * 2.0 - (np.arange(h) / h) * 1.1 - 0.3)
    m = (np.abs(slant % 1.0 - 0.15) < 0.05) & (np.arange(h)[:, None] / h < 0.85)
    img[m] = GLASS_L * 0.85
    rect(img, -0.99, 0.99, 1.67, 1.71, DARK, x_to_px, z_to_py)
    rect(img, -0.99, 0.99, 2.55, 2.59, DARK, x_to_px, z_to_py)
    rect(img, -0.99, -0.95, 1.70, 2.55, DARK, x_to_px, z_to_py)
    rect(img, 0.95, 0.99, 1.70, 2.55, DARK, x_to_px, z_to_py)
    # LED
    rect(img, -0.95, 0.95, 2.72, 2.82, np.array([0.05, 0.05, 0.05]), x_to_px, z_to_py)
    # 尾灯 (竖直红白)
    for sy in (-1, 1):
        rect(img, sy * 1.02 - 0.13, sy * 1.02 + 0.13, 0.62, 1.55,
             np.array([0.85, 0.10, 0.08]), x_to_px, z_to_py)
        rect(img, sy * 1.02 - 0.13, sy * 1.02 + 0.13, 0.62, 0.80,
             np.array([0.95, 0.95, 0.92]), x_to_px, z_to_py)
        rect(img, sy * 1.02 - 0.15, sy * 1.02 + 0.15, 0.60, 1.57,
             DARK * 0.9, x_to_px, z_to_py)
    # 后门缝 (检修门)
    rect(img, -0.012, 0.012, 0.70, 1.60, DARK * 0.8, x_to_px, z_to_py)

    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    f_led = ImageFont.truetype(FONT, 44)
    s = "108"
    dr.text((w // 2 - dr.textlength(s, font=f_led) / 2, z_to_py(2.81) - 44),
            s, font=f_led, fill=(255, 210, 40))
    f_pl = ImageFont.truetype(FONT, 34)
    s = "京A·D8888"
    dr.rectangle([w // 2 - 95, z_to_py(0.46), w // 2 + 95, z_to_py(0.24)],
                 fill=(245, 245, 240), outline=(30, 30, 30))
    dr.text((w // 2 - dr.textlength(s, font=f_pl) / 2, z_to_py(0.44) - 34),
            s, font=f_pl, fill=(20, 20, 20))
    im.save(os.path.join(OUT, "rear.png"))
    print("saved rear.png")


def wheel():
    n = 512
    cy = cx = n // 2
    X, Y = np.meshgrid(np.arange(n), np.arange(n))
    r = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2) / (n / 2)   # 0..~1.4 (UV 半径)
    img = np.zeros((n, n, 3))
    img += 0.04                                   # 底: 黑
    # ── 胎面条带 (v 0.836..1.0 → y_px 0..84, u=绕轴角度, 周期 24 块) ──
    band = np.zeros((n, n), bool)
    band[0:84, :] = True
    u = X / n
    block = ((u * 24) % 1.0) < 0.55
    img[band & block] = 0.22
    img[band & ~block] = 0.05
    # ── 侧面可见圆盘 (cap, UV 半径 <0.5 = 世界 r0.45/0.9) ──
    disc = r < 0.5
    img[disc] = 0.10                              # 胎 (最外圈)
    sw = (r > 0.40) & (r < 0.50)                  # 胎侧
    img[sw] = 0.12
    rim = r < 0.40                                # 银色轮毂
    img[rim] = 0.62
    ang = np.arctan2(Y - cy, X - cx)
    spoke = rim & (np.abs(((ang / (2 * np.pi)) * 6) % 1.0 - 0.5) > 0.40) & (r > 0.14)
    img[spoke] = 0.30                             # 6 辐条暗缝
    for i in range(6):                            # 螺栓圈
        a = i * 2 * np.pi / 6 + 0.3
        bx, by = cx + 0.24 * (n / 2) * np.cos(a), cy + 0.24 * (n / 2) * np.sin(a)
        m = (X - bx) ** 2 + (Y - by) ** 2 < (0.035 * (n / 2)) ** 2
        img[m] = 0.88
    img[r < 0.10] = 0.45                          # 中心盖
    img[r < 0.05] = 0.25
    Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8)) \
        .save(os.path.join(OUT, "wheel.png"))
    print("saved wheel.png")


side("R")
side("L")
front()
rear()
wheel()
print("TEXTURES_DONE ->", OUT)
