import bpy
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


#
# SWAY DRIVER FUNCTIONS
#


def clear_sway_drivers(rig, pb):
    """Remove sway chain drivers from a pose bone's rotation channels."""
    bone_path = pb.path_from_id()
    if rig.animation_data:
        remove_list = []
        for drv in rig.animation_data.drivers:
            if drv.data_path.startswith(bone_path) and "rotation_euler" in drv.data_path:
                has_marker = False
                for var in drv.driver.variables:
                    if var.name == "flow_sway_marker":
                        has_marker = True
                        break
                if has_marker:
                    remove_list.append(drv)

        for drv in remove_list:
            rig.animation_data.drivers.remove(drv)


def _add_sway_driver(rig, pb, axis_index, bone_index, total_bones, is_sub=False):
    """Add a single sway driver to a bone's rotation channel."""
    bone_path = pb.path_from_id()
    data_path = bone_path + ".rotation_euler"

    pb.rotation_mode = 'XYZ'

    fc = rig.driver_add(data_path, axis_index)
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
    var_marker.name = "flow_sway_marker"
    var_marker.type = 'SINGLE_PROP'
    var_marker.targets[0].id_type = 'OBJECT'
    var_marker.targets[0].id = rig
    var_marker.targets[0].data_path = root_path + '.flow_has_sway'

    prefix = "sub_" if is_sub else ""
    prop_prefix = "flow_sw_sub_" if is_sub else "flow_sw_"

    var_amp = drv.variables.new()
    var_amp.name = prefix + "amp"
    var_amp.type = 'SINGLE_PROP'
    var_amp.targets[0].id_type = 'OBJECT'
    var_amp.targets[0].id = rig
    var_amp.targets[0].data_path = root_path + '.' + prop_prefix + 'amplitude'

    var_freq = drv.variables.new()
    var_freq.name = prefix + "freq"
    var_freq.type = 'SINGLE_PROP'
    var_freq.targets[0].id_type = 'OBJECT'
    var_freq.targets[0].id = rig
    var_freq.targets[0].data_path = root_path + '.' + prop_prefix + 'frequency'

    var_delay = drv.variables.new()
    var_delay.name = prefix + "delay"
    var_delay.type = 'SINGLE_PROP'
    var_delay.targets[0].id_type = 'OBJECT'
    var_delay.targets[0].id = rig
    var_delay.targets[0].data_path = root_path + '.' + prop_prefix + 'delay'

    var_offset = drv.variables.new()
    var_offset.name = prefix + "offset"
    var_offset.type = 'SINGLE_PROP'
    var_offset.targets[0].id_type = 'OBJECT'
    var_offset.targets[0].id = rig
    var_offset.targets[0].data_path = root_path + '.' + prop_prefix + 'offset'

    var_fo = drv.variables.new()
    var_fo.name = prefix + "fo_start"
    var_fo.type = 'SINGLE_PROP'
    var_fo.targets[0].id_type = 'OBJECT'
    var_fo.targets[0].id = rig
    var_fo.targets[0].data_path = root_path + '.' + prop_prefix + 'falloff_start'

    var_speed = drv.variables.new()
    var_speed.name = "speed"
    var_speed.type = 'SINGLE_PROP'
    var_speed.targets[0].id_type = 'OBJECT'
    var_speed.targets[0].id = rig
    var_speed.targets[0].data_path = root_path + '.flow_sw_speed'

    var_seed = drv.variables.new()
    var_seed.name = "rseed"
    var_seed.type = 'SINGLE_PROP'
    var_seed.targets[0].id_type = 'OBJECT'
    var_seed.targets[0].id = rig
    var_seed.targets[0].data_path = root_path + '.flow_sw_random_seed'

    fps_val = bpy.context.scene.render.fps

    bi = bone_index
    tb = max(total_bones - 1, 1)
    tb2 = total_bones * 2

    expr = (
        "("
        f"radians({prefix}amp) "
        f"* ({prefix}fo_start + (1.0 - {prefix}fo_start) * ({bi} / {tb})) "
        f"* sin(6.283185 * {prefix}freq * speed * (frame + {prefix}delay * ({bi} / {tb2}) + rseed * {fps_val}) / {fps_val} + {prefix}offset / {fps_val}) "
        ")"
    )

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

            bone.flow_has_sway = True
            bone.flow_chain_id = num
            bone.flow_end_of_chain = cc == 0
            bone.rotation_mode = 'XYZ'

        root_bone = chain[-1][0].pose.bones[chain[-1][1]]

        if root_bone.flow_sw_random_seed == 0.0:
            root_bone["flow_sw_random_seed"] = random.uniform(-2.0, 2.0)

        for cc, c_dat in enumerate(chain[::-1]):
            rig = c_dat[0]
            bone = rig.pose.bones[c_dat[1]]

            bone_index = cc

            _add_sway_driver(rig, bone, 0, bone_index, total_bones, is_sub=False)

            _add_sway_driver(rig, bone, 2, bone_index, total_bones, is_sub=True)

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
        _add_sway_driver(rig, pb, 0, cc, total_bones, is_sub=False)
        _add_sway_driver(rig, pb, 2, cc, total_bones, is_sub=True)

    return


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

    preset_fp = Path(os.path.dirname(__file__)) / "presets" / "sway_chain_presets.json"
    user_preset_fp = Path(os.path.dirname(__file__)) / "user_created_presets" / "sway_chain_presets.json"
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


def apply_preset(preset_data, bone):

    prefs = bpy.context.preferences.addons[__package__].preferences

    if prefs.apply_to_all_chains:
        sim_chains = get_selected_bone_chains(bpy.context.selected_pose_bones)
    else:
        sim_chains = get_selected_bone_chains(bpy.context.selected_pose_bones_from_active_object, only_active=True)

    for s in preset_data.keys():

        if prefs.keep_existing_settings and s in bone:
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
