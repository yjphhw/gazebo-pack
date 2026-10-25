#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_falcon9.py — 猎鹰 9 号 Block 5（本资产包专用建模脚本，MANIFEST_SPEC §2.1）

用法（项目根目录）:
    python3 assets/falcon9/gen_textures.py
    /snap/blender/current/blender --background --python assets/falcon9/build_falcon9.py

产物: assets/falcon9/model.blend  （glb 由 blender_export.py 导出）

【造型】（真实比例，AABB 5.2×5.2×70 m，origin=center）
  z 0.0–1.5    9 台 Merlin 发动机喷管（8 环 + 1 中，深色金属）
  z 1.5–41.0   一级箭体 φ3.66（白漆，贴图含面板线/SPACEX/国旗/熏黑）
  z 41.0–47.0  级间段 φ3.66（黑色碳纤维）
  z 47.0–56.5  二级箭体 φ3.66（白漆）
  z 56.5–57.5  整流罩根部过渡 φ3.66 → φ5.2
  z 57.5–63.0  整流罩圆柱 φ5.2
  z 63.0–70.0  整流罩卵形头锥（幂函数母线）
  另加 4 条折叠着陆腿、4 片栅格舵、1 条电缆槽，各自是独立闭合壳
  （合成一个对象、一个 glb；每条边恰 2 面，V7 同口径自检）。

【贴图】5 张（见 gen_textures.py）：
  stage1 / stage2 / fairing 白漆面板贴图；carbon 碳纤维；fins 栅格舵网格。

【自检】bbox == SIZE、中心≈0、每条边恰 2 面、有向体积 > 0、材质/UV 齐全。
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEXD = os.path.join(HERE, "textures")
BLEND = os.path.join(HERE, "model.blend")

SIZE = (5.2, 5.2, 70.0)
NAME = "falcon9"
SEG = 96
TOTAL_H = 70.0

# (z0, z1, material_index) —— 材料编号与下方 mat 列表顺序一致
BANDS = [
    (1.5, 41.0, 0),     # 一级白漆
    (41.0, 47.0, 1),    # 级间段碳纤维
    (47.0, 56.5, 2),    # 二级白漆
    (56.5, 70.0, 3),    # 整流罩白漆
]


def band_of(z):
    for z0, z1, mi in BANDS:
        if z0 - 1e-9 <= z <= z1 + 1e-9:
            return z0, z1, mi
    return BANDS[-1]


def fairing_radius(z):
    """63–70 m 的卵形头锥：r = 2.6*(1-t)^0.7。"""
    t = min(max((z - 63.0) / 7.0, 0.0), 1.0)
    return 2.6 * (1.0 - t) ** 0.7


# 母线环 (z, r)
RINGS = [(1.5, 1.83), (41.0, 1.83), (47.0, 1.83), (56.5, 1.83),
         (57.5, 2.60), (63.0, 2.60)]
for z in (63.8, 64.6, 65.4, 66.2, 67.0, 67.8, 68.6, 69.3, 69.9):
    RINGS.append((z, fairing_radius(z)))


def add_body(bm, uv_layer):
    rings = []
    for z, r in RINGS:
        rings.append([bm.verts.new((r * math.cos(2 * math.pi * i / SEG),
                                    r * math.sin(2 * math.pi * i / SEG), z))
                      for i in range(SEG)])
    for k in range(len(RINGS) - 1):
        z0, _ = RINGS[k]
        z1, _ = RINGS[k + 1]
        bz0, bz1, mi = band_of((z0 + z1) / 2.0)
        span = bz1 - bz0
        for i in range(SEG):
            j = (i + 1) % SEG
            f = bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
            f.material_index = mi
            f.smooth = True
            u_i = i / SEG
            u_j = 1.0 if i == SEG - 1 else j / SEG
            v0 = (z0 - bz0) / span
            v1 = (z1 - bz0) / span
            for lp, uv in zip(f.loops, [(u_i, v0), (u_j, v0), (u_j, v1), (u_i, v1)]):
                lp[uv_layer].uv = uv

    # 底部封盖（发动机舱底板，深色）
    vc = bm.verts.new((0.0, 0.0, 1.5))
    for i in range(SEG):
        j = (i + 1) % SEG
        f = bm.faces.new((vc, rings[0][j], rings[0][i]))
        f.material_index = 4
        f.smooth = False
        for lp in f.loops:
            lp[uv_layer].uv = (0.5, 0.5)

    # 头锥顶点
    va = bm.verts.new((0.0, 0.0, TOTAL_H))
    last = rings[-1]
    for i in range(SEG):
        j = (i + 1) % SEG
        f = bm.faces.new((last[i], last[j], va))
        f.material_index = 3
        f.smooth = True
        for lp in f.loops:
            lp[uv_layer].uv = (0.5, 1.0)
    return rings


def add_frustum(bm, uv_layer, cx, cy, z0, z1, r0, r1, mat, n=24):
    """闭合圆台（发动机喷管）。r0 在 z0（底部），r1 在 z1（顶部）。"""
    ring0 = [bm.verts.new((cx + r0 * math.cos(2 * math.pi * i / n),
                           cy + r0 * math.sin(2 * math.pi * i / n), z0)) for i in range(n)]
    ring1 = [bm.verts.new((cx + r1 * math.cos(2 * math.pi * i / n),
                           cy + r1 * math.sin(2 * math.pi * i / n), z1)) for i in range(n)]
    for i in range(n):
        j = (i + 1) % n
        f = bm.faces.new((ring0[i], ring0[j], ring1[j], ring1[i]))
        f.material_index = mat
        f.smooth = True
        for lp in f.loops:
            lp[uv_layer].uv = (0.0, 0.0)
    for center, ring, z in (((cx, cy, z0), ring0, z0), ((cx, cy, z1), ring1, z1)):
        v = bm.verts.new(center)
        for i in range(n):
            j = (i + 1) % n
            f = bm.faces.new((v, ring[j], ring[i]))
            f.material_index = mat
            f.smooth = False
            for lp in f.loops:
                lp[uv_layer].uv = (0.0, 0.0)


def face_normal(f):
    vs = [v.co for v in f.verts]
    n = (vs[1] - vs[0]).cross(vs[2] - vs[0])
    if n.length < 1e-12:
        n = (vs[2] - vs[0]).cross(vs[3] - vs[0])
    return n.normalized()


def add_box(bm, uv_layer, center, ax, ay, half, mat, tile):
    """轴对齐局部盒子：ax/ay 为水平单位轴；half=(hx,hy,hz)。闭合、平直。"""
    cx, cy, cz = center
    hx, hy, hz = half

    def point(sx, sy, sz):
        return Vector((cx, cy, cz)) + ax * (sx * hx) + ay * (sy * hy) + Vector((0, 0, sz * hz))

    verts = [bm.verts.new(point(sx, sy, sz))
             for sz in (-1, 1) for sy in (-1, 1) for sx in (-1, 1)]
    quads = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    for quad in quads:
        f = bm.faces.new([verts[i] for i in quad])
        f.material_index = mat
        f.smooth = False
        n = face_normal(f)
        ax_i = max(range(3), key=lambda k: abs(n[k]))
        for lp in f.loops:
            co = lp.vert.co
            if ax_i == 0:
                u, v = co.y, co.z
            elif ax_i == 1:
                u, v = co.x, co.z
            else:
                u, v = co.x, co.y
            lp[uv_layer].uv = (u / tile, v / tile)


# ================= 场景重建 =================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

bm = bmesh.new()
uv_layer = bm.loops.layers.uv.new("UVMap")

# ---- 箭体（含整流罩）----
add_body(bm, uv_layer)

# ---- 9 台发动机 ----
add_frustum(bm, uv_layer, 0.0, 0.0, 0.0, 1.6, 0.42, 0.22, 4)
for k in range(8):
    a = 2 * math.pi * k / 8
    add_frustum(bm, uv_layer, 1.15 * math.cos(a), 1.15 * math.sin(a),
                0.0, 1.6, 0.42, 0.22, 4)

# ---- 4 条折叠着陆腿（碳纤维）----
for deg in (45, 135, 225, 315):
    a = math.radians(deg)
    ax, ay = Vector((-math.sin(a), math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0))
    add_box(bm, uv_layer,
            (1.90 * math.cos(a), 1.90 * math.sin(a), 6.0),
            ax, ay, (0.275, 0.06, 4.5), 1, 0.4)

# ---- 4 片栅格舵（钛合金网格）----
for deg in (0, 90, 180, 270):
    a = math.radians(deg)
    ax, ay = Vector((-math.sin(a), math.cos(a), 0)), Vector((math.cos(a), math.sin(a), 0))
    add_box(bm, uv_layer,
            (1.88 * math.cos(a), 1.88 * math.sin(a), 40.8),
            ax, ay, (0.65, 0.06, 0.60), 5, 1.3)

# ---- 电缆槽（沿一级箭体 +X 侧）----
add_box(bm, uv_layer, (1.87, 0.0, 20.75),
        Vector((1, 0, 0)), Vector((0, 1, 0)), (0.06, 0.06, 19.25), 6, 1.0)

bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# 锐边：相邻面夹角 > 35° 断开平滑
for e in bm.edges:
    if len(e.link_faces) == 2:
        e.smooth = e.calc_face_angle(0.0) < math.radians(35.0)

face_mats = [f.material_index for f in bm.faces]   # to_mesh 会按槽数夹紧，先记下
mesh = bpy.data.meshes.new(NAME)
bm.to_mesh(mesh)
bm.free()
mesh.update()

obj = bpy.data.objects.new(NAME, mesh)
scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# ================= 材质 / 贴图 =================
IMAGES = {}
for name in ("stage1", "stage2", "fairing", "carbon", "fins"):
    p = os.path.join(TEXD, f"{name}.png")
    if not os.path.exists(p):
        sys.exit(f"缺少贴图: {p}\n先跑: python3 {os.path.join(HERE, 'gen_textures.py')}")
    img = bpy.data.images.load(p, check_existing=True)
    if img.packed_file is None:
        img.pack()
    IMAGES[name] = img


def make_mat(name, image=None, color=None, metallic=0.0, roughness=0.4):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    if nt is None:
        mat.use_nodes = True
        nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if image is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = image
        tex.interpolation = "Linear"
        tex.extension = "REPEAT"
        tex.location = (-420, 260)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        base = (0.9, 0.9, 0.9, 1.0)
    else:
        base = (*color, 1.0)
        bsdf.inputs["Base Color"].default_value = base
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    mat.diffuse_color = base
    return mat


mesh.materials.clear()
mesh.materials.append(make_mat("stage1_white", IMAGES["stage1"], metallic=0.05, roughness=0.35))
mesh.materials.append(make_mat("interstage_carbon", IMAGES["carbon"], metallic=0.2, roughness=0.45))
mesh.materials.append(make_mat("stage2_white", IMAGES["stage2"], metallic=0.05, roughness=0.35))
mesh.materials.append(make_mat("fairing_white", IMAGES["fairing"], metallic=0.05, roughness=0.30))
mesh.materials.append(make_mat("engine_metal", color=(0.11, 0.11, 0.12), metallic=0.2, roughness=0.40))
mesh.materials.append(make_mat("grid_fin", IMAGES["fins"], metallic=0.2, roughness=0.35))
mesh.materials.append(make_mat("raceway", color=(0.72, 0.72, 0.70), metallic=0.10, roughness=0.45))
for poly, mi in zip(mesh.polygons, face_mats):
    poly.material_index = mi

# 归位到几何中心
for v in mesh.vertices:
    v.co.z -= TOTAL_H / 2.0
mesh.update()
obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)

# ================= 自检 =================
coords = [Vector(v.co) for v in mesh.vertices]
lo = Vector((min(c[i] for c in coords) for i in range(3)))
hi = Vector((max(c[i] for c in coords) for i in range(3)))
meas = hi - lo
print("\n==== falcon9 自检 ====")
print(f"实测 bbox  = {meas.x:.6f} x {meas.y:.6f} x {meas.z:.6f} m")
print(f"目标 SIZE  = {SIZE[0]:.6f} x {SIZE[1]:.6f} x {SIZE[2]:.6f} m")
print(f"AABB 中心  = ({(lo.x + hi.x) / 2:.6f}, {(lo.y + hi.y) / 2:.6f}, "
      f"{(lo.z + hi.z) / 2:.6f})   ← center 策略要求 ≈ 0")
print(f"顶点 {len(mesh.vertices)} / 面 {len(mesh.polygons)} / "
      f"材质 {len(mesh.materials)} / UV {len(mesh.uv_layers)}")

bbox_ok = all(abs(meas[i] - SIZE[i]) <= 0.001 for i in range(3))
center_ok = all(abs((lo[i] + hi[i]) / 2) <= 0.001 for i in range(3))

bm2 = bmesh.new()
bm2.from_mesh(mesh)
open_edges = sum(1 for e in bm2.edges if len(e.link_faces) != 2)
vol = bm2.calc_volume(signed=True)
bm2.free()
print(f"水密检查   = {open_edges} 条非双面边 (要求 0)")
print(f"有向体积   = {vol:.1f} m³  (正 = 法线朝外)")

if not bbox_ok or not center_ok or open_edges or vol <= 0:
    print("❌ 自检失败 —— 不写 blend", file=sys.stderr)
    raise SystemExit(1)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"\n✅ 已保存 {BLEND}")
print("下一步: /snap/blender/current/blender --background --python blender_export.py -- "
      "assets/falcon9")
