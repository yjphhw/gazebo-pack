#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_preview.py — 货架预览渲染（可选附随文件, MANIFEST_SPEC §2.1）

用法（项目根目录）:
    /snap/blender/current/blender --background --python assets/shelf/render_preview.py
产出: assets/shelf/preview.png (Cycles CPU, 900x1200)
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
sc.render.resolution_y = 1200
sc.render.image_settings.file_format = "PNG"
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"
sc.view_settings.look = "None"
sc.view_settings.exposure = -0.7

# 环境
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.52, 0.60, 0.70, 1.0)
bg.inputs[1].default_value = 0.45

# 地面（底面在 -1.0）
bpy.ops.mesh.primitive_plane_add(size=40, location=(0, 0, -1.0))
floor = bpy.context.object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.24, 0.26, 0.29, 1)
fb.inputs["Roughness"].default_value = 0.60
floor.data.materials.append(fm)

# 光
sd = bpy.data.lights.new("sun", "SUN")
sd.energy = 1.8
sd.angle = math.radians(3)
so = bpy.data.objects.new("sun", sd)
sc.collection.objects.link(so)
so.rotation_euler = (math.radians(50), 0.0, math.radians(25))

for name, loc, energy, size, color in (
    ("fill", (-3.0, -2.5, 2.6), 150, 2.5, (0.80, 0.86, 1.0)),
    ("rim", (2.6, 2.2, 2.4), 100, 2.0, (1.0, 0.98, 0.94)),
):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.size = size
    d.color = color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()

# 相机：3/4 前视，能看进层板
cd = bpy.data.cameras.new("cam")
cd.lens = 45
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0, 0, 0.02))
cam.location = Vector((1.85, -2.35, 1.15))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"OK  预览图 -> {OUT}")
