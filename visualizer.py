import bpy
import gpu
import math
from gpu_extras.batch import batch_for_shader
from mathutils import Vector


_draw_handler = None


def _draw_sway_arrows():
    context = bpy.context

    active_chain_id = ""
    if (context.active_object and
            context.active_object.type == 'ARMATURE' and
            context.mode == 'POSE' and
            context.active_pose_bone):
        active_chain_id = context.active_pose_bone.flow_chain_id

    active_lines = []
    inactive_lines = []

    for ob in context.scene.objects:
        if ob.type != 'ARMATURE':
            continue
        if not ob.visible_get():
            continue

        mat_world_rot = ob.matrix_world.to_3x3()

        for pb in ob.pose.bones:
            if not pb.flow_has_sway:
                continue

            is_active = (pb.flow_chain_id == active_chain_id)

            bone_head = ob.matrix_world @ pb.matrix.translation
            bone_x = (mat_world_rot @ pb.x_axis).normalized()
            bone_y = (mat_world_rot @ pb.y_axis).normalized()
            bone_z = (mat_world_rot @ pb.z_axis).normalized()

            roll_rad = math.radians(pb.flow_sw_roll)
            sway_dir = (bone_x * math.cos(roll_rad) - bone_z * math.sin(roll_rad)).normalized()

            shaft_len = pb.length * 0.5
            head_len = shaft_len * 0.3

            tip = bone_head + sway_dir * shaft_len
            base = bone_head

            wing1 = tip - sway_dir * head_len + bone_y * head_len * 0.6
            wing2 = tip - sway_dir * head_len - bone_y * head_len * 0.6

            lines = [base, tip, tip, wing1, tip, wing2]

            if is_active:
                active_lines.extend(lines)
            else:
                inactive_lines.extend(lines)

    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')

    viewport_size = gpu.state.viewport_get()[2:]

    if inactive_lines:
        coords = [(v.x, v.y, v.z) for v in inactive_lines]
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        shader.uniform_float("viewportSize", viewport_size)
        shader.uniform_float("lineWidth", 1.5)
        shader.uniform_float("color", (0.25, 0.35, 0.3, 0.25))
        batch.draw(shader)

    if active_lines:
        coords = [(v.x, v.y, v.z) for v in active_lines]
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        shader.uniform_float("viewportSize", viewport_size)
        shader.uniform_float("lineWidth", 2.5)
        shader.uniform_float("color", (0.2, 0.95, 0.6, 0.85))
        batch.draw(shader)


def enable_sway_visualizer():
    global _draw_handler
    if _draw_handler is None:
        _draw_handler = bpy.types.SpaceView3D.draw_handler_add(
            _draw_sway_arrows, (), 'WINDOW', 'POST_VIEW'
        )


def disable_sway_visualizer():
    global _draw_handler
    if _draw_handler is not None:
        bpy.types.SpaceView3D.draw_handler_remove(_draw_handler, 'WINDOW')
        _draw_handler = None


def register():
    prefs = bpy.context.preferences.addons[__package__].preferences
    if prefs.flow_show_sway_visualizer:
        enable_sway_visualizer()


def unregister():
    disable_sway_visualizer()
