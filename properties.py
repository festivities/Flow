from .functions import load_presets
from bpy.types import AddonPreferences
import bpy
import os
import json
from pathlib import Path


#
# SWAY CHAIN UPDATE FUNCTIONS
#


def update_sw_prop(self, attr_name, attr_value):
    prefs = bpy.context.preferences.addons[__package__].preferences

    if self.flow_update:
        chains, bones = [], []
        for pb in bpy.context.selected_pose_bones:
            if pb.flow_has_sway == False:
                continue

            if prefs.apply_to_all_chains == False and pb.flow_chain_id != bpy.context.active_pose_bone.flow_chain_id:
                continue

            if pb.flow_chain_id not in chains:
                chains.append(pb.flow_chain_id)
                bones.append(pb)

        skip_rigs = []
        for p, pb in enumerate(bones):
            if pb.id_data in skip_rigs:
                continue
            else:
                skip_rigs.append(pb.id_data)

            for c_pb in pb.id_data.pose.bones:
                if c_pb.flow_chain_id in chains and c_pb.flow_has_sway:
                    c_pb.flow_update = False
                    setattr(c_pb, attr_name, attr_value)
                    c_pb.flow_update = True

    return


def update_sw_amplitude(self, context):
    update_sw_prop(self, "flow_sw_amplitude", context.active_pose_bone.flow_sw_amplitude)
    return


def update_sw_frequency(self, context):
    update_sw_prop(self, "flow_sw_frequency", context.active_pose_bone.flow_sw_frequency)
    return


def update_sw_delay(self, context):
    update_sw_prop(self, "flow_sw_delay", context.active_pose_bone.flow_sw_delay)
    return


def update_sw_offset(self, context):
    update_sw_prop(self, "flow_sw_offset", context.active_pose_bone.flow_sw_offset)
    return


def update_sw_falloff_start(self, context):
    update_sw_prop(self, "flow_sw_falloff_start", context.active_pose_bone.flow_sw_falloff_start)
    return


def update_sw_speed(self, context):
    update_sw_prop(self, "flow_sw_speed", context.active_pose_bone.flow_sw_speed)
    return


def update_sw_random_seed(self, context):
    update_sw_prop(self, "flow_sw_random_seed", context.active_pose_bone.flow_sw_random_seed)
    return


def update_sw_roll(self, context):
    update_sw_prop(self, "flow_sw_roll", context.active_pose_bone.flow_sw_roll)
    return


def update_sw_sub_amplitude(self, context):
    update_sw_prop(self, "flow_sw_sub_amplitude", context.active_pose_bone.flow_sw_sub_amplitude)
    return


def update_sw_sub_frequency(self, context):
    update_sw_prop(self, "flow_sw_sub_frequency", context.active_pose_bone.flow_sw_sub_frequency)
    return


def update_sw_sub_delay(self, context):
    update_sw_prop(self, "flow_sw_sub_delay", context.active_pose_bone.flow_sw_sub_delay)
    return


def update_sw_sub_offset(self, context):
    update_sw_prop(self, "flow_sw_sub_offset", context.active_pose_bone.flow_sw_sub_offset)
    return


def update_sw_sub_falloff_start(self, context):
    update_sw_prop(self, "flow_sw_sub_falloff_start", context.active_pose_bone.flow_sw_sub_falloff_start)
    return


#
# PREFERENCES
#


def get_sw_presets(self, context):
    preset_fp = Path(os.path.dirname(__file__)) / "presets" / "sway_chain_presets.json"
    user_preset_fp = Path(os.path.dirname(__file__)) / "user_created_presets" / "sway_chain_presets.json"

    return load_presets(preset_fp) + load_presets(user_preset_fp)


class FlowPreferences(AddonPreferences):
    bl_idname = __package__

    sw_presets: bpy.props.EnumProperty(
        name="Sway Chain Presets",
        items=get_sw_presets,
    )

    apply_to_all_chains: bpy.props.BoolProperty(
        default=True,
        name="Auto Update All Selected Chains",
        description="Any settings change for the active chain will apply to all selected bone chains",
    )

    keep_existing_settings: bpy.props.BoolProperty(
        default=False,
        name="Keep Existing Settings",
        description="When readding a physics type to bones it will keep the previously set settings. Otherwise it will load in the active preset"
    )

    sw_general_menu: bpy.props.BoolProperty(
        default=True,
    )
    sw_subwave_menu: bpy.props.BoolProperty(
        default=True,
    )
    sw_global_menu: bpy.props.BoolProperty(
        default=True,
    )

    flow_batch_offset_increment: bpy.props.FloatProperty(
        default=24.0,
        min=0.0,
        max=100.0,
        name="Increment (frames)",
        description="Incremental offset value applied to each selected chain when using batch offset",
    )

    def draw(self, context):
        layout = self.layout
        column = layout.column(align=True)
        row = column.row(align=True)
        row.prop(self, "apply_to_all_chains")
        row = column.row(align=True)
        row.prop(self, "keep_existing_settings")


#
# PROPERTY REGISTRATION
#


_classes = [
    FlowPreferences,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()

    bpy.types.PoseBone.flow_has_sway = bpy.props.BoolProperty(
        default=False, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.flow_chain_id = bpy.props.StringProperty(
        default="", options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.flow_end_of_chain = bpy.props.BoolProperty(
        default=False, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.flow_update = bpy.props.BoolProperty(
        default=True, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    # Sway Chain Properties
    bpy.types.PoseBone.flow_sw_amplitude = bpy.props.FloatProperty(
        default=5.0,
        min=0.0,
        max=90.0,
        description="Maximum rotation angle in degrees for the main axis sway wave",
        update=update_sw_amplitude,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_frequency = bpy.props.FloatProperty(
        default=1.0,
        min=0.01,
        max=10.0,
        description="Number of complete wave cycles per second",
        update=update_sw_frequency,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_delay = bpy.props.FloatProperty(
        default=3.0,
        min=0.0,
        max=48.0,
        description="Frame offset between bones in the chain, creating the cascading sway effect (in frames)",
        update=update_sw_delay,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_offset = bpy.props.FloatProperty(
        default=0.0,
        min=-100.0,
        max=100.0,
        description="Frame offset for the chain's starting position in the wave cycle",
        update=update_sw_offset,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_falloff_start = bpy.props.FloatProperty(
        default=0.2,
        min=0.0,
        max=1.0,
        description="Amplitude factor at the chain root (0 = no motion at root, 1 = full motion everywhere)",
        update=update_sw_falloff_start,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_speed = bpy.props.FloatProperty(
        default=1.0,
        min=0.01,
        max=5.0,
        description="Global speed multiplier for the sway animation",
        update=update_sw_speed,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_random_seed = bpy.props.FloatProperty(
        default=0.0,
        min=-10.0,
        max=10.0,
        description="Random time offset for this chain to prevent all chains from syncing",
        update=update_sw_random_seed,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_roll = bpy.props.FloatProperty(
        default=0.0,
        min=-360.0,
        max=360.0,
        description="Per-bone phase offset in degrees to curve the sway direction along the chain",
        update=update_sw_roll,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_sub_amplitude = bpy.props.FloatProperty(
        default=0.0,
        min=0.0,
        max=90.0,
        description="Maximum rotation angle in degrees for the sub axis sway wave",
        update=update_sw_sub_amplitude,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_sub_frequency = bpy.props.FloatProperty(
        default=2.0,
        min=0.01,
        max=20.0,
        description="Number of complete Z-axis wave cycles per second",
        update=update_sw_sub_frequency,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_sub_delay = bpy.props.FloatProperty(
        default=1.5,
        min=0.0,
        max=48.0,
        description="Frame offset between bones for the Z-axis wave cascade (in frames)",
        update=update_sw_sub_delay,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_sub_offset = bpy.props.FloatProperty(
        default=0.0,
        min=-100.0,
        max=100.0,
        description="Frame offset for the Z-axis wave starting position",
        update=update_sw_sub_offset,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.flow_sw_sub_falloff_start = bpy.props.FloatProperty(
        default=0.0,
        min=0.0,
        max=1.0,
        description="Z-axis wave amplitude factor at the chain root",
        update=update_sw_sub_falloff_start,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )


def unregister():
    _unregister()

    del bpy.types.PoseBone.flow_sw_sub_falloff_start
    del bpy.types.PoseBone.flow_sw_sub_offset
    del bpy.types.PoseBone.flow_sw_sub_delay
    del bpy.types.PoseBone.flow_sw_sub_frequency
    del bpy.types.PoseBone.flow_sw_sub_amplitude
    del bpy.types.PoseBone.flow_sw_random_seed
    del bpy.types.PoseBone.flow_sw_roll
    del bpy.types.PoseBone.flow_sw_speed
    del bpy.types.PoseBone.flow_sw_falloff_start
    del bpy.types.PoseBone.flow_sw_offset
    del bpy.types.PoseBone.flow_sw_delay
    del bpy.types.PoseBone.flow_sw_frequency
    del bpy.types.PoseBone.flow_sw_amplitude
    del bpy.types.PoseBone.flow_update
    del bpy.types.PoseBone.flow_end_of_chain
    del bpy.types.PoseBone.flow_chain_id
    del bpy.types.PoseBone.flow_has_sway
