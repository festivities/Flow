from bpy.utils import register_submodule_factory
import os
import shutil


def _check_presets():
    addon_dir = os.path.dirname(__file__)
    addon_presets = os.path.join(addon_dir, "presets")
    user_presets = os.path.join(bpy.utils.user_resource('SCRIPTS'), "presets", "flow")

    if not os.path.isdir(addon_presets):
        return

    os.makedirs(user_presets, exist_ok=True)

    for fname in os.listdir(addon_presets):
        if fname.endswith('.py'):
            src = os.path.join(addon_presets, fname)
            dst = os.path.join(user_presets, fname)
            if not os.path.exists(dst):
                shutil.copy2(src, dst)


submodules = [
    "ui",
    "properties",
    "operators",
    "visualizer",
]

_register, _unregister = register_submodule_factory(__name__, submodules)


def register():
    import bpy
    _check_presets()
    _register()


def unregister():
    _unregister()
