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

    def draw(self, context):
        layout = self.layout
        layout.label(text="LLM Settings:")
        layout.prop(self, "api_url")
        layout.prop(self, "model_name")
        layout.prop(self, "api_key")

        # 加个简单的说明
        layout.separator()
        layout.label(text="Common Presets (Copy manually):", icon="INFO")
        layout.label(text="DeepSeek: https://api.deepseek.com/chat/completions | deepseek-chat")
        layout.label(text="Moonshot: https://api.moonshot.cn/v1/chat/completions | moonshot-v1-8k")


def register():
    bpy.utils.register_class(COPILOT_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(COPILOT_AddonPreferences)