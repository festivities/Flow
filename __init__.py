from bpy.utils import register_submodule_factory

submodules = [
    "ui",
    "properties",
    "operators",
    "visualizer",
]

register, unregister = register_submodule_factory(__name__, submodules)
