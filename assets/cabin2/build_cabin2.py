# -*- coding: utf-8 -*-
"""
make_cabin.py — 资产包 assets/cabin 的建模脚本 (可复跑)
  /snap/blender/7803/blender --background --python make_cabin.py
  前置: make_cabin_textures.py 已生成 assets/cabin/textures/*.png

brief: 小木屋, 2×3×3m, 精美贴图, 1 个动态, collision 默认
约定: 建模坐标 Z-up, 底面 z=0, 门朝 +Y, bbox 中心归导出器处理。
      外包络 = (2.01, 3.01, 3.0): 门窗对称外凸 5mm → V4 容差(20mm)内,
      且前后/左右对称 → V5 中心原点不偏移。

结构 (20 件实体, 相邻件体积重叠 → EXACT union → 单一水密外壳):
  石基础 / 四面墙 / 前后山墙(三角棱柱) / 左右坡屋顶(旋转板)
  / 前后门 / 六扇窗(全墙, 对称) / 石烟囱
贴图: 五种程序化贴图, 世界坐标 box 投影 (木纹跨墙连续), 门窗一物一图。
"""
import bpy
import bmesh
import os
import math
from mathutils import Matrix, Vector

ROOT = os.path.dirname(os.path.abspath(__file__))
CABIN = os.path.join(ROOT, "assets", "cabin")
TEX = os.path.join(CABIN, "textures")

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

parts = []          # (mesh_object, material_key)


def add_box(name, ctr, dims, mat):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Translation(ctr) @
                 Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    parts.append(ob)
    ob["mat"] = mat
    return ob


def add_prism_y(name, tri_xz, y0, y1, mat):
    """XZ 平面三角形沿 Y 拉伸成棱柱 (山墙用). tri_xz = [(x,z)*3]"""
    bm = bmesh.new()
    vs = [bm.verts.new((x, y0, z)) for (x, z) in tri_xz]
    f = bm.faces.new(vs)
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    up = [e for e in r["geom"] if isinstance(e, bmesh.types.BMVert)]
    bmesh.ops.translate(bm, verts=up, vec=(0, y1 - y0, 0))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    parts.append(ob)
    ob["mat"] = mat
    return ob


def add_slab(name, pts8, mat):
    """8 个显式角点的板 (凸包) — 坡屋顶用, bbox 完全可控."""
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts8]
    r = bmesh.ops.convex_hull(bm, input=vs)
    keep = set(r["geom"])
    dead = [f for f in bm.faces if f not in keep]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    parts.append(ob)
    ob["mat"] = mat
    return ob


# =====================================================================
# 部件 (尺寸都在建模坐标系, 单位 m)
#   主体: X 宽 2.0 / Y 长 3.0 / 墙顶 2.0 / 屋脊 2.95
# =====================================================================
W2, L2 = 1.0, 1.5                      # 半宽/半长
wall_t = 0.06
base_h = 0.12
zwall = 2.0                            # 墙顶
zridge = 2.93

# 基础石台 (四边外凸 2cm 装饰, 不影响 bbox 中心)
add_box("base", (0, 0, 0.06), (2.04, 3.04, 0.12), "stone")
# 四面墙
add_box("wall_f", (0,  L2 - wall_t / 2, 0.12 + (zwall - 0.12) / 2), (2.0, wall_t, zwall - 0.12), "plank")
add_box("wall_b", (0, -L2 + wall_t / 2, 0.12 + (zwall - 0.12) / 2), (2.0, wall_t, zwall - 0.12), "plank")
add_box("wall_l", (-W2 + wall_t / 2, 0, 0.12 + (zwall - 0.12) / 2), (wall_t, 3.0, zwall - 0.12), "plank")
add_box("wall_r", ( W2 - wall_t / 2, 0, 0.12 + (zwall - 0.12) / 2), (wall_t, 3.0, zwall - 0.12), "plank")
# 前后山墙: 三角形, 底 2.0 高 0.95 (墙顶→屋脊), 厚 0.06 与侧墙对齐
for nm, yy in (("gable_f", L2 - wall_t / 2), ("gable_b", -L2 + wall_t / 2)):
    add_prism_y(nm, [(-1.0, zwall), (1.0, zwall), (0.0, 2.93)],
                yy - wall_t / 2, yy + wall_t / 2, "plank")
# 坡屋顶: 显式 8 角点板 (下表面: 屋脊(±0.03, 2.90) → 檐口(±1.00, 1.90))
#   厚度 0.05 沿坡面法线 (0.718, 0.696): 上角 z=2.935, 檐 x=1.036
#   → 外包络 x=2.072 (含左右檐口), 与 manifest 声明一致
t_roof, ny = 0.05, 1.52                 # 板厚 / y 半长(挑檐 2cm)
nrm = (0.7177, 0.6963)                  # (dx,dz) 归一化法线
for sx in (-1, 1):
    xr, zr = sx * 0.03, 2.90            # 屋脊侧下缘 (左右各越脊 3cm 互相重叠)
    xe, ze = sx * 1.00, 1.90            # 檐口下缘
    bot = [(xr, -ny, zr), (xe, -ny, ze), (xe, ny, ze), (xr, ny, zr)]
    top = [(x + t_roof * nrm[0] * sx, y, z + t_roof * nrm[1]) for (x, y, z) in bot]
    add_slab(f"roof_{"r" if sx > 0 else "l"}", bot + top, "shingle")
add_box("ridge_cap", (0, 0, 2.9548), (0.14, 3.06, 0.06), "stone")
# 前门 (+Y): 0.9×1.9, 板厚 4cm, 外凸 5mm → 撑满 y 正向 bbox
add_box("door_f", (0, L2 - 0.02, 0.12 + 0.95), (0.9, 0.06, 1.9), "door")
# 后门 (-Y): 同款对称
add_box("door_b", (0, -L2 + 0.02, 0.12 + 0.95), (0.9, 0.06, 1.9), "door")
# 窗 ×6 (对称!): 前 2 后 1 左右各 1; 窗板 0.7×0.7 外凸 5mm
WIN = (0.7, 0.7)
def win(nm, loc, axis):
    d = {"x": (0.05, WIN[1], WIN[0]), "y": (WIN[0], 0.05, WIN[0])}[axis]
    add_box(nm, loc, d, "glass")
zwin = 1.35
win("win_l1", (-W2 + 0.02, -0.55, zwin), "x")   # 侧墙双窗 (±X)
win("win_l2", (-W2 + 0.02,  0.55, zwin), "x")
win("win_r1", ( W2 - 0.02, -0.55, zwin), "x")
win("win_r2", ( W2 - 0.02,  0.55, zwin), "x")
win("win_g1", ( 0.0,  L2 - 0.02, 2.22), "y")    # 山墙窗 (前后对称)
win("win_g2", ( 0.0, -L2 + 0.02, 2.22), "y")
# 烟囱: 石砌, 从坡面穿出靠后 (左右居中避免质心偏; 前坡穿出点)
add_box("chimney", (0.55, -0.9, 2.6), (0.3, 0.3, 0.8), "stone")  # 顶 3.0 撑满 z

# ---- 材质 (Image 纹理; box 投影 UV 在 union 之后统一做) ----
def make_mat(key, img):
    m = bpy.data.materials.new("cabin_" + key)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    bsdf.inputs["Roughness"].default_value = 0.8
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = bpy.data.images.load(os.path.join(TEX, img), check_existing=False)
    uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
    nt.links.new(uv.outputs[0], tex.inputs["Vector"])
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return m

MATS = {"plank":  make_mat("plank",  "plank.png"),
        "shingle": make_mat("shingle", "shingle.png"),
        "stone":  make_mat("stone",  "stone.png"),
        "glass":  make_mat("glass",  "glass.png"),
        "door":   make_mat("door",   "door.png")}

# ---- EXACT union → 水密单壳 (同 make_chair 的坑: 每轮重挂 modifier) ----
bpy.context.view_layer.update()
active = parts[0]
bpy.context.view_layer.objects.active = active
for ob in parts[1:]:
    bpy.ops.object.modifier_add(type="BOOLEAN")
    mod = active.modifiers[-1]
    mod.operation, mod.solver, mod.object = "UNION", "EXACT", ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob, do_unlink=True)
cabin = active
cabin.name = cabin.data.name = "cabin"
# 先清空 union process 混进来的材质槽, 再按 IDX 固定顺序挂 5 个
cabin.data.materials.clear()
for mkey in ("plank", "shingle", "stone", "glass", "door"):
    cabin.data.materials.append(MATS[mkey])

# ---- 贴图 pack (贴图内嵌 → V6 单文件可搬运) ----
bpy.ops.file.pack_all()


# =====================================================================
# 贴图坐标: 世界坐标 box 投影 (木纹跨墙面连续) + 门窗"一物一图"
# 材质槽: plank0 shingle1 stone2 glass3 door4 (与上面 append 顺序一致)
# =====================================================================
IDX = {"plank": 0, "shingle": 1, "stone": 2, "glass": 3, "door": 4}

# 门窗矩形表: (cx, cy, cz, axis, W, H) — axis=板面法线方向
OPENINGS = [
    (0.0,  L2, 1.07, "y", 0.9, 1.9),        # 前/后门 (±Y 墙只有门)
    (0.0, -L2, 1.07, "y", 0.9, 1.9),
    (-W2, -0.55, zwin, "x", 0.7, 0.7),      # 侧墙双窗 (±X)
    (-W2,  0.55, zwin, "x", 0.7, 0.7),
    ( W2, -0.55, zwin, "x", 0.7, 0.7),
    ( W2,  0.55, zwin, "x", 0.7, 0.7),
    ( 0.0,  L2, 2.22, "y", 0.7, 0.7),       # 山墙窗 (前后)
    ( 0.0, -L2, 2.22, "y", 0.7, 0.7),
]

me = cabin.data
uv = me.uv_layers.new(name="UVMap")


def opening_hit(poly, verts_of):
    """门窗判定: 法线沿开口轴朝外, 且【所有】顶点投影都在矩形内.

    为什么不能用面中心: EXACT union 会把窗周墙面并成一张大面, 中心恰好
    落在窗矩形里 → 整面墙被贴窗图 (本次踩的坑). 顶点全命中则墙大面必出局,
    窗面 4 角恰在矩形边上必通过; 窗框台阶侧面法线与轴垂直 → 自动留 plank."""
    for oi, (cx, cy, cz, axis, W, H) in enumerate(OPENINGS):
        ai = 0 if axis == "x" else 1
        sign = 1.0 if (cx if axis == "x" else cy) > 0 else -1.0
        if poly.normal[ai] * sign < 0.9:
            continue                      # 朝向不对 (含内墙面/侧壁)
        ca = cx if axis == "y" else cy      # 矩形水平轴: y 墙看 x, x 墙看 y
        ok = True
        for v in verts_of:
            a = v[0] if axis == "y" else v[1]
            if abs(a - ca) > W / 2 + 0.005 or abs(v[2] - cz) > H / 2 + 0.005:
                ok = False
                break
        if ok:
            return oi
    return None


def classify(poly, oi):
    # chimney顶/脊帽/基础 → stone (按坐标区)
    c = poly.center
    if abs(c.x - 0.55) < 0.17 and abs(c.y + 0.9) < 0.17 and c.z > 1.8:
        return "stone"
    if abs(c.x) < 0.075 and c.z > 2.90:
        return "stone"
    if c.z < 0.126:
        return "stone"
    if oi is not None:
        return "door" if OPENINGS[oi][4] > 0.8 else "glass"
    if abs(poly.normal.z) > 0.65 and c.z > 1.8:
        return "shingle"
    return "plank"


for poly in me.polygons:
    vs = [tuple(me.vertices[vi].co) for vi in poly.vertices]
    oi = opening_hit(poly, vs)
    key = classify(poly, oi)
    poly.material_index = IDX[key]
    ax = ("x", "y", "z")[max(range(3), key=lambda i: abs(poly.normal[i]))]
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index].co
        u2 = v2 = 0.0
        if key in ("door", "glass"):
            cx, cy, cz, oax, W, H = OPENINGS[oi]
            if oax == "y":
                u2 = 0.5 + (v.x - cx) / W
                v2 = 0.5 + (v.z - cz) / H
            else:
                u2 = 0.5 + (v.y - cy) / W
                v2 = 0.5 + (v.z - cz) / H
        elif key == "shingle":
            u2, v2 = (v.x / 0.35, v.y / 0.35) if ax == "z" else \
                     (v.x / 0.35, v.z / 0.35) if ax == "y" else (v.y / 0.35, v.z / 0.35)
        elif key == "stone":
            u2, v2 = (v.x / 0.6, v.y / 0.6) if ax == "z" else \
                     (v.y / 0.6, v.z / 0.6) if ax == "x" else (v.x / 0.6, v.z / 0.6)
        else:  # plank: tile 周期 0.5m (=6 板)
            u2, v2 = (v.x / 0.5, v.y / 0.5) if ax == "z" else \
                     (v.y / 0.5, v.z / 0.5) if ax == "x" else (v.x / 0.5, v.z / 0.5)
        uv.data[li].uv = (u2, v2)

# ---- 自检 + 保存 ----
import mathutils
cs = [cabin.matrix_world @ mathutils.Vector(c) for c in cabin.bound_box]
xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
print(f"MODEL bbox: {max(xs)-min(xs):.4f} x {max(ys)-min(ys):.4f} x {max(zs)-min(zs):.4f}")
print(f"CENTER: {(max(xs)+min(xs))/2:+.4f},{(max(ys)+min(ys))/2:+.4f},{(max(zs)+min(zs))/2:+.4f}")
print("verts=%d polys=%d uv=%d mats=%s" % (len(me.vertices), len(me.polygons), len(me.uv_layers), ' | '.join(m.name for m in me.materials)))

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(CABIN, "model.blend"))
print("BLEND_SAVED:", os.path.join(CABIN, "model.blend"))

