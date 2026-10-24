# -*- coding: utf-8 -*-
"""render_preview.py — 公交资产包预览渲染 (可选附随文件, MANIFEST_SPEC §2.1)
用法 (项目根): $BLENDER --background --python assets/bus/render_preview.py
产出: assets/bus/preview.png (Cycles CPU)
"""
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
bpy.ops.wm.open_mainfile(filepath=os.path.join(HERE, "model.blend"))
sc = bpy.context.scene

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 128
sc.cycles.use_denoising = True
sc.render.resolution_x = 1600
sc.render.resolution_y = 900
sc.render.image_settings.file_format = "PNG"
sc.view_settings.view_transform = "Standard"      # D2
sc.view_settings.look = "None"

# 世界: 柔灰天光
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.60, 0.65, 0.72, 1.0)
bg.inputs[1].default_value = 1.0

# 地面 (blend 里公交底面 z=0)
bpy.ops.mesh.primitive_plane_add(size=80, location=(0, 0, 0))
floor = bpy.context.object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.42, 0.43, 0.45, 1)
fb.inputs["Roughness"].default_value = 0.6
floor.data.materials.append(fm)
# 路边一条 (给点参照)
bpy.ops.mesh.primitive_plane_add(size=1, location=(0, -4.5, 0.001))
bpy.context.object.scale = (40, 0.8, 1)
lm = bpy.data.materials.new("lane")
lm.use_nodes = True
lb = lm.node_tree.nodes["Principled BSDF"]
lb.inputs["Base Color"].default_value = (0.85, 0.82, 0.35, 1)
bpy.context.object.data.materials.append(lm)


def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.energy, d.size, d.color = energy, size, color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((3, 0, 1.5)) - Vector(loc)).to_track_quat(
        "-Z", "Y").to_euler()


area("key", (14, -12, 9), 4500, 6.0)
area("fill", (-16, -8, 6), 1200, 8.0, (0.85, 0.9, 1.0))
area("rim", (-10, 10, 7), 2500, 5.0)

# 相机: 前右 3/4 视角
cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam"))
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0.5, 0, 1.35))
cam.location = Vector((13.5, -7.5, 2.6))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
cam.data.lens = 50

sc.render.filepath = os.path.join(HERE, "preview.png")
bpy.ops.render.render(write_still=True)
print("OK  预览图 ->", os.path.join(HERE, "preview.png"))
