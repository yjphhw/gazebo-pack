# -*- coding: utf-8 -*-
"""build_bus.py — 资产包 assets/bus 建模脚本 (可复跑, 后台 blender)
运行: $BLENDER --background --python assets/bus/build_bus.py
前置: python3 assets/bus/gen_bus_textures.py 已生成 textures/*.png

brief: 公交车 (真实城市公交, 载客30~40人), 1个动态, collision 要真实
尺寸: 10.5(X长) × 2.5(Y宽) × 3.05(Z高) — 标准城市单层公交
约定: 建模坐标 Z-up, 车头 +X, 底面 z=0, XY 对称 → 导出 center 归位后中心在原点

结构 (10 件实体, 相邻件体积重叠 → EXACT 布尔 → 单一水密外壳):
  车体 (顶角切角凸块) / 前保险杠 / 后保险杠 / 底盘裙
  / 4 车轮 (真实圆柱, 胎面 z=0 着地) / 4 轮拱 (差集切削)
贴图: 5 张程序化 PNG (侧R/侧L/前/后/轮), 按面分类 + 手算 UV:
  侧面 u=(±5.25∓x)/10.5 v=z/3.05; 前后 u=y/2.5 v=z/3.05;
  轮帽 (面) u=0.5+(x∓xc)/0.9 v=0.5+(z∓zc)/0.9, 胎面环绕条带。
"""
import bpy
import bmesh
import os
import math
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
TEX = os.path.join(HERE, "textures")
L, W, H = 10.5, 2.5, 3.05
WHEELS = [(3.1, 0.98, 0.45), (3.1, -0.98, 0.45),
          (-3.1, 0.98, 0.45), (-3.1, -0.98, 0.45)]   # (x, y, z轴心)
WR = 0.45                                             # 轮胎半径 (胎面 z=0)

# ---- 清空默认场景 ----
for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)

parts, cutters = [], []


def _obj(name, bm):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def add_box(name, ctr, dims, cut=False):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(Matrix.Translation(ctr) @
                 Matrix.Diagonal((dims[0], dims[1], dims[2], 1.0)))
    ob = _obj(name, bm)
    (cutters if cut else parts).append(ob)
    return ob


def add_slab(name, pts):
    bm = bmesh.new()
    vs = [bm.verts.new(p) for p in pts]
    r = bmesh.ops.convex_hull(bm, input=vs)
    keep = set(r["geom"])
    dead = [f for f in bm.faces if f not in keep]
    if dead:
        bmesh.ops.delete(bm, geom=dead, context="FACES")
    return _obj(name, bm)


def add_wheel(name, xc, yc, zc):
    # 轮底切平: 圆底探到 z=-0.02, 差集切掉 z<0 → z=0 平面胎斑 (真实轮胎接地);
    # 而非 24 边柱的刀刃棱 → 动态刚体静态接触才稳定 (实测刀刃棱整体上浮)
    r, cz = 0.46, zc - 0.01          # 圆底 z=cz-r=-0.02, 切到 z=0 → 平面胎斑
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=24,
                          radius1=r, radius2=r, depth=0.28)
    bm.transform(Matrix.Translation((xc, yc, cz)) @
                 Matrix.Rotation(math.pi / 2, 4, "X"))
    w = _obj(name, bm)
    cbm = bmesh.new()
    bmesh.ops.create_cube(cbm, size=1.0)
    cbm.transform(Matrix.Translation((xc, yc, -0.5)) @
                  Matrix.Diagonal((1.2, 0.36, 1.0, 1.0)))   # z∈[-1.0, 0.0]
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


# ---- 车体: 底 10.5×2.5 @z0.55, 顶折角 0.10 → z3.05 (一个凸块, 天防水密) ----
body_pts = [
    (L/2,  W/2, 0.55), (L/2, -W/2, 0.55), (-L/2,  W/2, 0.55), (-L/2, -W/2, 0.55),
    (L/2-0.10,  W/2-0.10, H), (L/2-0.10, -W/2+0.10, H),
    (-L/2+0.10,  W/2-0.10, H), (-L/2+0.10, -W/2+0.10, H),
]
parts.append(add_slab("body", body_pts))
# ---- 前/后保险杠 (z 0.2..0.70, 与车体 0.55..0.70 体积重叠) ----
add_box("bumper_f", ( L/2-0.225, 0, 0.45), (0.45, 2.30, 0.50))
add_box("bumper_r", (-L/2+0.225, 0, 0.45), (0.45, 2.30, 0.50))
# ---- 底盘裙 (轮间可见, 与车体重叠 0.05) ----
add_box("skirt", (0, 0, 0.525), (7.6, 1.8, 0.15))
# ---- 4 车轮 (轴沿 Y, 胎面 z=0) ----
for i, (xc, yc, zc) in enumerate(WHEELS):
    add_wheel(f"wheel_{i}", xc, yc, zc)
# ---- 4 轮拱切削器 (轴心 z=0.50 r=0.52; 腔底 y=±1.00, 穿过车体侧壁 ±1.25) ----
#  只在并车轮之前切车体 (差集先于并集), 所以大 y 向范围不会伤到车轮
for i, (xc, yc, zc) in enumerate(WHEELS):
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, cap_tris=False, segments=32,
                          radius1=0.52, radius2=0.52, depth=0.30)
    bm.transform(Matrix.Translation((xc, (1.125 if yc > 0 else -1.125), 0.50)) @
                 Matrix.Rotation(math.pi / 2, 4, "X"))
    cutters.append(_obj(f"arch_{i}", bm))

# ---- 布尔: 先切轮拱 (差集), 再并所有件 (并集) — 全 EXACT ----
bpy.context.view_layer.update()
active = parts[0]
bpy.context.view_layer.objects.active = active
ops = [(m, "DIFFERENCE") for m in cutters] + \
      [(m, "UNION") for m in parts[1:]]
for ob, mode in ops:
    bpy.ops.object.modifier_add(type="BOOLEAN")
    mod = active.modifiers[-1]
    mod.operation, mod.solver, mod.object = mode, "EXACT", ob
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(ob, do_unlink=True)
bus = active
bus.name = bus.data.name = "bus"
bus.data.materials.clear()

# ---- E5 清理: 焊接近重复顶点 + 统一法线 (布尔拆分的顶点还原成流形) ----
bpc = bmesh.new()
bpc.from_mesh(me := bus.data)
bmesh.ops.remove_doubles(bpc, verts=bpc.verts, dist=1e-6)
bmesh.ops.recalc_face_normals(bpc, faces=bpc.faces)
bpc.to_mesh(me)
bpc.free()

# ---- 材质 (5 图 + 1 平涂) ----
def make_mat(key, img, rough=0.75, metal=0.0):
    m = bpy.data.materials.new("bus_" + key)
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
    else:
        b.inputs["Base Color"].default_value = (0.75, 0.76, 0.78, 1.0)
    return m


MATS = {"sideR": make_mat("sideR", "side_R.png", 0.6),
        "sideL": make_mat("sideL", "side_L.png", 0.6),
        "front": make_mat("front", "front.png", 0.5),
        "rear":  make_mat("rear", "rear.png", 0.5),
        "roof":  make_mat("roof", None),
        "wheel": make_mat("wheel", "wheel.png", 0.9)}
IDX = {k: i for i, k in enumerate(MATS)}
for k in ("sideR", "sideL", "front", "rear", "roof", "wheel"):
    bus.data.materials.append(MATS[k])

# ---- 贴图 pack (V6) ----
bpy.ops.file.pack_all()

# =====================================================================
# UV: 逐面分类 (法线+位置) + 世界坐标投影
# =====================================================================
me = bus.data
uv = me.uv_layers.new(name="UVMap")


def wheel_axis(p):
    """点离哪个轮轴 (x,z 平面距离, 轴沿 Y) 最近 → (i, dist)"""
    best, bd = -1, 1e9
    for i, (xc, _yc, zc) in enumerate(WHEELS):
        d = math.hypot(p[0] - xc, p[2] - zc)
        if d < bd:
            best, bd = i, d
    return best, bd


for poly in me.polygons:
    c = poly.center
    n = poly.normal
    key, ufn = None, None
    if abs(n.z) >= abs(n.x) and abs(n.z) >= abs(n.y):
        if n.z > 0:
            key, ufn = "roof", lambda v: (v.x / L, v.z / H)
        elif c.z < 0.45:
            # 保险杠底面 → 前纹底部
            key, ufn = "front", lambda v: ((v.y + 1.25) / 2.5, (v.z - 0.2) / 0.5)
        else:
            # 底盘底面 (z=0.45, 几乎不可见) → 侧纹底部 (深灰)
            key, ufn = "rear", lambda v: ((1.25 - v.y) / 2.5, v.z / H)
    elif abs(n.x) >= abs(n.y):
        if n.x > 0:
            key, ufn = "front", lambda v: ((v.y + 1.25) / 2.5, v.z / H)
        else:
            key, ufn = "rear", lambda v: ((1.25 - v.y) / 2.5, v.z / H)
    else:
        if n.y > 0:
            key, ufn = "sideR", lambda v: ((5.25 - v.x) / L, v.z / H)
        else:
            key, ufn = "sideL", lambda v: ((v.x + 5.25) / L, v.z / H)
    # 车轮面: 近轮轴且低 → 覆盖上面分类
    wi, wd = wheel_axis((c.x, c.y, c.z))
    if wd < WR + 0.03 and c.z < 0.95:
        xc, yc, zc = WHEELS[wi]
        if abs(n.y) > 0.6:          # 轮帽 (侧面圆盘)
            key = "wheel"
            ufn = lambda v: (0.5 + (v.x - xc) / 0.9, 0.5 + (v.z - zc) / 0.9)
        elif abs(n.z) > 0.6:        # 胎顶/胎底 → 胎面条带
            key = "wheel"
            ufn = lambda v: (((math.atan2(v.x - xc, v.z - zc) % (2 * math.pi))
                              / (2 * math.pi)), 0.9)
        else:                       # 胎身 → 条带 (u=角度)
            key = "wheel"
            ufn = lambda v: (((math.atan2(v.x - xc, v.z - zc) % (2 * math.pi))
                              / (2 * math.pi)), 0.9)
    if ufn is None:
        ufn = lambda v: (0.0, 0.0)
    poly.material_index = IDX[key]
    for li in poly.loop_indices:
        v = me.vertices[me.loops[li].vertex_index].co
        uv.data[li].uv = ufn(v)

# ---- E5 清理: 焊接 1e-6 重复顶点 + 统一法线朝向 (布尔拆点还原流形) ----
bpc = bmesh.new()
bpc.from_mesh(me)
bmesh.ops.remove_doubles(bpc, verts=bpc.verts, dist=1e-6)
bmesh.ops.recalc_face_normals(bpc, faces=bpc.faces)
bpc.to_mesh(me)
bpc.free()
me.update()

# ---- 先存 blend (自检失败也能从文件查) ----
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "model.blend"))
print("BLEND_SAVED:", os.path.join(HERE, "model.blend"))

# ---- 自检: bbox + 水密 (bmesh: 每边恰 2 面 + 风车方向一致; 同 V7 口径) ----
cs = [bus.matrix_world @ Vector(c) for c in bus.bound_box]
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
            flipped += 1      # 两面对该边同向 → 法线翻面
print("EDGE_OPEN:", opening, " FLIPPED:", flipped)
if opening or flipped:
    raise SystemExit(f"网格不水密 (开口 {opening} / 翻面 {flipped}) → 修模")
print("WATERTIGHT: OK")
