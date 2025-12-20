import bpy
from . import operators  # 导入 operators 以访问 state


class NODE_PT_CopilotPanel(bpy.types.Panel):
    bl_label = "AI Copilot"
    bl_idname = "NODE_PT_copilot_main"
    bl_space_type = 'NODE_EDITOR'
    bl_region_type = 'UI'
    bl_category = "AI Copilot"

    def draw(self, context):
        layout = self.layout
        scene = context.scene

        # 引用全局状态
        is_thinking = operators.state.is_processing

        # --- 输入区域 ---
        layout.label(text="Description:")
        col = layout.column(align=True)
        # 如果正在思考，禁用输入框
        col.enabled = not is_thinking
        col.prop(scene, "copilot_prompt_text", text="")

        layout.separator()

        # --- 按钮区域 ---
        if is_thinking:
            # 显示加载状态
            row = layout.row(align=True)
            row.enabled = False  # 按钮变灰
            row.label(text="AI is thinking...", icon="TIME")
        else:
            # 显示发送按钮
            layout.operator("node.send_prompt_to_llm", text="Generate Nodes", icon="SHADING_RENDERED")


def register():
    bpy.utils.register_class(NODE_PT_CopilotPanel)


def unregister():
    bpy.utils.unregister_class(NODE_PT_CopilotPanel)