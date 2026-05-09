from bpy.types import AddonPreferences
import bpy

# Selection order tracking cache: {(armature_name, bone_name): bool}
_last_select_state = {}


@bpy.app.handlers.persistent
def _festivity_flow_track_selection(scene, depsgraph):
    global _last_select_state
    for arm_obj in bpy.data.objects:
        if arm_obj.type != 'ARMATURE' or arm_obj.mode != 'POSE':
            continue
        counter = arm_obj.get('_festivity_flow_sel_counter', 0)
        changed = False
        for pb in arm_obj.pose.bones:
            key = (arm_obj.name, pb.name)
            is_sel = pb.select
            was_sel = _last_select_state.get(key, False)
            if is_sel and not was_sel:
                counter += 1
                pb.festivity_flow_selection_order = counter
                changed = True
            _last_select_state[key] = is_sel
        if changed:
            arm_obj['_festivity_flow_sel_counter'] = counter


@bpy.app.handlers.persistent
def _festivity_flow_reset_on_undo(scene):
    global _last_select_state
    _last_select_state.clear()
    for arm_obj in bpy.data.objects:
        if arm_obj.type == 'ARMATURE' and '_festivity_flow_sel_counter' in arm_obj:
            del arm_obj['_festivity_flow_sel_counter']


#
# SWAY CHAIN UPDATE FUNCTIONS
#


def update_sw_prop(self, attr_name, attr_value):
    prefs = bpy.context.preferences.addons[__package__].preferences

    if self.festivity_flow_update:
        active_chain_id = self.festivity_flow_chain_id
        chains, bones = [], []
        for pb in bpy.context.selected_pose_bones:
            if pb.festivity_flow_has_sway == False:
                continue

            if prefs.apply_to_all_chains == False and pb.festivity_flow_chain_id != active_chain_id:
                continue

            if pb.festivity_flow_chain_id not in chains:
                chains.append(pb.festivity_flow_chain_id)
                bones.append(pb)

        skip_rigs = []
        for p, pb in enumerate(bones):
            if pb.id_data in skip_rigs:
                continue
            else:
                skip_rigs.append(pb.id_data)

            for c_pb in pb.id_data.pose.bones:
                if c_pb.festivity_flow_chain_id in chains and c_pb.festivity_flow_has_sway:
                    c_pb.festivity_flow_update = False
                    setattr(c_pb, attr_name, attr_value)
                    c_pb.festivity_flow_update = True

    return


def update_sw_amplitude(self, context):
    update_sw_prop(self, "festivity_flow_sw_amplitude", self.festivity_flow_sw_amplitude)
    return


def update_sw_frequency(self, context):
    update_sw_prop(self, "festivity_flow_sw_frequency", self.festivity_flow_sw_frequency)
    return


def update_sw_delay(self, context):
    update_sw_prop(self, "festivity_flow_sw_delay", self.festivity_flow_sw_delay)
    return


def update_sw_offset(self, context):
    update_sw_prop(self, "festivity_flow_sw_offset", self.festivity_flow_sw_offset)
    return


def update_sw_falloff_start(self, context):
    update_sw_prop(self, "festivity_flow_sw_falloff_start", self.festivity_flow_sw_falloff_start)
    return


def update_sw_speed(self, context):
    update_sw_prop(self, "festivity_flow_sw_speed", self.festivity_flow_sw_speed)
    return


def update_sw_random_seed(self, context):
    update_sw_prop(self, "festivity_flow_sw_random_seed", self.festivity_flow_sw_random_seed)
    return


def update_sw_roll(self, context):
    update_sw_prop(self, "festivity_flow_sw_roll", self.festivity_flow_sw_roll)
    return


def update_sw_sub_amplitude(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_amplitude", self.festivity_flow_sw_sub_amplitude)
    return


def update_sw_sub_frequency(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_frequency", self.festivity_flow_sw_sub_frequency)
    return


def update_sw_sub_delay(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_delay", self.festivity_flow_sw_sub_delay)
    return


def update_sw_sub_offset(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_offset", self.festivity_flow_sw_sub_offset)
    return


def update_sw_sub_falloff_start(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_falloff_start", self.festivity_flow_sw_sub_falloff_start)
    return


def update_sw_bias(self, context):
    update_sw_prop(self, "festivity_flow_sw_bias", self.festivity_flow_sw_bias)
    return


def update_sw_sub_bias(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_bias", self.festivity_flow_sw_sub_bias)
    return


def update_sw_limit_pos(self, context):
    update_sw_prop(self, "festivity_flow_sw_limit_pos", self.festivity_flow_sw_limit_pos)


def update_sw_limit_neg(self, context):
    update_sw_prop(self, "festivity_flow_sw_limit_neg", self.festivity_flow_sw_limit_neg)


def update_sw_sub_limit_pos(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_limit_pos", self.festivity_flow_sw_sub_limit_pos)


def update_sw_sub_limit_neg(self, context):
    update_sw_prop(self, "festivity_flow_sw_sub_limit_neg", self.festivity_flow_sw_sub_limit_neg)


def update_sway_visualizer(self, context):
    from .visualizer import enable_sway_visualizer, disable_sway_visualizer
    if self.festivity_flow_show_sway_visualizer:
        enable_sway_visualizer()
    else:
        disable_sway_visualizer()
    if context.screen:
        for area in context.screen.areas:
            if area.type == 'VIEW_3D':
                area.tag_redraw()
    return


#
# PREFERENCES
#


class FlowPreferences(AddonPreferences):
    bl_idname = __package__

    apply_to_all_chains: bpy.props.BoolProperty(
        default=True,
        name="Auto Update All Selected Chains",
        description="Any settings change for the active chain will apply to all selected bone chains",
    )

    keep_existing_settings: bpy.props.BoolProperty(
        default=True,
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

    festivity_flow_batch_offset_increment: bpy.props.FloatProperty(
        default=24.0,
        min=0.0,
        max=100.0,
        name="Increment (frames)",
        description="Incremental offset value applied to each selected chain when using batch offset",
    )

    festivity_flow_offset_adjust_value: bpy.props.FloatProperty(
        default=12.0,
        min=-100.0,
        max=100.0,
        name="Adjust (frames)",
        description="Value to add, subtract, or set the offset of selected sway chains",
    )

    festivity_flow_roll_adjust_value: bpy.props.FloatProperty(
        default=45.0,
        min=-360.0,
        max=360.0,
        name="Roll Adjust",
        description="Degrees to add, subtract, or set the y-axis roll of selected sway chains",
    )

    festivity_flow_show_sway_visualizer: bpy.props.BoolProperty(
        default=False,
        name="Show Sway Direction",
        description="Show arrows in the 3D viewport indicating the sway direction for each bone",
        update=update_sway_visualizer,
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

    bpy.types.PoseBone.festivity_flow_has_sway = bpy.props.BoolProperty(
        default=False, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.festivity_flow_chain_id = bpy.props.StringProperty(
        default="", options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.festivity_flow_end_of_chain = bpy.props.BoolProperty(
        default=False, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    bpy.types.PoseBone.festivity_flow_update = bpy.props.BoolProperty(
        default=True, options={"LIBRARY_EDITABLE"}, override={"LIBRARY_OVERRIDABLE"}
    )

    # Sway Chain Properties
    bpy.types.PoseBone.festivity_flow_sw_amplitude = bpy.props.FloatProperty(
        default=5.0,
        min=0.0,
        max=90.0,
        description="Maximum rotation angle in degrees for the main axis sway wave",
        update=update_sw_amplitude,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_frequency = bpy.props.FloatProperty(
        default=1.0,
        min=0.01,
        max=10.0,
        description="Number of complete wave cycles per second",
        update=update_sw_frequency,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_delay = bpy.props.FloatProperty(
        default=3.0,
        min=0.0,
        max=48.0,
        description="Frame offset between bones in the chain, creating the cascading sway effect (in frames)",
        update=update_sw_delay,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_offset = bpy.props.FloatProperty(
        default=0.0,
        min=-100.0,
        max=100.0,
        description="Frame offset for the chain's starting position in the wave cycle",
        update=update_sw_offset,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_falloff_start = bpy.props.FloatProperty(
        default=0.2,
        min=0.0,
        max=1.0,
        description="Amplitude factor at the chain root (0 = no motion at root, 1 = full motion everywhere)",
        update=update_sw_falloff_start,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_speed = bpy.props.FloatProperty(
        default=1.0,
        min=0.01,
        max=5.0,
        description="Global speed multiplier for the sway animation",
        update=update_sw_speed,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_random_seed = bpy.props.FloatProperty(
        default=0.0,
        min=-10.0,
        max=10.0,
        description="Random time offset for this chain to prevent all chains from syncing",
        update=update_sw_random_seed,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_roll = bpy.props.FloatProperty(
        default=0.0,
        min=-360.0,
        max=360.0,
        description="Per-bone phase offset in degrees to curve the sway direction along the chain",
        update=update_sw_roll,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_amplitude = bpy.props.FloatProperty(
        default=0.0,
        min=0.0,
        max=90.0,
        description="Maximum rotation angle in degrees for the sub axis sway wave",
        update=update_sw_sub_amplitude,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_frequency = bpy.props.FloatProperty(
        default=2.0,
        min=0.01,
        max=20.0,
        description="Number of complete Z-axis wave cycles per second",
        update=update_sw_sub_frequency,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_delay = bpy.props.FloatProperty(
        default=1.5,
        min=0.0,
        max=48.0,
        description="Frame offset between bones for the Z-axis wave cascade (in frames)",
        update=update_sw_sub_delay,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_offset = bpy.props.FloatProperty(
        default=0.0,
        min=-100.0,
        max=100.0,
        description="Frame offset for the Z-axis wave starting position",
        update=update_sw_sub_offset,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_falloff_start = bpy.props.FloatProperty(
        default=0.0,
        min=0.0,
        max=1.0,
        description="Z-axis wave amplitude factor at the chain root",
        update=update_sw_sub_falloff_start,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_bias = bpy.props.FloatProperty(
        default=0.0,
        min=-90.0,
        max=90.0,
        description="Constant angular offset in the main sway direction (positive = toward arrow, negative = against arrow)",
        update=update_sw_bias,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_sub_bias = bpy.props.FloatProperty(
        default=0.0,
        min=-90.0,
        max=90.0,
        description="Constant angular offset in the sub sway direction (positive = toward arrow, negative = against arrow)",
        update=update_sw_sub_bias,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_sw_limit_pos = bpy.props.FloatProperty(
        default=360.0, min=0.0, max=360.0,
        description="Maximum positive rotation (in rest space) on the main sway axis. Acts like a soft collision wall.",
        update=update_sw_limit_pos,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )
    bpy.types.PoseBone.festivity_flow_sw_limit_neg = bpy.props.FloatProperty(
        default=-360.0, min=-360.0, max=0.0,
        description="Minimum (most negative) rotation (in rest space) on the main sway axis.",
        update=update_sw_limit_neg,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )
    bpy.types.PoseBone.festivity_flow_sw_sub_limit_pos = bpy.props.FloatProperty(
        default=360.0, min=0.0, max=360.0,
        description="Maximum positive rotation (in rest space) on the sub sway axis.",
        update=update_sw_sub_limit_pos,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )
    bpy.types.PoseBone.festivity_flow_sw_sub_limit_neg = bpy.props.FloatProperty(
        default=-360.0, min=-360.0, max=0.0,
        description="Minimum (most negative) rotation (in rest space) on the sub sway axis.",
        update=update_sw_sub_limit_neg,
        options={"LIBRARY_EDITABLE", "ANIMATABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.types.PoseBone.festivity_flow_selection_order = bpy.props.IntProperty(
        default=0,
        options={"LIBRARY_EDITABLE"},
        override={"LIBRARY_OVERRIDABLE"},
    )

    bpy.app.handlers.depsgraph_update_post.append(_festivity_flow_track_selection)
    bpy.app.handlers.undo_post.append(_festivity_flow_reset_on_undo)


def unregister():
    _unregister()

    if _festivity_flow_track_selection in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.remove(_festivity_flow_track_selection)

    if _festivity_flow_reset_on_undo in bpy.app.handlers.undo_post:
        bpy.app.handlers.undo_post.remove(_festivity_flow_reset_on_undo)

    del bpy.types.PoseBone.festivity_flow_selection_order

    del bpy.types.PoseBone.festivity_flow_sw_sub_limit_neg
    del bpy.types.PoseBone.festivity_flow_sw_sub_limit_pos
    del bpy.types.PoseBone.festivity_flow_sw_limit_neg
    del bpy.types.PoseBone.festivity_flow_sw_limit_pos
    del bpy.types.PoseBone.festivity_flow_sw_sub_bias
    del bpy.types.PoseBone.festivity_flow_sw_bias
    del bpy.types.PoseBone.festivity_flow_sw_sub_falloff_start
    del bpy.types.PoseBone.festivity_flow_sw_sub_offset
    del bpy.types.PoseBone.festivity_flow_sw_sub_delay
    del bpy.types.PoseBone.festivity_flow_sw_sub_frequency
    del bpy.types.PoseBone.festivity_flow_sw_sub_amplitude
    del bpy.types.PoseBone.festivity_flow_sw_random_seed
    del bpy.types.PoseBone.festivity_flow_sw_roll
    del bpy.types.PoseBone.festivity_flow_sw_speed
    del bpy.types.PoseBone.festivity_flow_sw_falloff_start
    del bpy.types.PoseBone.festivity_flow_sw_offset
    del bpy.types.PoseBone.festivity_flow_sw_delay
    del bpy.types.PoseBone.festivity_flow_sw_frequency
    del bpy.types.PoseBone.festivity_flow_sw_amplitude
    del bpy.types.PoseBone.festivity_flow_update
    del bpy.types.PoseBone.festivity_flow_end_of_chain
    del bpy.types.PoseBone.festivity_flow_chain_id
    del bpy.types.PoseBone.festivity_flow_has_sway
