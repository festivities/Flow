import bpy

settings = {
    "festivity_flow_sw_amplitude": 3.0,
    "festivity_flow_sw_frequency": 0.5,
    "festivity_flow_sw_delay": 4.0,
    "festivity_flow_sw_offset": 0.0,
    "festivity_flow_sw_falloff_start": 0.1,
    "festivity_flow_sw_speed": 1.0,
    "festivity_flow_sw_sub_amplitude": 1.0,
    "festivity_flow_sw_sub_frequency": 1.5,
    "festivity_flow_sw_sub_delay": 2.0,
    "festivity_flow_sw_sub_falloff_start": 0.0,
}

for pb in bpy.context.selected_pose_bones:
    if not pb.festivity_flow_has_sway:
        continue
    pb.festivity_flow_update = False
    for attr, value in settings.items():
        setattr(pb, attr, value)
    pb.festivity_flow_update = True
