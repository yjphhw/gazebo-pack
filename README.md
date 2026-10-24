# gazebo-pack — 一句话生成 Gazebo 模型

**Make a Gazebo model in one sentence.**

让一个带贴图的模型真正跑进 `gz sim`，通常要趟完 Blender 建模、UV、导出、
手写 SDF、对碰撞/惯量、修轴向的整套坑。这个工具链把它压缩成：
**对 AI 说一句话 + 两条固定命令**。

```
"建模：公交车，10.5×2.5×3.05m，贴图要精细，1个动态，collision 要真实"
        │  AI 产出资产包 (assets/<name>/)
        ▼
① blender --background --python blender_export.py -- assets/<name>
② python3 gazebo_pack.py build assets/<name> --world
        ▼
gazebo_models/<name>_XX/  +  worlds/<name>_world.sdf   →  gz sim 直接跑
```

---

## 60 秒上手（现成示例，不用建模）

仓库自带 `assets/coke_bottle`（可乐瓶，动态，mesh 碰撞）。
**产物目录（`gazebo_models/`、`worlds/`）不进 git，由 build 生成**：

```bash
git clone https://github.com/yjphhw/gazebo-pack && cd gazebo-pack

python3 gazebo_pack.py build assets/coke_bottle --world   # 生成产物
export GZ_SIM_RESOURCE_PATH=$PWD/gazebo_models:$GZ_SIM_RESOURCE_PATH
export SDF_PATH=$PWD/gazebo_models:$SDF_PATH              # gz sdf -k 只认 SDF_PATH

gz sdf -k worlds/coke_bottle_world.sdf                     # → Valid.
gz sim -r worlds/coke_bottle_world.sdf                     # 红色可乐瓶立在地面
```

> 无 GUI 的机器：`gz sim -s -r ... &` 后采样
> `gz topic -e -t /world/coke_bottle_world/dynamic_pose/info`，
> 看 z 是否恒定（≈0.125–0.127）而不是持续下坠/上浮。

## 运行环境

| 依赖 | 要求 | 用途 | 检查 |
|---|---|---|---|
| Blender | 5.2 LTS 实测（4.x 未验证） | 建模脚本 / 导出 glb | `blender --version` |
| Python | ≥3.10 + PyYAML | 贴图生成 / 校验打包 | `python3 -c "import yaml"` |
| Gazebo | Harmonic（8.15 实测） | 验证 / 仿真 | `gz sim --version` |

- snap 安装时 `/snap/bin/blender` 可能因权限起不来，
  用 `/snap/blender/current/blender`，并 `export BLENDER=<该路径>`。
- 只跑仿真不建模：不需要 Blender，只需要 Python（build）+ Gazebo。
- 生成的 SDF **零 Fuel 依赖**，离线可跑。

## 功能

- **一句话建模**：把 brief 丢给有文件访问权的 AI（新会话开头说
  "先读 MANIFEST_SPEC.md 和 PACK_NOTES.md 再干活"），它返回完整资产包 + 两条命令。
- **全脚本化可复现**：每个模型的几何与贴图都是 Python 脚本生成的——
  改个 `SIZE = (…)` 常量重跑即可，不靠手动 Blender 操作，可 diff、可回滚。
- **契约先行**：尺寸 / 质量 / 碰撞 / 布局集中在一个 `manifest.yaml`，没有隐藏状态。
- **V1–V12 硬校验**：水密、有向体积、尺寸与 glb 实测 bbox 对账（容差每轴
  max(5%, 2cm)）、贴图必须内嵌、原点策略……任何 ❌ **拒绝打包**并打印原因。
- **物理真稳（实测筛选）**：`mesh`/`box`/`primitives` 碰撞 + auto 惯量。
  例：12t 公交 45s 无头仿真零漂移（选 box）；Tesla Model 3 四轮圆柱碰撞，
  静止 z = 0.71999999996，恰好等于理论高度。
- **world 生成**：`--world` 一步产出可直接 `gz sim` 的场景（地面/太阳/四插件内联）。

## 项目结构

```
.
├── README.md                  ← 本文件（入口）
├── README_HANDOFF.md          ← 详细文档：两条命令、新建模型、改尺寸、验收清单
├── README_HANDOFF.en.md       ← 同上英文版
├── MANIFEST_SPEC.md           ← 契约规范：manifest 每个字段的定义与默认值
├── PACK_NOTES.md              ← 实测事实与坑（轴向/水密/惯量/环境，均为踩过的）
├── blender_export.py          ← ① 导出器：blend → source/<对象名>.glb（纯 bpy，无第三方依赖）
├── gazebo_pack.py             ← ② 校验/打包器：manifest → model.sdf/config + world.sdf（仅 PyYAML）
│
├── assets/                    ← ★ 源（进 git）：每个目录 = 一个资产包
│   ├── bus/                   ← 城市公交 10.5×2.5×3.05m, 12t, 动态, box 碰撞
│   ├── tesla/                 ← Tesla Model 3 4.69×1.85×1.44m, 动态, primitives(盒+4轮)
│   ├── falcon9/               ← 猎鹰 9 火箭
│   ├── coke_bottle/           ← 可乐瓶 0.08×0.08×0.25m, 动态, mesh（示例起点）
│   ├── chair/  table/  shelf/ ← 家具类
│   ├── cabin/  cabin2/        ← 小屋（两种变体）
│   ├── skyscraper/            ← 摩天楼
│   └── tag_cube/              ← 标签立方体（带大字贴图）
│
├── gazebo_models/             ← ② 产物（不进 git，build 后生成，可随时删）
│   └── <name>_<inst>/         ←    model.sdf + model.config + <name>_<inst>.glb
└── worlds/                    ← ② 产物（不进 git）
    └── <name>_world.sdf       ←    可直接 gz sim 的场景
```

**资产包内部**（以 `assets/coke_bottle/` 为例）：

```
assets/coke_bottle/
├── manifest.yaml            ← 契约：尺寸/质量/碰撞/布局（唯一事实来源）
├── model.blend              ← 源场景（返工时才用）
├── source/coke_bottle.glb   ← ① 产物：glb（贴图已内嵌）
├── textures/coke_label.png  ← 贴图（脚本烘好的图）
├── build_coke_bottle.py     ← 建模脚本：改顶部 SIZE 重跑即可
├── gen_coke_label.py        ← 贴图脚本：改尺寸/文案重跑
├── render_preview.py        ← 可选：不启动 Gazebo 先预览（出 preview.png）
└── preview.png              ← 预览渲染
```

**铁律**：`assets/` 是源，`gazebo_models/` 与 `worlds/` 是随时可删的产物；
资产包里的脚本只许写自己目录内，不许碰产物目录。

## 使用方法速查

```bash
# 新建模型：让 AI 产出 assets/<name>/ 后，两条固定命令
blender --background --python blender_export.py -- assets/<name>   # ① 导干净 glb
python3 gazebo_pack.py build assets/<name> --world                 # ② 校验 + 打包

# 只检查不写盘
python3 gazebo_pack.py validate assets/<name>

# 批量打包
python3 gazebo_pack.py build assets/ --all

# 改了模型/贴图脚本后（如改 SIZE），先重跑脚本再两条命令
python3 assets/<name>/gen_<name>_textures.py
blender --background --python assets/<name>/build_<name>.py
# …再跑上面两条

# 验证 + 运行（每次改完）
gz sdf -k worlds/<name>_world.sdf        # → Valid.
gz sim -r worlds/<name>_world.sdf
```

常用旋钮（改 `manifest.yaml` 后重跑 ② 即可，不用重导出）：
`mass` 质量 · `static` 静态 · `collision.type` mesh/box/primitives ·
`collision.optimization` convex_hull/convex_decomposition · `world.layout` 布局。
详见 [README_HANDOFF.md §7](README_HANDOFF.md)。

## 文档索引

| 文件 | 读它当 |
|---|---|
| [README_HANDOFF.md](README_HANDOFF.md) | 要动手：完整流程、新建/改尺寸、踩坑速查、验收清单 |
| [MANIFEST_SPEC.md](MANIFEST_SPEC.md) | 要写/校 manifest：字段定义与默认值（AI 也先读它） |
| [PACK_NOTES.md](PACK_NOTES.md) | 要懂为什么：轴向、水密、惯量、环境的实测事实 |
