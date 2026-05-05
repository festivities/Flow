from bpy.utils import register_submodule_factory

submodules = [
    "ui",
    "properties",
    "operators",
]

register, unregister = register_submodule_factory(__name__, submodules)
