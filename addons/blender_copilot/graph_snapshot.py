"""Live graph inspection and non-destructive Graph Code export."""
import hashlib
import json
import math


def literal(value):
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("Non-finite value")
        return value
    if hasattr(value, "to_list"):
        return [literal(item) for item in value.to_list()]
    if isinstance(value, (tuple, list)) or type(value).__name__ in {"Vector", "Color", "bpy_prop_array"}:
        return [literal(item) for item in value]
    raise ValueError("Not a Graph Code literal")


def sockets(collection):
    result = []
    for index, socket in enumerate(collection):
        item = {"index": index, "name": socket.name, "identifier": socket.identifier,
                "type": socket.bl_idname, "linked": socket.is_linked, "enabled": socket.enabled}
        if hasattr(socket, "default_value"):
            try:
                item["value"] = literal(socket.default_value)
            except ValueError:
                item["value_datablock"] = getattr(socket.default_value, "name", None)
        result.append(item)
    return result


def properties(node):
    result = {}
    for prop in node.bl_rna.properties:
        if prop.identifier.startswith("bl_") or prop.identifier == "location_absolute":
            continue
        # Common editor metadata is exported separately; configuration drives socket layouts.
        if prop.identifier in {"rna_type", "name", "label", "location", "dimensions", "width", "height", "select", "color", "use_custom_color"}:
            continue
        if not prop.is_readonly and prop.type in {"BOOLEAN", "INT", "FLOAT", "STRING", "ENUM"}:
            try:
                result[prop.identifier] = literal(getattr(node, prop.identifier))
            except (ValueError, AttributeError):
                pass
    return result


def snapshot(material):
    result = {"material_name": material.name, "use_nodes": material.use_nodes, "nodes": [], "links": []}
    if material.node_tree:
        for node in material.node_tree.nodes:
            item = {"name": node.name, "type": node.bl_idname, "label": node.label,
                    "location": list(node.location), "properties": properties(node),
                    "inputs": sockets(node.inputs), "outputs": sockets(node.outputs)}
            if hasattr(node, "node_tree"):
                item["node_group"] = node.node_tree.name if node.node_tree else None
            if hasattr(node, "image"):
                item["image"] = node.image.name if node.image else None
            if hasattr(node, "color_ramp"):
                ramp = node.color_ramp
                item["color_ramp"] = {"interpolation": ramp.interpolation,
                    "color_mode": ramp.color_mode, "hue_interpolation": ramp.hue_interpolation,
                    "stops": [[element.position, list(element.color)] for element in ramp.elements]}
            result["nodes"].append(item)
        for link in material.node_tree.links:
            result["links"].append({"from_node": link.from_node.name,
                "from_socket": list(link.from_node.outputs).index(link.from_socket),
                "to_node": link.to_node.name, "to_socket": list(link.to_node.inputs).index(link.to_socket)})
    return result


def revision(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def export_graph(data):
    lines = ["# Graph Code: edit this existing material; not a standalone clone.",
             "# Socket indices preserve duplicate socket names. Group internals and external assets stay in Blender."]
    aliases = {}
    for index, node in enumerate(data["nodes"]):
        alias = f"n{index}"
        aliases[node["name"]] = alias
        lines.append(f"{alias} = Existing({node['name']!r}, alias={alias!r}, label={node['label']!r}, location={node['location']!r})")
        for name, value in node["properties"].items():
            lines.append(f"SetProperty({alias}, {name!r}, {value!r})")
        for socket in node["inputs"]:
            if "value" in socket:
                lines.append(f"SetInput({alias}, {socket['index']}, {socket['value']!r})")
        for socket in node["outputs"]:
            if "value" in socket:
                lines.append(f"SetOutput({alias}, {socket['index']}, {socket['value']!r})")
        if "color_ramp" in node:
            ramp = node["color_ramp"]
            lines.append(f"SetColorRamp({alias}, {ramp['stops']!r}, interpolation={ramp['interpolation']!r}, color_mode={ramp['color_mode']!r}, hue_interpolation={ramp['hue_interpolation']!r})")
    for link in data["links"]:
        lines.append(f"Link({aliases[link['from_node']]}, {link['from_socket']}, {aliases[link['to_node']]}, {link['to_socket']})")
    return "\n".join(lines) + "\n"
