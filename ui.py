from .functions import get_selected_bone_chains
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


class FLOW_PT_main_panel(Panel):
    bl_label = "Flow"
    bl_idname = "FLOW_PT_main_panel"
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

        if pb.flow_has_sway == False:
            box = layout.box()
            row = box.row(align=True)
            row.operator("flow.add_sway", text="Add Sway Chain")
            row.scale_y = 2.5
        else:
            box = layout.box()

            box = layout.box()
            row = box.row(align=True)
            row.operator("flow.remove_sway", text="Remove Sway Chain")
            row.scale_y = 1.5

            row = box.row(align=True)
            row.operator("flow.bake_sway", text="Bake to Keyframes")
            row.scale_y = 2

            box = layout.box()

            row = box.row(align=True)
            row.label(text="Presets:")
            row = box.row(align=True)
            row.prop(prefs, "sw_presets", text="")
            row.operator("flow.save_preset", text="", icon="ADD")
            row.operator("flow.delete_preset", text="", icon="REMOVE")

            row = box.row(align=True)
            row.operator("flow.apply_preset", text="Apply Preset")

            boxx, expanded = draw_subpanel(box, prefs, "sw_general_menu", "Wave X", "FORCE_HARMONIC")
            if expanded:

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_amplitude", text="X Amplitude")

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_frequency", text="X Frequency (Hz)")

                row = boxx.row(align=True)
                loop_period = 1.0 / max(pb.flow_sw_frequency * pb.flow_sw_speed, 0.001)
                row.label(text=f"Loop Period: {loop_period:.2f}s")

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_delay", text="X Delay")

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_offset", text="X Offset (frames)")

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_falloff_start", text="X Root Falloff")

                boxx.separator()

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_speed", text="Speed Multiplier")

                row = boxx.row(align=True)
                row.prop(pb, "flow_sw_random_seed", text="Random Seed")

            boxxx, expanded = draw_subpanel(boxx, prefs, "sw_subwave_menu", "Wave Z", "MOD_WAVE")
            if expanded:

                row = boxxx.row(align=True)
                row.prop(pb, "flow_sw_sub_amplitude", text="Z Amplitude")

                row = boxxx.row(align=True)
                row.prop(pb, "flow_sw_sub_frequency", text="Z Frequency (Hz)")

                row = boxxx.row(align=True)
                row.prop(pb, "flow_sw_sub_delay", text="Z Delay")

                row = boxxx.row(align=True)
                row.prop(pb, "flow_sw_sub_offset", text="Z Offset (frames)")

                row = boxxx.row(align=True)
                row.prop(pb, "flow_sw_sub_falloff_start", text="Z Root Falloff")

            boxww, expanded = draw_subpanel(boxx, prefs, "sw_wind_menu", "Wind Controller", "FORCE_WIND")
            if expanded:
                has_wind = pb.flow_sw_wind_object is not None
                if not has_wind:
                    row = boxww.row(align=True)
                    row.operator("flow.add_wind_controller", text="Add Wind Controller")
                    row.scale_y = 2.0
                else:
                    row = boxww.row(align=True)
                    row.prop(pb, "flow_sw_wind_object", text="Controller")
                    row = boxww.row(align=True)
                    row.operator("flow.remove_wind_controller", text="Remove Wind Controller")
                    row.scale_y = 1.5

            row = boxx.row(align=True)
            row.prop(pb, "flow_influence", text="Influence")


_classes = [
    FLOW_PT_main_panel,
]

_register, _unregister = bpy.utils.register_classes_factory(_classes)


def register():
    _register()


def unregister():
    _unregister()
