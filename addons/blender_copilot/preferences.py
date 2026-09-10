import bpy


class COPILOT_OT_Connection(bpy.types.Operator):
    bl_idname = "copilot.connection"
    bl_label = "MCP Connection"

    action: bpy.props.EnumProperty(items=[
        ("RESTART", "Start / Restart MCP", ""),
        ("STOP", "Stop MCP", ""),
        ("RESET", "Reset Access Token", "Invalidates configurations using the old token"),
        ("CODEX", "Copy Codex Config", ""),
        ("JSON", "Copy MCP JSON", ""),
    ])

    def execute(self, context):
        from . import bridge
        try:
            if self.action in {"CODEX", "JSON"}:
                context.window_manager.clipboard = bridge.config(self.action)
                self.report({'INFO'}, "MCP configuration copied")
            else:
                bridge.stop()
                if self.action == "RESET":
                    bridge.token(reset=True)
                if self.action != "STOP":
                    bridge.start()
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        return {'FINISHED'}


class COPILOT_AddonPreferences(bpy.types.AddonPreferences):
    bl_idname = __package__

    mcp_port: bpy.props.IntProperty(name="MCP Port", default=9877, min=1024, max=65535)
    graph_code_root: bpy.props.StringProperty(
        name="Graph Code Directory", subtype='DIR_PATH', default="",
        description="Default: beside the blend file, or your user directory for unsaved scenes")

    def draw(self, context):
        from . import bridge
        layout = self.layout
        layout.label(text="MCP running" if bridge._server else "MCP stopped", icon='CHECKMARK' if bridge._server else 'ERROR')
        layout.label(text=bridge.address())
        if bridge.last_error:
            layout.label(text=bridge.last_error, icon='ERROR')
        layout.prop(self, "mcp_port")
        layout.label(text="After changing port, restart MCP and copy the new configuration.")
        row = layout.row()
        row.operator("copilot.connection", text="Start / Restart MCP").action = "RESTART"
        row.operator("copilot.connection", text="Stop MCP").action = "STOP"
        row = layout.row()
        row.operator("copilot.connection", text="Copy Codex Config").action = "CODEX"
        row.operator("copilot.connection", text="Copy MCP JSON").action = "JSON"
        layout.operator("copilot.connection", text="Reset Access Token").action = "RESET"
        layout.prop(self, "graph_code_root")


def register():
    bpy.utils.register_class(COPILOT_OT_Connection)
    bpy.utils.register_class(COPILOT_AddonPreferences)


def unregister():
    bpy.utils.unregister_class(COPILOT_AddonPreferences)
    bpy.utils.unregister_class(COPILOT_OT_Connection)
