#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_shelf.py — 银灰色金属货架（本资产包专用建模脚本，MANIFEST_SPEC §2.1）

用法（项目根目录）:
    /snap/blender/current/blender --background --python assets/shelf/build_shelf.py

产物: assets/shelf/model.blend  （glb 由 blender_export.py 导出）

【造型】
  1×1×2 m 五层开放式货架：
      4 根方立柱 0.05×0.05×2.0，位于 (±0.475, ±0.475)
      5 块层板   0.96×0.96×0.03，z = -0.85/-0.40/0.05/0.50/0.95
  层板与立柱真实相交（各伸入立柱 0.03 m），9 个盒子 UNION(EXACT) 合成
  **一个水密网格**（E5）。AABB 恰为 1×1×2（X/Y 由立柱外沿给出，Z 由柱高）。

【collision = 真实】
  manifest 用 `type: primitives` 手列 4 柱 + 5 板（9 个 box），层与层之间是
  真实空腔 —— 不做 convex_hull（会把整架填成一坨）。见 PACK_NOTES C3/A3。

【自检（与 V4/V7 同口径）】
  实测 bbox == SIZE、每条边恰 2 面、有向体积 > 0。
"""

import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "model.blend")

# ============ ① 尺寸（米）============
SIZE = (1.0, 1.0, 2.0)       # AABB；必须与 manifest.geometry.size 一致
NAME = "shelf"               # 对象名 == manifest 里 glb 文件名主干

POST = 0.05                  # 立柱截面
POST_XY = 0.475              # 立柱中心（外沿 = 0.5）
SHELF_XY = 0.96              # 层板边长（伸入立柱 0.03）
SHELF_T = 0.03               # 层板厚
SHELF_Z = (-0.85, -0.40, 0.05, 0.50, 0.95)


def add_box(x, y, z0, z1):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, (z0 + z1) / 2.0))
    obj = bpy.context.object
    obj.name = "part"
    obj.dimensions = (x, y, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


# ================= 场景重建（幂等）=================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---- 4 根立柱 + 5 块层板 ----
base = add_box(POST, POST, -1.0, 1.0)                     # 第一根
parts = []
for sx in (-1, 1):
    for sy in (-1, 1):
        if (sx, sy) == (-1, -1):
            continue                                      # 已作为 base
        parts.append(add_box(POST, POST, -1.0, 1.0))
for z in SHELF_Z:
    parts.append(add_box(SHELF_XY, SHELF_XY, z - SHELF_T / 2, z + SHELF_T / 2))

# 把非 base 的立柱/层板平移到各自位置
idx = 0
for sx in (-1, 1):
    for sy in (-1, 1):
        if (sx, sy) == (-1, -1):
            continue
        parts[idx].location = (sx * POST_XY, sy * POST_XY, 0.0)
        idx += 1
# base 也移到 (-0.475,-0.475)
base.location = (-POST_XY, -POST_XY, 0.0)

# ---- 布尔并集 ----
for part in parts:
    mod = base.modifiers.new(name="bool", type="BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"                  # E5
    mod.object = part
    bpy.ops.object.select_all(action="DESELECT")
    base.select_set(True)
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(part, do_unlink=True)

base.name = NAME
mesh = base.data
mesh.name = NAME

# object 的 location 烘进网格 → 顶点坐标即世界坐标（已居中）
bpy.ops.object.select_all(action="DESELECT")
base.select_set(True)
bpy.context.view_layer.objects.active = base
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(mesh)
bm.free()
mesh.update()

# ================= 材质（银灰色金属）=================
mesh.materials.clear()
mat = bpy.data.materials.new("shelf_metal")
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
bsdf.inputs["Base Color"].default_value = (0.70, 0.72, 0.75, 1.0)
bsdf.inputs["Metallic"].default_value = 0.15  # D6: gz 无 IBL, metallic>0.2 发黑
bsdf.inputs["Roughness"].default_value = 0.38
mesh.materials.append(mat)
mat.diffuse_color = (0.72, 0.74, 0.77, 1.0)

# 无贴图，不需要 UV（V6 只查外部引用）
base.location = (0.0, 0.0, 0.0)
base.rotation_euler = (0.0, 0.0, 0.0)
base.scale = (1.0, 1.0, 1.0)

# ================= 自检 =================
coords = [Vector(v.co) for v in mesh.vertices]
lo = Vector((min(c[i] for c in coords) for i in range(3)))
hi = Vector((max(c[i] for c in coords) for i in range(3)))
meas = hi - lo
print("\n==== shelf 自检 ====")
print(f"实测 bbox  = {meas.x:.6f} x {meas.y:.6f} x {meas.z:.6f} m")
print(f"目标 SIZE  = {SIZE[0]:.6f} x {SIZE[1]:.6f} x {SIZE[2]:.6f} m")
print(f"AABB 中心  = ({(lo.x + hi.x) / 2:.6f}, {(lo.y + hi.y) / 2:.6f}, "
      f"{(lo.z + hi.z) / 2:.6f})   ← center 策略要求 ≈ 0")
print(f"顶点 {len(mesh.vertices)} / 面 {len(mesh.polygons)} / 材质 {len(mesh.materials)}")

bbox_ok = all(abs(meas[i] - SIZE[i]) <= 0.001 for i in range(3))
center_ok = all(abs((lo[i] + hi[i]) / 2) <= 0.001 for i in range(3))

bm2 = bmesh.new()
bm2.from_mesh(mesh)
open_edges = sum(1 for e in bm2.edges if len(e.link_faces) != 2)
vol = bm2.calc_volume(signed=True)
bm2.free()
print(f"水密检查   = {open_edges} 条非双面边 (要求 0)")
print(f"有向体积   = {vol:.4f} m³  (正 = 法线朝外)")

if not bbox_ok or not center_ok or open_edges or vol <= 0:
    print("❌ 自检失败 —— 不写 blend", file=sys.stderr)
    raise SystemExit(1)

bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"\n✅ 已保存 {BLEND}")
print("下一步: /snap/blender/current/blender --background --python blender_export.py -- "
      "assets/shelf")
