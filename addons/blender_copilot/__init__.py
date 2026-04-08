bl_info = {
    "name": "Blender Copilot",
    "author": "Aentro",
    "version": (0, 0, 2),
    "blender": (4, 2, 0),
    "location": "Shader Editor > N-Panel",
    "description": "",
    "category": "Node",
}

import bpy
import importlib
from . import preferences
from . import ui_panel
from . import operators
from . import executor
from . import context_manager

# 自动重载子模块 (开发必备)
importlib.reload(preferences)
importlib.reload(ui_panel)
importlib.reload(context_manager)
importlib.reload(operators)
importlib.reload(executor)


def register():
    # 1. 注册子模块
    preferences.register()
    operators.register()
    ui_panel.register()

    # 2. 在场景中注册一个变量来存用户的输入
    bpy.types.Scene.copilot_prompt_text = bpy.props.StringProperty(
        name="Prompt",
        description="Describe what nodes you want",
        default="Create a red glass material"
    )

    print("AI Copilot V2 Registered")


def unregister():
    ui_panel.unregister()
    operators.unregister()
    preferences.unregister()

    del bpy.types.Scene.copilot_prompt_text
    print("AI Copilot Unregistered")


if __name__ == "__main__":
    register()
