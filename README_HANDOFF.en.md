# README_HANDOFF — Chat-to-Model → Gazebo Asset Packages (5-minute guide)

> 中文: [README_HANDOFF.md](README_HANDOFF.md)
> Contract/schema: [MANIFEST_SPEC.md](MANIFEST_SPEC.md) · Field notes & pitfalls: [PACK_NOTES.md](PACK_NOTES.md)
> Tested with Blender 5.2.2 LTS · Gazebo Harmonic 8.15 · Python 3 + PyYAML 6.
> **Run all commands from the project root.**

## 0. At a glance

```
assets/<name>/                 ← the handoff (source of truth)
├── manifest.yaml              ← contract: size/mass/collision/layout
├── model.blend                ← source scene
├── source/<name>.glb          ← intermediate mesh (produced by the exporter)
├── build_<name>.py            ← optional build script (re-run after edits)
└── textures/                  ← optional baked textures
        │  two fixed commands
        ▼
gazebo_models/<name>_XX/       ← artifacts: model.sdf + model.config + <name>_XX.glb
│                                (+ thumbnails/1.png, if preview.png exists)
worlds/<name>_world.sdf        ← artifact: ready-to-run gz sim scene
```

**Artifacts are disposable; the asset package is the source.** The repo only commits
asset packages — a fresh clone has no `gazebo_models/` or `worlds/`; generate them by
running the two commands from §3 once (or the one-liner in §2).

## 1. Environment (one-time)

| Dependency | Requirement | Check |
|---|---|---|
| Blender | 5.2 LTS tested (4.x untested) | `$BLENDER --version` |
| Python | ≥3.10 + PyYAML | `python3 -c "import yaml; print(yaml.__version__)"` |
| Gazebo | Harmonic (8.15 tested) | `gz sim --version` |

On this machine `/snap/bin/blender` cannot start (snap permission); use
`/snap/blender/current/blender`:

```bash
export BLENDER=/snap/blender/current/blender     # or your own blender path
$BLENDER --version
```

## 2. Run the shipped example first (no modeling)

This repo ships `assets/coke_bottle`: a 0.08×0.08×0.25 m red cola bottle,
1 dynamic instance, mesh collision. The repo only commits asset packages, so the
artifact directories are **built, not cloned** — full sequence:

```bash
python3 gazebo_pack.py build assets/coke_bottle --world   # 1) generates gazebo_models/ + worlds/
export GZ_SIM_RESOURCE_PATH=$PWD/gazebo_models:$GZ_SIM_RESOURCE_PATH
export SDF_PATH=$PWD/gazebo_models:$SDF_PATH

gz sdf -k worlds/coke_bottle_world.sdf     # 2) expect "Valid." (an inertia warning may precede it — normal)
gz sim -r worlds/coke_bottle_world.sdf     # 3) GUI: the red bottle standing on the ground
```

Expected: `coke_bottle_00` near the origin, bottom on the ground, texture visible.

No GUI? Use headless:

```bash
gz sim -s -r worlds/coke_bottle_world.sdf &
SIM=$!
sleep 5    # use 8-10 on slow machines
timeout 3 gz topic -e -t /world/coke_bottle_world/dynamic_pose/info
kill $SIM
```

Check that z stays constant (≈0.125–0.127) instead of falling through / flying away.

## 3. The two fixed commands

Every `assets/<name>/` has exactly two steps:

```bash
$BLENDER --background --python blender_export.py -- assets/<name>   # 1) export clean glTF
python3 gazebo_pack.py build assets/<name> --world                  # 2) validate + package
```

- Step 1 reads `model.blend`, exports every mesh object to `source/<object_name>.glb`,
  re-centers it per `manifest.frame.origin`, and checks that textures are packed.
- Step 2 reads `manifest.yaml`, runs checks V1–V14; any ❌ refuses to package and
  prints the reason; on success it writes `gazebo_models/`, plus `worlds/` when the
  manifest has a `world:` block.
- Validate only, write nothing: `python3 gazebo_pack.py validate assets/<name>`.
- Batch: `python3 gazebo_pack.py build assets/ --all`.

**If the package has a `build_*.py` (e.g. the bottle), run it first after changing
dimensions/shape**, then the two commands:

```bash
$BLENDER --background --python assets/coke_bottle/build_coke_bottle.py
```

If the texture changed too, run `python3 assets/coke_bottle/gen_coke_label.py` first.

## 4. Create a new model (two routes)

**Route A · let the AI do it (recommended)** — one brief sentence (template in
[MANIFEST_SPEC.md §1](MANIFEST_SPEC.md)):

```
Model a desk, 0.8 x 0.6 x 0.75 m, light wood, 1 static prop, collision default
```

The AI returns the asset package plus the two commands. For a fresh session, prepend:
"Read MANIFEST_SPEC.md and PACK_NOTES.md before working."

**Route B · do it yourself**:

- Brand-new shape: build it in Blender following §8 → write `manifest.yaml` using
  the template in §6 → run the two commands from §3.
- Same shape, new size: copy `assets/coke_bottle`, rename it, and keep at least
  5 places in sync: `manifest.name`, the `source/*.glb` filename +
  `source.meshes[].file`, the Blender object name (= glb stem), and `NAME`/`SIZE`
  in `build_coke_bottle.py`. Rename `world.name` too.

## 5. Change the size — the bottle as a worked example (3 places + 4 commands)

1. `assets/coke_bottle/build_coke_bottle.py`, top: `SIZE = (0.08, 0.08, 0.25)` (m, X×Y×Z)
2. `assets/coke_bottle/manifest.yaml`: `geometry.size: [0.08, 0.08, 0.25]` (must match)
3. If the circumference:height ratio changes (e.g. from 0.8×0.6×0.75 to
   0.08×0.08×0.25), also change `W, H` in `gen_coke_label.py`: currently
   `2048×2048` ≈ circumference (π·D) : height. Uniform scaling needs no change.

```bash
python3 assets/coke_bottle/gen_coke_label.py
$BLENDER --background --python assets/coke_bottle/build_coke_bottle.py
$BLENDER --background --python blender_export.py -- assets/coke_bottle
python3 gazebo_pack.py build assets/coke_bottle --world
```

Only changing manifest fields (mass/layout/collision)? No re-export needed — just run
the final `build`.

## 6. Minimal manifest (copy-paste)

```yaml
schema_version: 1
kind: model-package
name: my_model                 # ^[a-z][a-z0-9_]*$; drives the directory and model://
description: "my model"
source:
  blend: model.blend
  meshes:
    - file: source/my_model.glb
      instance: "00"           # keep the quotes (YAML reads bare 00 as 0)
mass: 1.0                      # kg
inertia: auto
static: false
geometry:
  size: [0.1, 0.1, 0.2]        # metres, X×Y×Z; must equal the measured bbox
collision:
  type: mesh
  optimization: convex_hull
frame:
  origin: center               # or bottom-center
gazebo:
  sdf_version: "1.11"
# Uncomment to generate a world:
# world:
#   name: my_model_world
#   layout: {type: grid, cols: 1}
```

Rules: the Blender mesh object must be named `my_model` (= glb stem);
`geometry.size` must be the measured bbox.

## 7. Knobs you'll actually turn (edit manifest, re-run build)

| Want to change | Field | Notes |
|---|---|---|
| Mass | `mass` | kg; omit when `static: true` |
| Static prop | `static` | `true` = no gravity, no inertial block |
| Quantity | `source.meshes[].instance_count` | replace `instance` with `instance_count: N` (N copies; ids 0..N-1, zero-padded once the max id reaches 10) |
| Contact realism | `collision.optimization` | default `convex_hull` (fast; fills concavities); use `convex_decomposition` for true concave contact |
| Collision shape | `collision.type` | `mesh` (default) / `box` (fast, loses shape) / `primitives` (manual boxes/cylinders) |
| Layout | `world.layout` | `grid`/`line`/`explicit`; `pitch`; `poses` for explicit |
| Ground offset | `frame.origin` | `center` (world auto-raises z=size_z/2) / `bottom-center` (z=0) |
| Axis fix | `visual_pose` (top-level or under `frame`) | default roll+90°; rarely needs changing |

⚠️ Two iron rules: `instance: "00"` **must keep quotes**; `geometry.size` must match
the model (the tool measures the glb bbox; tolerance per axis = max(5%, 2 cm)).

## 8. Build the .blend yourself — four requirements

1. **One mesh object = one model**: object name = output glb stem
   (`my_model` → `source/my_model.glb`).
2. **Watertight**: every edge shared by exactly 2 faces. Check: Edit Mode →
   Select → All by Trait → **Non Manifold** (Shift+Ctrl+Alt+M) should select nothing.
   Join parts with `Boolean UNION (Exact)`; parts must truly intersect
   (face-on-face contact yields non-manifold edges).
3. **Textures**: image textures only (procedural nodes are lost in glTF);
   `File → External Data → Pack Resources`.
4. **Transforms**: don't rotate/scale objects (apply scale). Origin re-centering is
   handled by the exporter according to `frame.origin`.

## 9. Troubleshooting

| Symptom | Fix |
|---|---|
| `Unable to find uri[model://…]` | `gz sdf -k` only reads `SDF_PATH`; export both variables |
| `command not found` ($BLENDER unset/wrong path) / snap permission error | Use `/snap/blender/current/blender` |
| `~/.gz` prints "Error opening log file" | Permission issue, **harmless**; the sim still runs |
| `Custom moment of inertia calculator … using default inertial values` | `gz sdf -k` note for mesh+auto inertia; still `Valid`, packaging unaffected |
| Model looks like a flat sheet / lies down | Don't pre-rotate it; axis is handled by `visual_pose` (default roll+90°) |
| Chair sits on an invisible plank | `convex_hull` filled the concavity → `convex_decomposition` |
| `[V4]` size mismatch | `geometry.size` ≠ measured bbox → make them agree |
| `[V5]` origin violation | Re-export with `blender_export.py` per `frame.origin` |
| `[V7]` mesh not watertight | Holes/non-manifold → boolean-union or `Mesh → Clean Up` |
| No world generated | The manifest has no `world:` block (adding `--world` won't create one) |
| `instance: 00` becomes 0 | Keep the quotes |

## 10. Directory map (actual files in this repo)

```
assets/coke_bottle/
├── manifest.yaml            ← contract
├── model.blend              ← source scene
├── source/coke_bottle.glb   ← step-1 artifact (glb)
├── textures/coke_label.png  ← texture (baked image)
├── build_coke_bottle.py     ← build script (re-run after editing SIZE)
├── gen_coke_label.py        ← texture script (re-run after editing W/H/text)
├── render_preview.py        ← optional preview render
└── preview.png              ← preview image
gazebo_models/coke_bottle_00/   ← step-2 artifact (regenerable, don't hand-edit; not committed, appears after build)
worlds/coke_bottle_world.sdf    ← step-2 artifact (same)
blender_export.py               ← step-1 exporter (no third-party deps)
gazebo_pack.py                  ← step-2 validator/packer (PyYAML only)
```

(`gazebo_models/` and `worlds/` are not in git; run
`python3 gazebo_pack.py build assets/<name> --world` once after cloning.)

For a quick look without Gazebo: `$BLENDER --background --python assets/coke_bottle/render_preview.py`
→ writes `assets/coke_bottle/preview.png`.

Extra scripts/textures in a package are **companion files**: not in the manifest,
not in the artifacts, invisible to validation; they may only write inside their own
package, never into `gazebo_models/` or `worlds/`.

## 11. Acceptance checklist (after every change)

```bash
python3 gazebo_pack.py validate assets/<name>    # expect 0 errors, 0 warnings
gz sdf -k worlds/<world>.sdf                     # expect Valid.
```

No simulation-based ground/contact check by default: a 0–0.5 m gap is acceptable
(decided 2026-10). Use `gz sim -r` only to eyeball it; it is **not** an acceptance gate.
Watertightness, size, origin and textures are still enforced.
