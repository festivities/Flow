from .functions import get_bone_chains, get_selected_bone_chains, clear_sway_drivers, create_sway_chains, get_preset_data, apply_preset
from bpy.types import Operator
import bpy
import os
import json
from pathlib import Path


#
# OPERATORS
#


class FLOW_OT_add_sway(Operator):
    bl_idname = "flow.add_sway"
    bl_label = "Add Sway Chain"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Adds procedural sine-wave sway animation to selected bone chains using drivers"

    def execute(self, context):
        sim_chains = get_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report(
                {"ERROR"},
                "None of the bones you selected can be used. The bones need a parent to work",
            )
            return {"CANCELLED"}

        create_sway_chains(sim_chains)

        preset_data = get_preset_data()
        if preset_data is not None:
            apply_preset(preset_data, context.active_pose_bone)

        return {"FINISHED"}


class FLOW_OT_remove_sway(Operator):
    bl_idname = "flow.remove_sway"
    bl_label = "Remove Sway Chain"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Removes sway chain drivers and properties from selected bones"

    def execute(self, context):
        sim_chains = get_selected_bone_chains(context.selected_pose_bones)

        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                pb = rig.pose.bones[b_dat[1]]

                clear_sway_drivers(rig, pb)

                pb.flow_has_sway = False
                pb.flow_end_of_chain = False
                pb.flow_chain_id = ""

        return {"FINISHED"}


class FLOW_OT_bake_sway(Operator):
    bl_idname = "flow.bake_sway"
    bl_label = "Bake to Keyframes"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Bake sway driver animation to keyframes on rotation channels"

    sep_action: bpy.props.BoolProperty(
        name="Bake to New Action",
        default=False,
        description="Bake the physics to keyframes in a new action instead of overwriting the existing action",
    )

    def execute(self, context):
        if context.scene.use_preview_range:
            frame_start = context.scene.frame_preview_start
            frame_end = context.scene.frame_preview_end
        else:
            frame_start = context.scene.frame_start
            frame_end = context.scene.frame_end

        sim_chains = get_selected_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report(
                {"ERROR"},
                "Could not find any sway bone chains to bake",
            )
            return {"CANCELLED"}

        # Collect the rotation channel layout for each bone in each rig.
        # {rig: {bone_name: {rotation_mode, data_path, channel_count, frame_values}}}
        rig_driven = {}
        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                bone_name = b_dat[1]
                if rig not in rig_driven:
                    rig_driven[rig] = {}
                if bone_name in rig_driven[rig]:
                    continue

                pb = rig.pose.bones[bone_name]
                if pb.rotation_mode == 'QUATERNION':
                    data_path = 'pose.bones["%s"].rotation_quaternion' % bone_name
                    channel_count = 4
                elif pb.rotation_mode == 'AXIS_ANGLE':
                    data_path = 'pose.bones["%s"].rotation_axis_angle' % bone_name
                    channel_count = 4
                else:
                    data_path = 'pose.bones["%s"].rotation_euler' % bone_name
                    channel_count = 3

                rig_driven[rig][bone_name] = {
                    "rotation_mode": pb.rotation_mode,
                    "data_path": data_path,
                    "channel_count": channel_count,
                    "frame_values": [],
                }

        original_frame = context.scene.frame_current
        for frame in range(frame_start, frame_end + 1):
            context.scene.frame_set(frame)
            depsgraph = context.evaluated_depsgraph_get()
            depsgraph.update()
            for rig, bone_data in rig_driven.items():
                eval_rig = rig.evaluated_get(depsgraph)
                for bone_name, sample_data in bone_data.items():
                    try:
                        pb = eval_rig.pose.bones[bone_name]
                    except KeyError:
                        continue

                    if pb.parent is not None:
                        local_matrix = pb.bone.convert_local_to_pose(
                            pb.matrix,
                            pb.bone.matrix_local,
                            parent_matrix=pb.parent.matrix,
                            parent_matrix_local=pb.parent.bone.matrix_local,
                            invert=True,
                        )
                    else:
                        local_matrix = pb.bone.convert_local_to_pose(
                            pb.matrix,
                            pb.bone.matrix_local,
                            invert=True,
                        )

                    if sample_data["rotation_mode"] == 'QUATERNION':
                        quat = local_matrix.to_quaternion()
                        values = (quat.w, quat.x, quat.y, quat.z)
                    elif sample_data["rotation_mode"] == 'AXIS_ANGLE':
                        quat = local_matrix.to_quaternion()
                        axis, angle = quat.to_axis_angle()
                        values = (angle, axis.x, axis.y, axis.z)
                    else:
                        euler = local_matrix.to_euler(sample_data["rotation_mode"])
                        values = (euler.x, euler.y, euler.z)

                    sample_data["frame_values"].append((frame, values))
        context.scene.frame_set(original_frame)

        # Remove sway drivers to prevent re-evaluation during keyframe insertion
        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                pb = rig.pose.bones[b_dat[1]]
                pb.flow_update = False
                clear_sway_drivers(rig, pb)

        # Insert baked keyframes
        for rig, bone_data in rig_driven.items():
            for bone_name, sample_data in bone_data.items():
                frame_vals = sample_data["frame_values"]
                if len(frame_vals) == 0:
                    continue

                adt = rig.animation_data_create()

                if self.sep_action:
                    action = bpy.data.actions.new(name=rig.name + "_SwayBaked")
                    adt.action = action
                else:
                    if adt.action is None:
                        action = bpy.data.actions.new(name=rig.name + "_Action")
                        adt.action = action
                    else:
                        action = adt.action

                data_path = sample_data["data_path"]

                for axis in range(sample_data["channel_count"]):
                    if bpy.app.version[0] >= 5:
                        fcu = action.fcurve_ensure_for_datablock(rig, data_path, index=axis)
                    else:
                        fcu = action.fcurves.find(data_path, index=axis)
                        if fcu is None:
                            fcu = action.fcurves.new(data_path, index=axis)

                    while len(fcu.keyframe_points) > 0:
                        fcu.keyframe_points.remove(fcu.keyframe_points[0])

                    fcu.keyframe_points.add(len(frame_vals))
                    for i, (frame, values) in enumerate(frame_vals):
                        fcu.keyframe_points[i].co = (frame, values[axis])
                        fcu.keyframe_points[i].interpolation = 'LINEAR'
                
        # Clean up sway properties
        for chain in sim_chains:
            for b_dat in chain:
                pb = b_dat[0].pose.bones[b_dat[1]]
                pb.flow_has_sway = False
                pb.flow_end_of_chain = False
                pb.flow_chain_id = ""
                pb.flow_update = True

        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=800)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "sep_action")


class FLOW_OT_save_preset(Operator):
    bl_idname = "flow.save_preset"
    bl_label = "Save Preset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Saves current bone settings as a new preset"

    name: bpy.props.StringProperty(
        name="Preset Name",
        description="Name of the preset",
        default="",
    )

    description: bpy.props.StringProperty(
        name="Preset Description",
        description="Description of the preset",
        default="",
    )

    chain_preset: bpy.props.BoolProperty(
        name="Chain Preset",
        description="This preset will save the value profile of the whole chain for the bone settings",
        default=True,
    )

    def execute(self, context):

        if self.name == "":
            self.report(
                {"ERROR"},
                "You need to add a preset name to save the preset",
            )
            return {"CANCELLED"}

        pb = context.active_pose_bone
        p_dat = {}
        p_dat["Name"] = self.name
        p_dat["Description"] = self.description
        s_dat = {}

        user_preset_fp = Path(os.path.dirname(__file__)) / "user_created_presets"
        if os.path.exists(user_preset_fp) == False:
            os.makedirs(bpy.path.abspath(str(user_preset_fp)))

        sim_chains = get_selected_bone_chains(context.selected_pose_bones_from_active_object, only_active=True)
        for chain in sim_chains:

            s_dat["flow_sw_amplitude"] = pb.flow_sw_amplitude
            s_dat["flow_sw_frequency"] = pb.flow_sw_frequency
            s_dat["flow_sw_delay"] = pb.flow_sw_delay
            s_dat["flow_sw_offset"] = pb.flow_sw_offset
            s_dat["flow_sw_falloff_start"] = pb.flow_sw_falloff_start
            s_dat["flow_sw_speed"] = pb.flow_sw_speed
            s_dat["flow_sw_random_seed"] = pb.flow_sw_random_seed
            s_dat["flow_sw_roll"] = pb.flow_sw_roll

            s_dat["flow_sw_sub_amplitude"] = pb.flow_sw_sub_amplitude
            s_dat["flow_sw_sub_frequency"] = pb.flow_sw_sub_frequency
            s_dat["flow_sw_sub_delay"] = pb.flow_sw_sub_delay
            s_dat["flow_sw_sub_offset"] = pb.flow_sw_sub_offset
            s_dat["flow_sw_sub_falloff_start"] = pb.flow_sw_sub_falloff_start

            preset_fp = Path(os.path.dirname(__file__)) / "user_created_presets" / "sway_chain_presets.json"

            p_dat["Settings"] = s_dat

            presets_data = {}
            if os.path.exists(preset_fp):
                presets_data = json.load(open(str(preset_fp)))

            presets_data[self.name.replace(" ", "").upper()] = p_dat

            preset_file = open(preset_fp, "w")

            json.dump(presets_data, preset_file, indent=1, ensure_ascii=True)

            preset_file.close()

        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=800)

    def draw(self, context):
        layout = self.layout

        row = layout.row()
        row.prop(self, "name")

        row = layout.row()
        row.prop(self, "description")

        row = layout.row()
        row.prop(self, "chain_preset")


class FLOW_OT_delete_preset(Operator):
    bl_idname = "flow.delete_preset"
    bl_label = "Delete Preset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Deletes the active preset"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences

        preset_fp = Path(os.path.dirname(__file__)) / "user_created_presets" / "sway_chain_presets.json"
        presets_enum = prefs.sw_presets

        presets_data = {}
        if os.path.exists(preset_fp):
            presets_data = json.load(open(str(preset_fp)))

            if presets_enum.replace(" ", "").upper() in presets_data.keys():
                del presets_data[presets_enum.replace(" ", "").upper()]

            preset_file = open(preset_fp, "w")

            json.dump(presets_data, preset_file, indent=1, ensure_ascii=True)

            preset_file.close()

            presets_enum = 0

        return {"FINISHED"}

    def invoke(self, context, event):
        prefs = context.preferences.addons[__package__].preferences
        presets_enum = prefs.sw_presets

        if presets_enum in ["DEFAULTSWAY",
                            "GENTLEBREEZE",
                            "HEAVYWIND",
                            "PONYTAIL"]:
            self.report(
                {"ERROR"},
                "Cannot delete the base presets",
            )
            return {"CANCELLED"}

        return context.window_manager.invoke_props_dialog(self, width=400, confirm_text="Delete Preset? Cannot be recovered")


class FLOW_OT_apply_preset(Operator):
    bl_idname = "flow.apply_preset"
    bl_label = "Apply Preset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Applies the active preset to the selected bone chains"

    def execute(self, context):
        pb = context.active_pose_bone

        preset_data = get_preset_data()
        if preset_data is None:
            self.report(
                {"ERROR"},
                "Active Pose Bone has no sway physics",
            )
            return {"CANCELLED"}

        apply_preset(preset_data, pb)

        return {"FINISHED"}


#
# REGISTRATION
#


_classes = [
    FLOW_OT_add_sway,
    FLOW_OT_remove_sway,
    FLOW_OT_bake_sway,
    FLOW_OT_save_preset,
    FLOW_OT_delete_preset,
    FLOW_OT_apply_preset,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()


def unregister():
    _unregister()
