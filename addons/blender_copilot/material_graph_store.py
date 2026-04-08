import os
import re

import bpy


DEFAULT_GRAPH_CODE = """# Material Graph Code
ResetMaterial()

output = OutputMaterial()
surface = PrincipledBSDF(
    alias="surface",
    base_color=(0.8, 0.8, 0.8, 1.0),
    roughness=0.5,
)
Link(surface, "BSDF", output, "Surface")
"""


def _safe_name(value):
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", value.strip())
    safe = safe.strip("._")
    return safe or "material"


def _get_addon_preferences():
    addon_name = __package__.split(".")[0]
    addon = bpy.context.preferences.addons.get(addon_name)
    return addon.preferences if addon else None


def get_graph_code_root():
    prefs = _get_addon_preferences()
    if prefs and getattr(prefs, "graph_code_root", "").strip():
        return bpy.path.abspath(prefs.graph_code_root)

    if bpy.data.filepath:
        blend_dir = os.path.dirname(bpy.data.filepath)
        return os.path.join(blend_dir, "blender_copilot_graphs")

    return os.path.join(os.path.dirname(__file__), "_material_graphs")


def get_material_graph_path(material):
    bound_path = getattr(material, "copilot_graph_code_path", "").strip()
    if bound_path:
        return bpy.path.abspath(bound_path)

    filename = f"{_safe_name(material.name)}.py"
    return os.path.join(get_graph_code_root(), filename)


def bind_material_graph(material):
    path = get_material_graph_path(material)
    material.copilot_graph_code_path = path
    return path


def _bootstrap_from_existing_material(material):
    lines = [
        f"# Material Graph Code for {material.name}",
        "# Bootstrapped from the current Blender material.",
        "# Use Existing(...) to modify the current graph, or ResetMaterial() to replace it.",
        "",
    ]

    nodes = material.node_tree.nodes if material.use_nodes and material.node_tree else None
    if not nodes:
        lines.append(DEFAULT_GRAPH_CODE.strip())
        return "\n".join(lines) + "\n"

    output = nodes.get("Material Output")
    principled = nodes.get("Principled BSDF")

    if output:
        lines.append('output = Existing("Material Output", alias="output")')
    if principled:
        lines.append('surface = Existing("Principled BSDF", alias="surface")')
        lines.append("")
        lines.append("# Example edits:")
        lines.append('# SetInput(surface, "Base Color", (0.8, 0.4, 0.2, 1.0))')
        lines.append('# SetInput(surface, "Roughness", 0.6)')
    else:
        lines.append(DEFAULT_GRAPH_CODE.strip())

    return "\n".join(lines).strip() + "\n"


def ensure_material_graph_file(material):
    path = bind_material_graph(material)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if not os.path.exists(path):
        initial_code = _bootstrap_from_existing_material(material)
        with open(path, "w", encoding="utf-8") as file:
            file.write(initial_code)

    return path


def read_material_graph(material):
    path = ensure_material_graph_file(material)
    with open(path, "r", encoding="utf-8") as file:
        return file.read()


def write_material_graph(material, code_str):
    path = ensure_material_graph_file(material)
    with open(path, "w", encoding="utf-8") as file:
        file.write(code_str.rstrip() + "\n")
    return path


def write_material_graph_draft(material, code_str):
    path = ensure_material_graph_file(material)
    draft_path = path + ".draft.py"
    with open(draft_path, "w", encoding="utf-8") as file:
        file.write(code_str.rstrip() + "\n")
    return draft_path
