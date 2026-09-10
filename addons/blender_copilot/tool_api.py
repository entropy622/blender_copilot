"""The only operations reachable from the transport. Call on Blender's main thread."""
import bpy
from . import executor, graph_snapshot as graphs, material_graph_store as store


def get_material(name):
    material = bpy.data.materials.get(name)
    if material is None:
        raise ValueError(f"Material {name!r} does not exist. Use list_materials.")
    if material.library or material.is_library_indirect:
        raise ValueError("Linked library materials are read-only; make a local material first.")
    return material


def status():
    return {"blender_version": bpy.app.version_string, "blend_file": bpy.data.filepath,
            "active_object": bpy.context.active_object.name if bpy.context.active_object else None,
            "graph_code_calls": sorted(set(executor._build_execution_env(executor.MaterialGraphProgram())) - {"__builtins__"}),
            "protocol_version": 1}


def list_materials():
    return {"materials": [{"name": m.name, "use_nodes": m.use_nodes, "users": m.users,
                          "objects": [o.name for o in bpy.data.objects if any(s.material == m for s in o.material_slots)]}
                         for m in bpy.data.materials]}


def get_material_graph(material_name):
    material = get_material(material_name)
    data = graphs.snapshot(material)
    return {"graph": data, "revision": graphs.revision(data), "code": graphs.export_graph(data),
            "source_code": store.read_material_graph(material), "source_path": str(store.get_material_graph_path(material)),
            "export_mode": "existing", "notes": "code reflects the live graph. source_code is the last applied file and may be stale. Existing requires the same nodes; groups and images remain external dependencies."}


def get_node_schema(node_type):
    if not isinstance(node_type, str) or not node_type.startswith("ShaderNode"):
        raise ValueError("Expected a ShaderNode type identifier.")
    material = bpy.data.materials.new("__graph_schema__")
    try:
        material.use_nodes = True
        node = material.node_tree.nodes.new(node_type)
        enum_values = {}
        for prop in node.bl_rna.properties:
            if not prop.identifier.startswith("bl_") and not prop.is_readonly and prop.type == "ENUM":
                enum_values[prop.identifier] = [item.identifier for item in prop.enum_items]
        return {"node_type": node.bl_idname, "inputs": graphs.sockets(node.inputs),
                "outputs": graphs.sockets(node.outputs), "properties": graphs.properties(node),
                "enum_values": enum_values, "notes": "Socket layout is for default properties. Use live graph socket indices after changing modes."}
    finally:
        bpy.data.materials.remove(material)


def validate_graph_code(material_name, code, allow_reset=False):
    material = get_material(material_name)
    program = executor.compile_graph_code(code)
    counts = executor.preflight(program, material, allow_reset)
    return {"valid": True, **counts, "revision": graphs.revision(graphs.snapshot(material))}


def apply_graph_code(material_name, code, expected_revision, allow_reset=False):
    material = get_material(material_name)
    current = graphs.revision(graphs.snapshot(material))
    if expected_revision != current:
        raise ValueError("Material changed since it was read. Call get_material_graph again.")
    try:
        program = executor.compile_graph_code(code)
        executor.preflight(program, material, allow_reset)
    except Exception as exc:
        try:
            draft = store.write_material_graph_draft(material, code)
        except Exception as storage_error:
            raise ValueError(f"{exc}; draft could not be saved: {storage_error}") from exc
        raise ValueError(f"{exc}; original graph unchanged; draft: {draft}") from exc
    # Validate file access before touching the live graph; retain old source for rollback.
    path = store.get_material_graph_path(material)
    previous = path.read_bytes() if path.exists() else None
    store.atomic_write(path, code)
    try:
        executor.apply_program(program, material, allow_reset)
    except Exception as exc:
        if previous is None:
            path.unlink(missing_ok=True)
        else:
            store.atomic_write(path, previous.decode("utf-8"))
        raise RuntimeError(f"Unexpected commit error after successful preflight: {exc}. Read the graph before retrying.") from exc
    material.copilot_graph_code_path = str(path)
    data = graphs.snapshot(material)
    return {"applied": True, "material_name": material.name, "revision": graphs.revision(data),
            "source_path": str(path), "nodes": len(data["nodes"]), "links": len(data["links"])}


def create_material(material_name, code, object_name=""):
    if not isinstance(material_name, str) or not material_name.strip():
        raise ValueError("Material name cannot be empty.")
    if bpy.data.materials.get(material_name):
        raise ValueError(f"Material {material_name!r} already exists.")
    obj = None
    if object_name:
        obj = bpy.data.objects.get(object_name)
        if obj is None or obj.library or not hasattr(obj.data, "materials") or obj.data.library:
            raise ValueError("Target object must exist and have local material slots.")
    program = executor.compile_graph_code(code)
    material = bpy.data.materials.new(material_name)
    try:
        if material.name != material_name:
            raise ValueError("Blender truncated or changed the requested material name.")
        executor.apply_program(program, material, allow_reset=True)
        path = store.write_material_graph(material, code)
        material.use_fake_user = True
        if obj is not None:
            obj.data.materials.append(material)
            obj.active_material_index = len(obj.material_slots) - 1
        data = graphs.snapshot(material)
        return {"created": True, "material_name": material.name, "source_path": path,
                "revision": graphs.revision(data), "object_name": object_name or None}
    except Exception:
        bpy.data.materials.remove(material)
        raise


TOOLS = {function.__name__: function for function in (
    status, list_materials, get_material_graph, get_node_schema,
    validate_graph_code, apply_graph_code, create_material)}


def dispatch(tool, arguments):
    if tool not in TOOLS:
        raise ValueError(f"Unknown tool: {tool!r}")
    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")
    return TOOLS[tool](**arguments)
