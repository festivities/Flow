import bpy

settings = {
    "flow_sw_amplitude": 15.0,
    "flow_sw_frequency": 2.0,
    "flow_sw_delay": 2.0,
    "flow_sw_offset": 0.0,
    "flow_sw_falloff_start": 0.3,
    "flow_sw_speed": 1.0,
    "flow_sw_sub_amplitude": 5.0,
    "flow_sw_sub_frequency": 3.0,
    "flow_sw_sub_delay": 1.0,
    "flow_sw_sub_falloff_start": 0.1,
}

for pb in bpy.context.selected_pose_bones:
    if not pb.flow_has_sway:
        continue
    pb.flow_update = False
    for attr, value in settings.items():
        setattr(pb, attr, value)
    pb.flow_update = True
