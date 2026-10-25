#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_coke_bottle.py — 可口可乐瓶（本资产包专用建模脚本，MANIFEST_SPEC §2.1）

用法（项目根目录）:
    python3 assets/coke_bottle/gen_coke_label.py        # ① 生成贴图(仅需一次)
    /snap/blender/current/blender --background --python \
        assets/coke_bottle/build_coke_bottle.py          # ② 建 model.blend

产物: assets/coke_bottle/model.blend  （source/*.glb 由 blender_export.py 导出）

【造型】
  经典弧形瓶轮廓(contour bottle): 下腹鼓 → 腰部收 → 上腹鼓 → 肩部收 → 瓶颈 → 瓶盖。
  截面是椭圆: X 半轴 = 0.08/2, Y 半轴 = 0.08/2（= 圆截面, 真实 2L 瓶比例）——
  因此 AABB 精确等于 brief 确认的 0.08 × 0.08 × 0.25 m（V4 对账），
  也满足 frame.origin = center（V5）。
  整个瓶身是一个封闭流形曲面（水密, V7）: 侧面四边形环带 + 瓶底锥形凹底
  (punt) 扇面 + 瓶盖顶面扇面, 顶点共享, 每条边恰好 2 个面。

【贴图】
  整瓶一张 "皮肤" 贴图（textures/coke_label.png）:
      u = theta/2π 绕瓶一周, v = 瓶高归一化（0 瓶底 → 1 盖顶）。
  材质两种, 共用同一张图:
      coke_body : 塑料红 (metallic 0, roughness 0.32)
      coke_cap  : 金属盖 (metallic 0.85, roughness 0.28)
  图会 pack 进 .blend（D5），glb 导出时内嵌（V6）。

【自检（与 V4/V7 同口径，失败 exit≠0）】
  实测 bbox == SIZE、每条边恰 2 面、有向体积 > 0（法线朝外）。
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures", "coke_label.png")
BLEND = os.path.join(HERE, "model.blend")

# ============ ① 唯一需要改的尺寸参数（米，X × Y × Z）============
SIZE = (0.08, 0.08, 0.25)   # 必须与 manifest.geometry.size 逐值一致
NAME = "coke_bottle"        # 对象名 == manifest 里 glb 文件名主干
SEG = 96                    # 圆周分段（96 保证椭圆截面足够顺滑）

CAP_V = 0.866               # 瓶盖起点（与 gen_coke_label.py 的 V_CAP_BOTTOM 对齐）
PUNT = 0.022                # 凹底深度（占瓶高比例）

# ============ ② 轮廓线 (t=瓶高归一化, r=相对最大半径) ============
# 下腹鼓(t≈0.045)、腰(t≈0.225)、上腹鼓(t≈0.425)、肩、颈、盖 —— 经典可乐瓶曲线。
PROFILE = [
    (0.000, 0.900),   # 底缘
    (0.006, 0.945),
    (0.014, 0.975),
    (0.026, 0.994),
    (0.040, 1.000),   # 下腹最鼓 ← X 半宽 0.04 由此处给出
    (0.070, 0.998),
    (0.100, 0.988),
    (0.135, 0.968),
    (0.170, 0.938),
    (0.200, 0.905),
    (0.225, 0.878),
    (0.248, 0.862),   # 腰（最细）
    (0.272, 0.866),
    (0.300, 0.882),
    (0.335, 0.913),
    (0.370, 0.948),
    (0.405, 0.978),
    (0.435, 0.998),
    (0.455, 1.000),   # 上腹最鼓
    (0.480, 0.996),
    (0.505, 0.985),
    (0.528, 0.966),
    (0.548, 0.938),
    (0.566, 0.900),
    (0.582, 0.855),
    (0.598, 0.802),
    (0.614, 0.744),
    (0.630, 0.684),
    (0.646, 0.624),
    (0.661, 0.565),
    (0.675, 0.510),
    (0.688, 0.458),
    (0.700, 0.412),
    (0.711, 0.372),
    (0.720, 0.340),
    (0.728, 0.316),
    (0.735, 0.302),
    (0.742, 0.295),
    (0.750, 0.292),
    (0.760, 0.291),   # 瓶颈直段
    (0.790, 0.291),
    (0.820, 0.291),
    (0.840, 0.293),
    (0.852, 0.298),
    (0.860, 0.305),
    (0.866, 0.315),   # 盖沿（CAP_V 起）
    (0.872, 0.322),
    (0.878, 0.322),
    (0.990, 0.322),
    (0.996, 0.318),
    (1.000, 0.305),   # 盖顶倒角
]

X = SIZE[0] / 2.0
Y = SIZE[1] / 2.0
Z = SIZE[2]


def ring_xyz(t, r, i):
    """第 i 个圆环顶点（椭圆截面）: 周长参数均匀。"""
    th = 2.0 * math.pi * i / SEG
    return (X * r * math.cos(th), Y * r * math.sin(th), -Z / 2.0 + t * Z)


# ================= 场景重建（幂等，E6 要求）=================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

bm = bmesh.new()
uv_layer = bm.loops.layers.uv.new("UVMap")

# ---- 侧面: 环 → 环 的四边形 ----
ring_verts = []
ring_t = []
for t, r in PROFILE:
    row = [bm.verts.new(ring_xyz(t, r, i)) for i in range(SEG)]
    ring_verts.append(row)
    ring_t.append(t)

n_rings = len(ring_verts)
for k in range(n_rings - 1):
    a, b = ring_verts[k], ring_verts[k + 1]
    for i in range(SEG):
        j = (i + 1) % SEG
        f = bm.faces.new((a[i], a[j], b[j], b[i]))
        f.smooth = True
        f.material_index = 1 if ring_t[k] >= CAP_V else 0

# ---- 瓶底: 锥形凹底 punt 扇面 ----
zc = -Z / 2.0 + PUNT * Z
vc = bm.verts.new((0.0, 0.0, zc))
for i in range(SEG):
    j = (i + 1) % SEG
    f = bm.faces.new((vc, ring_verts[0][j], ring_verts[0][i]))
    f.smooth = False
    f.material_index = 0

# ---- 盖顶: 平盖扇面 ----
zt = Z / 2.0
vt = bm.verts.new((0.0, 0.0, zt))
last = ring_verts[-1]
for i in range(SEG):
    j = (i + 1) % SEG
    f = bm.faces.new((vt, last[i], last[j]))
    f.smooth = False
    f.material_index = 1

# ---- 法线统一朝外 ----
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)

# ---- 锐边: 相邻面夹角 > 35° 断开平滑（盖沿/底缘/倒角）----
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
for e in bm.edges:
    if len(e.link_faces) == 2:
        e.smooth = e.calc_face_angle(0.0) < math.radians(35.0)

# ---- UV: 逐 loop 写 (u=theta/2π, v=瓶高归一化)，跨接缝补 1.0 防回绕 ----
ring_uv_v = {tuple(round(c, 9) for c in v.co): ring_t[k]
             for k, row in enumerate(ring_verts) for v in row}
for f in bm.faces:
    us = []
    for lp in f.loops:
        co = tuple(round(c, 9) for c in lp.vert.co)
        # 环带顶点的 v 由环序号决定；punt/盖顶扇心取就近高度
        if co in ring_uv_v:
            vv = ring_uv_v[co]
        else:
            vv = PUNT if lp.vert is vc else 1.0
        us.append((co, vv))
    # u 由绕 Z 的角度给出
    vals = []
    for co, vv in us:
        u = (math.atan2(co[1] / Y if Y else 0.0, co[0] / X if X else 0.0)
             / (2 * math.pi)) % 1.0
        vals.append([u, vv])
    # 同一面内防 u 回绕: 若跨度 > 0.5, 把小的 u 加 1
    if max(v[0] for v in vals) - min(v[0] for v in vals) > 0.5:
        for v_ in vals:
            if v_[0] < 0.5:
                v_[0] += 1.0
    for lp, (u, vv) in zip(f.loops, vals):
        lp[uv_layer].uv = (u, vv)

mesh = bpy.data.meshes.new(NAME)
bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new(NAME, mesh)
scene.collection.objects.link(obj)
bpy.context.view_layer.objects.active = obj
obj.select_set(True)

# ================= 材质（贴图 pack 进 blend, D5）=================
if not os.path.exists(TEX):
    sys.exit(f"缺少贴图: {TEX}\n先跑: python3 {os.path.join(HERE, 'gen_coke_label.py')}")

img = bpy.data.images.load(TEX, check_existing=True)
if img.packed_file is None:
    img.pack()


def make_mat(name, metallic, roughness):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    if nt is None:                    # 5.x 新材质默认已有节点树（E3）
        mat.use_nodes = True
        nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = img
    tex.interpolation = "Linear"      # 可口可乐 logo 是照片类纹理，线性比 Closest 自然
    tex.extension = "REPEAT"
    tex.location = (-420, 260)
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


mat_body = make_mat("coke_body", 0.0, 0.32)
mat_cap = make_mat("coke_cap", 0.2, 0.28)  # D6: gz 无 IBL
obj.data.materials.append(mat_body)
obj.data.materials.append(mat_cap)

# 视口颜色（非渲染用，方便在 Blender 里一眼认出来）
mat_body.diffuse_color = (0.894, 0.0, 0.06, 1.0)
mat_cap.diffuse_color = (0.69, 0.0, 0.07, 1.0)

obj.location = (0.0, 0.0, 0.0)
obj.rotation_euler = (0.0, 0.0, 0.0)
obj.scale = (1.0, 1.0, 1.0)

# ================= 自检（V4 / V7 同口径）=================
coords = [Vector(v.co) for v in mesh.vertices]
lo = Vector((min(c[i] for c in coords) for i in range(3)))
hi = Vector((max(c[i] for c in coords) for i in range(3)))
meas = hi - lo
print("\n==== coke_bottle 自检 ====")
print(f"实测 bbox  = {meas.x:.6f} x {meas.y:.6f} x {meas.z:.6f} m")
print(f"目标 SIZE  = {SIZE[0]:.6f} x {SIZE[1]:.6f} x {SIZE[2]:.6f} m")
print(f"AABB 中心  = ({(lo.x + hi.x) / 2:.6f}, {(lo.y + hi.y) / 2:.6f}, "
      f"{(lo.z + hi.z) / 2:.6f})   ← center 策略要求 ≈ 0")
print(f"顶点 {len(mesh.vertices)} / 面 {len(mesh.polygons)}")

bbox_ok = all(abs(meas[i] - SIZE[i]) <= 0.001 for i in range(3))
center_ok = all(abs((lo[i] + hi[i]) / 2) <= 0.001 for i in range(3))

bm2 = bmesh.new()
bm2.from_mesh(mesh)
open_edges = sum(1 for e in bm2.edges if len(e.link_faces) != 2)
vol = bm2.calc_volume(signed=True)
bm2.free()
print(f"水密检查   = {open_edges} 条非双面边 (要求 0)")
print(f"有向体积   = {vol:.6f} m³  (正 = 法线朝外)")

if not bbox_ok or not center_ok or open_edges or vol <= 0:
    print("❌ 自检失败 —— 不写 blend", file=sys.stderr)
    raise SystemExit(1)

# ================= 保存 =================
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"\n✅ 已保存 {BLEND}")
print("下一步: /snap/blender/current/blender --background --python blender_export.py -- "
      "assets/coke_bottle")
