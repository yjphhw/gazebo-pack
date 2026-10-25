# -*- coding: utf-8 -*-
"""build_starship.py — SpaceX Starship 全栈建模 (Blender 背景执行)
运行: blender --background --python assets/starship/build_starship.py
产出: assets/starship/model.blend (对象名 "starship", 单一水密网格)
坐标: z-up, 底 z=0, 总高 121m, 直径 9m (R=4.5)
部件: booster 圆柱(0..71) + ship/鼻锥 loft(69..121) + 2前襟翼 + 2后襟翼
      + 4栅格翼 → EXACT union
UV:   圆柱投影 u=atan2/(2π)+0.5, v=z/121
材质: slot0=skin.png 不锈钢 / slot1=黑色(翼面/尾部)
"""
import bpy
import bmesh
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
H, R = 121.0, 4.5
N = 64

for ob in list(bpy.data.objects):
    bpy.data.objects.remove(ob, do_unlink=True)
for coll in (bpy.data.meshes, bpy.data.materials, bpy.data.images,
             bpy.data.lights, bpy.data.cameras):
    for x in list(coll):
        if x.users == 0:
            coll.remove(x)

# ---------- 材质 ----------
def new_mat(name):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])
    return m, bsdf

m_skin, b_skin = new_mat("starship_skin")
b_skin.inputs["Metallic"].default_value = 0.1   # D6: gz 无 IBL, 金属感靠贴图 sheen
b_skin.inputs["Roughness"].default_value = 0.32
tex = m_skin.node_tree.nodes.new("ShaderNodeTexImage")
img_path = os.path.join(HERE, "textures", "skin.png")
tex.image = bpy.data.images.load(img_path, check_existing=True)
m_skin.node_tree.links.new(tex.outputs["Color"], b_skin.inputs["Base Color"])

m_dark, b_dark = new_mat("starship_dark")
b_dark.inputs["Base Color"].default_value = (0.04, 0.04, 0.045, 1)
b_dark.inputs["Metallic"].default_value = 0.05
b_dark.inputs["Roughness"].default_value = 0.55


def link(ob):
    bpy.context.collection.objects.link(ob)
    return ob


def cyl(name, r, z0, z1, seg=N):
    bpy.ops.mesh.primitive_cylinder_add(vertices=seg, radius=r,
                                         depth=z1 - z0, location=(0, 0, (z0 + z1) / 2))
    ob = bpy.context.active_object
    ob.name = name
    return ob


def box(name, cx, cy, cz, sx, sy, sz):
    bpy.ops.mesh.primitive_cube_add(size=1, location=(cx, cy, cz))
    ob = bpy.context.active_object
    ob.scale = (sx, sy, sz)
    bpy.ops.object.transform_apply(scale=True)
    ob.name = name
    return ob


def loft(name, rings):
    """rings: [(z, r), ...] 底面 n-gon + 桥接 quads + 顶面 n-gon"""
    verts, faces = [], []
    for z, r in rings:
        for j in range(N):
            a = 2 * math.pi * j / N
            verts.append((r * math.cos(a), r * math.sin(a), z))
    for i in range(len(rings) - 1):
        b = i * N
        for j in range(N):
            j2 = (j + 1) % N
            faces.append((b + j, b + j2, b + N + j2, b + N + j))
    faces.append(tuple(reversed(range(N))))           # 底 cap: 外向 = -Z
    faces.append(tuple(range(len(verts) - N, len(verts))))  # 顶 cap: 外向 = +Z
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    ob = link(bpy.data.objects.new(name, me))
    return ob


def union(base, cutter):
    m = base.modifiers.new("u", 'BOOLEAN')
    m.operation = 'UNION'
    m.solver = 'EXACT'
    m.object = cutter
    bpy.context.view_layer.objects.active = base
    bpy.ops.object.modifier_apply(modifier=m.name)
    bpy.data.objects.remove(cutter, do_unlink=True)


# ---------- 几何 ----------
# 全箭体 = 单一 loft 实体 (避免与 booster 共面布尔产生开放边)
hull_rings = [(0.0, 4.5), (10.0, 4.5), (20.0, 4.5), (30.0, 4.5),
              (40.0, 4.5), (50.0, 4.5), (60.0, 4.5), (68.0, 4.5),
              (71.0, 4.5), (76.0, 4.5), (84.0, 4.5), (92.0, 4.5),
              (100.0, 4.5), (104.5, 4.47), (108.0, 4.35), (111.5, 4.05),
              (115.0, 3.6), (117.8, 2.9), (119.6, 2.0), (120.7, 1.05),
              (121.0, 0.45)]
booster = loft("starship", hull_rings)

parts = [
    box("fwd_flap_p", 4.9, 0, 101.0, 0.9, 0.16, 3.2),    # 前襟翼 ±X
    box("fwd_flap_n", -4.9, 0, 101.0, 0.9, 0.16, 3.2),
    box("aft_flap_p", 0, 4.85, 78.0, 3.4, 0.9, 4.6),     # 后襟翼 ±Y
    box("aft_flap_n", 0, -4.85, 78.0, 3.4, 0.9, 4.6),
    box("grid_pxp", 4.8, 0, 66.5, 0.6, 1.1, 1.5),        # 栅格翼 4 片
    box("grid_pxn", -4.8, 0, 66.5, 0.6, 1.1, 1.5),
    box("grid_pyp", 0, 4.8, 66.5, 1.1, 0.6, 1.5),
    box("grid_pyn", 0, -4.8, 66.5, 1.1, 0.6, 1.5),
]
for p in parts:
    union(booster, p)

booster.name = "starship"
me = booster.data

# ---------- 材质槽 & 分类 ----------
me.materials.clear()
me.materials.append(m_skin)
me.materials.append(m_dark)
for p in me.polygons:
    cz = p.center.z
    r = math.hypot(p.center.x, p.center.y)
    if cz < 0.06 or (cz > H - 0.05 and r < 2.0) or r > 4.56:
        p.material_index = 1        # 黑色: 翼面 / 尾喷区 / 鼻头帽
    else:
        p.material_index = 0        # skin

# ---------- UV: 圆柱投影 ----------
uv = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
for loop in me.loops:
    co = me.vertices[loop.vertex_index].co
    u = (math.atan2(co.y, co.x) / (2 * math.pi)) % 1.0
    uv.data[loop.index].uv = (u, co.z / H)

# ---------- pack + 保存 ----------
try:
    bpy.ops.object.select_all(action='DESELECT')
    booster.select_set(True)
    bpy.context.view_layer.objects.active = booster
    bpy.ops.object.join()          # 单对象确保
    bpy.ops.object.shade_auto_smooth(angle=0.6)
except Exception as e:
    print("SMOOTH_SKIP:", e)

try:
    bpy.ops.file.pack_all()
except Exception as e:
    print("PACK_WARN:", e)

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(HERE, "model.blend"))

# ---------- 自检 ----------
bm = bmesh.new()
bm.from_mesh(me)
bm.verts.ensure_lookup_table()
bm.edges.ensure_lookup_table()
n_w = sum(1 for e in bm.edges if len(e.link_faces) == 1)
xs = [v.co.x for v in bm.verts]
ys = [v.co.y for v in bm.verts]
zs = [v.co.z for v in bm.verts]
print(f"verts={len(bm.verts)} polys={len(me.polygons)} open_edges={n_w}")
print(f"bbox x[{min(xs):.3f},{max(xs):.3f}] y[{min(ys):.3f},{max(ys):.3f}] "
      f"z[{min(zs):.3f},{max(zs):.3f}]")
if n_w != 0:
    print("WATERTIGHT_FAIL")
else:
    print("WATERTIGHT_OK")
bm.free()
print("BUILD_DONE ->", os.path.join(HERE, "model.blend"))
