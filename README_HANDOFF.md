# README_HANDOFF —— 对话建模 → Gazebo 资产包（5 分钟上手）

> English: [README_HANDOFF.en.md](README_HANDOFF.en.md)
> 契约/字段：[MANIFEST_SPEC.md](MANIFEST_SPEC.md) · 实测事实与坑：[PACK_NOTES.md](PACK_NOTES.md)
> 实测环境：Blender 5.2.2 LTS · Gazebo Harmonic 8.15 · Python 3 + PyYAML 6。**以下命令都在项目根执行。**

## 0. 30 秒看懂

```
assets/<name>/                 ← 交接物（源）
├── manifest.yaml              ← 契约：尺寸/质量/碰撞/布局
├── model.blend                ← 源场景
├── source/<name>.glb          ← 中间网格（导出器产物）
├── build_<name>.py            ← 可选：建模脚本（改尺寸重跑）
└── textures/                  ← 可选：烘好的贴图
        │  两条命令
        ▼
gazebo_models/<name>_XX/       ← 产物：model.sdf + model.config + <name>_XX.glb
worlds/<name>_world.sdf        ← 产物：可直接 gz sim 跑的场景
```

**产物随时可删掉重建；资产包才是源。**

## 1. 环境（一次性）

| 依赖 | 要求 | 检查 |
|---|---|---|
| Blender | 5.2 LTS 实测（4.x 未验证） | `$BLENDER --version` |
| Python | ≥3.10 + PyYAML | `python3 -c "import yaml; print(yaml.__version__)"` |
| Gazebo | Harmonic（8.15 实测） | `gz sim --version` |

本机 `/snap/bin/blender` 因 snap 权限起不来，统一用 `/snap/blender/current/blender`：

```bash
export BLENDER=/snap/blender/current/blender     # 或你本机的 blender 路径
$BLENDER --version
```

## 2. 先跑现成示例（不用建模）

本仓库自带 `assets/coke_bottle`：0.08×0.08×0.25 m 红色可乐瓶，1 个动态实例，mesh 碰撞。

```bash
export GZ_SIM_RESOURCE_PATH=$PWD/gazebo_models:$GZ_SIM_RESOURCE_PATH
export SDF_PATH=$PWD/gazebo_models:$SDF_PATH

gz sdf -k worlds/coke_bottle_world.sdf     # 看到 Valid. 即可（前面可能带一条惯量警告，正常）
gz sim -r worlds/coke_bottle_world.sdf     # GUI：红色可乐瓶立在地面
```

应看到：`coke_bottle_00` 在原点附近、瓶底贴地、贴图正常。

无 GUI 的机器：

```bash
gz sim -s -r worlds/coke_bottle_world.sdf &
SIM=$!
sleep 5    # 慢机器调到 8–10
timeout 3 gz topic -e -t /world/coke_bottle_world/dynamic_pose/info
kill $SIM
```

看 pose 里的 z 是否恒定（≈0.125–0.127），没有一直下坠/飞出。

## 3. 两条固定命令

任何 `assets/<name>/` 的生命周期就两步：

```bash
$BLENDER --background --python blender_export.py -- assets/<name>   # ① 导干净 glb
python3 gazebo_pack.py build assets/<name> --world                  # ② 校验 + 打包
```

- ① 读 `model.blend`，把每个网格对象导出为 `source/<对象名>.glb`；按
  `manifest.frame.origin` 自动归位；检查贴图是否已 pack。
- ② 读 `manifest.yaml`，跑 V1–V12；任何 ❌ 都拒绝打包并打印原因；通过后写
  `gazebo_models/`，manifest 里有 `world:` 段时再写 `worlds/`。
- 只检查不写盘：`python3 gazebo_pack.py validate assets/<name>`。
- 批量：`python3 gazebo_pack.py build assets/ --all`。

**如果包里带 `build_*.py`（例如可乐瓶），改过尺寸/造型后要先跑它**，再跑上面两条：

```bash
$BLENDER --background --python assets/coke_bottle/build_coke_bottle.py
```

贴图也要改时，先跑 `python3 assets/coke_bottle/gen_coke_label.py`。

## 4. 新建一个模型（两条路）

**路 A · 让 AI 干活（推荐）**：说一句 brief（模板见 [MANIFEST_SPEC.md §1](MANIFEST_SPEC.md)）：

```
建模：桌子，0.8×0.6×0.75m，浅木色，1个静态摆件，collision 默认
```

AI 会返回资产包 + 两条命令。新会话开头加一句：
“先读 MANIFEST_SPEC.md 和 PACK_NOTES.md 再干活。”

**路 B · 自己动手**：

- 全新造型：Blender 新建场景 → 按 §8 的四条要求做网格 → 按 §6 写 `manifest.yaml`
  → 跑 §3 的两条命令。
- 同款改尺寸：复制 `assets/coke_bottle` 改名，至少同步 5 处：
  `manifest.name`、`source/*.glb` 文件名 + `source.meshes[].file`、Blender 对象名
  （= glb 主干）、`build_coke_bottle.py` 的 `NAME`/`SIZE`；`world.name` 建议一起改。

## 5. 改尺寸：以可乐瓶为例（3 个地方 + 4 条命令）

1. `assets/coke_bottle/build_coke_bottle.py` 顶部：`SIZE = (0.08, 0.08, 0.25)`（米，X×Y×Z）
2. `assets/coke_bottle/manifest.yaml`：`geometry.size: [0.08, 0.08, 0.25]`（必须一致）
3. 若“周长:高”比例变了（例如从 0.8×0.6×0.75 改成 0.08×0.08×0.25），还要改
   `gen_coke_label.py` 的 `W, H`：当前 `2048×2048` ≈ 周长(π·D) : 高。
   等比缩放则不用改。

```bash
python3 assets/coke_bottle/gen_coke_label.py
$BLENDER --background --python assets/coke_bottle/build_coke_bottle.py
$BLENDER --background --python blender_export.py -- assets/coke_bottle
python3 gazebo_pack.py build assets/coke_bottle --world
```

只改质量/布局/碰撞等 manifest 字段：不用重导出，直接跑最后一条 `build`。

## 6. 最小 manifest（复制就能用）

```yaml
schema_version: 1
kind: model-package
name: my_model                 # ^[a-z][a-z0-9_]*$；决定目录名与 model://
description: "我的模型"
source:
  blend: model.blend
  meshes:
    - file: source/my_model.glb
      instance: "00"           # 引号必加（YAML 00 会读成 0）
mass: 1.0                      # kg
inertia: auto
static: false
geometry:
  size: [0.1, 0.1, 0.2]        # 米，X×Y×Z；必须与实测 bbox 一致
collision:
  type: mesh
  optimization: convex_hull
frame:
  origin: center               # 或 bottom-center
gazebo:
  sdf_version: "1.11"
# 要生成 world 就取消注释：
# world:
#   name: my_model_world
#   layout: {type: grid, cols: 1}
```

要求：Blender 里网格对象名 = `my_model`（= glb 文件主干）；`geometry.size` 用实测 bbox。

## 7. 常用旋钮（改 manifest 后重跑 build）

| 想改 | 字段 | 说明 |
|---|---|---|
| 质量 | `mass` | kg；`static: true` 时可省 |
| 静态摆件 | `static` | `true` = 不受重力、不写惯量 |
| 数量 | `source.meshes[].instance_count` | 把 `instance` 换成 `instance_count: N`（同网格 N 个；编号 0..N-1，最大号 ≥10 才补零） |
| 碰撞精度 | `collision.optimization` | 默认 `convex_hull`（快；凹腔会被填实）；真凹接触用 `convex_decomposition` |
| 碰撞形状 | `collision.type` | `mesh`（默认）/ `box`（快，丢凹凸）/ `primitives`（手列盒/柱） |
| 摆放 | `world.layout` | `grid`/`line`/`explicit`；`pitch` 间距；`explicit` 用 `poses` |
| 离地方式 | `frame.origin` | `center`（world 自动垫 size_z/2）/ `bottom-center`（z=0） |
| 轴向 | `visual_pose`（顶层或 `frame` 下） | 默认 roll+90°，一般不用动 |

⚠️ 两个铁律：`instance: "00"` **引号必加**；`geometry.size` 必须与模型一致
（工具实测 glb bbox，容差每轴 max(5%, 2cm)）。

## 8. 自己建 .blend 的四条要求

1. **一个网格对象 = 一个模型**：对象名 = 输出 glb 主干（`my_model` → `source/my_model.glb`）。
2. **水密**：每条边恰好 2 个面。检查：编辑模式 → 选择 → 全部按特征 → **非流形**
   （Shift+Ctrl+Alt+M），应一个都选不中。多零件用 `Boolean UNION (Exact)`，
   零件要真实相交（面贴面会出非流形）。
3. **贴图**：只用图片纹理（程序化节点导出 glTF 会丢）；`File → External Data → Pack Resources`。
4. **坐标**：对象别旋转/缩放（scale 应用掉）；原点归位交给导出器，按 `frame.origin` 自动处理。

## 9. 踩坑速查

| 症状 | 解法 |
|---|---|
| `Unable to find uri[model://…]` | `gz sdf -k` 只认 `SDF_PATH`，两个环境变量都要 export |
| `command not found`（`$BLENDER` 未设/路径不对）/ snap 权限错误 | 用 `/snap/blender/current/blender` |
| `~/.gz` 报 “Error opening log file” | 权限问题，**无害**；仿真照常跑 |
| `Custom moment of inertia calculator … using default inertial values` | `gz sdf -k` 对 mesh+auto 惯量的提示，仍 `Valid`；不影响打包 |
| 模型变纸片/躺倒 | 别手动转模型；轴向由 `visual_pose`（默认 roll+90°）处理 |
| 椅子坐在隐形板上 | `convex_hull` 填实了凹腔 → `convex_decomposition` |
| `[V4]` 尺寸不符 | `geometry.size` ≠ 实测 bbox → 改齐 |
| `[V5]` 原点不对 | 用 `blender_export.py` 按 `frame.origin` 重新导出 |
| `[V7]` 网格不封闭 | 有破口/非流形 → UNION 或 `Mesh → Clean Up` |
| 没生成 world | manifest 里没有 `world:` 段（加 `--world` 也不会造） |
| `instance: 00` 变 0 | 引号必加 |

## 10. 目录地图（本仓库实际文件）

```
assets/coke_bottle/
├── manifest.yaml            ← 契约
├── model.blend              ← 源场景
├── source/coke_bottle.glb   ← ① 产物（glb）
├── textures/coke_label.png  ← 贴图（烘好的图）
├── build_coke_bottle.py     ← 建模脚本（改 SIZE 重跑）
├── gen_coke_label.py        ← 贴图脚本（改 W/H/文案重跑）
├── render_preview.py        ← 预览渲染（可选）
└── preview.png              ← 预览图
gazebo_models/coke_bottle_00/   ← ② 产物（可再生，别手改）
worlds/coke_bottle_world.sdf    ← ② 产物
blender_export.py               ← ① 导出器（无第三方依赖）
gazebo_pack.py                  ← ② 校验/打包器（只依赖 PyYAML）
```

想先看外观（不启动 Gazebo）：`$BLENDER --background --python assets/coke_bottle/render_preview.py`
→ 生成 `assets/coke_bottle/preview.png`。

包里多出来的脚本/贴图是**附随文件**：不进 manifest、不进产物、不影响校验；
只许写本包内，不许碰 `gazebo_models/` 与 `worlds/`。

## 11. 验收清单（每次改完跑）

```bash
python3 gazebo_pack.py validate assets/<name>    # 应 0 错 0 警
gz sdf -k worlds/<world>.sdf                     # 应 Valid.
```

默认**不**跑仿真验贴地/接触：离地 0–0.5 m 都可接受（2026-10 用户拍板）。
想看效果时再 `gz sim -r`，它**不作为验收项**；水密/尺寸/原点/贴图仍强制。
