import bpy


class COPILOT_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    api_key: bpy.props.StringProperty(
        name="API Key",
        description="Enter your API Key (e.g., sk-...)",
        subtype='PASSWORD',
    )

    # 新增：允许自定义 API 地址
    api_url: bpy.props.StringProperty(
        name="API URL",
        description="Full URL for chat completions",
        default="https://api.openai.com/v1/chat/completions"
    )

    # 新增：允许自定义模型名称
    model_name: bpy.props.StringProperty(
        name="Model Name",
        description="e.g., gpt-4o, deepseek-chat, moonshot-v1-8k",
        default="gpt-4o-mini"
    )

    graph_code_root: bpy.props.StringProperty(
        name="Graph Code Root",
        description="Optional directory for persistent Material Graph Code files. Leave blank to store beside the .blend file.",
        subtype='DIR_PATH',
        default=""
    )

    def draw(self, context):
        layout = self.layout
        layout.label(text="LLM Settings:")
        layout.prop(self, "api_url")
        layout.prop(self, "model_name")
        layout.prop(self, "api_key")
        layout.separator()
        layout.label(text="Graph Code Storage:")
        layout.prop(self, "graph_code_root")


def register():
    bpy.utils.register_class(COPILOT_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(COPILOT_AddonPreferences)
