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

    active_main = []
    active_sub = []
    inactive_main = []
    inactive_sub = []

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
            sr = math.sin(roll_rad)
            cr = math.cos(roll_rad)

            main_dir = (bone_x * sr + bone_z * cr).normalized()
            sub_dir = (bone_x * cr - bone_z * sr).normalized()

            shaft_len = pb.length * 0.5
            head_len = shaft_len * 0.3

            def make_arrow_lines(origin, direction):
                tip = origin + direction * shaft_len
                wing1 = tip - direction * head_len + bone_y * head_len * 0.6
                wing2 = tip - direction * head_len - bone_y * head_len * 0.6
                return [origin, tip, tip, wing1, tip, wing2]

            if is_active:
                active_main.extend(make_arrow_lines(bone_head, main_dir))
                active_sub.extend(make_arrow_lines(bone_head, sub_dir))
            else:
                inactive_main.extend(make_arrow_lines(bone_head, main_dir))
                inactive_sub.extend(make_arrow_lines(bone_head, sub_dir))

    shader = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
    viewport_size = gpu.state.viewport_get()[2:]

    def draw_batch(lines, line_width, color):
        if not lines:
            return
        coords = [(v.x, v.y, v.z) for v in lines]
        batch = batch_for_shader(shader, 'LINES', {"pos": coords})
        shader.uniform_float("viewportSize", viewport_size)
        shader.uniform_float("lineWidth", line_width)
        shader.uniform_float("color", color)
        batch.draw(shader)

    draw_batch(inactive_main, 1.5, (0.15, 0.40, 0.30, 0.25))
    draw_batch(inactive_sub, 1.2, (0.40, 0.25, 0.10, 0.25))
    draw_batch(active_main, 2.5, (0.20, 0.95, 0.60, 0.85))
    draw_batch(active_sub, 2.0, (0.95, 0.55, 0.20, 0.85))


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
