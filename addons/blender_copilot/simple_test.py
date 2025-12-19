import bpy


# 定义一个操作 (Operator) - 相当于按钮背后的函数
class NODE_OT_TestAi(bpy.types.Operator):
    bl_idname = "node.test_ai"
    bl_label = "Test AI Connection"

    def execute(self, context):
        self.report({'INFO'}, "Hello! PyCharm is connected to Blender.")
        return {'FINISHED'}


# 定义一个面板 (Panel) - 相当于侧边栏 UI
class NODE_PT_AiPanel(bpy.types.Panel):
    bl_label = "AI Copilot Dev"
    bl_idname = "NODE_PT_ai_panel"
    bl_space_type = 'NODE_EDITOR'  # 节点编辑器
    bl_region_type = 'UI'  # N-Panel (侧边栏)
    bl_category = "AI Copilot"  # 侧边栏的标签名

    def draw(self, context):
        layout = self.layout
        layout.label(text="Development Mode")
        # 添加按钮调用上面的 Operator
        layout.operator("node.test_ai")


# 注册类
classes = (NODE_OT_TestAi, NODE_PT_AiPanel)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)