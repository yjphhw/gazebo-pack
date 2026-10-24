#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""render_preview.py — 资产包自带的产品预览渲染（可选附随文件, MANIFEST_SPEC §2.1）

用法（项目根目录）:
    /snap/blender/current/blender --background --python \
        assets/coke_bottle/render_preview.py

产出: assets/coke_bottle/preview.png  (Cycles CPU, 1000x1250)
说明: 只是"看一眼"用的展示图, 不进 manifest、不影响打包。
      色彩管理用 Standard（D2），材质贴图来自 model.blend（已 pack）。
"""

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
sc.cycles.samples = 96
sc.cycles.use_denoising = True
sc.render.resolution_x = 1000
sc.render.resolution_y = 1250
sc.render.image_settings.file_format = "PNG"
sc.render.film_transparent = False
sc.view_settings.view_transform = "Standard"      # D2: 不用 AgX/Filmic
sc.view_settings.look = "None"

# ---- 世界：柔灰背景 ----
w = bpy.data.worlds.new("W")
sc.world = w
w.use_nodes = True
bg = w.node_tree.nodes["Background"]
bg.inputs[0].default_value = (0.62, 0.64, 0.68, 1.0)
bg.inputs[1].default_value = 1.0

# ---- 地面（模型 origin=center，底面在 -Z/2 = -0.375）----
bpy.ops.mesh.primitive_plane_add(size=12, location=(0, 0, -0.125))
floor = bpy.context.object
fm = bpy.data.materials.new("floor")
fm.use_nodes = True
fb = fm.node_tree.nodes["Principled BSDF"]
fb.inputs["Base Color"].default_value = (0.55, 0.56, 0.58, 1)
fb.inputs["Roughness"].default_value = 0.45
floor.data.materials.append(fm)


def area(name, loc, energy, size, color=(1, 1, 1)):
    d = bpy.data.lights.new(name, "AREA")
    d.energy = energy
    d.size = size
    d.color = color
    o = bpy.data.objects.new(name, d)
    sc.collection.objects.link(o)
    o.location = loc
    o.rotation_euler = (Vector((0, 0, 0.1)) - Vector(loc)).to_track_quat("-Z", "Y").to_euler()


area("key", (0.40, -0.72, 0.66), 42, 0.80)                      # 主光
area("fill", (-0.72, -0.46, 0.40), 13, 0.90, (0.85, 0.9, 1.0))  # 补光（冷）
area("rim", (0.03, 0.78, 0.53), 28, 0.70)                       # 轮廓光

# ---- 相机：对准正面 logo（u=0.75 在 -Y 方向）----
cd = bpy.data.cameras.new("cam")
cd.lens = 70
cam = bpy.data.objects.new("cam", cd)
sc.collection.objects.link(cam)
sc.camera = cam
target = Vector((0, 0, 0.005))
cam.location = Vector((0.13, -0.60, 0.175))
cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()

sc.render.filepath = OUT
bpy.ops.render.render(write_still=True)
print(f"OK  预览图 -> {OUT}")
