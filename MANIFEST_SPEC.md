# MANIFEST_SPEC — 资产包与 manifest 规范 v1.0

> **地位**：建模侧（AI 对话产出）与打包工具（`gazebo_pack.py`）之间**唯一契约**。
> 工具只认本文件定义的 manifest，不认口头约定、不认聊天记录。
> **配套阅读**：`PACK_NOTES.md`（事实卡片；未决/待实测项见其 J 区）。

---

## 0. 流水线（三层设计）

```
对话建模（层③创意 + 层②参数）→ assets/<name>/     ── 交接物（资产包）
    → gazebo_pack.py（层①骨架）: validate → render → write
    → gazebo_models/<name>_<instance>/ + worlds/<name>.sdf
```

- **层① 通用骨架**（写死进工具，永不进对话）：sdf/config 结构、glb 校验、轴向默认
  roll+90°、归零规则、auto 惯量写法、命名、贴图规则、启动流程。
- **层② 参数**（每模型一份，manifest 字段）：尺寸、质量、原点、collision+optimization、
  实例、布局、static、轴向覆写。
- **层③ 创意**（留在对话）：造型、材质美学、数量、摆放审美。
- 何时该重查/改卡片：见 PACK_NOTES K。

---

## 1. 一句话 brief（五个槽位）

> **建模：<物体>，<尺寸>，<材质>，<数量/动态性>，collision <偏好>**
> 可选第六槽：**摆放 <布局>**；补充：凹陷处需真实接触？静态摆件？

示例：`建模：椅子，45×45×90cm，白蜡木，4个动态，collision 要真实（座面下方要空）`

AI 收到 brief 后：
1. 生成/更新 `assets/<name>/`（manifest 草稿 + 建模脚本，见 §2）；
2. 返回资产包 + 固定两条命令：

```bash
blender --background --python blender_export.py -- assets/<name>   # 通用导出器（层①）
python3 gazebo_pack.py build assets/<name> [--world]               # 校验+打包（层①）
```

**规则**：brief 没说的槽位按 §4 默认值补，并在回复里列出"我替你默认了什么"——
**默认值永远显式告知，不静默**。

---

## 2. 资产包目录结构（交接物）

```
assets/<name>/
├── manifest.yaml          # ★ 必需，契约本体
├── model.blend            # 源场景（可选但强烈建议）
├── source/<name>_00.glb   # 中间网格（原点按 §5.2 归位，贴图内嵌）
├── build_<name>.py        # 本包建模脚本（可选，见 §2.1）
└── textures/*.png         # 建模中间产物（可选）
```

- 一个资产包 = 一个**概念模型**；多个网格用 `instance` 区分（多标签/多变体/同款多件）。
- `source/*.glb` 必须满足 **origin = §5.2 声明的原点策略**，工具强制校验。

### 2.1 附随文件（2026-10 用户拍板：允许并鼓励）

资产包是**自带工具的自足单元**：脚本、贴图与交接单同目录，改完重跑即可。

1. **工具白名单**：工具只读 `source.meshes[].file`、`source.blend`、`frame.origin`，
   不扫描资产包 → 附随文件可自由增删，不影响校验与产物（源码见 PACK_NOTES E6）。
2. **单向纪律**：附随文件归资产侧，工具永不写入；脚本只写本包
   `model.blend`/`source/`/`textures/`，**不碰** `gazebo_models/` 与 `worlds/`。
3. **跨包只读**（2026-10 用户拍板）：可读其他包的文件，但读来的东西只能落在本包
   （引用或复制）；**跨包写 = 违规**；跨包依赖须在脚本头注释写明来源，缺文件显式报错；
   `source/*.glb` 仍须本包独立可重建。
4. **不影响交付**：`.glb` 只由 `blender_export.py` 产出；脚本只生成 `.blend`。

**脚本写作要求（避开 E2 坑）**：

| 要求 | 写法 |
|---|---|
| 路径 | 以 `os.path.dirname(os.path.abspath(__file__))` 为根，或要求在项目根运行 |
| 幂等 | 每次 `read_factory_settings(use_empty=True)` 重建，不在旧场景上叠加 |
| 自检 | 末尾打印实测 bbox + "每边恰 2 面"水密结论；失败 `raise SystemExit`（与 V4/V7 同口径） |
| 命名 | 一个 MESH 对象名 == manifest 里 glb 文件名主干 |

---

## 3. manifest.yaml 完整 Schema（v1.0）

```yaml
# ── 元信息 ───────────────────────────────────────────
schema_version: 1            # [int] 必需；工具遇到更高版本直接报错（前向兼容）
kind: model-package          # [enum] 必需；v1 仅 model-package（预留 sensor-rig / world-fragment）
name: table                  # [str] 必需；^[a-z][a-z0-9_]*$，决定目录名与 model://URI
description: "浅木色书桌"     # [str] 可选；进 model.config

# ── 源文件 ───────────────────────────────────────────
source:
  blend: model.blend          # [str] 可选；存在则附带校验"贴图已 pack"
  meshes:                     # [list] 必需，≥1 项
    - file: source/table.glb  # [str] 必需；相对资产包根
      instance: "0"           # [str|int] 必需；引号必加（YAML 00 会读成 0）
      # instance_count: 5     # [int] 可选；与 instance_range 二选一，展开 5 个
      # instance_range: [0, 23]  # [start, end] 含端点，展开 24 个（编号自动补零）

# ── 物理参数（层②）───────────────────────────────────
mass: 20.0                   # [float] kg，>0；static: true 时可省略
inertia: auto                # [enum] auto | explicit
  # explicit 时必填 inertia_values: {ixx, iyy, izz, ixy, ixz, iyz}（工具原样写入）
static: false                # [bool]；true 时省略 inertial（静态模型无需惯量）

# ── 几何（层②）───────────────────────────────────────
geometry:
  size: [0.8, 0.6, 0.75]      # [vec3] 米；强烈建议填：V4 对账 + world 贴地高度
                              #   缺省时 V4 报错

# ── 碰撞（默认块：type 缺省 = mesh）──────────────────
collision:
  type: mesh                  # [enum] mesh(默认) | box | primitives
  optimization: convex_hull   # [enum] 仅 type=mesh：convex_hull(默认) |
                              #   convex_decomposition | none（none 仅 static 合法，
                              #   动态+none → V9 警告）
  convex_decomposition:       # 仅 optimization=convex_decomposition 时生效
    max_convex_hulls: 16      # [int] 默认 16
    voxel_resolution: 200000  # [int] 默认 200000
  # primitives:               # 仅 type=primitives：手列组合（如桌面+4 桌腿）
  #   - {shape: box, size: [0.8, 0.6, 0.04], pose: [0, 0, 0.73, 0, 0, 0]}
  #   - {shape: cylinder, radius: 0.03, length: 0.73, pose: [0.35, 0.25, 0.365, 0, 0, 0]}
  #   - {shape: sphere, radius: 0.05, pose: [0, 0, 0.05, 0, 0, 0]}

# ── 坐标与轴向 ───────────────────────────────────────
frame:
  origin: center              # [enum] center(默认) | bottom-center；V5 校验
visual_pose: [0, 0, 0, 1.57079632679, 0, 0]
                              # [vec6] x y z roll pitch yaw（弧度）；默认 roll+90°（B1）
                              # 朝向不符时覆写：朝下取负 roll；朝 ±X 改 pitch
                              # 不改 glb 本身；mesh 碰撞套用同一 pose（共用数据），
                              # box/primitives 不旋转
# ── Gazebo 输出 ──────────────────────────────────────
gazebo:
  sdf_version: "1.11"         # [str] 默认；<1.11 且 inertia=auto → V8 报错

# ── world（可选，--world 时生效；缺省 = 不生成）──────
world:
  name: house_office          # [str] 默认 name + "_world"
  layout:                     # 默认 grid
    type: grid                # grid | line | explicit
    cols: 6                   # grid：列数（instances/cols 向上取整）
    rows: 4                   #   （可只写 cols，rows 自动）
    pitch: 1.0                # grid/line：中心距（米），默认 2×max(size)
    z: auto                   # auto | 数值；auto：center → size_z/2，bottom-center → 0
    # axis: x                 # type: line 时（单排）
    # poses: [[x,y,z,r,p,y], ...]  # type: explicit 时，数量 = instance 数
  ground: true                # [bool] 内联地面（默认开，离线可跑）
  sun: true                   # [bool] 内联方向光（默认开）
  plugins: default            # [enum] default(四件套) | minimal(仅物理)
```

---

## 4. brief 缺槽 → 默认值（其余以 §3 为准）

| 缺槽 | 默认 / 处理 |
|---|---|
| `mass` | **无默认**：AI 按物体常识估，并显式告知（static 时可省） |
| `static` | `false`；brief 说"摆件/静态" → `true` |
| `frame.origin` | `center`（B2） |
| `visual_pose` | roll +90°（B1） |
| `collision.type` / `optimization` | `mesh` / `convex_hull`（A3） |
| `inertia` / `sdf_version` | `auto` / `"1.11"`（A2） |
| `geometry.size` | **必填**：AI 从建模实测尺寸抄入（V4） |
| `world` | `grid`，`cols=min(n,6)`，`pitch=2×max(size)`，`z=auto`；ground/sun/plugins 全开 |

**AI 必须把上表里实际用到的默认值写进回复**，不静默。

---

## 5. 命名与坐标约定（工具固化）

### 5.1 输出布局
```
gazebo_models/<name>_<instance>/
├── model.config             # name/version/入口 sdf + description
├── model.sdf                # §5.3 结构
└── <name>_<instance>.glb    # 同目录同名；visual URI = model://<name>_<instance>/…
worlds/<world.name>.sdf      # world 块存在时
```
同族多实例 = 同一资产包展开，**不允许 24 个文件夹各自为政**。

### 5.2 原点策略（validator 口径）
- `center`：glb 顶点 AABB 中心距原点 ≤ **1mm**；
- `bottom-center`：AABB 底面中心距原点 xy ≤ 1mm、|z_min| ≤ 1mm；
- 违规 → **报错拒打包**（宁可失败，不可生成 visual 错位的模型）。

### 5.3 model.sdf 骨架（字段全部来自 manifest）
```xml
<sdf version="{sdf_version}">
  <model name="{name}_{instance}">
    <static>{static}</static>                 <!-- 仅 static: true -->
    <link name="link">
      <!-- inertia=auto 且 static=false：不写 pose/density/inertia（C1） -->
      <inertial auto="true"><mass>{mass}</mass></inertial>
      <visual name="visual">
        <pose>{visual_pose 六值}</pose>        <!-- 层①默认 roll+90° -->
        <geometry><mesh><uri>model://…/{name}_{instance}.glb</uri>
          <!-- optimization 是 mesh 属性（A3） -->
          <scale>1 1 1</scale></mesh></geometry>
      </visual>
      <!-- collision：mesh = 同 uri + 同 pose + optimization 属性；
           box/primitives = 手列几何，无 pose -->
    </link>
  </model>
</sdf>
```

### 5.4 world 骨架（层①固定）
- 固定：scene、四插件（Physics/UserCommands/SceneBroadcaster/Sensors）、
  内联 ground+sun、**零 Fuel 引用（离线可跑）**；
- 变量：`<include>` 列表（name + pose，来自 layout）。

---

## 6. 工具 CLI 与校验

```bash
python3 gazebo_pack.py validate assets/<name>   # 只校验，不写盘
python3 gazebo_pack.py build    assets/<name>   # 校验+生成
python3 gazebo_pack.py build    assets/ --all   # 批量
python3 gazebo_pack.py build    assets/<name> --world   # 额外生成 world
```
- 退出码：0=成功；1=校验失败（逐条 ❌）；2=用法/文件错误。
- 幂等：重复 build 全量覆盖，产物逐字节一致。

### Validator（层①，与 PACK_NOTES 编号对应）

| # | 检查 | 级别 | 依据 |
|---|---|---|---|
| V1 | schema_version ≤ 工具支持；kind 已实现 | ❌ | spec v1.0 |
| V2 | name 合法；instance 唯一且展开数一致 | ❌ | §5.1 |
| V3 | mesh 存在、glb 可解析（顶点/包围盒） | ❌ | B2 |
| V4 | AABB ≈ geometry.size（各轴 ±5% 或 ±2cm 取宽） | ❌ | 防改模忘改单 |
| V5 | 原点策略（§5.2，容差 1mm） | ❌ | B2 |
| V6 | 贴图内嵌（glb 无外部 uri；blend 贴图已 pack） | ❌ | D4/A1 |
| V7 | auto 惯量 + mesh → 网格水密 | ❌ | C2 |
| V8 | sdf < 1.11 且 inertia=auto | ❌ | A2 |
| V9 | 动态 + optimization=none | ⚠️（仍打包） | A3 |
| V10 | mass>0；explicit 惯量六项齐全 | ❌ | C1 |
| V11 | layout.poses 数 = 实例数；z=auto 换算 | ❌ | §5.4 |
| V12 | 输出清单 + 体积 + 启动三步提示 | ℹ️ | F |

---

## 7. 边界与纪律（工具宪法）

1. **只读 `assets/`，只写 `gazebo_models/` + `worlds/`**，永不反向改资产；
   包内脚本同样只写本包 `model.blend`/`source/`/`textures/`（§2.1）。
2. **产物可随时删除重建**（丢失 = 重跑一条命令，资产才是源）。
3. **判断归对话，重复归工具**：造型/材质/朝向/质量估值由对话定；
   模板/校验/命名/布局计算由工具做。
4. **默认值必须显式告知**（§4），不静默。
5. **未验证的知识不进规范**：先进 PACK_NOTES J 区，实测后回填 A 区再入工具。
6. **本规范与 PACK_NOTES 同生共改**：每个默认值都能在 PACK_NOTES 找到出处编号
   （A2/A3/B1/B2/C1/C2/D4/F）。
7. **资产包自足**（2026-10 用户拍板）：建模脚本与中间产物随包存放，
   不进 manifest、不进产物、不影响校验（§2.1）。
8. **默认不做贴地/接触验证**（2026-10 用户拍板）：验收 = `validate` + `gz sdf -k`；
   离地 0–0.5 m 可接受。水密（脚本自检 + V7）、尺寸、原点、贴图仍强制。
