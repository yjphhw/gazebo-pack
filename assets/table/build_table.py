#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_table.py — 生成 assets/table/model.blend (浅木色书桌, 静态摆件)

【跑法】 在项目根目录:
        /snap/blender/current/blender --background --python assets/table/build_table.py

【设计要点, 每条对应 PACK_NOTES 编号】
  * 造型 (层③): 0.80(x) x 0.60(y) x 0.75(z); 桌面厚 4cm; 四条 5x5cm 方腿,
    内缩 3cm; 桌面下方一圈 4x3cm 横撑。整体几何中心 = 原点。
  * 水密 (C2 铁律 / V7): 桌面 + 4 腿 + 4 横撑全部 Boolean UNION(EXACT)
    合成**单一封闭外壳**, 绝不「面贴面」堆叠。合并后逐边自检 (每边恰好 2 面)。
  * 原点 (B2): 直接建在几何中心即原点, .blend 打开即所见即所得;
    blender_export.py 仍会做整体归位, V5 复检 1mm 容差。
  * 贴图 (D1/D3/D4/D5): 程序化节点导出 glTF 必丢 → 用 numpy 画木纹写 png,
    再 pack 进 .blend; colorspace 保持 sRGB (D3)。
  * 单位: 1 Blender 单位 = 1m, 尺寸全按米。

【对象结构】 场景里只有 1 个 MESH 对象 `table`
  → blender_export.py 约定式导出 source/table.glb (对象名 = 文件名)。
"""

import os

import bpy
import numpy as np

# ---------------------------------------------------------------- 尺寸常量 (米)
W, D, H = 0.80, 0.60, 0.75          # 外廓 x / y / z
TOP_T = 0.04                        # 桌面厚
LEG_S = 0.05                        # 腿截面
LEG_INSET = 0.025                   # 腿相对桌沿内缩
APRON_T = 0.025                     # 横撑厚
APRON_H = 0.035                     # 横撑高
TEX_SIZE = 512                      # 木纹贴图边长

HERE = os.path.dirname(os.path.abspath(__file__))
TEX_DIR = os.path.join(HERE, "textures")
TEX_PATH = os.path.join(TEX_DIR, "wood_light.png")

Z0 = -H / 2.0                       # 底面 z
ZT = Z0 + H                         # 顶面 z (= +H/2)
Z_TOP_BOT = ZT - TOP_T              # 桌面下沿
Z_LEG_TOP = Z_TOP_BOT               # 腿顶接桌面下沿
Z_LEG_MID = Z_LEG_TOP - LEG_S       # 腿高 = 桌面下沿 - 底面

# ---------------------------------------------------------------- 场景重置
bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1.0
scene.render.engine = "BLENDER_EEVEE"          # E1: 5.x 枚举名
scene.view_settings.view_transform = "Standard"  # D2


def add_box(name, size, loc):
    """轴对齐立方体 (size 为全尺寸, loc 为中心), 缩放已 apply。"""
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=loc)
    ob = bpy.context.active_object
    ob.name = name
    ob.scale = (size[0], size[1], size[2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    return ob


# ---------------------------------------------------------------- 零件
parts = []

# 桌面
parts.append(add_box("part_top", (W, D, TOP_T),
                     (0.0, 0.0, Z_TOP_BOT + TOP_T / 2.0)))

# 四条腿
leg_bottom = Z0
leg_top = Z_TOP_BOT
leg_h = leg_top - leg_bottom
lx = W / 2.0 - LEG_INSET - LEG_S / 2.0
ly = D / 2.0 - LEG_INSET - LEG_S / 2.0
leg_cz = leg_bottom + leg_h / 2.0
for sx, sy, nm in ((1, 1, "part_leg_xp_yp"), (1, -1, "part_leg_xp_yn"),
                   (-1, 1, "part_leg_xn_yp"), (-1, -1, "part_leg_xn_yn")):
    parts.append(add_box(nm, (LEG_S, LEG_S, leg_h),
                         (sx * lx, sy * ly, leg_cz)))

# 横撑 (四面, 贴在桌面下沿之内侧, 连接四腿之间)
apron_cz = leg_top - APRON_H / 2.0
apron_len_x = 2.0 * lx - LEG_S      # 两腿之间净距
apron_len_y = 2.0 * ly - LEG_S
parts.append(add_box("part_apron_yp", (apron_len_x, APRON_T, APRON_H),
                     (0.0, ly, apron_cz)))
parts.append(add_box("part_apron_yn", (apron_len_x, APRON_T, APRON_H),
                     (0.0, -ly, apron_cz)))
parts.append(add_box("part_apron_xp", (APRON_T, apron_len_y, APRON_H),
                     (lx, 0.0, apron_cz)))
parts.append(add_box("part_apron_xn", (APRON_T, apron_len_y, APRON_H),
                     (-lx, 0.0, apron_cz)))

# ---------------------------------------------------------------- Boolean UNION (EXACT)
# 依次把每个零件并进第一个 → 单一外壳。零件之间有真实相交体, 不会产生共面团。
base = parts[0]
base.name = "table"
for p in parts[1:]:
    mod = base.modifiers.new(name="bool_" + p.name, type="BOOLEAN")
    mod.operation = "UNION"
    mod.solver = "EXACT"
    mod.object = p
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(p, do_unlink=True)

# ---------------------------------------------------------------- 网格清理 + 合并共面
bpy.context.view_layer.objects.active = base
base.select_set(True)
bpy.ops.object.mode_set(mode="EDIT")
bpy.ops.mesh.select_all(action="SELECT")
bpy.ops.mesh.remove_doubles(threshold=1e-6)  # 合并布尔产生的重合顶点
bpy.ops.mesh.normals_make_consistent(inside=False)
bpy.ops.object.mode_set(mode="OBJECT")

# ---------------------------------------------------------------- 水密自检 (C2 / V7)
me = base.data
edge_faces = {}
for poly in me.polygons:
    vs = list(poly.vertices)
    for i in range(len(vs)):
        e = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
        edge_faces[e] = edge_faces.get(e, 0) + 1
bad_edges = [e for e, c in edge_faces.items() if c != 2]
print(f"[SELFTEST] verts={len(me.vertices)} polys={len(me.polygons)} "
      f"edges={len(edge_faces)} non-manifold-edges={len(bad_edges)}")
if bad_edges:
    raise SystemExit(f"[FAIL] 网格不水密: {len(bad_edges)} 条边不是恰好 2 面 "
                     f"(V7 会拒打包)")

dims = base.dimensions
print(f"[SELFTEST] dimensions = {dims.x:.4f} x {dims.y:.4f} x {dims.z:.4f} m")
print(f"[SELFTEST] bbox center  = {tuple(round(v, 6) for v in base.location)}")

# ---------------------------------------------------------------- 浅木色贴图 (numpy 画)
# 漫反射: 浅木色 (sRGB 约 #D9B98C) + 木纹条纹 + 轻微噪点
os.makedirs(TEX_DIR, exist_ok=True)
n = TEX_SIZE
rng = np.random.default_rng(7)
yy, xx = np.mgrid[0:n, 0:n].astype(np.float64)

# 木纹: 沿 x 方向拉伸的年度纹理 → 扭曲的正弦条带
warp = 6.0 * np.sin(2 * np.pi * yy / n * 3.0 + 0.7) \
    + 3.0 * np.sin(2 * np.pi * yy / n * 7.0 + 1.9)
bands = 0.5 + 0.5 * np.sin(2 * np.pi * yy / n * 22.0 + warp + 0.4 * xx / n)
grain = bands ** 2.2                       # 锐化条纹

base_rgb = np.array([0.85, 0.72, 0.53])     # 浅木色
dark_rgb = np.array([0.68, 0.52, 0.34])     # 木纹深处
t = 0.30 * grain[..., None] + 0.04 * np.random.default_rng(3).random((n, n, 1))
img = base_rgb[None, None, :] * (1 - t) + dark_rgb[None, None, :] * t

# 写 png (Blender 的图像 API 直接写) — 需要预乘 alpha=1
rgba = np.dstack([np.clip(img, 0, 1), np.ones((n, n))]).astype(np.float32)
im = bpy.data.images.new("wood_light", width=n, height=n, alpha=False)
im.pixels.foreach_set(rgba.ravel())
im.filepath_raw = TEX_PATH
im.file_format = "PNG"
im.save()
im.source = "FILE"
im.filepath = TEX_PATH
im.colorspace_settings.name = "sRGB"        # D3: 保持 sRGB, 不改 Non-Color
im.pack()                                   # D5: pack 进 blend
print(f"[SELFTEST] texture -> {TEX_PATH} packed={bool(im.packed_file)}")

# ---------------------------------------------------------------- 材质 (E3: 不写 use_nodes)
mat = bpy.data.materials.new("wood_light")
if mat.node_tree is None:                   # 新代码直接摸 node_tree, 没有才建
    mat.use_nodes = True
nt = mat.node_tree
nt.nodes.clear()
out = nt.nodes.new("ShaderNodeOutputMaterial")
bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
tex = nt.nodes.new("ShaderNodeTexImage")
tex.image = im
tex.interpolation = "Closest"               # D1: 防插值糊边
tex.extension = "REPEAT"
uvm = nt.nodes.new("ShaderNodeUVMap")
out.location = (400, 0)
bsdf.location = (100, 0)
tex.location = (-250, 0)
uvm.location = (-500, 0)
nt.links.new(uvm.outputs["UV"], tex.inputs["Vector"])
nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
bsdf.inputs["Roughness"].default_value = 0.55
nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

base.data.materials.clear()
base.data.materials.append(mat)

# ---------------------------------------------------------------- 保存
blend_path = os.path.join(HERE, "model.blend")
bpy.ops.wm.save_as_mainfile(filepath=blend_path, compress=True)
print(f"[SAVED] {blend_path}")
print("下一步: /snap/blender/current/blender --background --python blender_export.py "
      "-- assets/table")