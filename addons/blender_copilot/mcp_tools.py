"""MCP tool schemas shared by discovery and argument validation."""
import inspect
from . import tool_api

DESCRIPTIONS = {
    "blender_status": "Get Blender version, active object, current file and Graph Code functions.",
    "list_materials": "List materials and their object assignments.",
    "get_material_graph": "Read the LIVE graph, editable Existing Graph Code, last source and revision. Existing exports require the current nodes.",
    "get_node_schema": "Inspect Blender 5.2 shader sockets and writable properties. Use indices for duplicate socket names.",
    "validate_graph_code": "Preflight Graph Code on a temporary material copy; leave live graph and files unchanged.",
    "apply_graph_code": "Check expected_revision, preflight and apply Graph Code. ResetMaterial requires allow_reset=true. Read graph after errors before retrying.",
    "create_material": "Create a new material from Graph Code; optionally append an active material slot to an object. Existing face assignments are unchanged.",
}
FUNCTIONS = {"blender_status": tool_api.status, **{k: v for k, v in tool_api.TOOLS.items() if k != "status"}}
READ_ONLY = {"blender_status", "list_materials", "get_material_graph", "get_node_schema", "validate_graph_code"}


def schemas():
    result = []
    for name, function in FUNCTIONS.items():
        properties, required = {}, []
        for param in inspect.signature(function).parameters.values():
            kind = "boolean" if isinstance(param.default, bool) else "string"
            entry = {"type": kind}
            if param.default is inspect.Parameter.empty:
                required.append(param.name)
            else:
                entry["default"] = param.default
            properties[param.name] = entry
        result.append({"name": name, "description": DESCRIPTIONS[name],
            "inputSchema": {"type": "object", "properties": properties, "required": required, "additionalProperties": False},
            "annotations": {"readOnlyHint": name in READ_ONLY, "openWorldHint": False}})
    return result


def validate_arguments(schema, arguments):
    if not isinstance(arguments, dict):
        raise ValueError("arguments must be an object.")
    fields = schema["inputSchema"]
    if set(arguments) - set(fields["properties"]):
        raise ValueError("Unknown tool argument.")
    for name in fields["required"]:
        if name not in arguments:
            raise ValueError(f"Missing required argument: {name}")
    for name, value in arguments.items():
        expected = bool if fields["properties"][name]["type"] == "boolean" else str
        if not isinstance(value, expected):
            raise ValueError(f"{name} must be {fields['properties'][name]['type']}.")
