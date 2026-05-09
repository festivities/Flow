from .functions import get_root_from_sway_bone, get_selected_bone_chains
from bpy.types import Panel
import bpy


def draw_subpanel(layout, prefs, menu_name, label, icon):

    box = layout.box()
    row = box.row()
    row.alignment = "LEFT"
    row.prop(
        prefs,
        menu_name,
        icon="TRIA_DOWN" if getattr(prefs, menu_name) else "TRIA_RIGHT",
        icon_only=True,
        emboss=False,
    )
    row.label(text=label, icon=icon)

    return box, getattr(prefs, menu_name)


class FESTIVITY_FLOW_PT_main_panel(Panel):
    bl_label = "Flow"
    bl_idname = "FESTIVITY_FLOW_PT_main_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = "Flow"

    @classmethod
    def poll(cls, context):
        return (
            context.active_object is not None
            and context.active_object.type == 'ARMATURE'
            and context.mode == 'POSE'
            and context.active_pose_bone is not None
        )

    def draw(self, context):
        layout = self.layout
        pb = context.active_pose_bone
        prefs = context.preferences.addons[__package__].preferences

        if pb.festivity_flow_has_sway == False:
            box = layout.box()
            row = box.row(align=True)
            row.operator("festivity_flow.add_sway", text="Add Sway Chain")
            row.scale_y = 2.5
        else:
            root = get_root_from_sway_bone(pb)

            box = layout.box()

            box = layout.box()
            row = box.row(align=True)
            row.operator("festivity_flow.remove_sway", text="Remove Sway Chain")
            row.scale_y = 1.5

            row = box.row(align=True)
            row.operator("festivity_flow.bake_sway", text="Bake to Keyframes")
            row.scale_y = 2

            box = layout.box()

            row = box.row(align=True)
            row.menu("FESTIVITY_FLOW_MT_presets", text="Sway Presets")
            row.operator("festivity_flow.preset_add", text="", icon="ADD")
            row.operator("festivity_flow.preset_add", text="", icon="REMOVE").remove_active = True

            boxx, expanded = draw_subpanel(box, prefs, "sw_general_menu", "Main Axis Wave", "MOD_WAVE")
            if expanded:

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_amplitude", text="Amplitude")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_frequency", text="Frequency (Hz)")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_delay", text="Delay")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_delay_opposite", text="Reverse Direction")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_offset", text="Offset (frames)")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_falloff_start", text="Root Falloff")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_bias", text="Wind Bias")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_limit_neg", text="Limit -")
                row.prop(root, "festivity_flow_sw_limit_pos", text="Limit +")

            boxx, expanded = draw_subpanel(box, prefs, "sw_subwave_menu", "Sub Axis Wave", "MOD_WAVE")
            if expanded:

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_amplitude", text="Amplitude")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_frequency", text="Frequency (Hz)")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_delay", text="Delay")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_delay_opposite", text="Reverse Direction")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_offset", text="Offset (frames)")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_falloff_start", text="Root Falloff")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_bias", text="Wind Bias")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_sub_limit_neg", text="Limit -")
                row.prop(root, "festivity_flow_sw_sub_limit_pos", text="Limit +")

            boxx, expanded = draw_subpanel(box, prefs, "sw_global_menu", "General", "SETTINGS")
            if expanded:

                row = boxx.row(align=True)
                row.prop(prefs, "festivity_flow_show_sway_visualizer")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_roll", text="Y-Axis Roll")

                row = boxx.row(align=True)
                row.prop(prefs, "festivity_flow_roll_adjust_value")
                row.operator("festivity_flow.flip_roll", text="Flip 180\u00b0")

                row = boxx.row(align=True)
                op = row.operator("festivity_flow.adjust_roll", text="+ Roll")
                op.mode = 'ADD'
                op.value = prefs.festivity_flow_roll_adjust_value
                op = row.operator("festivity_flow.adjust_roll", text="- Roll")
                op.mode = 'ADD'
                op.value = -prefs.festivity_flow_roll_adjust_value
                op = row.operator("festivity_flow.adjust_roll", text="= Roll")
                op.mode = 'SET'
                op.value = prefs.festivity_flow_roll_adjust_value

                row = boxx.row(align=True)
                for a in (22.5, 45.0, 90.0):
                    op = row.operator("festivity_flow.adjust_roll", text="+{:.0f}\u00b0".format(a) if a == int(a) else "+{:.1f}\u00b0".format(a))
                    op.value = a
                    op = row.operator("festivity_flow.adjust_roll", text="-{:.0f}\u00b0".format(a) if a == int(a) else "-{:.1f}\u00b0".format(a))
                    op.value = -a

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_random_seed", text="Random Seed")

                row = boxx.row(align=True)
                row.prop(root, "festivity_flow_sw_speed", text="Speed Multiplier")

                row = boxx.row(align=True)
                row.prop(prefs, "festivity_flow_batch_offset_increment", text="Batch Offset")
                op = row.operator("festivity_flow.batch_offset", text="Main")
                op.mode = 'MAIN'
                op = row.operator("festivity_flow.batch_offset", text="Sub")
                op.mode = 'SUB'

                row = boxx.row(align=True)
                row.prop(prefs, "festivity_flow_offset_adjust_value")

                row = boxx.row(align=True)
                op = row.operator("festivity_flow.adjust_offset", text="+ Main")
                op.mode = 'ADD'
                op.target = 'MAIN'
                op = row.operator("festivity_flow.adjust_offset", text="- Main")
                op.mode = 'SUBTRACT'
                op.target = 'MAIN'
                op = row.operator("festivity_flow.adjust_offset", text="= Main")
                op.mode = 'SET'
                op.target = 'MAIN'

                row = boxx.row(align=True)
                op = row.operator("festivity_flow.adjust_offset", text="+ Sub")
                op.mode = 'ADD'
                op.target = 'SUB'
                op = row.operator("festivity_flow.adjust_offset", text="- Sub")
                op.mode = 'SUBTRACT'
                op.target = 'SUB'
                op = row.operator("festivity_flow.adjust_offset", text="= Sub")
                op.mode = 'SET'
                op.target = 'SUB'


_classes = [
    FESTIVITY_FLOW_PT_main_panel,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()


def unregister():
    _unregister()
