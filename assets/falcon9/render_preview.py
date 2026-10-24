#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_preview.py — 猎鹰 9 号预览渲染（可选附随文件, MANIFEST_SPEC §2.1）

用法（项目根目录）:
    /snap/blender/current/blender --background --python assets/falcon9/render_preview.py
产出: assets/falcon9/preview.png (Cycles CPU, 900x1500)
"""

import math
import os

import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
BLEND = os.path.join(HERE, "model.blend")
OUT = os.path.join(HERE, "preview.png")

bpy.ops.wm.open_mainfile(filepath=BLEND)
sc = bpy.context.scene

sc.render.engine = "CYCLES"
sc.cycles.device = "CPU"
sc.cycles.samples = 64
sc.cycles.use_denoising = True
sc.render.resolution_x = 900
sc.render.resolution_y = 1500
sc.render.image_settings.file_format = "PNG"
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = 0.05

# 天空
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.42, 0.53, 0.68, 1.0)
bg.inputs[1].default_value = 0.55

# 地面（模型底面在 -35）
bpy.ops.mesh.primitive_plane_add(size=1600, location=(0, 0, -35.0))
floor = bpy.context.object
fm = bpy.data.materials.new("ground")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.15, 0.16, 0.15, 1)
fb.inputs["Roughness"].default_value = 0.85
floor.data.materials.append(fm)

# 发射台（混凝土圆台）
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=12, depth=1.0,
                                    location=(0, 0, -35.49))
pad = bpy.context.object
pm = bpy.data.materials.new("pad")
pm.use_nodes = True
pb = pm.node_tree.nodes["Principled BSDF"]
pb.inputs["Base Color"].default_value = (0.10, 0.10, 0.095, 1)
pb.inputs["Roughness"].default_value = 0.75
pad.data.materials.append(pm)

# 中央熏黑圆盘
bpy.ops.mesh.primitive_cylinder_add(vertices=64, radius=7, depth=0.02,
                                    location=(0, 0, -34.98))
scorch = bpy.context.object
sm = bpy.data.materials.new("scorch")
sm.use_nodes = True
sb = sm.node_tree.nodes["Principled BSDF"]
sb.inputs["Base Color"].default_value = (0.05, 0.048, 0.045, 1)
sb.inputs["Roughness"].default_value = 0.9
scorch.data.materials.append(sm)

# 光
sd = bpy.data.lights.new("sun", "SUN")
sd.energy = 2.5
sd.angle = math.radians(2.5)
so = bpy.data.objects.new("sun", sd)
sc.collection.objects.link(so)
so.rotation_euler = (math.radians(55), 0.0, math.radians(35))

ad = bpy.data.lights.new("fill", "AREA")
ad.energy = 4.0e5
ad.size = 90
ad.color = (0.80, 0.87, 1.0)
ao = bpy.data.objects.new("fill", ad)
sc.collection.objects.link(ao)
ao.location = (-90, 70, 70)
ao.rotation_euler = (Vector((0, 0, 0)) - Vector(ao.location)).to_track_quat("-Z", "Y").to_euler()

# 相机：3/4 仰视，能看到 logo/国旗
cd = bpy.data.cameras.new("cam")
cd.lens = 50
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0, 0, -2))
cam.location = Vector((62, -92, 32))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"OK  预览图 -> {OUT}")
