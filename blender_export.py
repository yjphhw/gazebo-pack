#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
blender_export.py — 通用 glb 导出器 (流水线层①, MANIFEST_SPEC §1/§2)

【职责边界】只做一件事: 把 .blend 里的网格对象导出成 "原点干净、贴图内嵌" 的
单体 glb, 交付到 assets/<包名>/source/ 下。它:
  * 不读 yaml (Blender 内置 Python 没装 PyYAML, 参数走 JSON/命令行);
  * 不管 Gazebo 侧命名/目录 (那是 gazebo_pack.py 的事);
  * 不做任何美学判断 — 那是对话(层③)的事。

【用法一: 资产包目录 (MANIFEST_SPEC §1 固定命令)】
    blender --background --python blender_export.py -- assets/tag_cube
    给"资产包目录": 自动推导 blend=<包>/model.blend、输出 <包>/source/,
    并(内置 python 无 yaml)从 manifest.yaml 正则提取 frame.origin。
    约定: 场景里每个 MESH 对象 <obj> → source/<obj>.glb
    (对象名需与 manifest 的 source.meshes[].file 文件名一一对应)

【用法一b: 只给 blend (--blend 或当前位置参数给 .blend 文件)】
    blender --background --python blender_export.py -- \\
        --blend assets/tag_cube/model.blend [--origin center]

【用法二: 显式式 (合并导出/改名时)】
    blender --background --python blender_export.py -- \\
        --json '{"blend":"assets/chair/model.blend",
                 "exports":[{"objects":["leg_L","leg_R"],"out":"legs.glb"}]}'
    exports 省略 = 约定式; objects 填多个 = 同一次导出打包成一个 glb
    (glTF 支持一文件多节点, 不需要先 join; out 相对 out_dir, 默认 out_dir=source/)

【为什么要"整体归位" —— 本项目第 1 号坑的推广, PACK_NOTES B2】
    建模时对象带场景摆放位置(如 tag_00 在 (-0.375,-0.225,0.05)), glTF 会把
    这个偏移记进 glb 节点 transform。Gazebo 加载后 visual 相对 link 原点
    (=collision/惯性中心)错开最多 0.4m。所以导出前要把整个导出集平移:
        --origin center         → 整体包围盒中心移到 glb 原点
        --origin bottom-center  → 整体包围盒"底面中心"移到 glb 原点 (落模型贴地)
    平移的是"导出集的世界坐标"而非逐对象归零 —— 对单对象效果一样(相当于
    location 归零), 对多对象模型(桌面+四条腿)则保住零件间相对位置, 只整体挪。
    归位后 Gazebo 里: 模型原点 == link 原点 == collision/惯性中心, 且原点
    位置符合 manifest frame.origin 声明 —— 由 gazebo_pack.py V5 强制复检。
    对象原点定在几何哪里(center/bottom-center)由 manifest 声明, 本脚本负责
    兑现, 两边不一致 V5 直接拒打包。

【贴图: 为什么 glb 是"单文件交付"】
    导出 GLB 格式时 Blender 把图片像素写进 glb 内嵌 bufferView
    (所以 Gazebo AssimpLoader 能直接读, 见 PACK_NOTES A1)。
    本脚本另做一次"贴图是否 pack 进 blend"的自检 —— 不 pack 的话
    .blend 文件换台机器打开会丢图, 属于源头把关(工具侧 V6 只验最终产物 glb)。

【产物路径约定】
    blender_export.py 产出:  assets/<包>/source/*.glb      (原料, 通用名)
    gazebo_pack.py 消费后:   gazebo_models/<name>_<inst>/<name>_<inst>.glb
                                                        (按 manifest 重命名复制)
"""

import argparse   # blender 内置 python 也有, 用来解析 `--` 之后的参数
import json
import os
import re
import sys

import bpy       # Blender Python API (只在 Blender 进程里可用)


# ==============================================================
# 1. 解析参数: `--` 之后的内容才是给本脚本的
#    (blender 自己也会吃掉 -- 之前的所有参数)
# ==============================================================
def parse_args():
    """支持 --json 整包传参, 或 --blend/--out-dir 单独传。"""
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    p = argparse.ArgumentParser(prog="blender_export.py")
    p.add_argument("blend_pos", nargs="?", default=None, metavar="BLENDFILE",
                   help="最简用法: 直接给 .blend 路径 (等价 --blend)")
    p.add_argument("--json", default=None,
                   help="整包 JSON 参数 (见模块文档【用法二])")
    p.add_argument("--blend", default=None, help=".blend 路径 (用法一)")
    p.add_argument("--out-dir", default=None,
                   help="输出目录, 默认 <blend所在目录>/source")
    p.add_argument("--origin", default=None, choices=["center", "bottom-center"],
                   help="glb 原点策略, 需与 manifest 的 frame.origin 一致 (默认 center)")
    return p.parse_args(argv)


args = parse_args()
if args.json:
    spec = json.loads(args.json)
else:
    spec = {"blend": args.blend or args.blend_pos}
    if args.out_dir:
        spec["out_dir"] = args.out_dir
    if args.origin:
        spec["origin"] = args.origin

# ---- 路径解析: 相对路径按"当前工作目录"展开 (在项目根运行即可) ----
blend_path = spec.get("blend")
origin_arg = spec.get("origin")
pkg_dir_guess = None
if blend_path and os.path.isdir(os.path.abspath(blend_path)):
    # 位置参数给的是资产包目录 (MANIFEST_SPEC §1 固定命令形态)
    pkg_dir_guess = os.path.abspath(blend_path)
    blend_path = os.path.join(pkg_dir_guess, spec.get("blend_file", "model.blend"))
    # 没有显式 --origin 时, 从 manifest 扫一行 frame.origin (免 yaml)
    if not origin_arg:
        mf = os.path.join(pkg_dir_guess, "manifest.yaml")
        if os.path.exists(mf):
            m = re.search(r"(?m)^\s{0,8}origin:\s*(bottom-center|center)\b",
                          open(mf, encoding="utf-8").read())
            if m:
                origin_arg = m.group(1)
                print(f"(从 manifest 读到 frame.origin: {origin_arg})")
if not blend_path:
    sys.exit("用法: blender --background --python blender_export.py -- assets/<包名>"
             "   (或 --blend x.blend / --json '{...}')")
blend_path = os.path.abspath(blend_path)
if not os.path.exists(blend_path):
    sys.exit(f"找不到 blend: {blend_path}")

pkg_dir = pkg_dir_guess or os.path.dirname(blend_path)
out_dir = os.path.abspath(spec.get("out_dir") or   # 默认: 包根下的 source/
                          os.path.join(pkg_dir, "source"))


# ==============================================================
# 2. 打开场景
# ==============================================================
# 直接读磁盘上的 .blend (贴图若已 pack 则换目录打开也不丢图)
bpy.ops.wm.open_mainfile(filepath=blend_path)

mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
if not mesh_objs:
    sys.exit(f"{blend_path} 里没有任何网格对象")

# ---- 贴图 pack 自检 (源头把关; 见模块文档【贴图】) ----
# 只看 file 来源的图片 (Render Result 这类生成图不计)
file_imgs = [i for i in bpy.data.images if i.source == "FILE"]
unpacked = [i.name for i in file_imgs if not i.packed_file]
if unpacked:
    print(f"[警告] {len(unpacked)} 张贴图未 pack 进 blend: {unpacked[:5]} ... "
          f"→ .blend 换机器会丢图 (glb 导出仍会内嵌, 但请尽快修复)",
          file=sys.stderr)


# ==============================================================
# 3. 解析导出清单: exports 缺省 = 约定式 (每对象 → source/<名>.glb)
# ==============================================================
exports = spec.get("exports")
if not exports:
    exports = [{"objects": [o.name], "out": f"{o.name}.glb"} for o in mesh_objs]

# ---- 原点策略: --origin 显式值 > manifest 读出值 > center (与 §4 默认一致) ----
origin_policy = origin_arg or "center"
if origin_policy not in ("center", "bottom-center"):
    sys.exit(f"未知 origin: {origin_policy!r} (支持 center / bottom-center)")


def set_bbox_anchor(objs, policy):
    """把整组对象平移, 使"锚点"落在世界原点, 返回(组包围盒尺寸, 锚点).

    center        → 锚点 = 包围盒中心
    bottom-center → 锚点 = 底面中心 (cx, cy, z_min)  模型落地即贴地

    平移整组而不是逐对象归零: 单对象效果等同归零; 多对象模型(桌面+桌腿)
    则零件间相对位置不变, 只整体挪动 —— 这正是 glb 想要的"模型局部坐标"。
    注意: 这里假设对象未旋转/未缩放(建模侧铁律); 若有旋转, matrix_world 仍
    会参与包围盒计算, 但平移不改旋转, 结果依然正确。
    """
    from mathutils import Vector

    mins = Vector((1e18, 1e18, 1e18))
    maxs = Vector((-1e18, -1e18, -1e18))
    for obj in objs:
        mw = obj.matrix_world
        for corner in obj.bound_box:          # 局部空间的 8 个角点
            w = mw @ Vector(corner)
            for k in range(3):
                mins[k] = min(mins[k], w[k])
                maxs[k] = max(maxs[k], w[k])

    if policy == "center":
        anchor = Vector([(mins[k] + maxs[k]) / 2.0 for k in range(3)])
    else:  # bottom-center: xy 居中 + 底面
        anchor = Vector(((mins[0] + maxs[0]) / 2.0,
                         (mins[1] + maxs[1]) / 2.0, mins[2]))

    for obj in objs:                           # 只挪 location (不烘焙进网格)
        obj.location = obj.location - anchor

    return (maxs - mins), anchor


# ==============================================================
# 4. 逐条导出
# ==============================================================
exported = []
for entry in exports:
    # ---- 4.1 找齐这次要导出的对象 ----
    objs = []
    for name in entry["objects"]:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            sys.exit(f"场景里缺少网格对象: {name}")
        objs.append(obj)

    # ---- 4.2 记住原位置 (只改内存, 全程不保存场景文件) ----
    saved = [obj.location.copy() for obj in objs]

    # ---- 4.3 反选 → 按 origin 策略整体归位 → 只选目标 ----
    # 归位是核心铁律: 消除摆放偏移 + 让原点落在 manifest 声明的位置 (B2)
    bpy.ops.object.select_all(action="DESELECT")
    dims, _anchor = set_bbox_anchor(objs, origin_policy)
    for obj in objs:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]

    # ---- 4.4 导出单文件 glb (贴图自动内嵌) ----
    glb_path = os.path.join(out_dir, entry["out"])
    os.makedirs(os.path.dirname(glb_path), exist_ok=True)
    bpy.ops.export_scene.gltf(
        filepath=glb_path,
        export_format="GLB",       # 单文件二进制 glTF, 图片进内嵌 bufferView
        use_selection=True,       # 只导当前选中的对象
        export_apply=False,       # 无修改器时不需要烘焙; 保持顶点原样
        # 坐标系: 导出器自动做 Blender(Z-up) → glTF(Y-up) 换轴;
        # 这个换轴关系正是 gazebo_pack.py 在 SDF visual_pose 里补 roll+90° 的原因 (B1)
    )

    # ---- 4.5 还原位移, 不影响下一个对象 ----
    for obj, loc in zip(objs, saved):
        obj.location = loc

    exported.append(entry["out"])
    # 顺便打印实测尺寸 → 和 manifest geometry.size 对一眼 (gazebo_pack V4 会严查)
    dim_s = " x ".join(f"{v:.4f}" for v in dims)
    print(f"[{len(exported):2d}/{len(exports)}] -> {glb_path}  (bbox {dim_s}, origin={origin_policy})")


# ==============================================================
# 5. 汇总
# ==============================================================
print(f"\nDONE: 导出 {len(exported)} 个 glb -> {out_dir}")
print("下一步: python3 gazebo_pack.py validate assets/<包名>   # 先校验")
print("        python3 gazebo_pack.py build    assets/<包名> --world")
