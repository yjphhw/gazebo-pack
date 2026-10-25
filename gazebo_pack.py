#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
gazebo_pack.py — 资产包 → Gazebo 模型库 打包工具 (层①骨架, MANIFEST_SPEC v1.0)

【它在流水线里的位置】
    对话建模 → assets/<包>/manifest.yaml + source/*.glb    (层②③: 人/AI)
    ──────────────────────────────────────────────────────────
    本工具   → validate(校验) → render(填模板) → write(落盘)  (层①: 纯机械)
    ──────────────────────────────────────────────────────────
    产物     → gazebo_models/<name>_<instance>/ + worlds/<world>.sdf

【三条纪律 (§7 工具宪法)】
    1. 只读 assets/, 只写 gazebo_models/ + worlds/, 永不反向改资产;
    2. 产物可随时删除重建 —— 资产才是源;
    3. 校验不过宁可失败, 不生成"看起来成功、实际是坏的"模型 (❌ 即拒).

【用法 (§6 CLI, 在项目根目录运行)】
    python3 gazebo_pack.py validate assets/tag_cube           # 只体检, 不写盘
    python3 gazebo_pack.py build    assets/tag_cube            # 体检通过才生成
    python3 gazebo_pack.py build    assets/tag_cube --world    # 额外生成 world
    python3 gazebo_pack.py build    assets/ --all              # 批量
    退出码: 0=成功  1=校验失败(逐条打印)  2=用法/文件错误

【校验器为什么这么"啰嗦" —— 每一条都对应踩过的坑, PACK_NOTES H 表】
    V4 尺寸不符 = 改了模型忘改交接单;  V5 原点不对 = visual/collision 错位;
    V6 贴图外链 = 换机器加载黑盒;      V7 非水密   = auto 惯量体积积分算不出;
    V8 版本不够 = auto 语法被 SDF 拒;  V9 动态+不优化 = 接触不稳.

【一个必须知道的解码约定 (V4/V5 的前提)】
    Blender 导出器的 Y-up 换轴 (PACK_NOTES B1) 是烘焙进"顶点数据"的
    (实测: 节点无 transform, 标签面顶点在 +Y)。 换轴映射:
        glTF.xyz  =  Blender (x, z, -y)      正向 (导出时)
        Blender   =  glTF    (x, -z, y)      反向 (本工具解码)
    所以 validator 拿到 glb 顶点后先做反向映射回到"建模坐标系",
    再和 manifest 的 geometry.size / frame.origin 对账 —— 否则对
    非立方体(比如 0.8x0.6x0.75 的桌子)会比错轴。

【实现约束】只用标准库 + PyYAML。glb 解析按规范手撸 (GLB 容器 +
    POSITION/indices 解码, struct.unpack), 不引入 trimesh 等第三方库。
"""

import argparse
import json
import os
import re
import shutil
import struct
import sys

try:
    import yaml                          # 交接单是 YAML
except ImportError:
    sys.exit("缺少 PyYAML: pip install pyyaml (多数系统 python3 自带)")

# ============================== 常量 ==============================
TOOL_VERSION = "1.0"
SCHEMA_MAX = 1                            # 本工具实现的最高 schema 版本
KINDS = {"model-package"}                 # v1 仅此一型
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")        # §5.1 模型名规则
TOL_ORIGIN_M = 1e-3                       # V5 原点容差 1mm (§5.2)
TOL_SIZE_REL = 0.05                       # V4 尺寸容差 5%
TOL_SIZE_ABS = 0.02                       # V4 尺寸容差 2cm (二者取宽)
COMP_FLOAT = 5126                         # glTF componentType FLOAT
IDX_FMT = {5121: "B", 5123: "H", 5125: "I"}       # 索引三种无符号整型
OPT_ENUM = {"convex_hull", "convex_decomposition", "none"}    # §3/A3
TOL_METALLIC_MAX = 0.2                      # V14: gz 无 IBL, 金属度上限 (D6)
MODELS_DIR = "gazebo_models"              # §7: 只写这两个目录 **■ 相对运行目录**
WORLDS_DIR = "worlds"
PREVIEW_NAME = "preview.png"              # §5.1: 资产包预览图 → 产物 thumbnails/1.png
THUMB_MIN_SIDE = 128                      # V13: 缩略图最小边 (Fuel 轮播图)
THUMB_MAX_MB = 5                          # V13: 单图体积上限

E, W, I = "❌", "⚠", "ℹ"                  # 三种打印级别


# ============================== 小工具 ==============================
def fmt_num(v):
    """SDF/XML 数字写法: 尽量短且保精度.
    True→'true', 0→'0', 1.0→'1', Decimal 0.1→'0.1', 1.57079632679 原样."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    f = float(v)
    return str(int(f)) if f == int(f) else repr(f)


def fmt_pose(vals):
    return " ".join(fmt_num(v) for v in vals)


def r9(v):
    """布局坐标去掉浮点噪声: (0-2.5)*0.15=add-0.22499999999999998
    round 到 9 位小数后 repr 变回 '-0.225'; 对 SDF 是同一个数.
    布局值都是人为设定的规整数字, 9 位足够."""
    return round(float(v), 9)


def decode_yup(p):
    """glTF 坐标 → 建模坐标系 (解开 Blender Y-up 换轴, 见模块文档)."""
    return [p[0], -p[2], p[1]]


# ============================== GLB 解析 ==============================
class GlbError(Exception):
    pass


def glb_parse(path):
    """读 GLB 容器 → (glTF_json, BIN字节). 结构: 12B 头 | JSON chunk | BIN chunk."""
    with open(path, "rb") as f:
        head = f.read(12)
        if len(head) < 12 or struct.unpack("<I", head[:4])[0] != 0x46546C67:
            raise GlbError("魔数不是 'glTF', 不是有效 GLB")
        ver, total = struct.unpack("<II", head[4:12])
        if ver != 2:
            raise GlbError(f"只支持 GLB v2, 读到 v{ver}")
        data = f.read()
    if len(data) + 12 != total:
        raise GlbError("声明长度与实际不符 (文件损坏?)")
    gjson, blob = None, b""
    off = 0
    while off + 8 <= len(data):
        clen, ctype = struct.unpack("<II", data[off:off + 8])
        chunk = data[off + 8: off + 8 + clen]
        if ctype == 0x4E4F534A:                # 'JSON'
            gjson = json.loads(chunk.decode("utf-8"))
        elif ctype == 0x004E4942:              # 'BIN\0'
            blob = chunk
        off += 8 + clen
    if gjson is None:
        raise GlbError("缺少 JSON chunk")
    return gjson, blob


def node_matrix(node):
    """glTF 节点 → 4x4 行主序矩阵 (matrix 优先, 否则 T*R(四元数)*S)."""
    if "matrix" in node:
        m = node["matrix"]                     # 列主序 16 flat → 行主序 4x4
        return [[m[r + 4 * c] for c in range(4)] for r in range(4)]
    t = node.get("translation", (0.0, 0.0, 0.0))
    q = node.get("rotation", (0.0, 0.0, 0.0, 1.0))
    s = node.get("scale", (1.0, 1.0, 1.0))
    x, y, z, w = q
    r = [[w * w + x * x - y * y - z * z, 2 * (x * y - w * z),       2 * (x * z + w * y)],
         [2 * (x * y + w * z),       w * w - x * x + y * y - z * z, 2 * (y * z - w * x)],
         [2 * (x * z - w * y),       2 * (y * z + w * x),           w * w - x * x - y * y + z * z]]
    M = [[r[i][0] * s[0], r[i][1] * s[1], r[i][2] * s[2], t[i]] for i in range(3)]
    M.append([0.0, 0.0, 0.0, 1.0])
    return M


def mat_mul(A, B):
    return [[sum(A[i][k] * B[k][j] for k in range(4)) for j in range(4)]
            for i in range(4)]


def mat_apply(M, p):
    return [M[i][0] * p[0] + M[i][1] * p[1] + M[i][2] * p[2] + M[i][3]
            for i in range(3)]


def read_vec3(gjson, blob, acc_idx):
    """解码 VEC3/FLOAT 属性 (POSITION), 处理 byteStride."""
    acc = gjson["accessors"][acc_idx]
    if acc.get("type") != "VEC3" or acc.get("componentType") != COMP_FLOAT:
        raise GlbError("POSITION 必须是 VEC3/FLOAT")
    bv = gjson["bufferViews"][acc["bufferView"]]
    if bv.get("buffer", 0) != 0:
        raise GlbError("多 buffer glb 暂不支持 (Blender 导出的都是单 buffer)")
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 12)
    return [struct.unpack_from("<3f", blob, base + i * stride)
            for i in range(acc["count"])]


def read_indices(gjson, blob, acc_idx):
    acc = gjson["accessors"][acc_idx]
    fmt = IDX_FMT.get(acc.get("componentType"))
    if not fmt or acc.get("type") != "SCALAR":
        raise GlbError("不支持的索引类型")
    bv = gjson["bufferViews"][acc["bufferView"]]
    base = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    size = struct.calcsize(fmt)
    stride = bv.get("byteStride", size)
    return [struct.unpack_from(fmt, blob, base + i * stride)[0]
            for i in range(acc["count"])]


def glb_scan(path):
    """一次遍历 glTF 场景树, 返回校验所需的全部几何信息:
      tris        : 三角形 [(p0,p1,p2)] 顶点在 glTF 世界坐标(已应用节点变换)
      ext_size    : 顶点包围盒尺寸   (已解码回建模坐标系)
      ext_center  : 顶点包围盒中心   (同上)
      z_min       : 建模坐标系 z 最小 (bottom-center 校验用)
      tris_n      : 三角形数
    """
    gjson, blob = glb_parse(path)
    scene = gjson["scenes"][gjson.get("scene", 0)]
    nodes = gjson["nodes"]
    verts, tris = [], []
    stack = [(n, node_matrix(nodes[n])) for n in scene.get("nodes", [])]
    while stack:
        ni, M = stack.pop()
        node = nodes[ni]
        if "mesh" in node:
            mesh = gjson["meshes"][node["mesh"]]
            for prim in mesh["primitives"]:
                pos_i = prim["attributes"].get("POSITION")
                if pos_i is None:
                    continue
                local = read_vec3(gjson, blob, pos_i)
                world = [mat_apply(M, v) for v in local]
                verts.extend(world)
                idx = (read_indices(gjson, blob, prim["indices"])
                       if "indices" in prim else list(range(len(local))))
                for k in range(0, len(idx) - 2, 3):
                    tris.append(tuple(world[idx[k + j]] for j in range(3)))
        for c in node.get("children", []):
            stack.append((c, mat_mul(M, node_matrix(nodes[c]))))
    if not verts:
        raise GlbError("没有顶点数据")
    dec = [decode_yup(v) for v in verts]        # ← 回到建模坐标系再算包围盒
    lo = [min(v[i] for v in dec) for i in range(3)]
    hi = [max(v[i] for v in dec) for i in range(3)]
    return {"verts_n": len(verts), "tris": tris, "tris_n": len(tris),
            "ext_size": [hi[i] - lo[i] for i in range(3)],
            "ext_center": [(hi[i] + lo[i]) / 2.0 for i in range(3)],
            "z_min": lo[2], "gjson": gjson}


def glb_external_refs(gjson):
    """V6: 找外部引用. 贴图 image.uri (非 data:) 或 buffer.uri → 换机器即坏."""
    bad = []
    for img in gjson.get("images", []):
        uri = img.get("uri")
        if uri and not uri.startswith("data:"):
            bad.append(f"贴图 {img.get('name', '?')} 引用外部文件 {uri[:48]}")
    for i, buf in enumerate(gjson.get("buffers", [])):
        if buf.get("uri"):
            bad.append(f"buffer[{i}] 外部引用 {buf['uri'][:48]}")
    return bad


def glb_material_report(gjson):
    """V14 材质可渲染性 (D6): gz ogre2 无环境贴图 →
    ① 无 material 的 primitive 走 glTF 默认材质 (metallic=1) → 渲染成黑色;
    ② metallicFactor 高的材质同样发黑 (金属无漫反射, 无 IBL 可反).
    返回 (无材质 primitive 数, metallic>上限 的材质名列表)."""
    mats = gjson.get("materials", [])
    no_mat = 0
    for mesh in gjson.get("meshes", []):
        for prim in mesh.get("primitives", []):
            if "material" not in prim:
                no_mat += 1
    hi = []
    for i, m in enumerate(mats):
        pbr = m.get("pbrMetallicRoughness", {})
        # glTF 规范: metallicFactor 缺省 = 1.0
        mf = pbr.get("metallicFactor", 1.0)
        if mf > TOL_METALLIC_MAX + 1e-3:  # 浮点容差: Blender 0.2 导出成 0.200000003
            hi.append(f"{m.get('name') or 'material' + str(i)}({mf:.2f})")
    return no_mat, hi


def watertight_report(tris):
    """V7 封闭流形检查 (C2: auto 惯量 = 网格体积积分 → 必须水密).
    原理: 封闭可定向三角网格里, 每条无向边恰好被 2 个三角形以相反方向共用.
    顶点先按 1e-5m 量化合并: glTF 导出在 UV/法线接缝会复制顶点
    (实测立方体 24 个), 量化还原成 8 个后边计数才有意义."""
    def q(p):
        return tuple(int(round(c * 1e5)) for c in p)
    cnt, dirs = {}, {}
    for a, b, c in tris:
        ka, kb, kc = q(a), q(b), q(c)
        if ka == kb or kb == kc or kc == ka:
            continue                                  # 退化三角形跳过
        for u, v in ((ka, kb), (kb, kc), (kc, ka)):
            key = min(u, v), max(u, v)
            cnt[key] = cnt.get(key, 0) + 1
            dirs.setdefault(key, set()).add((u, v))
    opening = sum(1 for n in cnt.values() if n == 1)   # 只有一条边共用 → 破口
    flipped = sum(1 for key, ds in dirs.items()
                  if cnt[key] == 2 and len(ds) == 1)   # 两条同向 → 法线翻面
    return opening, flipped


# ============================== 实例展开 ==============================
def expand_instances(m):
    """source.meshes[] → ([(file, instance_str), ...], 错误消息或 None).

    三种写法 (§3):
      instance: "00"            → 1 项
      instance_range: [0, 23]   → 24 项, 编号按最大号自动补零 (00..23)
      instance_count: 5         → 5 项 (00..04), 从 0 起
    file 里可写 {instance} 占位符 (range/count 展开时逐个代入),
    没有占位符则同一文件复制给每个实例 (同款网格摆多件).
    """
    out = []
    for entry in (m.get("source") or {}).get("meshes") or []:
        if not isinstance(entry, dict):
            return out, f"meshes[] 项必须是字典: {entry!r}"
        f = entry.get("file")
        if not isinstance(f, str) or not f:
            return out, f"meshes[] 项缺少 file: {entry!r}"
        ids = None
        if "instance" in entry:
            ids = [str(entry["instance"])]
        elif "instance_range" in entry:
            rng = entry["instance_range"]
            if not (isinstance(rng, list) and len(rng) == 2):
                return out, f"instance_range 需为 [start, end]: {rng!r}"
            width = len(str(int(rng[1])))
            ids = [f"{i:0{width}d}" for i in range(int(rng[0]), int(rng[1]) + 1)]
        elif "instance_count" in entry:
            n = int(entry["instance_count"])
            if n < 1:
                return out, f"instance_count 需 ≥1: {n}"
            width = len(str(n - 1))
            ids = [f"{i:0{width}d}" for i in range(n)]
        else:
            return out, f"meshes[] 项缺 instance/instance_range/instance_count: {entry!r}"
        for inst in ids:
            out.append((f.replace("{instance}", inst) if "{instance}" in f else f, inst))
    if not out:
        return out, "source.meshes 为空, 没有任何网格"
    return out, None


# ============================== 默认值 (§4 总表) ==============================
def apply_defaults(m):
    """把 manifest 补齐成"全字段都有值"的视图 (工具与文档口径同一)."""
    d = {}
    d["name"] = m.get("name")
    d["description"] = m.get("description", "")
    src = m.get("source") or {}
    d["blend"] = src.get("blend")
    d["mass"] = m.get("mass")
    d["inertia"] = m.get("inertia", "auto")
    d["inertia_values"] = m.get("inertia_values") or {}
    d["static"] = bool(m.get("static", False))
    geom = m.get("geometry") or {}
    d["size"] = geom.get("size")
    col = m.get("collision") or {}
    d["col_type"] = col.get("type", "mesh")                       # §4 默认 mesh
    d["optimization"] = col.get("optimization",                                   # 默认凸包
                                "convex_hull" if col.get("type", "mesh") == "mesh"
                                else "none")
    dec = col.get("convex_decomposition") or {}
    d["max_convex_hulls"] = dec.get("max_convex_hulls", 16)       # SDF 规范默认
    d["voxel_resolution"] = dec.get("voxel_resolution", 200000)
    d["primitives"] = col.get("primitives") or []
    frame = m.get("frame") or {}
    d["origin"] = frame.get("origin", "center")                   # §4 默认 center
    d["visual_pose"] = frame.get("visual_pose") or m.get("visual_pose") \
                       or [0, 0, 0, 1.57079632679, 0, 0]  # 层① roll+90° (B1)
    # (§3 规定写在 frame 下; 顶层写法也兼容, 优先 frame)
    gz = m.get("gazebo") or {}
    d["sdf_version"] = str(gz.get("sdf_version", "1.11"))         # A2
    d["world"] = m.get("world")                                   # 可为 None
    return d


# ============================== 校验 (V1~V13) ==============================
def png_size(path):
    """读 PNG IHDR 宽高; 非 PNG 返回 None."""
    try:
        with open(path, "rb") as fh:
            head = fh.read(24)
        if head[:8] != b"\x89PNG\r\n\x1a\n" or head[12:16] != b"IHDR":
            return None
        return struct.unpack(">II", head[16:24])
    except OSError:
        return None


def preview_check(pkg_dir):
    """V13 (§5.1): 资产包 preview.png. 返回 (err|None, 绝对路径|None)."""
    p = os.path.join(pkg_dir, PREVIEW_NAME)
    if not os.path.exists(p):
        return None, None                     # 缺席只警告, 不拦路
    dims = png_size(p)
    if dims is None:
        return f"{PREVIEW_NAME} 不是合法 PNG → 用 render_preview.py 重渲", None
    if min(dims) < THUMB_MIN_SIDE:
        return (f"{PREVIEW_NAME} {dims[0]}×{dims[1]} 过小: 最小边 "
                f"{min(dims)}px < {THUMB_MIN_SIDE}px"), None
    if os.path.getsize(p) > THUMB_MAX_MB * 1024 * 1024:
        return (f"{PREVIEW_NAME} 超过 {THUMB_MAX_MB}MB (Fuel 轮播图用, 降分辨率/重压缩)"), None
    return None, p
def validate_package(pkg_dir, want_world):
    """资产包体检. ➔ (issues=[(级别,编号,消息)], d=补齐后的视图, insts, scans)
    issues 里只要有一条 ❌, build 就拒绝动工."""
    issues = []
    bad = lambda code, msg: issues.append((E, code, msg))
    warn = lambda code, msg: issues.append((W, code, msg))

    manifest_path = os.path.join(pkg_dir, "manifest.yaml")
    if not os.path.exists(manifest_path):
        issues.append((E, "V0", f"{manifest_path} 不存在"))
        return issues, None, [], {}
    m = yaml.safe_load(open(manifest_path, encoding="utf-8")) or {}

    # ---- V1 schema / kind ----
    sv = m.get("schema_version")
    if not isinstance(sv, int) or sv < 1:
        bad("V1", f"schema_version 缺失或非整数: {sv!r}")
        return issues, None, [], {}
    if sv > SCHEMA_MAX:
        bad("V1", f"manifest schema_version={sv} 高于工具支持 v{SCHEMA_MAX}, 升级工具")
        return issues, None, [], {}
    if m.get("kind") not in KINDS:
        bad("V1", f"kind 未实现: {m.get('kind')!r} (v1 仅 {sorted(KINDS)})")
        return issues, None, [], {}

    d = apply_defaults(m)

    # ---- V2 name / instance 唯一 ----
    if not isinstance(d["name"], str) or not NAME_RE.match(d["name"]):
        bad("V2", f"name 不符合 ^[a-z][a-z0-9_]*$: {d['name']!r}")
    insts, err = expand_instances(m)
    if err:
        bad("V2", err)
        return issues, d, [], {}
    seen = {}
    for f, inst in insts:
        model_dir_name = f"{d['name']}_{inst}"
        if model_dir_name in seen:
            bad("V2", f"实例目录名冲突: {model_dir_name} (instance={inst})")
        seen[model_dir_name] = f

    # ---- V3 文件存在 + 可解析; V4 尺寸; V5 原点; V6 贴图; V7 水密 ----
    if d["col_type"] not in ("mesh", "box", "primitives"):
        bad("V1", f"collision.type 未实现: {d['col_type']!r}")
    if d["optimization"] not in OPT_ENUM:
        bad("V1", f"collision.optimization 非法: {d['optimization']!r} "
                  f"(选 {sorted(OPT_ENUM)})")
    scans = {}
    for f, inst in insts:
        path = os.path.join(pkg_dir, f)
        try:
            scan = glb_scan(path)
        except FileNotFoundError:
            bad("V3", f"[{inst}] 网格文件不存在: {f}")
            continue
        except Exception as e:
            bad("V3", f"[{inst}] glb 解析失败 {f}: {e}")
            continue
        scans[f] = scan
        tag = f"[{f}]"

        # V4 尺寸对账 (包围盒已解码回建模坐标系)
        dstar = d["size"]
        if dstar is None:
            bad("V4", "geometry.size 必填 (§4): validator 与 world 高度都靠它")
        else:
            for i, ax in enumerate("XYZ"):
                tol = max(TOL_SIZE_REL * dstar[i], TOL_SIZE_ABS)
                dev = abs(scan["ext_size"][i] - dstar[i])
                if dev > tol:
                    bad("V4", f"{tag} {ax} 轴向实测 {scan['ext_size'][i]:.4f}m "
                              f"≠ manifest {dstar[i]}m (偏差 {dev*1000:.1f}mm > 容差 {tol*1000:.0f}mm) "
                              f"→ 改模忘改单?")
        # V5 原点策略 (§5.2)
        cx, cy, cz = scan["ext_center"]
        if d["origin"] == "center":
            if max(abs(cx), abs(cy), abs(cz)) > TOL_ORIGIN_M:
                bad("V5", f"{tag} 声明 origin=center 但 AABB 中心=({cx:.4f},{cy:.4f},{cz:.4f}) "
                          f"偏离原点 >1mm → 用 blender_export.py --origin center 重导")
        elif d["origin"] == "bottom-center":
            if max(abs(cx), abs(cy)) > TOL_ORIGIN_M or abs(scan["z_min"]) > TOL_ORIGIN_M:
                bad("V5", f"{tag} 声明 origin=bottom-center 但中心=({cx:.4f},{cy:.4f}) "
                          f"z_min={scan['z_min']:.4f} → 用 --origin bottom-center 重导")
        else:
            bad("V5", f"frame.origin 非法: {d['origin']!r}")
        # V6 贴图/缓冲外部引用 (A1/D4)
        for msg in glb_external_refs(scan["gjson"]):
            bad("V6", f"{tag} {msg} → 贴图必须内嵌 (重导前在 Blender 里 pack/烘图)")
        # V7 水密 (仅 auto 惯量 + mesh 碰撞 才有意义, C2)
        if d["inertia"] == "auto" and not d["static"] and d["col_type"] == "mesh":
            opening, flipped = watertight_report(scan["tris"])
            if opening:
                bad("V7", f"{tag} 网格不封闭: {opening} 条开口边 "
                          f"(auto 惯量按体积积分, 破网格算不出 → 修模重导)")
            if flipped:
                bad("V7", f"{tag} {flipped} 条边两侧三角形同向 (法线不一致), "
                          f"体积积分符号会错 → Blender 里 Normal Align 后重导")
        # V14 材质可渲染性 (D6: gz ogre2 无 IBL; 无材质=默认metallic1黑; 高metallic黑)
        no_mat, hi_metal = glb_material_report(scan["gjson"])
        if no_mat:
            bad("V14", f"{tag} {no_mat} 个 primitive 无 material → Gazebo 按 glTF 默认材质"
                       f" (metallic=1) 渲染成黑色 (检查 Blender 材质槽是否留了 None 空槽)")
        if hi_metal:
            warn("V14", f"{tag} metallic>{TOL_METALLIC_MAX:g} 的材质: {', '.join(hi_metal)}"
                        f" — gz 无环境贴图, 金属面发黑 (D6), 建议 ≤{TOL_METALLIC_MAX:g}")

    # blend 若声明则查存在 (glb 才是产物, blend 只是返工源, 缺了仅警告)
    if d["blend"] and not os.path.exists(os.path.join(pkg_dir, d["blend"])):
        warn("V6", f"manifest.source.blend 不存在: {d['blend']} (返工时才需要)")

    # ---- V8 auto 惯量需要 SDF≥1.11 (A2) ----
    try:
        sdfv = tuple(int(x) for x in d["sdf_version"].split("."))
    except ValueError:
        bad("V8", f"sdf_version 无法解析: {d['sdf_version']!r}")
        sdfv = None
    if sdfv and d["inertia"] == "auto" and not d["static"] and sdfv < (1, 11):
        bad("V8", f"inertia=auto 需 sdf_version≥1.11 (A2), 现为 {d['sdf_version']}")

    # ---- V9 动态 + 不优化 (A3) ----
    if (not d["static"]) and d["col_type"] == "mesh" and d["optimization"] == "none":
        warn("V9", "动态模型 + mesh 碰撞未开 optimization: 非凸动态网格接触不稳 "
                   "(建议 convex_hull / convex_decomposition, 仍会打包)")

    # ---- V10 mass / 惯量字段 ----
    if d["inertia"] == "explicit":
        need = {"ixx", "iyy", "izz", "ixy", "ixz", "iyz"}
        got = set(d["inertia_values"])
        if not need <= got:
            bad("V10", f"inertia=explicit  inertia_values 缺项: {sorted(need - got)}")
    if not d["static"]:
        if not isinstance(d["mass"], (int, float)) or isinstance(d["mass"], bool) \
                or d["mass"] <= 0:
            bad("V10", f"动态模型 mass 需 >0 的数字: {d['mass']!r}")
    elif d["mass"] is not None and (not isinstance(d["mass"], (int, float))
                                    or isinstance(d["mass"], bool) or d["mass"] <= 0):
        warn("V10", f"static:true 不读 mass, 但给了非法值 {d['mass']!r} (将被忽略)")

    # ---- V11 world 布局 ----
    if want_world or d["world"] is not None:
        werr = world_layout_errors(d, len(insts))
        for msg in werr:
            bad("V11", msg)

    # ---- V13 预览图 (§5.1: 存在则打包成产物 thumbnails/1.png) ----
    perr, _ppath = preview_check(pkg_dir)
    if perr:
        bad("V13", perr)
    elif _ppath is None:
        warn("V13", f"缺 {PREVIEW_NAME}: 产物将没有 thumbnails/1.png (Fuel 展示页会空白; "
                    "建议补 render_preview.py 渲一张, 仍会打包)")

    return issues, d, insts, scans


def world_layout_errors(d, n_inst):
    """V11: layout 合法性预检 (build --world 或 manifest 带 world 段时)."""
    errs = []
    w = d["world"] or {}
    lay = w.get("layout") or {}
    ltype = lay.get("type", "grid")
    if ltype not in ("grid", "line", "explicit"):
        errs.append(f"--world.layout.type 非法: {ltype!r} (grid/line/explicit)")
        return errs
    if ltype == "explicit":
        poses = lay.get("poses") or []
        if len(poses) != n_inst:
            errs.append(f"--world.layout.poses 有 {len(poses)} 个, 但实例有 {n_inst} 个")
        for p in poses:
            if not (isinstance(p, list) and len(p) in (3, 6)):
                errs.append(f"poses 项需 [x y z] 或 [x y z roll pitch yaw]: {p!r}")
    else:
        if d["size"] is None:
            errs.append("--world 用 z=auto/pitch 默认时需要 geometry.size")
    return errs


# ============================== 渲染 (填模板, 字段全来自 manifest) ==============================
def collision_block(d, uri, pose_str):
    """collision 几何 (§5.3): mesh 与 visual 共用同一 glb → 必须继承同一
    轴向修正 pose (同份数据进行相同旋转);box/primitives 是直接在建模坐标系
    手写的形状 → 不加 pose. (对立方体两种写法等价, 对非立方体是正确性问题)"""
    if d["col_type"] == "mesh":
        opt_attr = ""
        if d["optimization"] == "convex_hull":
            opt_attr = ' optimization="convex_hull"'
        elif d["optimization"] == "convex_decomposition":
            opt_attr = ' optimization="convex_decomposition"'
        inner = f"""        <geometry>
          <mesh{opt_attr}>
            <uri>{uri}</uri>
            <scale>1 1 1</scale>"""
        if d["optimization"] == "convex_decomposition":
            inner += f"""
            <convex_decomposition>
              <max_convex_hulls>{d['max_convex_hulls']}</max_convex_hulls>
              <voxel_resolution>{d['voxel_resolution']}</voxel_resolution>
            </convex_decomposition>"""
        inner += """
          </mesh>
        </geometry>"""
        pose_line = f"        <pose>{pose_str}</pose>\n" if pose_str else ""
        return f"      <collision name=\"collision\">\n{pose_line}{inner}\n      </collision>"
    if d["col_type"] == "box":
        s = " ".join(fmt_num(v) for v in d["size"])
        return (f"      <collision name=\"collision\">\n"
                f"        <geometry>\n"
                f"          <box><size>{s}</size></box>\n"
                f"        </geometry>\n"
                f"      </collision>")
    # primitives: 每项一个 <collision>, 自带 pose
    parts = []
    for i, pr in enumerate(d["primitives"]):
        shape = pr.get("shape")
        pose = pr.get("pose")
        if shape == "box":
            geo = f"<box><size>{' '.join(fmt_num(v) for v in pr['size'])}</size></box>"
        elif shape == "cylinder":
            geo = (f"<cylinder><radius>{fmt_num(pr['radius'])}</radius>"
                   f"<length>{fmt_num(pr['length'])}</length></cylinder>")
        elif shape == "sphere":
            geo = f"<sphere><radius>{fmt_num(pr['radius'])}</radius></sphere>"
        else:
            geo = None
        if geo is None:
            continue                      # validate 没拦住也不会写坏
        pose_line = f"        <pose>{fmt_pose(pose)}</pose>\n" if pose else ""
        parts.append(f"      <collision name=\"collision_{i}\">\n{pose_line}"
                     f"        <geometry>{geo}</geometry>\n      </collision>")
    return "\n".join(parts)


def render_sdf(d, inst, glb_name):
    """单个实例的 model.sdf (骨架固定, 全部变量来自 manifest)."""
    model_name = f"{d['name']}_{inst}"
    uri = f"model://{model_name}/{glb_name}"
    pose_str = fmt_pose(d["visual_pose"])

    # inertial: static 省略; auto 写 auto+mass, 绝不写 pose/inertia/density ◎C1;
    #           explicit 写全六项
    if d["static"]:
        inertial = ""      # 静态模型不需要惯量
    elif d["inertia"] == "auto":
        inertial = (f"      <inertial auto=\"true\">\n"
                    f"        <mass>{fmt_num(d['mass'])}</mass>\n"
                    f"      </inertial>\n")
    else:
        iv = d["inertia_values"]
        inertial = (f"      <inertial>\n"
                    f"        <mass>{fmt_num(d['mass'])}</mass>\n"
                    f"        <inertia>\n"
                    + "".join(f"          <{k}>{fmt_num(iv[k])}</{k}>\n"
                              for k in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"))
                    + f"        </inertia>\n      </inertial>\n")

    static_line = "    <static>true</static>\n" if d["static"] else ""
    return f"""<?xml version="1.0"?>
<sdf version="{d['sdf_version']}">
  <model name="{model_name}">
{static_line}    <link name="link">
{inertial}      <visual name="visual">
        <!-- 轴向修正 (glTF Y-up → Gazebo Z-up, PACK_NOTES B1 层①默认) -->
        <pose>{pose_str}</pose>
        <geometry>
          <mesh>
            <uri>{uri}</uri>
            <scale>1 1 1</scale>
          </mesh>
        </geometry>
      </visual>

{collision_block(d, uri, pose_str if d["col_type"] == "mesh" else "")}
    </link>
  </model>
</sdf>
"""


def render_config(d, inst):
    return f"""<?xml version="1.0"?>
<model>
  <name>{d['name']}_{inst}</name>
  <version>1.0</version>
  <sdf version="{d['sdf_version']}">model.sdf</sdf>
  <author>
    <name>gazebo_pack.py v{TOOL_VERSION}</name>
    <email>noreply@example.com</email>
  </author>
  <description>{d['description']}</description>
</model>
"""


# ============================== world (§5.4 骨架固定) ==============================
WORLD_PLUGINS = """    <!-- gz-sim 功能以插件形式启用, 缺一个对应功能就不工作 (PACK_NOTES F) -->
    <plugin filename="gz-sim-physics-system" name="gz::sim::systems::Physics"/>
    <plugin filename="gz-sim-user-commands-system" name="gz::sim::systems::UserCommands"/>
    <plugin filename="gz-sim-scene-broadcaster-system" name="gz::sim::systems::SceneBroadcaster"/>
    <plugin filename="gz-sim-sensors-system" name="gz::sim::systems::Sensors"/>"""

WORLD_SUN = """    <light name="sun" type="directional">
      <cast_shadows>true</cast_shadows>
      <pose>0 0 10 0 0 0</pose>
      <diffuse>0.8 0.8 0.8 1</diffuse>
      <specular>0.1 0.1 0.1 1</specular>
      <direction>0.3 0.2 -1</direction>
    </light>"""

WORLD_GROUND = """    <model name="ground_plane">
      <static>true</static>
      <link name="link">
        <collision name="collision">
          <geometry>
            <plane><normal>0 0 1</normal><size>10 10</size></plane>
          </geometry>
        </collision>
        <visual name="visual">
          <geometry>
            <plane><normal>0 0 1</normal><size>10 10</size></plane>
          </geometry>
          <material>
            <ambient>0.75 0.75 0.75 1</ambient>
            <diffuse>0.75 0.75 0.75 1</diffuse>
          </material>
        </visual>
      </link>
    </model>"""


def layout_poses(d, insts):
    """按 layout 算每个实例的摆放位姿 (§3 world.layout / §4 默认)."""
    w = d["world"] or {}
    lay = w.get("layout") or {}
    ltype = lay.get("type", "grid")
    n = len(insts)
    size = d["size"] or [1.0, 1.0, 1.0]
    # 贴地高度: auto 由原点策略决定 (center → 半高; bottom-center → 0)
    z = lay.get("z", "auto")
    if z == "auto":
        z = 0.0 if d["origin"] == "bottom-center" else size[2] / 2.0
    pitch = lay.get("pitch") or (2.0 * max(size))          # §4: 2×max(size)

    out = []
    if ltype == "explicit":
        for p in lay["poses"]:
            p = list(p) + [0, 0, 0] if len(p) == 3 else list(p)
            out.append(fmt_pose(p))
        return out
    if ltype == "line":
        axis = lay.get("axis", "x")
        for i in range(n):
            t = (i - (n - 1) / 2.0) * pitch
            x, y = (t, 0.0) if axis == "x" else (0.0, t)
            out.append(fmt_pose([r9(x), r9(y), r9(z), 0, 0, 0]))
        return out
    # grid (§4: cols=min(n,6), rows 自动)
    cols = int(lay.get("cols") or min(n, 6))
    rows = int(lay.get("rows") or -(-n // cols))           # 向上取整
    for i, (_f, _inst) in enumerate(insts):
        col, row = i % cols, i // cols
        x = (col - (cols - 1) / 2.0) * pitch
        y = (row - (rows - 1) / 2.0) * pitch
        out.append(fmt_pose([r9(x), r9(y), r9(z), 0, 0, 0]))
    return out


def render_world(d, insts):
    """world 文件: 固定骨架 + include 列表 (§5.4). 返回 (文件名, 内容)."""
    w = d["world"] or {}
    wname = w.get("name") or f"{d['name']}_world"
    poses = layout_poses(d, insts)
    includes = "\n".join(
        f"    <include>\n"
        f"      <name>{d['name']}_{inst}</name>\n"
        f"      <pose>{pose}</pose>\n"
        f"      <uri>model://{d['name']}_{inst}</uri>\n"
        f"    </include>"
        for (_f, inst), pose in zip(insts, poses))
    blocks = [WORLD_PLUGINS]
    if w.get("sun", True):
        blocks.append(WORLD_SUN)
    if w.get("ground", True):
        blocks.append(WORLD_GROUND)
    body = "\n\n".join(blocks)
    if w.get("plugins") == "minimal":     # 只要物理 (无 GUI 交互/传感器)
        body = body.replace(WORLD_PLUGINS,
                            '    <plugin filename="gz-sim-physics-system" '
                            'name="gz::sim::systems::Physics"/>')
    content = f"""<?xml version="1.0"?>
<sdf version="{d['sdf_version']}">
  <world name="{wname}">
    <scene>
      <ambient>0.4 0.4 0.4 1</ambient>
      <background>0.7 0.8 0.9 1</background>
      <shadows>true</shadows>
    </scene>

{body}

    <!-- {len(insts)} 个 {d['name']} 实例, 由 gazebo_pack.py 按 manifest 布局 -->
{includes}
  </world>
</sdf>
"""
    return f"{wname}.sdf", content


# ============================== build ==============================
def build_package(pkg_dir, want_world):
    """校验 → 渲染 → 落盘. 返回退出码."""
    issues, d, insts, _scans = validate_package(pkg_dir, want_world)
    for lvl, code, msg in issues:
        print(f"  {lvl} [{code}] {msg}")
    errors = [x for x in issues if x[0] == E]
    if errors:
        print(f"\n校验失败: {len(errors)} 个错误 → 拒绝打包 (§7 纪律3: 宁可失败)")
        return 1

    # ---- 落盘: 只写 MODELS_DIR / WORLDS_DIR (§7 纪律1) ----
    total_bytes = 0
    written = []
    for f, inst in insts:
        model_name = f"{d['name']}_{inst}"
        glb_name = f"{model_name}.glb"                # §5.1 同目录同名
        out_dir = os.path.join(MODELS_DIR, model_name)
        os.makedirs(out_dir, exist_ok=True)           # 幂等: 覆盖式重写
        src_glb = os.path.join(pkg_dir, f)
        dst_glb = os.path.join(out_dir, glb_name)
        shutil.copyfile(src_glb, dst_glb)             # 资产只读, 复制进产物
        with open(os.path.join(out_dir, "model.sdf"), "w", encoding="utf-8") as fh:
            fh.write(render_sdf(d, inst, glb_name))
        with open(os.path.join(out_dir, "model.config"), "w", encoding="utf-8") as fh:
            fh.write(render_config(d, inst))
        # §5.1/A5: 资产包 preview.png → 产物 thumbnails/1.png (Fuel 规范, 可空)
        perr, ppath = preview_check(pkg_dir)
        tdir = os.path.join(out_dir, "thumbnails")
        if ppath:
            os.makedirs(tdir, exist_ok=True)
            shutil.copyfile(ppath, os.path.join(tdir, "1.png"))
        elif os.path.isdir(tdir):
            shutil.rmtree(tdir)               # 覆盖式重写: preview 撤了缩略图也要消失
        total_bytes += sum(os.path.getsize(os.path.join(out_dir, x))
                           for x in ("model.sdf", "model.config", glb_name))
        written.append(model_name)

    world_path = None
    if want_world and d["world"] is not None:
        os.makedirs(WORLDS_DIR, exist_ok=True)
        wname, wcontent = render_world(d, insts)
        world_path = os.path.join(WORLDS_DIR, wname)
        with open(world_path, "w", encoding="utf-8") as fh:
            fh.write(wcontent)
    models_abs = os.path.abspath(MODELS_DIR)          # 提示用绝对路径, 复制即用
    steps = [f"  export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:{models_abs}"
             "   # gz sim 运行时找模型",
             f"  export SDF_PATH=$SDF_PATH:{models_abs}"
             "                  # gz sdf -k 找模型 (命令行工具只认 SDF_PATH, F1 坑)"]
    if world_path:
        steps += [f"  gz sdf -k {world_path}",
                  f"  gz sim -r {world_path}"]
    else:
        steps += ["  gz sdf -k gazebo_models/<模型名>/model.sdf",
                  "  或在 gz sim 图形界面里手动 Add Model"]
    print("\n启动三步 (PACK_NOTES F):\n" + "\n".join(steps))

    return 0


# ============================== CLI (§6) ==============================
def iter_packages(arg, flags):
    """build assets/ --all → assets/ 下每个子目录; validate assets/x → 单包."""
    if flags.get("all"):
        base = arg.rstrip("/")
        subs = sorted(os.path.join(base, p) for p in os.listdir(base)
                      if os.path.isdir(os.path.join(base, p)))
        return [s for s in subs if os.path.exists(os.path.join(s, "manifest.yaml"))]
    if os.path.exists(os.path.join(arg, "manifest.yaml")):
        return [arg]
    # 也可能是 assets/ 不带 --all 的误用: 友好提示
    sys.exit(f"{arg} 里没有 manifest.yaml; 批量请加 --all")


def main():
    ap = argparse.ArgumentParser(prog="gazebo_pack.py",
                                 description=__doc__.splitlines()[1])
    sub = ap.add_subparsers(dest="cmd", required=True)
    for cmd in ("validate", "build"):
        sp = sub.add_parser(cmd)
        sp.add_argument("path", help="资产包目录 (assets/<name>) 或 assets/ 配 --all")
        sp.add_argument("--all", action="store_true")
        sp.add_argument("--world", action="store_true",
                        help="额外生成 world 场景 (manifest 需含 world 段)")
    args = ap.parse_args()

    pkgs = iter_packages(args.path, vars(args))
    if not pkgs:
        sys.exit("没找到任何含 manifest.yaml 的资产包")

    rc = 0
    for p in pkgs:
        print(f"\n=== {p} ===")
        if args.cmd == "validate":
            issues, *_ = validate_package(p, args.world)
            for lvl, code, msg in issues:
                print(f"  {lvl} [{code}] {msg}")
            errs = [x for x in issues if x[0] == E]
            if errs:
                print(f"结论: {len(errs)} 个错误")
                rc = rc or 1
            else:
                print(f"结论: ✓ 可打包"
                      f" ({sum(1 for x in issues if x[0]==W)} 个警告)")
        else:
            rc = max(rc, build_package(p, args.world))
    return rc


if __name__ == "__main__":
    sys.exit(main())
