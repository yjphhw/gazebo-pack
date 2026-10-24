"""make_tag_cubes.py — 批量生成贴 AprilTag 的立方体并导出

用法 (先跑 gen_apriltags.py 生成贴图):
    blender --background --python make_tag_cubes.py

输出 (与本脚本同目录):
    tag_cubes.blend          完整场景 (贴图已内嵌, 可独立打开)
    gltf/tag_00.glb ~ ...    每个立方体一个 glb (纹理内嵌)
    preview_top.png          俯视预览图, 用来肉眼检查标签朝向/可读性

结构:
    1. 配置区   2. 建材质(标签/木纹)  3. 建 24 个立方体并打 UV
    4. 相机/灯光/世界  5. 打包+存 blend  6. 逐个导出 glb  7. 渲染预览
"""

import bpy
import os
import sys

# =========================== 1. 配置区 ===========================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__)) if "__file__" in globals() else os.getcwd()
TAG_DIR    = os.path.join(SCRIPT_DIR, "tags")
WOOD_PNG   = os.path.join(SCRIPT_DIR, "wood.png")
OUT_BLEND  = os.path.join(SCRIPT_DIR, "tag_cubes.blend")
OUT_GLTF   = os.path.join(SCRIPT_DIR, "gltf")
PREVIEW    = os.path.join(SCRIPT_DIR, "preview_top.png")

TAG_COUNT = 24      # 立方体数量 = ID 0~23
CUBE      = 0.1     # 边长, 米 (Gazebo/ROS 惯用米制)
GAP       = 0.05    # 立方体之间的间隙
COLS, ROWS = 6, 4   # 网格布局: 6 列 x 4 行 = 24
PITCH     = CUBE + GAP          # 网格间距 (中心到中心)

# ---- 前置检查: 贴图必须先由 gen_apriltags.py 生成好 ----
missing = [p for p in [WOOD_PNG] +
           [os.path.join(TAG_DIR, f"tag_{i:02d}.png") for i in range(TAG_COUNT)]
           if not os.path.exists(p)]
if missing:
    sys.exit("缺少贴图, 请先运行: python3 gen_apriltags.py\n缺失: " + missing[0])
assert COLS * ROWS == TAG_COUNT, "COLS*ROWS 必须等于 TAG_COUNT"

bpy.ops.wm.read_factory_settings(use_empty=True)   # 清空成空白场景
scene = bpy.context.scene


# =========================== 2. 材质 ===========================
def _new_material(name):
    """建一个只带 Principled BSDF 的空材质, 返回 (材质, 节点字典, 连线器)。"""
    mat = bpy.data.materials.new(name)
    if mat.node_tree is None:      # 兼容: 老版本材质默认无节点树
        mat.use_nodes = True
    nodes = mat.node_tree.nodes
    links = mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    bsdf.inputs["Metallic"].default_value = 0.0   # 标签/木头都不反金属光
    return mat, nodes, links, bsdf


def _load_image(path):
    """把 png 读进 Blender 并内嵌到 .blend (pack), 这样文件拷到别处也不丢贴图。

    colorspace 保持默认 sRGB: 标签是给人眼/检测器看的显示色,
    导出 glTF 时也会按 sRGB 编码, 千万别改成 Non-Color。
    """
    img = bpy.data.images.load(path)
    img.pack()
    return img


def make_tag_material(tag_id):
    """标签材质: UV -> Image Texture(NEAREST 采样) -> Base Color。

    interpolation='Closest' 即"最近邻采样": 放大/缩小时不插值,
    黑白模块边缘保持刀切般锐利, AprilTag 检测最怕模糊, 所以不能用
    默认的 Linear (会产生灰色过渡)。
    """
    mat, nodes, links, bsdf = _new_material(f"TagMat_{tag_id:02d}")
    img = _load_image(os.path.join(TAG_DIR, f"tag_{tag_id:02d}.png"))

    texcoord = nodes.new("ShaderNodeTexCoord")
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = img
    image_node.interpolation = 'Closest'    # NEAREST, 关键!
    image_node.extension = 'CLIP'           # UV 超出 0~1 直接透明, 防止串色

    links.new(texcoord.outputs["UV"], image_node.inputs["Vector"])
    links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.35   # 略微光滑, 像贴纸
    return mat


def make_wood_material():
    """木纹材质: 5 面共用一张 wood.png。

    为什么用图片而不是程序化节点 (noise/wave)? 因为 glTF 导出时
    Blender 无法把程序化节点转换过去 (glTF 只认图片纹理),
    Gazebo 里会丢失/变成纯白。所以木纹也提前生成成 png。
    """
    mat, nodes, links, bsdf = _new_material("WoodMat")
    img = _load_image(WOOD_PNG)

    texcoord = nodes.new("ShaderNodeTexCoord")
    image_node = nodes.new("ShaderNodeTexImage")
    image_node.image = img
    image_node.interpolation = 'Linear'     # 木纹不是检测目标, 平滑点好看
    image_node.extension = 'REPEAT'         # 允许平铺

    links.new(texcoord.outputs["UV"], image_node.inputs["Vector"])
    links.new(image_node.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.6    # 木头比较粗糙
    return mat


wood_mat = make_wood_material()
tag_mats = [make_tag_material(i) for i in range(TAG_COUNT)]


# =========================== 3. 建立方体 + 打 UV ===========================
def planar_uv(normal, co):
    """按面法线方向选投影平面, 把顶点局部坐标 (x,y,z) 映射到 0~1 的 UV。

    方块以自身中心为原点, 顶点坐标范围是 [-CUBE/2, +CUBE/2],
    加半边长再除以边长正好归一化到 [0,1]:
      * 水平顶/底面 (法线沿 Z): 用 x,y 投影 —— 标签面也用这个,
        等价于"从正上方往下看", u 轴 = 世界 +X, v 轴 = 世界 +Y;
      * 竖直侧面 (法线沿 X 或 Y): 用对应另外两个坐标轴, 避免投影
        成一条线 (退化)。
    每个面都映射到完整的 0~1 区域, 各面 UV 重叠没关系 —— 它们
    要么共享同一张木纹, 要么是独立面。
    """
    h = CUBE / 2.0
    if abs(normal.z) > 0.5:
        return (co.x + h) / CUBE, (co.y + h) / CUBE
    if abs(normal.x) > 0.5:
        return (co.y + h) / CUBE, (co.z + h) / CUBE
    return (co.x + h) / CUBE, (co.z + h) / CUBE


for i in range(TAG_COUNT):
    col, row = i % COLS, i // COLS
    x = (col - (COLS - 1) / 2.0) * PITCH     # 网格居中排布
    y = (row - (ROWS - 1) / 2.0) * PITCH

    bpy.ops.mesh.primitive_cube_add(size=CUBE, location=(x, y, CUBE / 2))  # 底面贴 z=0
    obj = bpy.context.active_object
    obj.name = f"tag_{i:02d}"          # 导出的文件名 = tag_00.glb
    me = obj.data

    # ---- 材质槽: 0=标签, 1=木纹 ----
    me.materials.append(tag_mats[i])
    me.materials.append(wood_mat)

    # ---- UV 层: 逐面逐顶点写入 ----
    uv_layer = me.uv_layers.active or me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        poly.material_index = 0 if n.z > 0.5 else 1   # 只有顶面(+Z)贴标签
        for li in poly.loop_indices:                  # loop = 面上的一个角点引用
            co = me.vertices[me.loops[li].vertex_index].co
            uv_layer.data[li].uv = planar_uv(n, co)


# =========================== 4. 相机 / 灯光 / 世界 ===========================
world = bpy.data.worlds.new("World")
scene.world = world
if world.use_nodes:
    bg = world.node_tree.nodes.get("Background")
    if bg:
        bg.inputs[0].default_value = (0.8, 0.8, 0.8, 1.0)   # 浅灰环境光, 方便检查
        bg.inputs[1].default_value = 1.0

bpy.ops.object.light_add(type='SUN', location=(0, 0, 3))
bpy.context.active_object.data.energy = 2.0    # 太阳光默认朝 -Z 打, 正对顶面

# 俯视正交相机: rotation=(0,0,0) 即朝 -Z 看, 正好看到 24 个标签面
bpy.ops.object.camera_add(location=(0, 0, 1.6), rotation=(0, 0, 0))
cam = bpy.context.active_object
cam.data.type = 'ORTHO'
cam.data.ortho_scale = COLS * PITCH * 1.1      # 视野宽度 = 网格宽度 * 1.1 留边
scene.camera = cam

# 渲染设置: 标签对比度不能被色彩管理调灰, 用 Standard 而非 AgX/Filmic
scene.view_settings.view_transform = 'Standard'
scene.render.engine = 'BLENDER_EEVEE'           # Blender 5.x 枚举名
scene.render.resolution_x = 1280
scene.render.resolution_y = int(1280 * (ROWS * PITCH) / (COLS * PITCH))


# =========================== 5. 打包 + 存 .blend ===========================
bpy.ops.file.pack_all()                        # 把所有外置贴图内嵌进 .blend
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
print(f"[1/3] 已保存 .blend: {OUT_BLEND}")


# =========================== 6. 逐个导出 glb ===========================
os.makedirs(OUT_GLTF, exist_ok=True)
tag_objs = sorted((o for o in bpy.data.objects
                   if o.type == 'MESH' and o.name.startswith("tag_")),
                  key=lambda o: o.name)

for o in tag_objs:
    bpy.ops.object.select_all(action='DESELECT')
    o.select_set(True)
    bpy.context.view_layer.objects.active = o
    # use_selection=True: 只导出选中的这一个立方体;
    # export_format='GLB': 单文件二进制 glTF, 贴图自动内嵌
    bpy.ops.export_scene.gltf(
        filepath=os.path.join(OUT_GLTF, f"{o.name}.glb"),
        export_format='GLB',
        use_selection=True,
        export_apply=False,
    )
print(f"[2/3] 已导出 {len(tag_objs)} 个 glb -> {OUT_GLTF}/")


# =========================== 7. 渲染俯视预览 ===========================
scene.render.filepath = PREVIEW
bpy.ops.render.render(write_still=True)
print(f"[3/3] 已渲染预览: {PREVIEW}")
print("DONE")
