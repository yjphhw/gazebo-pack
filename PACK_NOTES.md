# PACK_NOTES — Gazebo 模型打包事实卡片（新会话必读）

> **用途**：新会话建模/打包前，先读本文件 + 用户 brief，恢复背景，**不再进行网络/源码搜索**。
> **维护规则**：只收"实测或源码查证过"的知识，每条带出处；未验证的进 J 区，不得当定论；
> **重查触发统一见 K**；本文件只记事实，不记变更历史。
> **查证基准**：Gazebo Harmonic / sdformat14 / gz-common5 / Blender 5.2 LTS（2026-10）。

---

## A. 格式与版本兼容

**A1. 网格格式**：gz-sim 支持 `.glb`/`.gltf`（AssimpLoader；内嵌 PNG 可读）；
Gazebo Classic 11 不支持 glb（仅 stl/dae/obj，会报 "Unsupported mesh format"）。
出处：gz-common `graphics/src/MeshManager.cc`、`AssimpLoader.cc`（`LoadEmbeddedTexture`）；
classic 的 `gazebo/common/MeshManager.cc`（gazebo11 分支）。

**A2. SDF 版本与 auto 惯量**：`<inertial auto="true">` 需 **SDF ≥ 1.11**；Harmonic 携带的
sdformat14 支持。出处：`sdf/1.11/inertial.sdf` 的 `attribute auto`。manifest 固定 `"1.11"`。

**A3. mesh optimization**：
- `convex_hull`：单个凸包，凸形体无损、最快，**默认**；
- `convex_decomposition`：VHACD 多凸包，桌椅等**凹形体**用；参数默认 16 / 200000；
- `none`（空）：不优化，仅 static 或调试。
⚠️ `convex_hull` 会**把凹陷填实**（椅子四腿被包成一坨，放椅面会悬空）——凹处要真实接触
必须用 `convex_decomposition`。
出处：gz-common `MeshManager.cc`（VHACD）、`sdformat/sdf14/sdf/1.11/mesh_shape.sdf`。

**A4. 用户环境**：Gazebo Harmonic（`gz sim`，本机 8.15.0）。

**A5. 模型目录 = Fuel 上传规范**：官方结构 `materials/ meshes/ thumbnails/ model.config
model.sdf`。`thumbnails/` 放 **`1.png`~`5.png`**（同一模型不同角度，Fuel 网页轮播图），
**本地 gz sim 完全忽略该目录**。出处：gz-sim 官方教程 `mesh_to_fuel.md`（"Thumbnails are
.png files named 1 through 5"）+ 本机实锤 `/opt/ros/jazzy/share/ros_gz_sim_demos/models/
cardboard_box/thumbnails/1..5.png`。本项目约定：资产包 `preview.png` → 打包时复制为产物
`thumbnails/1.png`（V13；preview 缺席只 ⚠️）。

**A6. 本工具与 Fuel 的差异**：产物目录用 `source glb 同目录同名`（而非 Fuel 的 `meshes/`），
贴图内嵌 glb（而非 `materials/textures/`）——为的是单文件分发 + 零外部引用（A1/D4）。
**如需上传 Fuel，需转换**：glb 挪 `meshes/`、model.sdf 的 `<uri>` 改
`model://<name>/meshes/…`、preview 改名补齐 `thumbnails/1..5.png`。未做，也不在 v1 做。

---

## B. 坐标系与轴向（本项目实证）

**B1. glb 顶面朝侧面**：glTF 是 Y-up，Blender 导出把 +Z 烘进顶点数据的 +Y；Gazebo 是
Z-up 且不换向 → 视觉上顶面出现在侧面。修法：**SDF visual 加 roll +90°**
（`<pose>0 0 0 1.57079632679 0 0</pose>`），**不动 glb**——这是 Blender→glTF→Gazebo
通病，层①默认。备选：朝下取负 roll；朝 ±X 改 pitch `0 1.57079632679 0`；pose 必须 6 值。
工具解码：换轴烘焙进顶点（节点 transform=单位阵）→ 比对尺寸/原点前做
`glTF→Blender: xyz=(x,z,-y)`。

**B2. 原点偏移**：Blender 按世界位置导出时 `location` 会进 glTF 节点 transform，
Gazebo 里 visual 相对 link 原点错位（本项目实测错 0.375m）。修法：**导出前把整组对象
平移到锚点**（`blender_export.py --origin`），保证 模型原点 = 几何中心/底面中心 = link 原点。
硬规范：glb 必须满足 `frame.origin`（center / bottom-center），V5 强制，违规拒打包。
（几何不变量，永久有效。）

---

## C. 物理与惯量

**C1. auto 惯量**：`<inertial auto="true">` 按 **collision 形状**算惯量；写了 `<mass>`
则把结果缩放到该质量（0.1m 立方体 @0.1kg → I≈1.667e-4）。**不要写 `<density>`**
（会覆盖质量语义）；**不要在 inertial 里写 `<pose>`/`<inertia>`**（触发覆盖警告）。
出处：sdformat14 `src/Link.cc` `ResolveAutoInertials()`。

**C2. mesh + auto = 体积积分 → 必须水密**：`auto_inertia_params` 面向 **mesh 惯量
计算器**，网格须封闭、流形、无自交、法线朝外，否则算错/算不出。
派生规则：建模侧自检（AI 铁律）+ validator V7 拒打包。

**C3. collision 策略**：`mesh`（默认，共用同一 glb + optimization，几何精确）；
`box`（快、丢凹凸）；`primitives`（手列盒/柱，如桌面+桌腿）。动态 + 非凸原始网格
物理不稳（A3 的由来），所以动态默认带 `convex_hull`。

---

## D. 贴图与渲染

- **D1** 标签/检测类纹理：`interpolation='Closest'` + **关 mipmap**（防远处模糊导致检测失败）。
- **D2** 色彩管理用 `Standard`（不是 AgX/Filmic），防黑白对比度被调灰。
- **D3** 贴图 colorspace 保持默认 sRGB，**不要改 Non-Color**；glTF 按 sRGB 编码。
- **D4** 程序化节点材质（noise/wave）导出 glTF 会丢——进 Gazebo 的材质必须先烘成 png。
- **D5** 贴图 `pack()` 进 .blend，文件搬家不丢图。

---

## E. Blender 5.x API

- **E1** EEVEE 枚举是 `'BLENDER_EEVEE'`（`_NEXT` 在 5.x 已删除，旧名报 TypeError）。
- **E2** 未保存场景不能用 `bpy.path.abspath("//x.png")`——用 `__file__` 目录或 cwd。
- **E3** `mat.use_nodes = True` 标记 6.0 移除——直接用 `mat.node_tree`，无树时才建。
- **E4** AprilTag 绘制：OpenCV ≥4.7 用 `aruco.generateImageMarker()`（旧 `drawMarker`，
  hasattr 兼容）；aruco 在 **opencv-contrib-python**（独立版没有）。
- **E5** 布尔用 `solver="EXACT"`（旧 `"BMESH"` 4.5+ 废弃）；`UNION` 后逐件 apply。
  **零件必须有真实相交体**（面贴面会产出非流形边，V7 拒打包）；合并后
  `remove_doubles(1e-6)` + `normals_make_consistent(inside=False)`。
- **E6 脚本随包**：`build_*.py` 放包内，只写本包 `model.blend`/`source/`/`textures/`；
  可跨包只读、不可写；白名单与细则见 spec §2.1。实测：`/snap/bin/blender` 缺
  `cap_dac_override` 起不来，用 `/snap/blender/current/blender`；`~/.gz` 日志不可写但
  仿真正常运行（无害）。

---

## F. 启动与校验（固定三步）

```bash
export GZ_SIM_RESOURCE_PATH=$GZ_SIM_RESOURCE_PATH:<库根目录>   # 1 模型搜索路径
gz sdf -k worlds/<x>.sdf                                       # 2 语法+引用校验
gz sim -r worlds/<x>.sdf                                       # 3 启动（-r 即时运行）
```
- world 必备 4 插件：Physics / UserCommands / SceneBroadcaster / **Sensors**；内联
  ground+sun，**不引 Fuel → 完全离线可跑**。
- **F1** `gz sdf -k` 校验含 `model://` include 的 world 时只认 **`SDF_PATH`**（sdformat
  自己的搜索路径），不是 `GZ_SIM_RESOURCE_PATH`；两者都要 export，`gz sim` 运行时才认后者。
- **F2** headless 验证：`gz sim -s -r <world>` + `gz topic -e -t /world/<名>/dynamic_pose/info`
  （话题用 `-t`，类型自动推断，**不要**传 `-n 1`/位置参数）。
- **F3（2026-10 用户拍板）**：**不默认起仿真验证贴地/接触**；0–0.5 m 离地可接受。
  验收 = `validate` + `gz sdf -k`；水密/尺寸/原点/贴图仍强制。F2 仅在明确要求时用。

---

## G. AprilTag

- **G1** `tag36h11`：36 数据位（6×6 模块），h11 码距；图案 8×8 模块（6×6 + 1 圈黑边）；
  四周需 **≥1 模块白色静区**——本流水线把静区烘进贴图（"占满整面"指纹理，白边在纹理内）。
- **G2** tag36h11 共 **587 个有效码（ID 0–586）**；"36"是位数不是数量。
- **G3** 生成后必须回读自校验：`ArucoDetector.detectMarkers` 逐张，ID 不符立即报错。

---

## H. 本项目实证的坑（改模板前必读）

| # | 坑 | 修法 | 层 |
|---|---|---|---|
| 1 | glb 节点位置偏移 → visual/collision 错位 | 导出前整体归位 | ① |
| 2 | Y-up/Z-up → 顶面变侧面 | visual roll +90° | ① |
| 3 | `use_nodes` 废弃 / `BLENDER_EEVEE_NEXT` 删除 | 见 E1/E3 | ① |
| 4 | auto 惯量 × mesh → 需水密网格 | 建模自检 + V7 拒打包 | ①+② |
| 5 | `//` 路径依赖已保存 blend | 绝对路径拼接 | ① |
| 6 | 标签纹理被插值/mipmap 糊掉 | Closest + 关 mipmap + Standard | ① |
| 7 | 程序化材质导出丢失 | 烘成 png（D4） | ① |
| 8 | 零件面贴面 → 布尔后非流形 | 真实相交后 UNION(EXACT)（E5） | ② |
| 9 | 脚本散落 → 改尺寸到处找 | 脚本随包（E6 / spec §2.1） | ② |

---

## J. 待实测（不得当定论）

- **J1（半实测, gz 8.15.0）**：`optimization="convex_hull"` 过 `gz sdf -k`（无
  unknown-attribute，Valid）；headless 加载 mesh collision + auto 惯量正常（24 模型入
  场景、tag_cube_05 静置 z=0.05 无穿地/飞出）。❓ 未直接证明"DART 拿到的是凸包而非
  原始网格"；对凸形体二者等价，风险低。
- **J1b（chair）**：凹体（椅面下空腔）用 convex_hull 会把空腔填实——直立/推倒/滑动
  正常（4 把椅子 z=0.450000、四元数≈单位），但"塞进桌下"类接触需
  `convex_decomposition`（VHACD）。
- **J1c（coke_bottle）**：box 碰撞 z=0.125000 精确贴地；mesh+convex_hull 静置
  **z=0.126506**（比几何底高 1.5 mm ≈0.6% 瓶高；旧 0.8m 版为 +4.8 mm，同比例），
  稳定、无穿地/飞出。推测 gz-common 凸包比原网格略"鼓"（非引擎全局 margin：同 world
  的 box 精确贴地）。视觉不可见；贴地/堆叠敏感场景先 box 或实测。**膨胀来源未查证**。
- **J1d（coke_bottle）**：`gz sdf -k` 对 mesh+auto 惯量会打
  `Custom moment of inertia calculator ... using default inertial values` 警告，
  但仍 Valid；离线 CLI 无物理引擎，不影响打包。运行时 mesh 的 auto 惯量是否真按
  体积积分尚未直接验证。
- **J2**：roll+90° 已实测通过（标签朝上），但仅验证"顶面=+Z"一种建模朝向；pitch 未实测。
- **J3**：`convex_decomposition` 的 VHACD 分解质量/耗时未实测。

---

## K. 何时必须重新搜索

1. Gazebo 大版本升级（gz-sim / sdformat / gz-common major bump）；
2. Blender 大版本升级（API 枚举再变）；
3. 用户反馈"卡片与实测不符"→ 先实测，再改卡片，再改工具；
4. 出现卡片未覆盖的新需求（urdf 输出、ros_gz 集成、传感器配置）。
