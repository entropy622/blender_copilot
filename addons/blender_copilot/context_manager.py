from . import material_graph_store


def _format_value(value):
    try:
        if isinstance(value, float):
            return f"{value:.3f}"
        if hasattr(value, "__len__") and not isinstance(value, str) and len(value) <= 4:
            parts = []
            for item in value:
                if isinstance(item, float):
                    parts.append(f"{item:.3f}")
                else:
                    parts.append(str(item))
            return "(" + ", ".join(parts) + ")"
        return str(value)
    except Exception:
        return "?"


def _node_summary(node):
    fields = [f'- "{node.name}" [{node.bl_idname}]']
    interesting_inputs = []

    for socket in node.inputs:
        if socket.is_linked or not hasattr(socket, "default_value"):
            continue
        if len(interesting_inputs) >= 4:
            break
        interesting_inputs.append(f'{socket.name}={_format_value(socket.default_value)}')

    if interesting_inputs:
        fields.append("  values: " + ", ".join(interesting_inputs))
    return "\n".join(fields)


def _collect_main_links(node_tree):
    summaries = []
    output = node_tree.nodes.get("Material Output")
    if not output:
        return summaries

    for socket in output.inputs:
        for link in socket.links:
            summaries.append(
                f'- "{link.from_node.name}".{link.from_socket.name} -> "{output.name}".{socket.name}'
            )
    return summaries


def get_node_tree_context(node_tree):
    if not node_tree:
        return "No active node tree."

    lines = [
        f"CURRENT MATERIAL NODE TREE: {node_tree.name}",
        "MAIN OUTPUT LINKS:",
    ]

    main_links = _collect_main_links(node_tree)
    if main_links:
        lines.extend(main_links)
    else:
        lines.append("- No output links.")

    lines.append("EXISTING NODES:")
    for node in node_tree.nodes:
        lines.append(_node_summary(node))

    lines.append("GRAPH CODE NOTES:")
    lines.append('- Use ResetMaterial() when the user asks for a brand-new material.')
    lines.append('- Use Existing("Node Name") when editing current nodes.')
    lines.append('- Prefer concise Graph Code over direct bpy access.')
    return "\n".join(lines)


def get_material_context(material):
    lines = [
        get_node_tree_context(material.node_tree if material and material.use_nodes else None),
    ]

    if material:
        graph_path = material_graph_store.ensure_material_graph_file(material)
        graph_code = material_graph_store.read_material_graph(material)
        lines.append(f"CURRENT GRAPH CODE FILE: {graph_path}")
        lines.append("CURRENT GRAPH CODE:")
        lines.append("```python")
        lines.append(graph_code.rstrip())
        lines.append("```")

    return "\n\n".join(lines)
