import os
import bpy
from bpy.utils import register_submodule_factory

submodules = [
    "ui",
    "properties",
    "operators",
    "visualizer",
]

_sub_register, _sub_unregister = register_submodule_factory(__name__, submodules)


def register():
    _sub_register()
    bpy.utils.register_preset_path(os.path.dirname(__file__))


def unregister():
    _sub_unregister()
    bpy.utils.unregister_preset_path(os.path.dirname(__file__))
