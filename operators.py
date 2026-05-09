from .functions import get_bone_chains, get_selected_bone_chains, clear_sway_drivers, create_sway_chains, bone_has_custom_sway_settings
from bpy.types import Operator, Menu
from bl_operators.presets import AddPresetBase
import bpy
import os


#
# OPERATORS
#


class FESTIVITY_FLOW_OT_add_sway(Operator):
    bl_idname = "festivity_flow.add_sway"
    bl_label = "Add Sway Chain"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Adds procedural sine-wave sway animation to selected bone chains using drivers"

    def execute(self, context):
        prefs = context.preferences.addons[__package__].preferences
        sim_chains = get_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report(
                {"ERROR"},
                "None of the bones you selected can be used. The bones need a parent to work",
            )
            return {"CANCELLED"}

        preset_chains = []
        for chain in sim_chains:
            chain_has_history = False
            for rig, bone_name in chain:
                if bone_has_custom_sway_settings(rig.pose.bones[bone_name]):
                    chain_has_history = True
                    break

            if prefs.keep_existing_settings:
                if chain_has_history == False:
                    preset_chains.append(chain)
            else:
                preset_chains.append(chain)

        create_sway_chains(sim_chains)

        if len(preset_chains) > 0:
            py_files = []
            for preset_dir in bpy.utils.preset_paths("festivity_flow"):
                if os.path.isdir(preset_dir):
                    for f in os.listdir(preset_dir):
                        if f.endswith(".py"):
                            fp = os.path.join(preset_dir, f)
                            py_files.append((os.path.getmtime(fp), fp))
            if py_files:
                py_files.sort(reverse=True)
                bpy.ops.script.execute_preset(
                    filepath=py_files[0][1],
                    menu_idname="FESTIVITY_FLOW_MT_presets",
                )

        return {"FINISHED"}


class FESTIVITY_FLOW_OT_remove_sway(Operator):
    bl_idname = "festivity_flow.remove_sway"
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

                pb.festivity_flow_has_sway = False
                pb.festivity_flow_end_of_chain = False
                pb.festivity_flow_chain_id = ""

        return {"FINISHED"}


class FESTIVITY_FLOW_OT_bake_sway(Operator):
    bl_idname = "festivity_flow.bake_sway"
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
                pb.festivity_flow_update = False
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
                pb.festivity_flow_has_sway = False
                pb.festivity_flow_end_of_chain = False
                pb.festivity_flow_chain_id = ""
                pb.festivity_flow_update = True

        return {"FINISHED"}

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=800)

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.prop(self, "sep_action")


class FESTIVITY_FLOW_MT_presets(Menu):
    bl_label = "Sway Presets"
    bl_idname = "FESTIVITY_FLOW_MT_presets"
    preset_subdir = "festivity_flow"
    preset_operator = "script.execute_preset"
    draw = Menu.draw_preset


class FESTIVITY_FLOW_OT_preset_add(AddPresetBase, Operator):
    """Save current sway settings as a preset"""
    bl_idname = "festivity_flow.preset_add"
    bl_label = "Add Sway Preset"
    preset_menu = "FESTIVITY_FLOW_MT_presets"
    preset_subdir = "festivity_flow"

    name: bpy.props.StringProperty(
        name="Name",
        description="Name of the preset",
        default="",
        options={"SKIP_SAVE"},
    )

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=400)

    def draw(self, context):
        layout = self.layout
        if self.remove_active:
            import os
            preset_dir = os.path.join(bpy.utils.script_path_user(), "presets", self.preset_subdir)
            if os.path.isdir(preset_dir):
                py_files = sorted(f for f in os.listdir(preset_dir) if f.endswith(".py"))
                if py_files:
                    layout.label(text="Select a preset to remove:")
                    col = layout.column(align=True)
                    for f in py_files:
                        name = f[:-3]
                        op = col.operator("festivity_flow.preset_remove", text=name)
                        op.preset_name = name
                else:
                    layout.label(text="No user presets found")
            else:
                layout.label(text="No user presets found")
        else:
            layout.prop(self, "name")

    def execute(self, context):
        return AddPresetBase.execute(self, context)

    def add(self, context, filepath):
        bone = context.active_pose_bone
        if not bone or not bone.festivity_flow_has_sway:
            self.report({'ERROR'}, "No active sway bone")
            return

        props = [
            "festivity_flow_sw_amplitude", "festivity_flow_sw_frequency", "festivity_flow_sw_delay",
            "festivity_flow_sw_delay_opposite",
            "festivity_flow_sw_offset", "festivity_flow_sw_falloff_start", "festivity_flow_sw_speed",
            "festivity_flow_sw_sub_amplitude", "festivity_flow_sw_sub_frequency",
            "festivity_flow_sw_sub_delay", "festivity_flow_sw_sub_delay_opposite",
            "festivity_flow_sw_sub_falloff_start",
        ]

        with open(filepath, 'w', encoding='utf-8') as f:
            f.write("import bpy\n\n")
            f.write("settings = {\n")
            for p in props:
                f.write(f"    '{p}': {getattr(bone, p)!r},\n")
            f.write("}\n\n")
            f.write("for pb in bpy.context.selected_pose_bones:\n")
            f.write("    if not pb.festivity_flow_has_sway:\n")
            f.write("        continue\n")
            f.write("    pb.festivity_flow_update = False\n")
            f.write("    for attr, value in settings.items():\n")
            f.write("        setattr(pb, attr, value)\n")
            f.write("    pb.festivity_flow_update = True\n")


class FESTIVITY_FLOW_OT_preset_remove(Operator):
    """Remove a user-created preset"""
    bl_idname = "festivity_flow.preset_remove"
    bl_label = "Remove Preset"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}

    preset_name: bpy.props.StringProperty()

    def execute(self, context):
        import os
        preset_dir = os.path.join(bpy.utils.script_path_user(), "presets", "festivity_flow")
        filepath = os.path.join(preset_dir, self.preset_name + ".py")
        if os.path.exists(filepath):
            os.remove(filepath)
        return {'FINISHED'}


class FESTIVITY_FLOW_OT_batch_offset(Operator):
    bl_idname = "festivity_flow.batch_offset"
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
        increment = prefs.festivity_flow_batch_offset_increment

        chain_info = {}  # chain_id -> (selection_order, representative_bone)
        for pb in context.selected_pose_bones:
            if not pb.festivity_flow_has_sway or not pb.festivity_flow_chain_id:
                continue
            cid = pb.festivity_flow_chain_id
            order = pb.festivity_flow_selection_order
            if cid not in chain_info or order < chain_info[cid][0]:
                chain_info[cid] = (order, pb)

        if not chain_info:
            self.report({"ERROR"}, "No sway chains selected")
            return {"CANCELLED"}

        sorted_items = sorted(chain_info.items(), key=lambda x: x[1][0])
        orders = [info[0] for _, info in sorted_items]
        if len(set(orders)) <= 1:
            sorted_items = sorted(chain_info.items(), key=lambda x: x[0])
        chains, bones = zip(*[(cid, info[1]) for cid, info in sorted_items])

        attr = "festivity_flow_sw_sub_offset" if self.mode == 'SUB' else "festivity_flow_sw_offset"

        skip_rigs = []
        for i, pb in enumerate(bones):
            if pb.id_data in skip_rigs:
                continue
            skip_rigs.append(pb.id_data)

            for c_pb in pb.id_data.pose.bones:
                if c_pb.festivity_flow_chain_id in chains and c_pb.festivity_flow_has_sway:
                    try:
                        chain_idx = chains.index(c_pb.festivity_flow_chain_id)
                    except ValueError:
                        continue
                    c_pb.festivity_flow_update = False
                    setattr(c_pb, attr, chain_idx * increment)
                    c_pb.festivity_flow_update = True

        return {"FINISHED"}


class FESTIVITY_FLOW_OT_adjust_offset(Operator):
    bl_idname = "festivity_flow.adjust_offset"
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
        adjust_value = prefs.festivity_flow_offset_adjust_value

        attr = "festivity_flow_sw_sub_offset" if self.target == 'SUB' else "festivity_flow_sw_offset"

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

                pb.festivity_flow_update = False
                setattr(pb, attr, new_val)
                pb.festivity_flow_update = True

        return {"FINISHED"}


class FESTIVITY_FLOW_OT_adjust_roll(Operator):
    bl_idname = "festivity_flow.adjust_roll"
    bl_label = "Adjust Roll"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Add or set the y-axis sway roll of selected sway chains"

    value: bpy.props.FloatProperty(
        name="Value",
        default=0.0,
    )

    mode: bpy.props.EnumProperty(
        name="Mode",
        items=[
            ('ADD', "Add", "Add value to current roll"),
            ('SET', "Set", "Set roll to the given value"),
        ],
        default='ADD',
    )

    def execute(self, context):
        sim_chains = get_selected_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report({"ERROR"}, "No sway chains selected")
            return {"CANCELLED"}

        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                pb = rig.pose.bones[b_dat[1]]

                if self.mode == 'SET':
                    new_val = self.value
                else:
                    new_val = pb.festivity_flow_sw_roll + self.value

                pb.festivity_flow_update = False
                pb.festivity_flow_sw_roll = new_val
                pb.festivity_flow_update = True

        return {"FINISHED"}


class FESTIVITY_FLOW_OT_flip_roll(Operator):
    bl_idname = "festivity_flow.flip_roll"
    bl_label = "Flip Roll"
    bl_options = {"REGISTER", "UNDO", "INTERNAL"}
    bl_description = "Flip the y-axis sway roll by 180 degrees (subtract if positive, add if negative)"

    def execute(self, context):
        sim_chains = get_selected_bone_chains(context.selected_pose_bones)

        if len(sim_chains) == 0:
            self.report({"ERROR"}, "No sway chains selected")
            return {"CANCELLED"}

        for chain in sim_chains:
            for b_dat in chain:
                rig = b_dat[0]
                pb = rig.pose.bones[b_dat[1]]

                current = pb.festivity_flow_sw_roll
                if current > 0:
                    new_val = current - 180.0
                elif current < 0:
                    new_val = current + 180.0
                else:
                    new_val = current + 180.0

                pb.festivity_flow_update = False
                pb.festivity_flow_sw_roll = new_val
                pb.festivity_flow_update = True

        return {"FINISHED"}


#
# REGISTRATION
#


_classes = [
    FESTIVITY_FLOW_OT_add_sway,
    FESTIVITY_FLOW_OT_remove_sway,
    FESTIVITY_FLOW_OT_bake_sway,
    FESTIVITY_FLOW_MT_presets,
    FESTIVITY_FLOW_OT_preset_add,
    FESTIVITY_FLOW_OT_preset_remove,
    FESTIVITY_FLOW_OT_batch_offset,
    FESTIVITY_FLOW_OT_adjust_offset,
    FESTIVITY_FLOW_OT_adjust_roll,
    FESTIVITY_FLOW_OT_flip_roll,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()


def unregister():
    _unregister()
