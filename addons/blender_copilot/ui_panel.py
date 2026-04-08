import bpy

from . import material_graph_store
from . import operators


class NODE_PT_CopilotPanel(bpy.types.Panel):
    bl_label = "AI Copilot"
    bl_idname = "NODE_PT_copilot_main"
    bl_space_type = "NODE_EDITOR"
    bl_region_type = "UI"
    bl_category = "AI Copilot"

    def draw(self, context):
        layout = self.layout
        scene = context.scene
        is_thinking = operators.state.is_processing

        layout.label(text="Description:")
        input_col = layout.column(align=True)
        input_col.enabled = not is_thinking
        input_col.prop(scene, "copilot_prompt_text", text="")

        obj = context.active_object
        if obj and obj.active_material:
            material = obj.active_material
            graph_path = material_graph_store.get_material_graph_path(material)
            box = layout.box()
            box.label(text=f"Material: {material.name}")
            box.label(text="Graph Code File:")
            box.label(text=graph_path)

        layout.separator()

        if is_thinking:
            row = layout.row(align=True)
            row.enabled = False
            row.label(text="AI is thinking...", icon="TIME")
        else:
            layout.operator("node.send_prompt_to_llm", text="Generate Nodes", icon="SHADING_RENDERED")


def register():
    bpy.utils.register_class(NODE_PT_CopilotPanel)


def unregister():
    bpy.utils.unregister_class(NODE_PT_CopilotPanel)
