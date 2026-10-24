# -*- coding: utf-8 -*-
"""
make_cabin_textures.py — 程序化生成小木屋贴图 (可平铺, 512px)
运行: /tmp/pptenv/bin/python make_cabin_textures.py   (需要 numpy + pillow)
产出: assets/cabin/textures/{plank,shingle,stone,glass,door}.png

设计配合 make_cabin.py 的 "世界坐标 box 投影 UV":
  贴图在纹理空间可平铺 → UV(tile 周期=世界尺寸) 后, 木纹在所有墙面/山墙
  之间连续流动, 接缝无痕。每张图的注释标了 tile 周期对应的世界尺寸。
"""
import numpy as np
from PIL import Image
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "cabin", "textures")
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(20261023)
N = 512


def value_noise(size, cells, octaves=4, persistence=0.55):
    """可平铺的分形值噪声. 每层: cells×cells 随机网格, 双线性上采样到 size
    (用 PIL BICUBIC + 3x3 邻接采样保证 wrap 平铺无缝), 逐层叠半频."""
    from PIL import Image as I
    acc = np.zeros((size, size))
    amp = 1.0
    norm = 0.0
    for o in range(octaves):
        c = max(2, min(cells * (2 ** o), size))
        g = rng.random((c, c))
        # 平铺双线性: 复制 3x3 邻块取中心块 — wrap 边界自动连续
        tile = np.concatenate([np.concatenate([g] * 3, 0)] * 3, 1)
        im = I.fromarray((tile * 255).astype(np.uint8), "L")
        im = im.resize((c * 3 * 4, c * 3 * 4), I.BICUBIC)
        a = np.asarray(im, dtype=float) / 255.0
        k = c * 4                                     # 中心块 = 原 tile
        base = a[k:k + k, k:k + k]
        # base 尺寸 c*4 → 放大到 size (最近邻块尺寸向上取整; size 是 4 的幂即可整除)
        if base.shape[0] != size:
            im2 = I.fromarray((base * 255).astype(np.uint8), "L")
            im2 = im2.resize((size, size), I.BICUBIC)
            base = np.asarray(im2, dtype=float) / 255.0
        acc += base * amp
        norm += amp
        amp *= persistence
    acc /= norm
    return acc - acc.mean()


def save(arr, name):
    """float 0..1 RGBA/RGB → PNG"""
    a = np.clip(arr, 0, 1)
    if a.ndim == 2:
        a = np.stack([a] * 3, -1)
    Image.fromarray((a * 255).round().astype(np.uint8)).save(os.path.join(OUT, name))
    print("saved", name)


# ============ plank: 原木色横木板 (u=世界水平, v=世界竖直) ============
# tile 周期: 6 条板 ≈ 世界 0.5m (make_cabin 里 uv scale=2/m)
def plank():
    x, y = np.meshgrid(np.arange(N), np.arange(N))
    wood = value_noise(N, 3, 5)                       # 大块木纹明暗
    grain = np.sin((x * 0.06 + wood * 6.0)) * 0.06    # 横向细纹沿 u 流动
    base = np.array([0.60, 0.42, 0.27])
    img = np.ones((N, N, 3)) * base
    lum = (0.92 + wood * 0.22 + grain)[:, :, None]
    img = img * lum
    # 横板: 6 条, 缝在水平线 (v 方向); 每条板独立亮度/相位
    BH = N // 6
    for b in range(6):
        j0, j1 = b * BH, (b + 1) * BH
        tint = 0.90 + rng.random() * 0.16             # 每板亮度 0.90..1.06
        img[j0:j1] *= tint
        # 缝: 板交界处 2px 深线 + 下沿 1px 高光线
        img[(j1 - 2):j1] *= np.array([0.32, 0.24, 0.16])
        img[(j1 - 3):(j1 - 2)] *= np.array([1.12, 1.05, 0.95])
    yy = (y % BH).astype(float)
    seam = np.clip(1.0 - (N - yy - 1) / 3.0, 0, 1)     # 靠缝压暗
    img *= (1 - 0.28 * seam)[:, :, None]
    # 钉帽: 每条板两端 (u=0 附近与中心, 保证平铺): 深色圆+白高光
    for px, py in [(28, None), (N // 2, None), (N - 28, None)]:
        for b in range(6):
            py2 = b * BH + BH // 2
            r2 = ((x - px) ** 2 + (y - py2) ** 2)
            m = r2 < 3.5 ** 2
            img[m] = np.array([0.16, 0.13, 0.10])
            m2 = ((x - px - 1) ** 2 + (y - py2 - 1) ** 2) < 1.6 ** 2
            img[m2] = np.array([0.55, 0.52, 0.5])
    return img


# =fffffff=========== shingle: 深蓝灰瓦片屋顶 (周期: 竖 6 列 × 横 8 行 = 0.35m) ============
def shingle():
    x, y = np.meshgrid(np.arange(N), np.arange(N))
    base = np.array([0.34, 0.40, 0.48])
    CW, RH = N // 6, N // 8                            # 6 列 × 8 行
    row = (y // RH).astype(int)
    xr = (x - (row % 2) * (CW // 2)) % N               # 错缝: 奇数行半列偏移
    col = (xr // CW).astype(int) % 8                   # wrap 索引 (8 列容错缝)
    shades = rng.uniform(0.80, 1.15, (8, 8))
    img = np.ones((N, N, 3)) * base[None, None, :] * shades[row, col][:, :, None]
    tex = value_noise(N, 6, 5) * 0.16
    img *= (1.0 + tex)[:, :, None]
    # 瓦缝: 行底 3px 深影线 + 高位 1px 高光; 列左 2px 暗缝
    r_edge = (y % RH)
    c_edge = (xr % CW)
    img[r_edge >= RH - 3] *= np.array([0.48, 0.50, 0.54])
    img[r_edge == RH - 4] *= np.array([1.15, 1.15, 1.12])
    img[c_edge < 2] *= np.array([0.72, 0.74, 0.78])
    return img


# ============ stone: 灰蓝石砌基座/烟囱 (周期 0.6m, 6×4 块石) ============
def stone():
    x, y = np.meshgrid(np.arange(N), np.arange(N))
    img = np.ones((N, N, 3)) * np.array([0.52, 0.54, 0.56])
    # 30 个种子点 (环绕平铺): Voronoi 近似 = 每像素找最近点 → 每格一色
    # 26 个种子(环绕平铺): 每个像素归最近种子 → 一块石; 每块独立色
    seeds = rng.random((26, 2)) * N
    D = np.stack([
        (lambda dx, dy: dx * dx + dy * dy)(
            np.minimum(np.abs(x - sx), N - np.abs(x - sx)),
            np.minimum(np.abs(y - sy), N - np.abs(y - sy)))
        for sx, sy in seeds])
    order = np.argsort(D, axis=0)                      # (S, N, N)
    lab = order[0]                                     # 最近种子编号
    shades = rng.random(len(seeds))
    dmin = D[order[0], np.arange(N)[None, :], np.arange(N)[:, None]] \
        if False else np.take_along_axis(D, order[:1], 0)[0]
    d2nd = np.take_along_axis(D, order[1:2], 0)[0]
    stone_tint = 0.80 + shades[lab] * 0.36
    img = img * stone_tint[:, :, None]
    tex = value_noise(N, 8, 4) * 0.12
    img *= (1 + tex)[:, :, None]
    # 砂浆缝: 最近/次近距离差小 = 石块交界
    border = np.sqrt(d2nd) - np.sqrt(dmin)
    mortar = 1.0 - np.clip(border / 26.0, 0, 1.0)
    img = img * (1 - 0.45 * mortar[:, :, None]) + \
        np.array([0.62, 0.60, 0.55]) * (0.35 * mortar[:, :, None])
    return img


# ============ glass: 暖黄发光窗 (一扇窗=一整个 tile, 边框落在窗缘) ============
def glass():
    x, y = np.meshgrid(np.arange(N), np.arange(N))
    # 暖黄渐变 + 云絮 (室内灯光感)
    g = value_noise(N, 4, 4)
    lum = 0.86 + 0.14 * (y / N) + g * 0.10
    img = np.stack([(0.98 * lum), (0.80 * lum), (0.50 * lum)], -1)
    # 窗棂: 十字 + 外框 (深咖啡)
    frame = 26
    bars = 12
    m = (x < frame) | (x >= N - frame) | (y < frame) | (y >= N - frame)
    mx = np.abs(x - N // 2) < bars
    my = np.abs(y - N // 2) < bars
    frame_c = np.array([0.18, 0.12, 0.08])
    img[m] = frame_c
    img[mx] = frame_c
    img[my] = frame_c
    # 玻璃高光: 左上斜掠白光
    gl = np.clip(0.30 * np.exp(-(((x * 0.7 + y - 160) / 60.0) ** 2)), 0, 0.3)
    img += gl[:, :, None]
    return img


# ============ door: 深棕木门 (一扇=一 tile: 竖板+门把手+铆钉) ============
def door():
    x, y = np.meshgrid(np.arange(N), np.arange(N))
    img = np.ones((N, N, 3)) * np.array([0.34, 0.20, 0.12])
    wood = value_noise(N, 3, 5)
    grain = np.sin((x * 0.10 + wood * 7.0)) * 0.05
    img *= (0.94 + wood * 0.16 + grain)[:, :, None]
    # 竖板缝 5 条 (不平铺方向也无妨, 门只出现一次)
    for i in range(1, 5):
        cx = i * N // 5
        img[:, cx - 1:cx + 1] *= np.array([0.45, 0.40, 0.38])
    # 两道横向加固件
    for yy in (90, 380):
        img[yy:yy + 26, :] *= np.array([0.55, 0.52, 0.55])
        img[yy:yy + 2, :] *= 0.7
        img[yy + 25:yy + 27, :] *= 0.7
    # 门把手 (右侧中部圆环) 〜坐标 (x=428, y=256)
    r2 = (x - 428) ** 2 + (y - 256) ** 2
    ring = (r2 > 11 ** 2) & (r2 < 16 ** 2)
    img[ring] = np.array([0.75, 0.68, 0.50])
    img[(x - 434) ** 2 + (y - 256) ** 2 < 5 ** 2] = np.array([0.2, 0.18, 0.16])
    # 铰链 ×2 左侧
    for yy in (120, 350):
        img[yy:yy + 14, 0:70] = np.array([0.22, 0.20, 0.19]) * 0.9 + wood[yy:yy + 14, 0:70][:, :, None] * 0.1
    return img


save(plank(),   "plank.png")
save(shingle(), "shingle.png")
save(stone(),   "stone.png")
save(glass(),   "glass.png")
save(door(),    "door.png")
print("TEXTURES_DONE ->", OUT)
