#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_preview.py — 摩天大楼预览渲染（可选附随文件, MANIFEST_SPEC §2.1）

用法（项目根目录）:
    /snap/blender/current/blender --background --python \
        assets/skyscraper/render_preview.py

产出: assets/skyscraper/preview.png  (Cycles CPU, 900x1300)
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
sc.render.resolution_y = 1300
sc.render.image_settings.file_format = "PNG"
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"      # D2
sc.view_settings.look = "None"
sc.view_settings.exposure = -0.3

# ---- 天空 ----
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.48, 0.58, 0.70, 1.0)
bg.inputs[1].default_value = 0.55

# ---- 地面（模型底面在 -30）----
bpy.ops.mesh.primitive_plane_add(size=1200, location=(0, 0, -30))
floor = bpy.context.object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.26, 0.28, 0.32, 1)
fb.inputs["Roughness"].default_value = 0.65
floor.data.materials.append(fm)

# ---- 太阳 + 补光 ----
sd = bpy.data.lights.new("sun", "SUN")
sd.energy = 2.6
sd.angle = math.radians(3)
so = bpy.data.objects.new("sun", sd)
sc.collection.objects.link(so)
so.rotation_euler = (math.radians(52), 0.0, math.radians(20))

ad = bpy.data.lights.new("fill", "AREA")
ad.energy = 2.5e6
ad.size = 120
ad.color = (0.80, 0.86, 1.0)
ao = bpy.data.objects.new("fill", ad)
sc.collection.objects.link(ao)
ao.location = (-140, 90, 90)
ao.rotation_euler = (Vector((0, 0, 0)) - Vector(ao.location)).to_track_quat("-Z", "Y").to_euler()

# ---- 相机：3/4 仰视全景 ----
cd = bpy.data.cameras.new("cam")
cd.lens = 30
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0, 0, 0))
cam.location = Vector((35, -48, 10))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"OK  预览图 -> {OUT}")
