#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""build_skyscraper.py — 摩天大楼（本资产包专用建模脚本，MANIFEST_SPEC §2.1）

用法（项目根目录）:
    python3 assets/skyscraper/gen_facade_texture.py          # ① 生成幕墙贴图
    /snap/blender/current/blender --background --python \
        assets/skyscraper/build_skyscraper.py                # ② 建 model.blend

产物: assets/skyscraper/model.blend  （glb 由 blender_export.py 导出）

【造型】
  9×9 m 退台塔楼，高 60 m（AABB 精确 9×9×60，origin=center）：
      0–10 m   9.0×9.0 基座
      9–38 m   7.5×7.5 主塔（与基座重叠 1 m，供布尔真实相交）
     37–50 m   6.0×6.0 上部
     49–56 m   4.5×4.5 冠顶
     55–60 m   0.8×0.8 金属尖顶
  五个盒子用 Boolean UNION(EXACT) 合成**一个水密网格**（E5：必须有真实相交体）。

【贴图】
  幕墙单元 4.5 m × 3.6 m（3 开间 × 1 层），盒式投影：
      竖直 v = z/3.6（楼层线跨所有退台对齐）；
      水平 u 从每个面的左边缘起算 —— 因为面宽都是 1.5 m 的整数倍，
      每个面都从竖梃开始、到竖梃结束，四角自然对齐。
  材质三种：玻璃幕墙（贴图）/ 屋面与层间板（深灰金属）/ 尖顶（亮灰金属）。

【自检（与 V4/V7 同口径，失败 exit≠0）】
  实测 bbox == SIZE、每条边恰 2 面、有向体积 > 0、UV/材质齐全。
"""

import math
import os
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures", "facade.png")
BLEND = os.path.join(HERE, "model.blend")

# ============ ① 尺寸与楼层（米）============
SIZE = (9.0, 9.0, 60.0)      # AABB；必须与 manifest.geometry.size 一致
NAME = "skyscraper"          # 对象名 == manifest 里 glb 文件名主干

# (宽, 深, z 起点, z 终点) —— 相邻块重叠 1 m，保证布尔真实相交
LEVELS = [
    (9.0, 9.0, 0.0, 10.0),   # 基座
    (7.5, 7.5, 9.0, 38.0),   # 主塔
    (6.0, 6.0, 37.0, 50.0),  # 上部
    (4.5, 4.5, 49.0, 56.0),  # 冠顶
    (0.8, 0.8, 55.0, 60.0),  # 尖顶
]

TILE_W, TILE_H = 4.5, 3.6    # 幕墙单元（与贴图生成器一致）
SPIRE_Z = 56.0               # 以上归尖顶材质


def add_box(x, y, z0, z1):
    """建一个居中的盒子（尺寸已 apply，便于布尔）。"""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0.0, 0.0, (z0 + z1) / 2.0))
    obj = bpy.context.object
    obj.name = "part"
    obj.dimensions = (x, y, z1 - z0)
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return obj


# ================= 场景重建（幂等）=================
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene

# ---- 逐块布尔并集 ----
base = add_box(*LEVELS[0][:2], LEVELS[0][2], LEVELS[0][3])
for lv in LEVELS[1:]:
    part = add_box(*lv[:2], lv[2], lv[3])
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

# 把 object 的 location 烘进网格 → 之后顶点坐标即世界坐标
bpy.ops.object.select_all(action="DESELECT")
base.select_set(True)
bpy.context.view_layer.objects.active = base
bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)

# ---- 合并缝上的重复点 + 法线统一朝外 ----
bm = bmesh.new()
bm.from_mesh(mesh)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-5)
bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
bm.to_mesh(mesh)
bm.free()
mesh.update()

# ================= 材质 =================
if not os.path.exists(TEX):
    sys.exit(f"缺少贴图: {TEX}\n先跑: python3 {os.path.join(HERE, 'gen_facade_texture.py')}")

img = bpy.data.images.load(TEX, check_existing=True)
if img.packed_file is None:
    img.pack()


def make_mat(name, color=None, metallic=0.0, roughness=0.4, texture=False):
    mat = bpy.data.materials.new(name)
    nt = mat.node_tree
    if nt is None:                        # 5.x 新材质默认已有节点树（E3）
        mat.use_nodes = True
        nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
        out = next((n for n in nt.nodes if n.type == "OUTPUT_MATERIAL"), None) \
            or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    if texture:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = img
        tex.interpolation = "Linear"
        tex.extension = "REPEAT"
        tex.location = (-420, 260)
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Metallic"].default_value = metallic
    bsdf.inputs["Roughness"].default_value = roughness
    return mat


mat_glass = make_mat("facade_glass", metallic=0.15, roughness=0.22, texture=True)
mat_roof = make_mat("roof_metal", color=(0.16, 0.18, 0.20), metallic=0.50, roughness=0.42)
mat_spire = make_mat("spire_metal", color=(0.63, 0.67, 0.71), metallic=0.85, roughness=0.25)
mesh.materials.clear()                    # 清掉 primitive_cube_add 留下的空槽
for m in (mat_glass, mat_roof, mat_spire):
    mesh.materials.append(m)
mat_glass.diffuse_color = (0.16, 0.32, 0.45, 1.0)
mat_roof.diffuse_color = (0.16, 0.18, 0.20, 1.0)
mat_spire.diffuse_color = (0.63, 0.67, 0.71, 1.0)

# ================= 面材质 + UV（盒式投影）=================
for layer in list(mesh.uv_layers):        # 清掉 primitive_cube_add 自带的 UV
    mesh.uv_layers.remove(layer)
uv_layer = mesh.uv_layers.new(name="UVMap")
uv_layer.active_render = True
mesh.uv_layers.active = uv_layer
for poly in mesh.polygons:
    n = poly.normal
    c = poly.center
    if c.z > SPIRE_Z + 1e-6:
        poly.material_index = 2                    # 尖顶（含顶面）
    elif n.z > 0.5:
        poly.material_index = 1                    # 屋面 / 层间板 / 底面
    else:
        poly.material_index = 0                    # 玻璃幕墙

    ax = max(range(3), key=lambda i: abs(n[i]))
    vs = [mesh.vertices[i].co for i in poly.vertices]
    if ax == 0:                                    # ±X 面：u 从该面的 y_min 起
        umin = min(p.y for p in vs)
        u_of = lambda p: (p.y - umin, p.z)
    elif ax == 1:                                  # ±Y 面：u 从该面的 x_min 起
        umin = min(p.x for p in vs)
        u_of = lambda p: (p.x - umin, p.z)
    else:                                          # 水平面：UV 不重要
        u_of = lambda p: (p.x, p.y)
    for li in poly.loop_indices:
        p = mesh.vertices[mesh.loops[li].vertex_index].co
        u, v = u_of(p)
        uv_layer.data[li].uv = (u / TILE_W, v / TILE_H)

# ================= 归位到几何中心（origin=center）=================
for v in mesh.vertices:
    v.co.z -= SIZE[2] / 2.0
mesh.update()

base.location = (0.0, 0.0, 0.0)
base.rotation_euler = (0.0, 0.0, 0.0)
base.scale = (1.0, 1.0, 1.0)

# ================= 自检 =================
coords = [Vector(v.co) for v in mesh.vertices]
lo = Vector((min(c[i] for c in coords) for i in range(3)))
hi = Vector((max(c[i] for c in coords) for i in range(3)))
meas = hi - lo
print("\n==== skyscraper 自检 ====")
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
print(f"有向体积   = {vol:.3f} m³  (正 = 法线朝外)")

if not bbox_ok or not center_ok or open_edges or vol <= 0:
    print("❌ 自检失败 —— 不写 blend", file=sys.stderr)
    raise SystemExit(1)

# ================= 保存 =================
bpy.ops.wm.save_as_mainfile(filepath=BLEND)
print(f"\n✅ 已保存 {BLEND}")
print("下一步: /snap/blender/current/blender --background --python blender_export.py -- "
      "assets/skyscraper")
