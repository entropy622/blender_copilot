bl_info = {
    "name": "Blender Copilot — Graph Code Tools",
    "author": "Aentro",
    "version": (0, 4, 0),
    "blender": (5, 2, 0),
    "location": "Preferences > Add-ons > Blender Copilot",
    "description": "Material Graph Code tools for external MCP agents",
    "category": "Node",
}

import bpy
from . import bridge, preferences


def register():
    if bpy.app.version[:2] != (5, 2):
        raise RuntimeError("Blender Copilot requires Blender 5.2.x.")
    preferences.register()
    bpy.types.Material.copilot_graph_code_path = bpy.props.StringProperty(
        name="Graph Code Path", subtype='FILE_PATH', default="")
    try:
        bridge.start()
    except Exception as exc:
        # Keep preferences available so users can resolve a port conflict.
        print(f"Blender Copilot MCP could not start: {exc}")


def unregister():
    bridge.stop()
    del bpy.types.Material.copilot_graph_code_path
    preferences.unregister()
