import bpy
import math
import os
import json
import random
from pathlib import Path


#
# BONE CHAIN DETECTION
#


def get_bone_chains(bones):

    valid_bones, dep_bones = [], []
    for pb in bones:
        if pb.parent is None:
            continue

        children = []
        for cpb in pb.children:
            if bpy.app.version[0] >= 5:
                child_sel = cpb.select
            else:
                child_sel = cpb.bone.select

            if child_sel:
                children.append(cpb)

        valid_bones.append(pb)
        dep_bones.append(children)

    for ob in bpy.context.selected_objects:
        if ob.type == "ARMATURE":
            for pb in ob.pose.bones:

                for con in pb.constraints:

                    if con.type in ["COPY_TRANSFORMS", "COPY_ROTATION", "COPY_LOCATION"]:
                        if con.target is None or con.target.type != "ARMATURE" or con.subtarget == "":
                            continue

                        tar = con.target.pose.bones[con.subtarget]
                        if tar in valid_bones:
                            for cpb in pb.children:

                                if bpy.app.version[0] >= 5:
                                    child_sel = cpb.select
                                else:
                                    child_sel = cpb.bone.select

                                if child_sel:
                                    dep_bones[valid_bones.index(tar)].append(cpb)

    chain_roots, is_dep = [], []
    for d in dep_bones:
        if len(d) == 1:
            is_dep += d
        else:
            for dpb in d:
                if dpb not in chain_roots:
                    chain_roots.append(dpb)

    for p, pb in enumerate(valid_bones):
        if pb not in is_dep and pb not in chain_roots:
            chain_roots.append(pb)

    chain_parts = []
    for pb in valid_bones:
        if pb not in chain_roots:
            chain_parts.append(pb)

    chains = []
    for pb in chain_roots:
        chain = [[pb.id_data, pb.name]]

        for i in range(len(chain_parts)):
            deps = dep_bones[valid_bones.index(pb)]

            if len(deps) == 1:
                if deps[0] in chain_roots:
                    break
                pb = deps[0]
                chain.append([pb.id_data, pb.name])
            else:
                break
        chains.append(chain[::-1])

    return chains


def get_selected_bone_chains(bones, only_active=False):
    chains, skip_bones = [], []
    for pb in bones:
        if pb.flow_has_sway and pb.name not in skip_bones:
            if only_active and bpy.context.active_pose_bone.flow_chain_id != pb.flow_chain_id:
                continue

            chain = [[pb.id_data, pb.name]]

            for par in pb.parent_recursive:
                if par.flow_has_sway and par.flow_chain_id == pb.flow_chain_id:
                    chain.insert(0, [par.id_data, par.name])
                    if par.flow_end_of_chain:
                        break
                else:
                    break

            searching = True
            search_pb = pb
            while searching:
                search_len = len(chain)
                for child in search_pb.children:
                    if child.flow_has_sway and child.flow_chain_id == pb.flow_chain_id:
                        if child.flow_end_of_chain == False:
                            chain.append([child.id_data, child.name])
                            search_pb = child
                            break
                    else:
                        break
                searching = len(chain) != search_len

            skip_bones += [c[1] for c in chain]
            chains.append(chain)
            continue

    return chains

def get_root_from_sway_bone(pb):
    chain = get_selected_bone_chains([pb])
    root = None
    if chain:
        rig, bone_name = chain[0][0]
        root = rig.pose.bones[bone_name]

    return root

#
# SWAY DRIVER FUNCTIONS
#


def _get_sway_target_name(rig, pb):
    return f"FLOW_SwayTarget_{rig.name}_{pb.name}"


def _get_sway_constraint_name():
    return "FLOW_Sway"


def _ensure_sway_target(rig, pb):
    target_name = _get_sway_target_name(rig, pb)
    sway_target = bpy.data.objects.get(target_name)

    if sway_target is None:
        sway_target = bpy.data.objects.new(target_name, None)
        sway_target.empty_display_type = "ARROWS"
        sway_target.empty_display_size = 0.25
        sway_target.hide_render = True
        sway_target.hide_viewport = True

        if len(rig.users_collection) > 0:
            rig.users_collection[0].objects.link(sway_target)
        else:
            bpy.context.scene.collection.objects.link(sway_target)

    if sway_target.parent != rig:
        sway_target.parent = rig
        sway_target.matrix_parent_inverse = rig.matrix_world.inverted()

    sway_target.matrix_world = rig.matrix_world @ pb.bone.matrix_local
    sway_target.rotation_mode = 'XYZ'
    sway_target.rotation_euler = (0, 0, 0)

    return sway_target


def _ensure_sway_constraint(pb, sway_target):
    con = pb.constraints.get(_get_sway_constraint_name())
    if con is None:
        con = pb.constraints.new("COPY_ROTATION")
        con.name = _get_sway_constraint_name()

    con.target = sway_target
    con.subtarget = ""
    con.use_x = True
    con.use_y = True
    con.use_z = True
    con.mix_mode = "ADD"
    con.owner_space = "LOCAL_WITH_PARENT"
    con.target_space = "LOCAL"
    con.influence = 1.0

    return con


def clear_sway_drivers(rig, pb):
    """Remove sway chain drivers and helper constraints from a pose bone."""
    bone_path = pb.path_from_id()
    if rig.animation_data:
        remove_list = []
        for drv in rig.animation_data.drivers:
            if drv.data_path.startswith(bone_path) and "rotation_euler" in drv.data_path:
                has_marker = False
                for var in drv.driver.variables:
                    if var.name == "sw":
                        has_marker = True
                        break
                if has_marker:
                    remove_list.append(drv)

        for drv in remove_list:
            rig.animation_data.drivers.remove(drv)

    sway_con = pb.constraints.get(_get_sway_constraint_name())
    if sway_con is not None:
        pb.constraints.remove(sway_con)

    sway_target = bpy.data.objects.get(_get_sway_target_name(rig, pb))
    if sway_target is not None:
        bpy.data.objects.remove(sway_target, do_unlink=True)


def _add_sway_driver(rig, pb, sway_target, axis_index, bone_index, total_bones, is_sub=False):
    """Add a single sway driver to the hidden helper target."""
    fc = sway_target.driver_add("rotation_euler", axis_index)
    drv = fc.driver
    drv.type = 'SCRIPTED'

    chain_root = pb
    for par in pb.parent_recursive:
        if par.flow_has_sway and par.flow_chain_id == pb.flow_chain_id:
            chain_root = par
            if par.flow_end_of_chain:
                break
        else:
            break

    root_path = chain_root.path_from_id()

    var_marker = drv.variables.new()
    var_marker.name = "sw"
    var_marker.type = 'SINGLE_PROP'
    var_marker.targets[0].id_type = 'OBJECT'
    var_marker.targets[0].id = rig
    var_marker.targets[0].data_path = root_path + '.flow_has_sway'

    var_amp = drv.variables.new()
    var_amp.name = "amp"
    var_amp.type = 'SINGLE_PROP'
    var_amp.targets[0].id_type = 'OBJECT'
    var_amp.targets[0].id = rig
    var_amp.targets[0].data_path = root_path + '.flow_sw_amplitude'

    var_frq = drv.variables.new()
    var_frq.name = "frq"
    var_frq.type = 'SINGLE_PROP'
    var_frq.targets[0].id_type = 'OBJECT'
    var_frq.targets[0].id = rig
    var_frq.targets[0].data_path = root_path + '.flow_sw_frequency'

    var_dly = drv.variables.new()
    var_dly.name = "dly"
    var_dly.type = 'SINGLE_PROP'
    var_dly.targets[0].id_type = 'OBJECT'
    var_dly.targets[0].id = rig
    var_dly.targets[0].data_path = root_path + '.flow_sw_delay'

    var_off = drv.variables.new()
    var_off.name = "off"
    var_off.type = 'SINGLE_PROP'
    var_off.targets[0].id_type = 'OBJECT'
    var_off.targets[0].id = rig
    var_off.targets[0].data_path = root_path + '.flow_sw_offset'

    var_fo = drv.variables.new()
    var_fo.name = "fo"
    var_fo.type = 'SINGLE_PROP'
    var_fo.targets[0].id_type = 'OBJECT'
    var_fo.targets[0].id = rig
    var_fo.targets[0].data_path = root_path + '.flow_sw_falloff_start'

    var_amp2 = drv.variables.new()
    var_amp2.name = "a2"
    var_amp2.type = 'SINGLE_PROP'
    var_amp2.targets[0].id_type = 'OBJECT'
    var_amp2.targets[0].id = rig
    var_amp2.targets[0].data_path = root_path + '.flow_sw_sub_amplitude'

    var_frq2 = drv.variables.new()
    var_frq2.name = "f2"
    var_frq2.type = 'SINGLE_PROP'
    var_frq2.targets[0].id_type = 'OBJECT'
    var_frq2.targets[0].id = rig
    var_frq2.targets[0].data_path = root_path + '.flow_sw_sub_frequency'

    var_dly2 = drv.variables.new()
    var_dly2.name = "d2"
    var_dly2.type = 'SINGLE_PROP'
    var_dly2.targets[0].id_type = 'OBJECT'
    var_dly2.targets[0].id = rig
    var_dly2.targets[0].data_path = root_path + '.flow_sw_sub_delay'

    var_off2 = drv.variables.new()
    var_off2.name = "o2"
    var_off2.type = 'SINGLE_PROP'
    var_off2.targets[0].id_type = 'OBJECT'
    var_off2.targets[0].id = rig
    var_off2.targets[0].data_path = root_path + '.flow_sw_sub_offset'

    var_fo2 = drv.variables.new()
    var_fo2.name = "g2"
    var_fo2.type = 'SINGLE_PROP'
    var_fo2.targets[0].id_type = 'OBJECT'
    var_fo2.targets[0].id = rig
    var_fo2.targets[0].data_path = root_path + '.flow_sw_sub_falloff_start'

    var_sp = drv.variables.new()
    var_sp.name = "sp"
    var_sp.type = 'SINGLE_PROP'
    var_sp.targets[0].id_type = 'OBJECT'
    var_sp.targets[0].id = rig
    var_sp.targets[0].data_path = root_path + '.flow_sw_speed'

    var_rs = drv.variables.new()
    var_rs.name = "rs"
    var_rs.type = 'SINGLE_PROP'
    var_rs.targets[0].id_type = 'OBJECT'
    var_rs.targets[0].id = rig
    var_rs.targets[0].data_path = root_path + '.flow_sw_random_seed'

    var_rl = drv.variables.new()
    var_rl.name = "rl"
    var_rl.type = 'SINGLE_PROP'
    var_rl.targets[0].id_type = 'OBJECT'
    var_rl.targets[0].id = rig
    var_rl.targets[0].data_path = pb.path_from_id() + '.flow_sw_roll'

    fps = bpy.context.scene.render.fps

    bi = bone_index
    tb = max(total_bones - 1, 1)
    f1 = round(bi / tb, 4)
    f2_const = round(bi / (total_bones * 2), 4)

    xw = f"radians(amp)*(fo+(1-fo)*{f1})*sin(2*pi*frq*sp*(frame+dly*{f2_const}+rs*{fps})/{fps}+off/{fps})"
    zw = f"radians(a2)*(g2+(1-g2)*{f1})*sin(2*pi*f2*sp*(frame+d2*{f2_const}+rs*{fps})/{fps}+o2/{fps})"

    if is_sub:
        expr = f"{xw}*sin(radians(rl))+{zw}*cos(radians(rl))"
    else:
        expr = f"{xw}*cos(radians(rl))-{zw}*sin(radians(rl))"

    drv.expression = expr

    for mod in fc.modifiers:
        fc.modifiers.remove(mod)

    while len(fc.keyframe_points) > 0:
        fc.keyframe_points.remove(fc.keyframe_points[0])

    return fc


def create_sway_chains(chains):
    """Create sway chain physics for the given bone chains."""
    prefs = bpy.context.preferences.addons[__package__].preferences

    for c, chain in enumerate(chains):
        next_num = c
        for ob in bpy.context.view_layer.objects:
            if ob.type == "ARMATURE":
                for pb in ob.pose.bones:
                    if pb.flow_has_sway and pb.flow_chain_id:
                        try:
                            cur_num = int(pb.flow_chain_id)
                            if next_num < cur_num:
                                next_num = cur_num
                        except:
                            pass

        num = "%02d" % (next_num + 1)
        total_bones = len(chain)

        for cc, c_dat in enumerate(chain[::-1]):
            rig = c_dat[0]
            bone = rig.pose.bones[c_dat[1]]

            clear_sway_drivers(rig, bone)
            sway_target = _ensure_sway_target(rig, bone)

            bone.flow_has_sway = True
            bone.flow_chain_id = num
            bone.flow_end_of_chain = cc == 0

            _ensure_sway_constraint(bone, sway_target)

        root_bone = chain[-1][0].pose.bones[chain[-1][1]]

        if root_bone.flow_sw_random_seed == 0.0:
            root_bone["flow_sw_random_seed"] = random.uniform(-2.0, 2.0)

        for cc, c_dat in enumerate(chain[::-1]):
            rig = c_dat[0]
            bone = rig.pose.bones[c_dat[1]]
            sway_target = bpy.data.objects.get(_get_sway_target_name(rig, bone))

            if sway_target is None:
                sway_target = _ensure_sway_target(rig, bone)

            bone_index = cc

            _add_sway_driver(rig, bone, sway_target, 0, bone_index, total_bones, is_sub=False)

            _add_sway_driver(rig, bone, sway_target, 2, bone_index, total_bones, is_sub=True)

    return


def rebuild_sway_drivers(bone):
    """Rebuild all sway drivers for the chain containing the given bone."""
    if not bone.flow_has_sway:
        return

    rig = bone.id_data
    chain_id = bone.flow_chain_id

    chain_bones = []
    for pb in rig.pose.bones:
        if pb.flow_has_sway and pb.flow_chain_id == chain_id:
            chain_bones.append(pb)

    if len(chain_bones) == 0:
        return

    root_bone = None
    for pb in chain_bones:
        if pb.flow_end_of_chain:
            root_bone = pb
            break

    if root_bone is None:
        root_bone = chain_bones[0]

    ordered = [root_bone]
    current = root_bone
    for _ in range(len(chain_bones)):
        found = False
        for child in current.children:
            if child in chain_bones and child not in ordered:
                ordered.append(child)
                current = child
                found = True
                break
        if not found:
            break

    total_bones = len(ordered)

    for cc, pb in enumerate(ordered):
        clear_sway_drivers(rig, pb)
        sway_target = _ensure_sway_target(rig, pb)
        _ensure_sway_constraint(pb, sway_target)
        _add_sway_driver(rig, pb, sway_target, 0, cc, total_bones, is_sub=False)
        _add_sway_driver(rig, pb, sway_target, 2, cc, total_bones, is_sub=True)

    return


def bone_has_custom_sway_settings(pb):
    """Return True when a pose bone has sway settings that differ from the defaults."""
    sway_props = (
        "flow_sw_amplitude",
        "flow_sw_frequency",
        "flow_sw_delay",
        "flow_sw_offset",
        "flow_sw_falloff_start",
        "flow_sw_speed",
        "flow_sw_random_seed",
        "flow_sw_roll",
        "flow_sw_sub_amplitude",
        "flow_sw_sub_frequency",
        "flow_sw_sub_delay",
        "flow_sw_sub_offset",
        "flow_sw_sub_falloff_start",
    )

    for prop_name in sway_props:
        prop = pb.bl_rna.properties[prop_name]
        current_value = getattr(pb, prop_name)
        default_value = prop.default

        if isinstance(current_value, float):
            if not math.isclose(current_value, default_value, rel_tol=1e-06, abs_tol=1e-06):
                return True
        else:
            if current_value != default_value:
                return True

    return False


#
# PRESET FUNCTIONS
#


def load_presets(preset_fp):

    presets_data = None
    if os.path.exists(preset_fp):
        presets_data = json.load(open(str(preset_fp)))

    items = []
    if presets_data is not None:
        for k in presets_data.keys():
            items.append(
                (
                    k,
                    presets_data[k]["Name"],
                    presets_data[k]["Description"],
                )
            )

    return sorted(items)


def get_preset_data(preset_override=None):
    prefs = bpy.context.preferences.addons[__package__].preferences

    preset_fp = Path(os.path.dirname(__file__)) / "presets" / "default_presets.json"
    user_preset_fp = Path(os.path.dirname(__file__)) / "presets" / "user_presets.json"
    presets_enum = prefs.sw_presets

    pb = bpy.context.active_pose_bone
    bone_has_settings = "flow_sw_amplitude" in pb

    if preset_override is not None:
        presets_enum = preset_override

    user_presets_data = {}
    if os.path.exists(user_preset_fp):
        user_presets_data = json.load(open(str(user_preset_fp)))

    base_presets_data = {}
    if os.path.exists(preset_fp):
        base_presets_data = json.load(open(str(preset_fp)))

    presets_data = base_presets_data | user_presets_data

    if presets_enum is not None and presets_enum.replace(" ", "").upper() in presets_data.keys():
        p_data = presets_data[presets_enum.replace(" ", "").upper()]["Settings"]

        if prefs.keep_existing_settings and bone_has_settings:
            for k in p_data.keys():
                if k in pb:
                    p_data[k] = pb[k]

        return p_data

    return None


def apply_preset(preset_data, bone, sim_chains=None, keep_existing_settings=None):

    prefs = bpy.context.preferences.addons[__package__].preferences

    if keep_existing_settings is None:
        keep_existing_settings = prefs.keep_existing_settings

    if sim_chains is None:
        if prefs.apply_to_all_chains:
            sim_chains = get_selected_bone_chains(bpy.context.selected_pose_bones)
        else:
            sim_chains = get_selected_bone_chains(bpy.context.selected_pose_bones_from_active_object, only_active=True)

    for s in preset_data.keys():

        if keep_existing_settings and s in bone:
            continue

        if isinstance(preset_data[s], list) == False:

            if hasattr(bone, s):
                setattr(bone, s, preset_data[s])

        else:

            vals = [float(v) for v in preset_data[s]]

            for chain in sim_chains:
                chain_len = len(chain)
                for b, b_dat in enumerate(chain):
                    bo = b_dat[0].pose.bones[b_dat[1]]

                    if chain_len > 1:
                        t = b / (chain_len - 1)
                    else:
                        t = 0.0

                    src_idx = t * (len(vals) - 1)
                    lo = int(src_idx)
                    hi = min(lo + 1, len(vals) - 1)
                    frac = src_idx - lo
                    val = vals[lo] + (vals[hi] - vals[lo]) * frac

                    if hasattr(bo, s):
                        bo.flow_update = False
                        setattr(bo, s, val)
                        bo.flow_update = True

    return
