# -*- coding: utf-8 -*-
"""render_preview.py — Tesla Model 3 预览 (Cycles 3/4 视角)
运行: $BLENDER --background --python assets/tesla/render_preview.py
产出: preview.png (1600x900)
"""
import bpy
import os
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "model.blend")

bpy.ops.wm.open_mainfile(filepath=BLEND)
for ob in list(bpy.data.objects):
    if ob.name not in ("tesla_model3",):
        bpy.data.objects.remove(ob, do_unlink=True)
car = bpy.data.objects["tesla_model3"]
car.location = (0, 0, 0)

scene = bpy.context.scene
scene.render.engine = "CYCLES"
scene.cycles.samples = 96
scene.cycles.use_denoising = True
try:
    scene.cycles.device = "GPU"
except Exception:
    pass
scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.resolution_percentage = 100
scene.view_settings.view_transform = "Standard"

# 地面
bm = __import__("bmesh").new()
__import__("bmesh").ops.create_grid(bm, x_segments=1, y_segments=1, size=40)
me = bpy.data.meshes.new("ground")
bm.to_mesh(me)
g = bpy.data.objects.new("ground", me)
scene.collection.objects.link(g)
mg = bpy.data.materials.new("g_mat")
mg.use_nodes = True
mg.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.18, 0.18, 0.19, 1)
mg.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
g.data.materials.append(mg)

# 车道标线
import bmesh
for i, x in enumerate((-2.0, 2.0)):
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bm.transform(__import__("mathutils").Matrix.Translation((x, 0, 0.002)) @
                 __import__("mathutils").Matrix.Diagonal((0.15, 80, 0.004, 1.0)))
    me = bpy.data.meshes.new("lane%d" % i)
    bm.to_mesh(me)
    ob = bpy.data.objects.new("lane%d" % i, me)
    scene.collection.objects.link(ob)
    m = bpy.data.materials.new("lane%d" % i)
    m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.85, 0.85, 0.85, 1)
    ob.data.materials.append(m)

# 相机: 3/4 前右
cam_data = bpy.data.cameras.new("cam")
cam_data.lens = 50
cam = bpy.data.objects.new("cam", cam_data)
scene.collection.objects.link(cam)
cam.location = (7.5, -5.0, 1.9)
scene.camera = cam
target = Vector((0.1, 0, 0.72))
d = target - cam.location
cam.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()

# 灯光: 主光 + 补光
def area(name, loc, energy, size, target):
    ld = bpy.data.lights.new(name, "AREA")
    ld.energy, ld.size = energy, size
    ob = bpy.data.objects.new(name, ld)
    scene.collection.objects.link(ob)
    ob.location = loc
    dd = Vector(target) - Vector(loc)
    ob.rotation_euler = dd.to_track_quat("-Z", "Y").to_euler()

area("key", (6, -6, 5), 900, 4, (0, 0, 0.8))
area("fill", (-5, 4, 3.5), 350, 5, (0, 0, 0.8))
area("rim", (-3, -6, 3), 300, 3, (0, 0, 1.0))
world = scene.world
world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.65, 0.78, 1)
world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.7

scene.render.filepath = os.path.join(HERE, "preview.png")
bpy.ops.render.render(write_still=True)
print("PREVIEW_SAVED:", os.path.join(HERE, "preview.png"))
