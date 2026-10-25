# -*- coding: utf-8 -*-
"""build_tesla.py — Tesla Model 3 建模 (可复跑)
运行: $BLENDER --background --python assets/tesla/build_tesla.py
前置: python3 assets/tesla/gen_tesla_textures.py

brief: tesla model3, 快速; 尺寸按真实车 4.69×1.85×1.44m
结构 (8 件, 体积重叠 → EXACT 布尔 → 单一水密外壳):
  车顶舱 (12 点凸块, 侧面=快背弧线) / 车体裙 (z0.3..0.62 满宽)
  / 4 轮胎 (圆柱, 底切平面 z=0.02 贴地) / 4 轮拱差集
贴图: 4 张 (side/front/rear/wheel), 面分类 + 世界坐标 UV (见 gen_tesla_textures 头)
约定: 建模 Z-up, 车头 +X, 底面 z=0, XY 对称 → center 原点
"""
import bpy
import bmesh
import os
import math
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
L, W, H = 4.69, 1.85, 1.44
AX = 1.45                # 轮距 (前后轴 x)
WY = 0.75               # 轮胎中心 y
TZ = 0.33               # 轮轴 z
TR = 0.33               # 轮胎半径 (0.33+0.02 切平)

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

parts, cutters = [], []


def _obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_box(name, ctr, dims):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Translation(ctr) @
                 Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0)))
    parts.append(_obj(name, bm))
    return parts[-1]


def add_slab(name, pts):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    r = bmesh.ops.convex_hull(bm, input=vs)
    keep = set(r["geom"])
    dead = [f for f in bm.faces if f not in keep]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    return _obj(name, bm)


def add_tire(name, xc, yc):
    # 圆柱 r0.35 轴心 z=TZ+0.02, 切掉 z<0.02 → 平面胎斑 (凸包底成面, 接触稳定)
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
                          radius1=TR, radius2=TR, depth=0.24)
    bm.transform(Matrix.Translation((xc, yc, TZ)) @
                 Matrix.Rotation(math.pi / 2, 4, "X"))
    w = _obj(name, bm)
    cbm = bmesh.new()
    bmesh.ops.create_cube(cbm, size=1.0)
    cbm.transform(Matrix.Translation((xc, yc, -0.5)) @
                  Matrix.Diagonal((1.0, 0.36, 1.0, 1.0)))   # z∈[-1.0, 0.0] 切到 z=0
    cutter = _obj(name + "_cut", cbm)
    bpy.context.view_layer.update()
    bpy.context.view_layer.objects.active = w
    bpy.ops.object.modifier_add(type="BOOLEAN")
    mod = w.modifiers[-1]
    mod.operation, mod.solver, mod.object = "DIFFERENCE", "EXACT", cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter, do_unlink=True)
    parts.append(w)
    return w


def add_arch(name, xc, yc):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                          radius1=0.37, radius2=0.37, depth=0.20)
    bm.transform(Matrix.Translation(
        (xc, (0.975 if yc > 0 else -0.975), TZ)) @
        Matrix.Rotation(math.pi / 2, 4, "X"))   # y∈[0.825,1.125] 穿侧壁
    cutters.append(_obj(name, bm))


# 车顶舱: 底 z0.55, 顶折角 0.30 内缩 → z1.44 (12 点)
roof_pts = [
    (L/2, W/2, 0.55), (L/2, -W/2, 0.55), (-L/2, W/2, 0.55), (-L/2, -W/2, 0.55),
    (L/2-0.30, W/2-0.10, 1.20), (L/2-0.30, -W/2+0.10, 1.20),
    (-L/2+0.30, W/2-0.10, 1.32), (-L/2+0.30, -W/2+0.10, 1.32),
    (L/2-1.30, W/2-0.10, H), (L/2-1.30, -W/2+0.10, H),
    (-L/2+1.20, W/2-0.10, H-0.02), (-L/2+1.20, -W/2+0.10, H-0.02),
]
parts.append(add_slab("roof", roof_pts))
# 车体裙: 前后延伸到鼻/尾 (z 0.30..0.62, 与车顶舱 0.55..0.62 重叠)
add_box("body", (0, 0, 0.46), (L, W, 0.32))
# 4 轮胎 + 4 轮拱
for i, (sx, sy) in enumerate(((1, 1), (1, -1), (-1, 1), (-1, -1))):
    add_tire(f"tire_{i}", sx * AX, sy * WY)
    add_arch(f"arch_{i}", sx * AX, sy * WY)

# ---- 布尔: 先差集轮拱, 再并集全部 ----
bpy.context.view_layer.update()
active = parts[0]
bpy.context.view_layer.objects.active = active
for ob, mode in [(m, "DIFFERENCE") for m in cutters] + \
                [(m, "UNION") for m in parts[1:]]:
    bpy.ops.object.modifier_add(type="BOOLEAN")
    mod = active.modifiers[-1]
    mod.operation, mod.solver, mod.object = mode, "EXACT", ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob, do_unlink=True)
car = active
car.name = car.data.name = "tesla_model3"
car.data.materials.clear()

# E5: 焊接 + 统一法线
me = car.data
bpc = bmesh.new()
bpc.from_mesh(me)
bmesh.ops.remove_doubles(bpc, verts=bpc.verts, dist=1e-6)
bmesh.ops.recalc_face_normals(bpc, faces=bpc.faces)
bpc.to_mesh(me)
bpc.free()
me.update()

# ---- 材质 ----
def make_mat(key, img, rough=0.35, metal=0.2):  # D6: gz 无 IBL, metallic>0.2 发黑
    m = bpy.data.materials.new("tm3_" + key)
    m.use_nodes = True
    nt = m.node_tree
    b = nt.nodes["Principled BSDF"]
    b.inputs["Roughness"].default_value = rough
    b.inputs["Metallic"].default_value = metal
    if img:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.image = bpy.data.images.load(os.path.join(TEX, img),
                                         check_existing=False)
        uv = nt.nodes.new("ShaderNodeUVMap")
        uv.uv_map = "UVMap"
        nt.links.new(uv.outputs[0], tex.inputs["Vector"])
        nt.links.new(tex.outputs["Color"], b.inputs["Base Color"])
    return m


MATS = {"side": make_mat("side", "side.png"),
        "front": make_mat("front", "front.png", 0.3, 0.15),
        "rear": make_mat("rear", "rear.png", 0.3, 0.15),
        "roof": make_mat("roof", "roof.png", 0.25, 0.2),
        "tire": make_mat("tire", "wheel.png", 0.9, 0.0)}
IDX = {k: i for i, k in enumerate(MATS)}
for k in ("side", "front", "rear", "roof", "tire"):
    me.materials.append(MATS[k])
bpy.ops.file.pack_all()

# ---- UV: 面分类 + 世界坐标投影 ----
uv = me.uv_layers.new(name="UVMap")


def nearest_axle(p):
    bd = 1e9
    for xc in (AX, -AX):
        d = math.hypot(p[0] - xc, p[2] - TZ)
        bd = min(bd, d)
    return bd


for poly in me.polygons:
    c = poly.center
    n = poly.normal
    if nearest_axle((c.x, c.y, c.z)) < TR + 0.03 and c.z < 0.70:
        # 轮胎面
        xc = AX if c.x > 0 else -AX
        if abs(n.y) > 0.6:      # 轮帽
            ufn = lambda v: (0.5 + (v.x - xc) / 0.6, 0.5 + (v.z - TZ) / 0.6)
        else:                   # 胎面/胎侧 → 环绕条带
            ufn = lambda v: (((math.atan2(v.x - xc, v.z - TZ) % (2 * math.pi))
                              / (2 * math.pi)), 0.9)
        poly.material_index = IDX["tire"]
    elif abs(n.y) >= abs(n.x) and abs(n.y) >= abs(n.z):
        if n.y > 0:
            poly.material_index = IDX["side"]
            ufn = lambda v: ((2.345 - v.x) / L, v.z / H)
        else:
            poly.material_index = IDX["side"]
            ufn = lambda v: ((2.345 - v.x) / L, v.z / H)
    elif abs(n.x) >= abs(n.z):
        if n.x > 0:
            poly.material_index = IDX["front"]
            ufn = lambda v: ((v.y + W / 2) / W, v.z / H)
        else:
            poly.material_index = IDX["rear"]
            ufn = lambda v: ((W / 2 - v.y) / W, v.z / H)
    else:  # n.z 主导
        if n.z > 0:
            if n.x > 0.05:      # 前风挡斜面 → 前贴图 (挡风矩形已画好)
                poly.material_index = IDX["front"]
                ufn = lambda v: ((v.y + W / 2) / W, v.z / H)
            elif n.x < -0.05:   # 后风挡斜面 → 后贴图
                poly.material_index = IDX["rear"]
                ufn = lambda v: ((W / 2 - v.y) / W, v.z / H)
            else:               # 顶面 (全景玻璃) → roof 贴图
                poly.material_index = IDX["roof"]
                ufn = lambda v: ((v.y + W / 2) / W, (v.x + 2.345) / L)
        else:                   # 底面 → 侧贴图下部 (黑裙, 不可见)
            poly.material_index = IDX["side"]
            ufn = lambda v: ((2.345 - v.x) / L, v.z / H)
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = ufn(v)

# ---- 存 + 自检 ----
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "model.blend"))
print("BLEND_SAVED:", os.path.join(HERE, "model.blend"))
cs = [car.matrix_world @ Vector(c) for c in car.bound_box]
xs = [c.x for c in cs]; ys = [c.y for c in cs]; zs = [c.z for c in cs]
print(f"MODEL bbox: {max(xs)-min(xs):.4f} x {max(ys)-min(ys):.4f} x "
      f"{max(zs)-min(zs):.4f}, z_min={min(zs):.4f}, verts={len(me.vertices)}")
bm2 = bmesh.new()
bm2.from_mesh(me)
opening = sum(1 for e in bm2.edges if len(e.link_faces) != 2)
flipped = 0
for e in bm2.edges:
    if len(e.link_faces) == 2:
        dirs = []
        for f in e.link_faces:
            for lp in f.loops:
                if lp.edge == e:
                    dirs.append((lp.vert.index, lp.link_loop_next.vert.index))
                    break
        if len(dirs) == 2 and dirs[0] == dirs[1]:
            flipped += 1
print("EDGE_OPEN:", opening, " FLIPPED:", flipped)
if opening or flipped:
    raise SystemExit(f"网格不水密 (开口 {opening} / 翻面 {flipped})")
print("WATERTIGHT: OK")
