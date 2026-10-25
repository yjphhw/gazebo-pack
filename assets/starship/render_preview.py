# -*- coding: utf-8 -*-
"""render_preview.py — 星舰预览渲染 (Blender 背景执行)
运行: blender --background --python assets/starship/render_preview.py
产出: assets/starship/preview.png (1600×900, EEVEE Next, 失败退 Cycles)
"""
import bpy
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "preview.png")

bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "model.blend"))

scene = bpy.context.scene
# 试 EEVEE Next, 不行退 Cycles
for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
    try:
        scene.render.engine = eng
        break
    except TypeError:
        continue
print("ENGINE:", scene.render.engine)
if scene.render.engine == "CYCLES":
    scene.cycles.samples = 48
else:
    try:
        scene.eevee.taa_render_samples = 32
    except AttributeError:
        pass

# 地面 (混凝土灰)
bpy.ops.mesh.primitive_plane_add(size=600, location=(0, 0, -0.01))
gnd = bpy.context.active_object
gnd.name = "ground"
mg = bpy.data.materials.new("gnd")
mg.use_nodes = True
mg.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = \
    (0.28, 0.28, 0.30, 1)
mg.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
gnd.data.materials.append(mg)

# 发射台圈 (简单圆盘垫)
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=14, depth=0.6,
                                    location=(0, 0, 0.3))
pad = bpy.context.active_object
mp = bpy.data.materials.new("pad")
mp.use_nodes = True
mp.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = \
    (0.15, 0.15, 0.16, 1)
pad.data.materials.append(mp)

# 世界背景: 天光
world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
scene.world = world
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs[0].default_value = (0.55, 0.70, 0.95, 1)
bg.inputs[1].default_value = 0.7

# 太阳
sun = bpy.data.lights.new("sun", 'SUN')
sun.energy = 4.0
sun.angle = math.radians(2.0)
so = bpy.data.objects.new("sun", sun)
bpy.context.collection.objects.link(so)
so.rotation_euler = (math.radians(50), 0, math.radians(-30))

# 相机: 3/4 侧面远观全箭
aim = bpy.data.objects.new("aim", None)
bpy.context.collection.objects.link(aim)
aim.location = (0, 0, 55)
cam_d = bpy.data.cameras.new("cam")
cam_d.lens = 32
cam_d.clip_end = 2000
cam = bpy.data.objects.new("cam", cam_d)
bpy.context.collection.objects.link(cam)
cam.location = (160, -120, 80)
con = cam.constraints.new('TRACK_TO')
con.target = aim
con.track_axis = 'TRACK_NEGATIVE_Z'
con.up_axis = 'UP_Y'
scene.camera = cam

scene.render.resolution_x = 1600
scene.render.resolution_y = 900
scene.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print("PREVIEW_DONE ->", OUT)
