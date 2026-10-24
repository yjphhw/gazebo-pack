#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_cabin.py — 小木屋资产包建模脚本 (MANIFEST_SPEC §2.1 / PACK_NOTES E6)

brief: 建模：小木屋，2×3×3m，精美贴图，1个动态，collision 默认
       (用户追加: optimization=convex_decomposition)
尺寸: 墙体内芯 X=2.0 Y=3.0 Z=3.0 (m); 含屋檐/屋脊/门窗外扩的实测 bbox
      由本脚本自检打印，并须抄入 manifest 的 geometry.size (V4 对账口径)
原点: center (frame.origin 默认, B2)
铁律:
  * 一个 MESH 对象 "cabin" → source/cabin.glb
  * 水密封闭流形 (C2/V7): 墙体/地板/屋顶/门窗真实相交后 BOOLEAN UNION(EXACT)
    (convex_decomposition 不豁免 V7 —— auto 惯量仍按体积积分)
  * 贴图用 numpy 烘成 png 并 pack (D4/D5), 不依赖程序化节点
用法:
  /snap/blender/current/blender --background --python assets/cabin/build_cabin.py
产物:
  assets/cabin/model.blend, assets/cabin/textures/*.png
"""

import os
import sys
import math

import bpy
import bmesh
from mathutils import Vector

try:
    import numpy as np
except ImportError:
    raise SystemExit("Blender 内置 Python 缺 numpy，本脚本依赖它烘贴图；"
                     "请换用官方发行版 Blender (自带 numpy)")

# ---------- 路径 (E2: 以 __file__ 为根, 不用 //) ----------
HERE = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(HERE, "textures")
os.makedirs(TEX_DIR, exist_ok=True)

# ---------- 目标尺寸 (m) ----------
SX, SY, SZ = 2.0, 3.0, 3.0
WALL_T = 0.12          # 墙厚
FLOOR_T = 0.15         # 地板厚
ROOF_T = 0.14          # 屋顶板厚
ROOF_OVERHANG = 0.22   # 屋檐外伸
RIDGE_H = 0.55         # 屋脊抬高(相对墙顶)

# ---------- 0. 清空重建 (E6: 幂等) ----------
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.context.scene.render.engine = "BLENDER_EEVEE"   # E1


# ============================================================
# 1. 贴图生成 (numpy → png, 256x256)
# ============================================================
def save_png(arr, path):
    """arr: (H,W,3) uint8 numpy 数组 → png (RGBA float 写入 Blender image)。"""
    h, w, _ = arr.shape
    img = bpy.data.images.new(os.path.basename(path), width=w, height=h)
    rgba = np.ones((h, w, 4), dtype=np.float32)
    rgba[:, :, :3] = arr.astype(np.float32) / 255.0
    rgba = rgba[::-1, :, :]                      # Blender pixels 行序自下而上
    img.pixels[:] = rgba.ravel().tolist()
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.images.remove(img)


def make_wood_texture(path, base=(150, 100, 60), plank_w=32, seed=7):
    """竖向木板 + 板缝暗线 + 木纹噪点。"""
    rng = np.random.default_rng(seed)
    H = W = 256
    yy, xx = np.mgrid[0:H, 0:W]
    plank = xx // plank_w
    per_plank = rng.integers(-14, 15, size=W // plank_w + 1)
    base_shift = per_plank[plank]
    grain = (18 * np.sin((xx % plank_w) * 0.7 + plank * 1.3)).astype(np.int32)
    noise = rng.integers(-6, 7, size=(H, W))
    ch = []
    for b in base:
        c = b + base_shift + grain + noise
        ch.append(np.clip(c, 0, 255).astype(np.uint8))
    arr = np.stack(ch, axis=-1)
    seam = (xx % plank_w) < 2
    arr[seam] = (arr[seam] // 2).astype(np.uint8)
    save_png(arr, path)


def make_roof_texture(path, base=(120, 40, 35), tile=32, seed=11):
    """交错瓦片: 弧形高光 + 瓦缝暗线。"""
    rng = np.random.default_rng(seed)
    H = W = 256
    yy, xx = np.mgrid[0:H, 0:W]
    row = yy // tile
    off = np.where(row % 2 == 0, 0, tile // 2)
    tx = (xx + off) % tile
    shade = (40 * np.sin(np.pi * tx / tile)).astype(np.int32)
    noise = rng.integers(-10, 11, size=(H, W))
    ch = []
    for k, b in enumerate(base):
        div = 1 if k == 0 else 2
        c = b + shade // div + noise
        ch.append(np.clip(c, 0, 255).astype(np.uint8))
    arr = np.stack(ch, axis=-1)
    seam = (yy % tile) < 2
    arr[seam] = (arr[seam] // 2).astype(np.uint8)
    save_png(arr, path)


def make_door_texture(path, base=(90, 55, 30), seed=3):
    """深色木门 + 门板框线 + 门把亮点。"""
    rng = np.random.default_rng(seed)
    H = W = 256
    arr = np.zeros((H, W, 3), dtype=np.int32)
    for k, b in enumerate(base):
        arr[:, :, k] = b + rng.integers(-8, 9, size=(H, W))
    arr = np.clip(arr, 0, 255)
    frame = (np.arange(W)[None, :] % 64 < 2) | (np.arange(H)[:, None] % 64 < 2)
    arr[frame] = arr[frame] // 2
    arr[120:136, 200:216] = (220, 200, 120)      # 门把
    save_png(arr.astype(np.uint8), path)


# ============================================================
# 2. 材质 (Principled + Image Texture, glTF 认)
# ============================================================
def make_material(name, png_path, rough=0.7):
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:                    # E3: 5.x 不建议裸写 use_nodes
        mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = rough
    tex = nt.nodes.new("ShaderNodeTexImage")
    img = bpy.data.images.load(png_path, check_existing=True)
    img.pack()                                   # D5
    tex.image = img
    tex.interpolation = "Closest"                # D1
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


tex_wood = os.path.join(TEX_DIR, "wood.png")
tex_roof = os.path.join(TEX_DIR, "roof.png")
tex_door = os.path.join(TEX_DIR, "door.png")
make_wood_texture(tex_wood)
make_roof_texture(tex_roof)
make_door_texture(tex_door)

MAT_WOOD = make_material("wood", tex_wood, 0.8)
MAT_ROOF = make_material("roof", tex_roof, 0.6)
MAT_DOOR = make_material("door", tex_door, 0.5)


# ============================================================
# 3. 几何: 实体块真实相交 (E5 第 8 坑), 布尔前挂好材质
#    坐标: 世界原点居中, Z ∈ [-SZ/2, +SZ/2]
#    最终整体归位 center 交给 blender_export.py
# ============================================================
def make_box(name, center, size, mat):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=center)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = size
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.data.materials.append(mat)                # 单槽, UNION 时按索引保留
    return ob


parts = []
z0 = -SZ / 2.0
z_floor_top = z0 + FLOOR_T
z_wall_top = SZ / 2.0 - ROOF_T - RIDGE_H * 0.3

# 地板 (略宽于墙, 形成基座)
parts.append(make_box("floor", (0, 0, z0 + FLOOR_T / 2),
                      (SX + 0.1, SY + 0.1, FLOOR_T), MAT_WOOD))

# 四墙: 前后墙横跨全长, 左右墙略长 2cm 插入, 保证真实相交
wall_h = z_wall_top - z_floor_top
wall_z = z_floor_top + wall_h / 2
parts.append(make_box("wall_front", (0, -SY / 2 + WALL_T / 2, wall_z),
                      (SX, WALL_T, wall_h), MAT_WOOD))
parts.append(make_box("wall_back", (0, SY / 2 - WALL_T / 2, wall_z),
                      (SX, WALL_T, wall_h), MAT_WOOD))
parts.append(make_box("wall_left", (-SX / 2 + WALL_T / 2, 0, wall_z),
                      (WALL_T, SY - 2 * WALL_T + 0.02, wall_h), MAT_WOOD))
parts.append(make_box("wall_right", (SX / 2 - WALL_T / 2, 0, wall_z),
                      (WALL_T, SY - 2 * WALL_T + 0.02, wall_h), MAT_WOOD))

# 屋顶: 两块斜板在屋脊相交
roof_half_span = SY / 2 + ROOF_OVERHANG
roof_len = SX + 2 * ROOF_OVERHANG
slope = math.atan2(RIDGE_H, roof_half_span)
slab_len = math.sqrt(roof_half_span ** 2 + RIDGE_H ** 2) + 0.10
for sign, nm in ((-1, "roof_a"), (1, "roof_b")):
    bpy.ops.mesh.primitive_cube_add(
        size=1.0,
        location=(0, sign * roof_half_span / 2, z_wall_top + RIDGE_H / 2))
    ob = bpy.context.active_object
    ob.name = nm
    ob.scale = (roof_len, slab_len, ROOF_T)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    ob.rotation_euler = (math.radians(-sign * math.degrees(slope)), 0, 0)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
    ob.data.materials.append(MAT_ROOF)
    parts.append(ob)

# 门: 前墙外表面凸出, 与墙相交
door_w, door_h = 0.8, 1.9
parts.append(make_box("door",
                      (0, -SY / 2 + WALL_T / 2 - 0.02, z_floor_top + door_h / 2),
                      (door_w, WALL_T + 0.06, door_h), MAT_DOOR))

# 窗: 左右墙各一, 与墙相交
win_w, win_h = 0.6, 0.7
for sx, tag in ((-1, "L"), (1, "R")):
    parts.append(make_box(f"win_{tag}",
                          (sx * (SX / 2 - WALL_T / 2 + 0.02), 0.4,
                           z_floor_top + wall_h * 0.62),
                          (WALL_T + 0.06, win_w, win_h), MAT_WOOD))

# ============================================================
# 4. UNION(EXACT) 合成单一外壳
#    EXACT 解算器保留各零件的面材质索引 → UNION 后材质槽合并
# ============================================================
bpy.ops.object.select_all(action="DESELECT")
base = parts[0]
bpy.context.view_layer.objects.active = base
for ob in parts[1:]:
    mod = base.modifiers.new("u", "BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"                          # E5
    mod.object = ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob, do_unlink=True)

cabin = base
cabin.name = "cabin"                              # E6: 对象名 == glb 主干

# 清理: 合并重复顶点 + 法线朝外 (E5)
bpy.ops.object.select_all(action="DESELECT")
cabin.select_set(True)
bpy.context.view_layer.objects.active = cabin
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=1e-6)
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# 材质槽合并去重 (UNION 后可能出现重复同名槽)
seen = {}
for i, slot in enumerate(cabin.material_slots):
    key = slot.material.name if slot.material else None
    if key in seen:
        for poly in cabin.data.polygons:
            if poly.material_index == i:
                poly.material_index = seen[key]
    else:
        seen[key] = i

# ============================================================
# 5. 自检: bbox 尺寸 + 水密 (与 gazebo_pack V4/V7 同口径)
#    尺寸口径 = 含屋檐/屋脊/门窗凸出的实测 bbox (选 A);
#    断言外扩量在合理上限内, 且每轴都不小于内芯 —— 而非"等于内芯"
# ============================================================
deps = bpy.context.evaluated_depsgraph_get()
ev = cabin.evaluated_get(deps)
me_ev = ev.to_mesh()
mins = Vector((1e18, 1e18, 1e18))
maxs = Vector((-1e18, -1e18, -1e18))
for v in me_ev.vertices:
    w = cabin.matrix_world @ v.co
    for k in range(3):
        mins[k] = min(mins[k], w[k])
        maxs[k] = max(maxs[k], w[k])
dims = maxs - mins
ev.to_mesh_clear()

bm = bmesh.new()
bm.from_mesh(cabin.data)
edge_face = {}
for f in bm.faces:
    for e in f.edges:
        edge_face[e] = edge_face.get(e, 0) + 1
opening = sum(1 for n in edge_face.values() if n != 2)
bm.free()

ext_x = dims.x - SX
ext_y = dims.y - SY
ext_z = dims.z - SZ
print(f"[自检] bbox = {dims.x:.4f} x {dims.y:.4f} x {dims.z:.4f} m  "
      f"(内芯 {SX} x {SY} x {SZ})")
print(f"[自检] 外扩 X={ext_x:+.4f} Y={ext_y:+.4f} Z={ext_z:+.4f} m "
      f"(上限 0.60/0.75/0.50)")
print(f"[自检] 水密: 非2面边 = {opening}  (0 = 封闭流形)")

ok = (opening == 0
      and -0.01 <= ext_x <= 0.60
      and -0.01 <= ext_y <= 0.75
      and -0.01 <= ext_z <= 0.50)
if not ok:
    print("[失败] 自检不通过", file=sys.stderr)
    raise SystemExit(1)

print(f"[提示] 把上面 bbox 三个数抄进 manifest 的 geometry.size, 例如:")
print(f"       size: [{dims.x:.4f}, {dims.y:.4f}, {dims.z:.4f}]")

# ============================================================
# 6. 保存 blend (贴图已 pack, D5)
# ============================================================
blend_out = os.path.join(HERE, "model.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_out)
print(f"DONE -> {blend_out}")
print("下一步:")
print(f"  /snap/blender/current/blender --background --python blender_export.py -- {HERE}")
print(f"  python3 gazebo_pack.py build {HERE} --world")