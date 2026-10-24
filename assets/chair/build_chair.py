# -*- coding: utf-8 -*-
"""
make_chair.py — 资产包 assets/chair 的来源脚本 (层③ 对话创意的固化, 可复跑)
  在 Blender 后台运行:
    /snap/blender/7803/blender --background --python make_chair.py
  产出: assets/chair/model.blend (单对象 chair, 水密, 原点在建模位置,
        之后由 blender_export.py 统一归位)

brief: 椅子, 0.45×0.45×0.90 m, 白蜡木, 动态, collision 默认 mesh
约定 (PACK_NOTES): 建模坐标 Z-up, 顶面 +Z, 椅背朝 -Y, 正面朝 +Y,
                   底面 z=0, XY 对称 → 导出器 center 归位后中心在原点。

设计 = 20 件原木方块/圆棍搭成, 所有相邻件**体积重叠**(不是面贴面),
最后 EXACT 布尔并集 → 单一水密外壳 → auto 惯量体积积分才正确 (V7)。
"""
import bpy
import bmesh
from mathutils import Matrix

# ---- 清空默认场景 (cube/camera/light) ----
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

# =====================================================================
# 部件表: (名称, 类型, 中心 xyz, 尺寸 xyz=box / (r, depth)=cyl)
#   尺寸都是人工推演过的: 相邻件两两体积重叠 ≥10mm (见注释),
#   最终外包络恰好 0.45×0.45×0.90 (V4 校验对账尺寸)。
# =====================================================================
LEG_XY = 0.2025            # 腿中心到轴的距离 → 腿外缘 ±0.225 = 半宽 ✓

BOXES = [
    # ---- 4 条腿 0.045 见方, z 0→0.46 (顶部伸进坐垫框 z 0.445..0.47 内) ----
    ("leg_fr", ( LEG_XY,  LEG_XY, 0.23),  (0.045, 0.045, 0.46)),
    ("leg_fl", (-LEG_XY,  LEG_XY, 0.23),  (0.045, 0.045, 0.46)),
    ("leg_bl", (-LEG_XY, -LEG_XY, 0.23),  (0.045, 0.045, 0.46)),
    ("leg_br", ( LEG_XY, -LEG_XY, 0.23),  (0.045, 0.045, 0.46)),
    # ---- 围条 apron: z 0.375..0.455, 端头伸进腿 (x/y 0.18..0.19 重叠带) ----
    ("apron_f", (0,  LEG_XY, 0.415), (0.38, 0.035, 0.08)),
    ("apron_b", (0, -LEG_XY, 0.415), (0.38, 0.035, 0.08)),
    ("apron_l", (-LEG_XY, 0, 0.415), (0.035, 0.38, 0.08)),
    ("apron_r", ( LEG_XY, 0, 0.415), (0.035, 0.38, 0.08)),
    # ---- 坐垫框 (边框一圈 + 3 根板条), 板面顶 z=0.47 ----
    ("seat_f", (0,  0.2025, 0.4575), (0.41, 0.04, 0.025)),
    ("seat_b", (0, -0.2025, 0.4575), (0.41, 0.04, 0.025)),
    ("seat_l", (-0.2025, 0, 0.4575), (0.04, 0.41, 0.025)),
    ("seat_r", ( 0.2025, 0, 0.4575), (0.04, 0.41, 0.025)),
    ("slat_1", (0, -0.10375, 0.4575), (0.41, 0.05, 0.025)),
    ("slat_2", (0,  0.0,     0.4575), (0.41, 0.05, 0.025)),
    ("slat_3", (0,  0.10375, 0.4575), (0.41, 0.05, 0.025)),
    # ---- 靠背板: y -0.22..-0.195, z 0.44..0.89 (下缘插进后腿重叠带) ----
    ("back_slat", (0, -0.2075, 0.665), (0.42, 0.025, 0.45)),
    # ---- 顶梁: z 0.825..0.90, y/x 外缘正好 ±0.225/-0.225 → 撑满 bbox ----
    ("top_rail", (0, -0.2025, 0.8625), (0.45, 0.045, 0.075)),
]
CYLS = [  # ---- 3 根车木立柱 r15mm, z 0.45..0.85: 下插坐框后梁, 上插顶梁 ----
    ("spindle_1", (-0.12, -0.2025, 0.65), (0.015, 0.40)),
    ("spindle_2", ( 0.00, -0.2025, 0.65), (0.015, 0.40)),
    ("spindle_3", ( 0.12, -0.2025, 0.65), (0.015, 0.40)),
]


def add_box(name, ctr, dims):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Translation(ctr) @
                 Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0)))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_cyl(name, ctr, r, depth):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
                          radius1=r, radius2=r, depth=depth)
    bm.transform(Matrix.Translation(ctr))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me); bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


objs  = [add_box(n, c, d) for n, c, d in BOXES]
objs += [add_cyl(n, c, *rd) for n, c, rd in CYLS]

# ---- EXACT 布尔并集: 椅子 = 20 件的 union, 结果只剩一个外壳 (必水密) ----
# 坑: modifier_apply 应用完会把 modifier 从对象上摘掉,
#     每个操作数都要"挂新 modifier -> 应用 -> 删操作数", 不能复用同一个 mod
bpy.context.view_layer.update()
active = objs[0]
bpy.context.view_layer.objects.active = active
for ob in objs[1:]:
    bpy.ops.object.modifier_add(type="BOOLEAN")
    mod = active.modifiers[-1]
    mod.operation, mod.solver, mod.object = "UNION", "EXACT", ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob, do_unlink=True)
active.name = "chair"
active.data.name = "chair"

# ---- 白蜡木材质 (纯色 Principled, 与 tag_cube 同路数: 导出器 pack 自检可过) ----
mat = bpy.data.materials.new("ash")
mat.use_nodes = True
bsdf = mat.node_tree.nodes["Principled BSDF"]
bsdf.inputs["Base Color"].default_value = (0.80, 0.66, 0.44, 1.0)  # 白蜡木浅黄
bsdf.inputs["Roughness"].default_value = 0.55
active.data.materials.append(mat)

# ---- 自检: 报告外包络 (应 0.450×0.450×0.900, z_min=0) ----
import mathutils
cs = [active.matrix_world @ mathutils.Vector(c) for c in active.bound_box]
xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
print(f"MODEL bbox: {max(xs)-min(xs):.4f} x {max(ys)-min(ys):.4f} x "
      f"{max(zs)-min(zs):.4f}, z_min={min(zs):.4f}, verts={len(active.data.vertices)}")

# ---- 存 blend (导出器读它; 世界原点先不归位, 归位是导出器的职责) ----
import os
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets", "chair")
os.makedirs(out, exist_ok=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out, "model.blend"))
print("BLEND_SAVED:", os.path.join(out, "model.blend"))

