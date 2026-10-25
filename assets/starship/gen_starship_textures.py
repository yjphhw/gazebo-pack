# -*- coding: utf-8 -*-
"""gen_starship_textures.py — 星舰 Skin 纹理 (numpy+PIL, 系统 python3)
运行: python3 assets/starship/gen_starship_textures.py
产出: textures/skin.png
UV 约定: 圆柱投影 u=atan2(y,x)/2π+0.5 (u0 在 +X 方位), v=z/121 (v0 底部 z=0)
参考外观 (Starship 2024 级): 不锈钢银色体 + 焊缝竖线, 贮箱环横线,
  尾部黑色烟熏, 整流罩黑色防热瓦 (方格), Ship 段 "SPACEX" 大字
尺寸: 直径 9m (周长 28.27m) × 高 121m → 纹理 2048×8192 (约 72px/m 周长向)
"""
import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "textures")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(71023)
FONT = "/usr/share/fonts/truetype/hw/NotoSansSC-VF.ttf"

H = 121.0          # 总高
D = 9.0            # 直径
W = np.pi * D      # 周长 28.27
w_px, h_px = 2048, 8192
pxm_u = w_px / W   # px/米 环向
pxm_v = h_px / H   # px/米 高向

py = lambda z: int((1 - z / H) * h_px)          # z → 行
pu = lambda a: int(((a / (2 * np.pi)) % 1.0) * w_px)  # 弧度方位 → 列


def steel_base():
    """不锈钢: 每列随机亮度(钢板条) + 大平面反光渐变 + 噪点"""
    img = np.zeros((h_px, w_px, 3))
    cols = rng.random(w_px) * 0.10 + 0.62           # 每条钢卷色差
    cols = np.convolve(cols, np.ones(24) / 24, mode="same")  # 平滑成宽条
    img += cols[None, :, None]
    # 高向: 下暗上亮
    g = np.linspace(0.82, 1.06, h_px)[:, None, None]
    img *= g
    # 两道高光带 (抛光反射)
    xs = np.linspace(0, 2 * np.pi, w_px)[None, :]
    for a0, amp, sig in ((-0.5, 0.35, 0.25), (2.2, 0.22, 0.30)):
        img += amp * np.exp(-((xs - a0) / sig) ** 2)[:, :, None]
    img += rng.random((h_px, w_px, 1)) * 0.02 - 0.01
    return img


def draw(img):
    im = Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8))
    dr = ImageDraw.Draw(im)
    BLACK = (18, 19, 22)
    DK = (40, 42, 46)
    # ---- 贮箱环缝横线: 每 10m 一条细暗线; 每 2m 极淡 ----
    for z in range(4, 105, 2):
        alpha = 0.55 if z % 10 == 0 else 0.15
        c = int(150 * (1 - alpha) + 45)
        dr.line([(0, py(z)), (w_px, py(z))], fill=(c, c, int(c * 1.05)))
    # ---- 级间段: z 68..71.5 深色环带 ----
    dr.rectangle([0, py(71.5), w_px, py(68)], fill=DK)
    # ---- 尾段烟熏: 0..7m 黑→灰渐变 ----
    for i, z in enumerate(np.linspace(0, 7, 60)):
        v = int(20 + (z / 7) ** 1.6 * 110)
        dr.line([(0, py(z)), (w_px, py(z))], fill=(v, v, v + 4))
    # ---- 鼻锥防热瓦: z>=105.6 黑瓦方格 ----
    tile = 0.28                                   # m
    z0, z1 = 105.6, 121
    for zz in np.arange(z0, z1, tile):
        r_y0, r_y1 = py(zz + tile), py(zz)
        for k in range(0, w_px, 18):
            shade = int(10 + rng.random() * 30)
            dr.rectangle([k, r_y0, k + 17, r_y1], fill=(shade, shade, shade + 2))
    # 瓦缝: 纵向浅线
    for k in range(0, w_px, 18):
        dr.line([(k, py(z1)), (k, py(z0))], fill=(70, 72, 76), width=1)
    # 整流罩基部白色环带 (瓦与钢交界)
    dr.rectangle([0, py(105.9), w_px, py(105.3)], fill=(205, 208, 212))
    # ---- SPACEX 大字 (Ship 尾段, z 78..90, 朝相机方位 u≈0.91) ----
    fs = int(11 * pxm_v)                          # 字高约 11m
    f = ImageFont.truetype(FONT, fs)
    txt = "SPACEX"
    tw = dr.textlength(txt, font=f)
    cx = pu(2 * np.pi * 0.91)
    cy = py(88)
    dr.text((cx - tw / 2, cy), txt, font=f, fill=(58, 62, 70))
    # logo X (小, 字下方)
    f2 = ImageFont.truetype(FONT, int(4.5 * pxm_v))
    t2 = "✕"
    dr.text((cx - dr.textlength(t2, font=f2) / 2, py(76)), t2, font=f2,
            fill=(58, 62, 70))
    # ---- 前襟翼安装座黑块 (±X 方位, z 99..103.5) ----
    for a in (0.0, np.pi):
        cx2 = pu(a)
        dr.rectangle([cx2 - 24, py(103.5), cx2 + 24, py(99)], fill=BLACK)
    return np.asarray(im, dtype=np.float64) / 255


img = draw(steel_base())
Image.fromarray((np.clip(img, 0, 1) * 255).round().astype(np.uint8)) \
    .save(os.path.join(OUT, "skin.png"))
print("saved skin.png", img.shape)
print("TEXTURES_DONE ->", OUT)
