# -*- coding: utf-8 -*-
"""render_previews_batch.py — 给缺预览图的资产包批量补 preview.png (MANIFEST_SPEC §5.1)
运行: blender --background --python render_previews_batch.py
取景: 自动按模型 bbox——相机放 (d, -d, 0.45d) 三视角, d = 2.8×最大边
"""
import bpy
import math
import mathutils
import os

BASE = os.path.dirname(os.path.abspath(__file__))
PACKAGES = ["cabin", "cabin2", "chair", "table", "tag_cube"]

for name in PACKAGES:
    pkg = os.path.join(BASE, "assets", name)
    blend = os.path.join(pkg, "model.blend")
    if not os.path.exists(blend):
        print(f"[{name}] SKIP no blend")
        continue
    bpy.ops.wm.open_mainfile(filepath=blend)
    scene = bpy.context.scene
    for eng in ("BLENDER_EEVEE_NEXT", "BLENDER_EEVEE", "CYCLES"):
        try:
            scene.render.engine = eng
            break
        except TypeError:
            continue

    # ---- bbox (只算原模型网格) ----
    pts = []
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            for c in ob.bound_box:
                pts.append(ob.matrix_world @ mathutils.Vector(c))
    if not pts:
        print(f"[{name}] SKIP no mesh")
        continue
    mn = mathutils.Vector((min(p.x for p in pts), min(p.y for p in pts),
                           min(p.z for p in pts)))
    mx = mathutils.Vector((max(p.x for p in pts), max(p.y for p in pts),
                           max(p.z for p in pts)))
    ctr = (mn + mx) / 2
    d = 2.8 * max(mx.x - mn.x, mx.y - mn.y, mx.z - mn.z)

    # ---- 地面 ----
    bpy.ops.mesh.primitive_plane_add(size=4 * d, location=(0, 0, mn.z - 0.005))
    gnd = bpy.context.active_object
    mg = bpy.data.materials.new(name + "_gnd")
    mg.use_nodes = True
    mg.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = \
        (0.30, 0.30, 0.32, 1)
    mg.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.9
    gnd.data.materials.append(mg)

    # ---- 世界天光 + 太阳 ----
    world = bpy.data.worlds.get("World") or bpy.data.worlds.new("World")
    scene.world = world
    world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.55, 0.70, 0.95, 1)
    bg.inputs[1].default_value = 0.7
    sun = bpy.data.lights.new("sun", 'SUN')
    sun.energy = 4.0
    so = bpy.data.objects.new("sun", sun)
    bpy.context.collection.objects.link(so)
    so.rotation_euler = (math.radians(50), 0, math.radians(-30))

    # ---- 相机 3/4 视角 ----
    aim = bpy.data.objects.new("aim", None)
    bpy.context.collection.objects.link(aim)
    aim.location = ctr
    cd = bpy.data.cameras.new("cam")
    cd.lens = 50
    cd.clip_end = 100 * max(d, 1.0)
    cam = bpy.data.objects.new("cam", cd)
    bpy.context.collection.objects.link(cam)
    cam.location = (ctr.x + d, ctr.y - d, ctr.z + 0.45 * d)
    con = cam.constraints.new('TRACK_TO')
    con.target = aim
    con.track_axis = 'TRACK_NEGATIVE_Z'
    con.up_axis = 'UP_Y'
    scene.camera = cam

    scene.render.resolution_x = 1600
    scene.render.resolution_y = 900
    scene.render.filepath = os.path.join(pkg, "preview.png")
    bpy.ops.render.render(write_still=True)
    print(f"[{name}] PREVIEW_OK -> {scene.render.filepath}")

print("BATCH_DONE")
