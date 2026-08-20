# AGENTS.md

Context for agents working on **Flow**, a Blender extension that drives procedural sine-wave sway
onto bone chains with drivers.

> **Maintenance rule:** updating this file is the *last* step of every meaningful change. If you
> altered the driver math, the data model, a parameter's meaning, the file layout, or a workflow
> described here, edit the relevant section before you report the work as done. Keep it short and
> factual — it is context, not a changelog.

## Layout

| File | Contents |
| --- | --- |
| `__init__.py` | `register_submodule_factory` over `ui`, `properties`, `operators`, `visualizer`; registers the preset path |
| `properties.py` | All `bpy.types.PoseBone.festivity_flow_*` properties (declared inside `register()`, not a PropertyGroup), `FlowPreferences`, the selection-order `depsgraph_update_post` handler, and the `update_sw_*` callbacks |
| `functions.py` | Chain detection, sway targets, constraints, and every driver expression |
| `operators.py` | Add / Remove / Bake sway, preset add / remove / menu |
| `ui.py` | The `Flow` N-panel |
| `visualizer.py` | `POST_VIEW` GPU handler drawing sway-direction arrows |
| `presets/festivity_flow/*.py` | Bundled presets; plain scripts that assign a `settings` dict onto `bpy.context.selected_pose_bones` |
| `build.bat` | `blender --command extension build` — zips are gitignored, don't commit them |

No third-party dependencies. Minimum Blender is 4.4 (`blender_manifest.toml`); development happens on 5.2.

## How the sway works

Nothing is driven on the bone itself. Per sway bone:

1. A hidden empty `FESTIVITY_FLOW_SwayTarget_<rig>_<bone>` is parented to the rig and linked into a
   `Festivity Flow` collection (`hide_render`).
2. A `COPY_ROTATION` constraint named `FESTIVITY_FLOW_Sway` (mix `ADD`, owner and target space
   `LOCAL`) copies that empty's rotation onto the bone, so the sway adds on top of any animation.
3. Two custom properties on the empty, `_sw_mo` and `_sw_so`, are each driven by a sine — the main
   and sub wave. `rotation_euler[0]` (main) and `[2]` (sub) are then driven from those two values
   plus amplitude, falloff, bias, limits and roll.

Settings are mirrored onto **every** bone of a chain by `update_sw_prop()`, but the drivers only ever
read from the **chain root** — the bone with `festivity_flow_end_of_chain = True`, which despite the
name is the parent-most bone. Use `_get_chain_root()` / `get_ordered_chain_bones()`; the latter
returns bones root-first, which is the `bone_index` ordering every driver helper expects
(`bone_index == 0` is the root, `total_bones - 1` the tip).

A chain is identified by `festivity_flow_chain_id`, a zero-padded string (`"01"`).

`create_sway_chains()` gives each **fresh** chain a random `festivity_flow_sw_random_seed`, a time
shift of ±2 seconds that keeps chains from moving as one. Chains that already have custom settings
(`bone_has_custom_sway_settings()`) keep the seed they have, so a chain deliberately synced to 0
survives a re-add. To sync chains for a shot: select them all and set Random Seed to 0 (with the
default `apply_to_all_chains` preference that propagates in one edit), matching Offset, Frequency and
Speed. To sync the bones *within* a chain, set Delay to 0%.

### The driver expressions

Written in `_ensure_phase_drivers()` and `_add_sway_driver()`; `fps` is the scene fps interpolated as
a literal at build time.

```
_sw_mo = sin(2*pi*(frq*sp*(frame+rs*fps)/fps + dly*K/100) + off/fps)
_sw_so = sin(2*pi*(f2 *sp*(frame+rs*fps)/fps + d2 *K/100) + o2 /fps)

rotation_euler[0] =  pi/360*(main)*cos(rl*pi/180) - pi/360*(sub)*sin(rl*pi/180)
rotation_euler[2] =  pi/360*(main)*sin(rl*pi/180) + pi/360*(sub)*cos(rl*pi/180)

main = max(lmn, min(bm,lmp) - amp*(fo*F2+F1))*(1-mo) + min(lmp, max(lmn,bm) + amp*(fo*F2+F1))*(1+mo)
```

The per-bone constants baked into the expression strings:

- `K` — the delay factor from `_get_delay_factor()`: `index/(total_bones-1)`, 0 at the leading end and
  1 at the trailing one, flipped by `..._delay_opposite`.
- `F1 = bone_index/(total_bones-1)` and `F2 = 1-F1` — the amplitude falloff, so the root gets
  `falloff_start` and the tip full amplitude.

Because the delay term sits **outside** the `frq*sp` factor and is normalized by `total_bones-1`
rather than fps, **Delay is a phase lag in percent of one wave cycle** and is independent of
Frequency, Speed, scene fps and chain length. Delay 50% means the trailing bone is half a cycle
behind the leading one. Do not move `dly` back inside the time term — that is exactly the coupling
that was removed in 1.4.0.

Everything else in the expressions is a live driver variable reading the chain root, so changing a
setting needs no rebuild. Only the baked constants (`K`, `F1`, `F2`, `fps`) require
`rebuild_sway_drivers()`, which is why `..._delay_opposite` has its own update callback.

## Conventions

- Adding a pose-bone property means touching four places: the declaration in `register()`, the
  matching `del` in `unregister()` (reverse order), an `update_sw_*` callback that calls
  `update_sw_prop()`, and a row in `ui.py`. Add it to `bone_has_custom_sway_settings()` if it should
  count as user history, and to the `props` list in `FESTIVITY_FLOW_OT_preset_add.add()` if presets
  should carry it.
- Guard writes that must not cascade with `pb.festivity_flow_update = False` / `True`;
  `update_sw_prop()` returns early on that flag. It is also what preset scripts use.
- Version branches use `if bpy.app.version[0] >= 5:` — currently pose bone selection in
  `properties.py` and `functions.py` (`pb.select` vs `pb.bone.select`) and fcurve creation
  (`action.fcurve_ensure_for_datablock` vs `action.fcurves.new`).
- Bake samples the evaluated pose per frame, *then* removes the drivers, writes keys only inside the
  bake range, and clears `has_sway` — a baked chain is no longer a Flow chain.

## Gotchas

- **`pb["festivity_flow_x"] = v` does not set the property.** Verified on 5.2: runtime `bpy.props` on
  `PoseBone` live in a system ID-property group, so item assignment silently creates a *separate*
  user custom property while the real setting keeps its old value. Always assign the attribute, with
  `festivity_flow_update = False` around it when the write must not cascade.
- `fps` is baked into the expressions when the drivers are built. Changing the scene frame rate
  afterwards silently redefines Frequency (it becomes cycles per *old* fps frames) until the chain is
  rebuilt.
- Offset is labelled "(frames)" but enters the expression as `off/fps` **radians**, so 24 frames at
  24 fps is 1 radian, not one second. Long-standing behaviour; presets depend on it.
- Pre-1.4 files keep the driver expressions saved in them, so they play back on the old delay math
  while the slider reads the old frame value as a percentage; anything that triggers a rebuild snaps
  them to the new meaning. This is intentional — there is deliberately **no** migration code, users
  keep 1.3.3 for old projects.

## Testing

There is no test suite; verify against a running Blender.

Flow is installed at `C:\Apps\blender\portable\extensions\blender_org\festivity_flow`
(Blender at `C:\Apps\blender\blender.exe`). Copy the repo's `*.py`, `blender_manifest.toml` and
`presets/festivity_flow/*.py` over it, then hot reload without disturbing the MCP addon:

```python
mod = "bl_ext.blender_org.festivity_flow"
bpy.ops.preferences.addon_disable(module=mod)
for n in [n for n in sys.modules if n == mod or n.startswith(mod + ".")]:
    del sys.modules[n]
bpy.ops.preferences.addon_enable(module=mod)
```

Headless: `blender.exe -b file.blend --python script.py`. Do **not** add `--factory-startup --addons`
— `register()` reads `context.preferences.addons[__package__].preferences`, which does not exist
under that flag. Expect noisy unrelated tracebacks from other installed addons; filter the output.

Useful checks when touching the math:

- Sample `sway_target.evaluated_get(depsgraph)["_sw_mo"]` across subframes and locate the rising zero
  crossing per bone; the difference times `rate/fps` is the lag in cycles. Sweep Frequency and Speed
  and confirm it does not move.
- Build a chain, record `rotation_euler` over a frame range, change the code, and diff. Anything
  above ~1e-4 rad is a real behaviour change, not rounding.
- Exercise both driver paths: `add_sway` (`create_sway_chains`) and a `..._delay_opposite` toggle
  (`rebuild_sway_drivers`).
- Do the work on a throwaway armature and delete it afterwards; restore the user's mode, active
  object and selection.
