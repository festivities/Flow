from .functions import get_bone_chains, get_selected_bone_chains, clear_sway_drivers, create_sway_chains
from bl_operators.presets import AddPresetBase
from bpy.types import Operator, Menu
import bpy
import os
import shutil
from os.path import basename


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


class FLOW_MT_presets(Menu):
    bl_label = "Presets"

    def draw(self, context):
        layout = self.layout

        addon_presets_dir = os.path.join(os.path.dirname(__file__), "presets")
        if os.path.isdir(addon_presets_dir):
            for fname in sorted(os.listdir(addon_presets_dir)):
                if fname.endswith('.py'):
                    name = bpy.path.display_name(fname)
                    op = layout.operator("flow.execute_preset", text=name)
                    op.filepath = os.path.join(addon_presets_dir, fname)

        user_presets_dir = os.path.join(bpy.utils.user_resource('SCRIPTS'), "presets", "flow")
        if os.path.isdir(user_presets_dir):
            user_files = sorted(f for f in os.listdir(user_presets_dir) if f.endswith('.py'))
            if user_files:
                layout.separator()
                for fname in user_files:
                    name = bpy.path.display_name(fname)
                    op = layout.operator("flow.execute_preset", text=name)
                    op.filepath = os.path.join(user_presets_dir, fname)


class FLOW_OT_execute_preset(Operator):
    bl_idname = "flow.execute_preset"
    bl_label = "Execute Preset"
    bl_description = "Apply the selected preset to the active sway chain"

    filepath: bpy.props.StringProperty(subtype='FILE_PATH')
    menu_idname: bpy.props.StringProperty(name="Menu ID Name", default="FLOW_MT_presets")

    def execute(self, context):
        from os.path import basename
        preset_class = getattr(bpy.types, self.menu_idname)
        preset_class.bl_label = bpy.path.display_name(basename(self.filepath))

        try:
            exec(compile(open(self.filepath).read(), self.filepath, 'exec'))
        except Exception as ex:
            self.report({'ERROR'}, "Failed to execute preset: " + str(ex))
            return {'CANCELLED'}

        return {'FINISHED'}


class FLOW_OT_add_preset(AddPresetBase, Operator):
    bl_idname = "flow.add_preset"
    bl_label = "Save Preset"
    preset_menu = "FLOW_MT_presets"
    preset_subdir = "flow"

    preset_defines = [
        "obj = bpy.context.active_pose_bone",
    ]

    preset_values = [
        "obj.flow_sw_amplitude",
        "obj.flow_sw_frequency",
        "obj.flow_sw_delay",
        "obj.flow_sw_offset",
        "obj.flow_sw_falloff_start",
        "obj.flow_sw_speed",
        "obj.flow_sw_sub_amplitude",
        "obj.flow_sw_sub_frequency",
        "obj.flow_sw_sub_delay",
        "obj.flow_sw_sub_falloff_start",
    ]

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'ARMATURE'
                and context.mode == 'POSE'
                and context.active_pose_bone is not None
                and context.active_pose_bone.flow_has_sway)


class FLOW_OT_remove_preset(AddPresetBase, Operator):
    bl_idname = "flow.remove_preset"
    bl_label = "Delete Preset"
    preset_menu = "FLOW_MT_presets"
    preset_subdir = "flow"

    preset_defines = FLOW_OT_add_preset.preset_defines
    preset_values = FLOW_OT_add_preset.preset_values

    def execute(self, context):
        self.remove_active = True
        return super().execute(context)

    @classmethod
    def poll(cls, context):
        return (context.active_object is not None
                and context.active_object.type == 'ARMATURE'
                and context.mode == 'POSE'
                and context.active_pose_bone is not None)


class FLOW_OT_batch_offset(Operator):
    bl_idname = "flow.batch_offset"
    bl_label = "Batch Offset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Apply an incremental offset to all selected sway chains"

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('MAIN', "Main Axis", "Apply offset to main axis wave"),
            ('SUB', "Sub Axis", "Apply offset to sub axis wave"),
        ],
        default='MAIN',
    )

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        increment = prefs.flow_batch_offset_increment

        chains, bones = [], []
        for pb in context.selected_pose_bones:
            if not pb.flow_has_sway:
                continue
            if pb.flow_chain_id not in chains:
                chains.append(pb.flow_chain_id)
                bones.append(pb)

        if len(chains) == 0:
            self.report({"ERROR"}, "No sway chains selected")
            return {"CANCELLED"}

        paired = sorted(zip(chains, bones), key=lambda x: x[0])
        chains, bones = zip(*paired)

        attr = "flow_sw_sub_offset" if self.mode == 'SUB' else "flow_sw_offset"

        skip_rigs = []
        for i, pb in enumerate(bones):
            if pb.id_data in skip_rigs:
                continue
            skip_rigs.append(pb.id_data)

            for c_pb in pb.id_data.pose.bones:
                if c_pb.flow_chain_id in chains and c_pb.flow_has_sway:
                    try:
                        chain_idx = chains.index(c_pb.flow_chain_id)
                    except ValueError:
                        continue
                    c_pb.flow_update = False
                    setattr(c_pb, attr, chain_idx * increment)
                    c_pb.flow_update = True

        return {"FINISHED"}


class FLOW_OT_adjust_offset(Operator):
    bl_idname = "flow.adjust_offset"
    bl_label = "Adjust Offset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Add, subtract, or set the offset of selected sway chains"

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('ADD', "Add", "Add value to current offset"),
            ('SUBTRACT', "Subtract", "Subtract value from current offset"),
            ('SET', "Set", "Set offset to the given value"),
        ],
        default='ADD',
    )

    target: bpy.props.EnumProperty(
        name="Target",
        items=[
            ('MAIN', "Main Axis", "Apply to main axis offset"),
            ('SUB', "Sub Axis", "Apply to sub axis offset"),
        ],
        default='MAIN',
    )

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        adjust_value = prefs.flow_offset_adjust_value

        attr = "flow_sw_sub_offset" if self.target == 'SUB' else "flow_sw_offset"

        sim_chains = get_selected_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report({"ERROR"}, "No sway chains selected")
            return {"CANCELLED"}

        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                pb = rig.pose.bones[b_dat[1]]

                current = getattr(pb, attr)

                if self.mode == 'ADD':
                    new_val = current + adjust_value
                elif self.mode == 'SUBTRACT':
                    new_val = current - adjust_value
                else:
                    new_val = adjust_value

                pb.flow_update = False
                setattr(pb, attr, new_val)
                pb.flow_update = True

        return {"FINISHED"}


#
# REGISTRATION
#


_classes = [
    FLOW_OT_add_sway,
    FLOW_OT_remove_sway,
    FLOW_OT_bake_sway,
    FLOW_MT_presets,
    FLOW_OT_execute_preset,
    FLOW_OT_add_preset,
    FLOW_OT_remove_preset,
    FLOW_OT_batch_offset,
    FLOW_OT_adjust_offset,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()


def unregister():
    _unregister()
