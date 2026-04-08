import ast
import re
from dataclasses import dataclass, field


def clean_code_string(ai_response):
    pattern = r"```(?:python)?\s*(.*?)```"
    match = re.search(pattern, ai_response, re.DOTALL)
    if match:
        return match.group(1).strip()
    return ai_response.strip()


class GraphCodeValidationError(ValueError):
    pass


@dataclass
class NodeHandle:
    alias: str


@dataclass
class NodeSpec:
    alias: str
    node_type: str
    name: str | None = None
    label: str | None = None
    location: tuple[float, float] | None = None
    mode: str = "create"
    input_values: dict[str, object] = field(default_factory=dict)
    property_values: dict[str, object] = field(default_factory=dict)
    color_ramp: dict[str, object] | None = None


@dataclass
class LinkSpec:
    from_alias: str
    from_socket: str
    to_alias: str
    to_socket: str


class MaterialGraphProgram:
    DEFAULT_LOCATIONS = {
        "output": (420.0, 0.0),
        "shader": (120.0, 0.0),
        "convert": (-180.0, 0.0),
        "texture": (-500.0, 0.0),
        "input": (-780.0, 0.0),
        "utility": (-140.0, -260.0),
    }

    NODE_KIND_BY_TYPE = {
        "ShaderNodeOutputMaterial": "output",
        "ShaderNodeBsdfPrincipled": "shader",
        "ShaderNodeBsdfDiffuse": "shader",
        "ShaderNodeBsdfGlossy": "shader",
        "ShaderNodeEmission": "shader",
        "ShaderNodeMixShader": "shader",
        "ShaderNodeBsdfTransparent": "shader",
        "ShaderNodeShaderToRGB": "convert",
        "ShaderNodeValToRGB": "convert",
        "ShaderNodeRGBCurve": "convert",
        "ShaderNodeHueSaturation": "convert",
        "ShaderNodeBump": "utility",
        "ShaderNodeFresnel": "utility",
        "ShaderNodeLayerWeight": "utility",
        "ShaderNodeMath": "utility",
        "ShaderNodeMixRGB": "utility",
        "ShaderNodeTexNoise": "texture",
        "ShaderNodeTexVoronoi": "texture",
        "ShaderNodeTexCoord": "input",
        "ShaderNodeMapping": "input",
        "ShaderNodeRGB": "input",
        "ShaderNodeValue": "input",
    }

    SOCKET_ALIASES = {
        "ShaderNodeBsdfPrincipled": {
            "base_color": "Base Color",
            "metallic": "Metallic",
            "roughness": "Roughness",
            "ior": "IOR",
            "alpha": "Alpha",
            "normal": "Normal",
            "coat_weight": "Coat Weight",
            "coat_roughness": "Coat Roughness",
            "emission_color": "Emission Color",
            "emission_strength": "Emission Strength",
            "transmission_weight": "Transmission Weight",
            "specular_ior_level": "Specular IOR Level",
        },
        "ShaderNodeBsdfDiffuse": {
            "color": "Color",
            "roughness": "Roughness",
            "normal": "Normal",
        },
        "ShaderNodeBsdfGlossy": {
            "color": "Color",
            "roughness": "Roughness",
            "normal": "Normal",
        },
        "ShaderNodeEmission": {
            "color": "Color",
            "strength": "Strength",
        },
        "ShaderNodeMixShader": {
            "factor": "Fac",
            "fac": "Fac",
            "shader_1": "Shader",
            "shader_2": "Shader_001",
        },
        "ShaderNodeValToRGB": {
            "factor": "Fac",
            "fac": "Fac",
        },
        "ShaderNodeTexNoise": {
            "vector": "Vector",
            "scale": "Scale",
            "detail": "Detail",
            "roughness": "Roughness",
            "distortion": "Distortion",
        },
        "ShaderNodeTexVoronoi": {
            "vector": "Vector",
            "scale": "Scale",
            "randomness": "Randomness",
        },
        "ShaderNodeBump": {
            "strength": "Strength",
            "distance": "Distance",
            "height": "Height",
            "normal": "Normal",
        },
        "ShaderNodeFresnel": {
            "ior": "IOR",
            "normal": "Normal",
        },
        "ShaderNodeLayerWeight": {
            "blend": "Blend",
            "normal": "Normal",
        },
        "ShaderNodeMath": {
            "value": "Value",
            "value_1": "Value",
            "value_2": "Value_001",
        },
        "ShaderNodeMixRGB": {
            "factor": "Fac",
            "fac": "Fac",
            "color_1": "Color1",
            "color_2": "Color2",
        },
        "ShaderNodeMapping": {
            "vector": "Vector",
            "location": "Location",
            "rotation": "Rotation",
            "scale": "Scale",
        },
        "ShaderNodeOutputMaterial": {
            "surface": "Surface",
            "volume": "Volume",
            "displacement": "Displacement",
        },
        "ShaderNodeRGB": {
            "color": "Color",
        },
        "ShaderNodeValue": {
            "value": "Value",
        },
        "ShaderNodeShaderToRGB": {
            "shader": "Shader",
        },
        "ShaderNodeBsdfTransparent": {
            "color": "Color",
        },
    }

    NODE_PROPERTIES = {
        "ShaderNodeValToRGB": {"interpolation"},
        "ShaderNodeMath": {"operation"},
        "ShaderNodeMixRGB": {"blend_type"},
        "ShaderNodeMapping": {"vector_type"},
        "ShaderNodeTexVoronoi": {"feature", "distance"},
    }

    def __init__(self):
        self.node_specs: list[NodeSpec] = []
        self.links: list[LinkSpec] = []
        self.clear_requested = False
        self._alias_counts: dict[str, int] = {}
        self._layout_counts: dict[str, int] = {}
        self._known_aliases: set[str] = set()

    def reset_material(self):
        self.clear_requested = True

    def existing_node(self, name, alias=None):
        alias = alias or self._make_alias(name)
        spec = NodeSpec(alias=alias, node_type="", name=name, mode="existing")
        self.node_specs.append(spec)
        self._known_aliases.add(alias)
        return NodeHandle(alias)

    def node(self, node_type, alias=None, name=None, label=None, location=None, ensure=False, **kwargs):
        alias = alias or self._make_alias(name or node_type)
        mode = "ensure" if ensure else "create"
        spec = NodeSpec(
            alias=alias,
            node_type=node_type,
            name=name,
            label=label,
            location=self._normalize_location(location) if location is not None else None,
            mode=mode,
        )
        self._apply_kwargs_to_spec(spec, kwargs)
        self.node_specs.append(spec)
        self._known_aliases.add(alias)
        return NodeHandle(alias)

    def ensure_node(self, node_type, name, alias=None, label=None, location=None, **kwargs):
        return self.node(node_type, alias=alias, name=name, label=label, location=location, ensure=True, **kwargs)

    def output_material(self, alias="output", name="Material Output", **kwargs):
        return self.ensure_node("ShaderNodeOutputMaterial", name=name, alias=alias, **kwargs)

    def principled_bsdf(self, alias="principled", name="Principled BSDF", **kwargs):
        return self.ensure_node("ShaderNodeBsdfPrincipled", name=name, alias=alias, **kwargs)

    def diffuse_bsdf(self, alias="diffuse", name="Diffuse BSDF", **kwargs):
        return self.node("ShaderNodeBsdfDiffuse", alias=alias, name=name, **kwargs)

    def glossy_bsdf(self, alias="glossy", name="Glossy BSDF", **kwargs):
        return self.node("ShaderNodeBsdfGlossy", alias=alias, name=name, **kwargs)

    def emission(self, alias="emission", name="Emission", **kwargs):
        return self.node("ShaderNodeEmission", alias=alias, name=name, **kwargs)

    def transparent_bsdf(self, alias="transparent", name="Transparent BSDF", **kwargs):
        return self.node("ShaderNodeBsdfTransparent", alias=alias, name=name, **kwargs)

    def mix_shader(self, alias="mix_shader", name="Mix Shader", **kwargs):
        return self.node("ShaderNodeMixShader", alias=alias, name=name, **kwargs)

    def shader_to_rgb(self, alias="shader_to_rgb", name="Shader to RGB", **kwargs):
        return self.node("ShaderNodeShaderToRGB", alias=alias, name=name, **kwargs)

    def color_ramp(self, alias="color_ramp", name="Color Ramp", stops=None, interpolation=None, **kwargs):
        spec = NodeSpec(
            alias=alias,
            node_type="ShaderNodeValToRGB",
            name=name,
            mode="create",
        )
        if interpolation is not None:
            spec.property_values["interpolation"] = interpolation
        if stops is not None:
            spec.color_ramp = {"stops": stops}
        self._apply_kwargs_to_spec(spec, kwargs)
        self.node_specs.append(spec)
        self._known_aliases.add(alias)
        return NodeHandle(alias)

    def noise_texture(self, alias="noise", name="Noise Texture", **kwargs):
        return self.node("ShaderNodeTexNoise", alias=alias, name=name, **kwargs)

    def voronoi_texture(self, alias="voronoi", name="Voronoi Texture", **kwargs):
        return self.node("ShaderNodeTexVoronoi", alias=alias, name=name, **kwargs)

    def bump(self, alias="bump", name="Bump", **kwargs):
        return self.node("ShaderNodeBump", alias=alias, name=name, **kwargs)

    def fresnel(self, alias="fresnel", name="Fresnel", **kwargs):
        return self.node("ShaderNodeFresnel", alias=alias, name=name, **kwargs)

    def layer_weight(self, alias="layer_weight", name="Layer Weight", **kwargs):
        return self.node("ShaderNodeLayerWeight", alias=alias, name=name, **kwargs)

    def mix_rgb(self, alias="mix_rgb", name="Mix", **kwargs):
        return self.node("ShaderNodeMixRGB", alias=alias, name=name, **kwargs)

    def math(self, alias="math", name="Math", **kwargs):
        return self.node("ShaderNodeMath", alias=alias, name=name, **kwargs)

    def mapping(self, alias="mapping", name="Mapping", **kwargs):
        return self.node("ShaderNodeMapping", alias=alias, name=name, **kwargs)

    def texture_coordinate(self, alias="tex_coord", name="Texture Coordinate", **kwargs):
        return self.node("ShaderNodeTexCoord", alias=alias, name=name, **kwargs)

    def rgb(self, alias="rgb", name="RGB", **kwargs):
        return self.node("ShaderNodeRGB", alias=alias, name=name, **kwargs)

    def value(self, alias="value", name="Value", **kwargs):
        return self.node("ShaderNodeValue", alias=alias, name=name, **kwargs)

    def connect(self, from_node, from_socket, to_node, to_socket):
        from_alias = self._coerce_alias(from_node)
        to_alias = self._coerce_alias(to_node)
        self.links.append(LinkSpec(from_alias, from_socket, to_alias, to_socket))

    def set_input(self, node_handle, socket_name, value):
        alias = self._coerce_alias(node_handle)
        spec = self._get_or_create_patch_spec(alias)
        spec.input_values[socket_name] = value

    def set_property(self, node_handle, property_name, value):
        alias = self._coerce_alias(node_handle)
        spec = self._get_or_create_patch_spec(alias)
        spec.property_values[property_name] = value

    def _get_or_create_patch_spec(self, alias):
        for spec in reversed(self.node_specs):
            if spec.alias == alias:
                return spec
        spec = NodeSpec(alias=alias, node_type="", name=alias, mode="existing")
        self.node_specs.append(spec)
        return spec

    def _apply_kwargs_to_spec(self, spec, kwargs):
        for key, value in kwargs.items():
            normalized = self._normalize_key(key)
            if normalized == "location":
                spec.location = self._normalize_location(value)
                continue
            if normalized == "label":
                spec.label = value
                continue
            if normalized == "name":
                spec.name = value
                continue

            property_names = self.NODE_PROPERTIES.get(spec.node_type, set())
            if normalized in property_names:
                spec.property_values[normalized] = value
                continue

            socket_name = self.SOCKET_ALIASES.get(spec.node_type, {}).get(normalized)
            if socket_name is None:
                socket_name = self._humanize_socket_name(key)
            spec.input_values[socket_name] = value

    def _normalize_key(self, value):
        return str(value).strip().lower().replace(" ", "_")

    def _humanize_socket_name(self, value):
        parts = str(value).replace("-", "_").split("_")
        return " ".join(part.capitalize() if part else part for part in parts)

    def _normalize_location(self, value):
        if not isinstance(value, (tuple, list)) or len(value) != 2:
            raise GraphCodeValidationError("location must be a 2-item tuple/list.")
        return (float(value[0]), float(value[1]))

    def _make_alias(self, seed):
        base = re.sub(r"[^a-zA-Z0-9_]+", "_", str(seed).strip().lower()).strip("_") or "node"
        count = self._alias_counts.get(base, 0)
        self._alias_counts[base] = count + 1
        return base if count == 0 else f"{base}_{count}"

    def _coerce_alias(self, node_ref):
        if isinstance(node_ref, NodeHandle):
            return node_ref.alias
        if isinstance(node_ref, str):
            return node_ref
        raise GraphCodeValidationError("Node references must be a node handle or alias string.")

    def ensure_locations(self):
        for spec in self.node_specs:
            if spec.location is not None:
                continue
            kind = self.NODE_KIND_BY_TYPE.get(spec.node_type, "utility")
            x_pos, y_pos = self.DEFAULT_LOCATIONS.get(kind, self.DEFAULT_LOCATIONS["utility"])
            index = self._layout_counts.get(kind, 0)
            self._layout_counts[kind] = index + 1
            spec.location = (x_pos, y_pos - index * 220.0)


ALLOWED_AST_NODES = (
    ast.Module,
    ast.Assign,
    ast.Expr,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Constant,
    ast.Tuple,
    ast.List,
    ast.Dict,
    ast.keyword,
    ast.UnaryOp,
    ast.USub,
)


def _validate_graph_code(code_str):
    try:
        tree = ast.parse(code_str, mode="exec")
    except SyntaxError as exc:
        raise GraphCodeValidationError(f"Graph Code syntax error: {exc}") from exc

    for node in ast.walk(tree):
        if not isinstance(node, ALLOWED_AST_NODES):
            raise GraphCodeValidationError(f"Unsupported syntax in Graph Code: {type(node).__name__}")


def _build_execution_env(program):
    return {
        "__builtins__": {},
        "graph": program,
        "ResetMaterial": program.reset_material,
        "Existing": program.existing_node,
        "Node": program.node,
        "EnsureNode": program.ensure_node,
        "OutputMaterial": program.output_material,
        "PrincipledBSDF": program.principled_bsdf,
        "DiffuseBSDF": program.diffuse_bsdf,
        "GlossyBSDF": program.glossy_bsdf,
        "Emission": program.emission,
        "TransparentBSDF": program.transparent_bsdf,
        "MixShader": program.mix_shader,
        "ShaderToRGB": program.shader_to_rgb,
        "ColorRamp": program.color_ramp,
        "NoiseTexture": program.noise_texture,
        "VoronoiTexture": program.voronoi_texture,
        "Bump": program.bump,
        "Fresnel": program.fresnel,
        "LayerWeight": program.layer_weight,
        "MixRGB": program.mix_rgb,
        "Math": program.math,
        "Mapping": program.mapping,
        "TextureCoordinate": program.texture_coordinate,
        "RGB": program.rgb,
        "Value": program.value,
        "Link": program.connect,
        "SetInput": program.set_input,
        "SetProperty": program.set_property,
    }


def _resolve_socket_name(sockets, desired_name):
    socket = sockets.get(desired_name)
    if socket:
        return desired_name

    normalized_desired = re.sub(r"[^a-z0-9]+", "", desired_name.lower())
    for socket in sockets:
        normalized_socket = re.sub(r"[^a-z0-9]+", "", socket.name.lower())
        if normalized_socket == normalized_desired:
            return socket.name

    raise GraphCodeValidationError(f"Socket '{desired_name}' was not found.")


def _apply_color_ramp(node, ramp_spec):
    if not ramp_spec:
        return

    stops = ramp_spec.get("stops") or []
    color_ramp = node.color_ramp

    while len(color_ramp.elements) > 1:
        color_ramp.elements.remove(color_ramp.elements[-1])

    first_stop = stops[0] if stops else (0.0, (0.0, 0.0, 0.0, 1.0))
    color_ramp.elements[0].position = float(first_stop[0])
    color_ramp.elements[0].color = tuple(first_stop[1])

    for position, color in stops[1:]:
        element = color_ramp.elements.new(float(position))
        element.color = tuple(color)


def _apply_spec_to_node(node_tree, node_cache, spec):
    import bpy

    nodes = node_tree.nodes

    if spec.mode == "existing":
        node = nodes.get(spec.name or spec.alias)
        if not node:
            raise GraphCodeValidationError(f"Existing node '{spec.name or spec.alias}' was not found.")
    elif spec.mode == "ensure":
        node = nodes.get(spec.name or spec.alias)
        if not node:
            node = nodes.new(spec.node_type)
    else:
        node = nodes.new(spec.node_type)

    if spec.name:
        node.name = spec.name
    if spec.label is not None:
        node.label = spec.label
    if spec.location is not None:
        node.location = spec.location

    for property_name, value in spec.property_values.items():
        if hasattr(node, property_name):
            setattr(node, property_name, value)

    for socket_name, value in spec.input_values.items():
        if isinstance(value, NodeHandle):
            continue
        resolved_socket_name = _resolve_socket_name(node.inputs, socket_name)
        socket = node.inputs[resolved_socket_name]
        if hasattr(socket, "default_value"):
            socket.default_value = value

    if spec.node_type == "ShaderNodeValToRGB":
        _apply_color_ramp(node, spec.color_ramp)

    node_cache[spec.alias] = node
    return node


def _apply_links(node_tree, node_cache, program):
    links = node_tree.links

    for spec in program.node_specs:
        target_node = node_cache.get(spec.alias)
        if not target_node:
            continue
        for socket_name, value in spec.input_values.items():
            if not isinstance(value, NodeHandle):
                continue
            source_node = node_cache.get(value.alias)
            if not source_node:
                raise GraphCodeValidationError(f"Source node alias '{value.alias}' is missing.")

            source_socket_name = source_node.outputs[0].name
            target_socket_name = _resolve_socket_name(target_node.inputs, socket_name)
            target_socket = target_node.inputs[target_socket_name]
            for old_link in list(target_socket.links):
                links.remove(old_link)
            links.new(source_node.outputs[source_socket_name], target_socket)

    for link_spec in program.links:
        from_node = node_cache.get(link_spec.from_alias)
        to_node = node_cache.get(link_spec.to_alias)
        if not from_node or not to_node:
            raise GraphCodeValidationError("A link references a missing node alias.")

        from_socket_name = _resolve_socket_name(from_node.outputs, link_spec.from_socket)
        to_socket_name = _resolve_socket_name(to_node.inputs, link_spec.to_socket)
        target_socket = to_node.inputs[to_socket_name]
        for old_link in list(target_socket.links):
            links.remove(old_link)
        links.new(from_node.outputs[from_socket_name], target_socket)


def execute_generated_code(code_str, material_name):
    import bpy

    material = bpy.data.materials.get(material_name)
    if not material:
        print(f"Error: Material '{material_name}' not found!")
        return False

    if not material.use_nodes:
        material.use_nodes = True

    _validate_graph_code(code_str)

    program = MaterialGraphProgram()
    execution_env = _build_execution_env(program)

    try:
        exec(code_str, execution_env, {})
    except Exception as exc:
        print(f"Graph Code runtime error: {exc}")
        import traceback
        traceback.print_exc()
        return False

    program.ensure_locations()

    node_tree = material.node_tree
    nodes = node_tree.nodes

    if program.clear_requested:
        nodes.clear()

    node_cache = {}

    try:
        for spec in program.node_specs:
            _apply_spec_to_node(node_tree, node_cache, spec)

        _apply_links(node_tree, node_cache, program)
        node_tree.nodes.update()
        return True
    except Exception as exc:
        print(f"Graph Code execution error: {exc}")
        import traceback
        traceback.print_exc()
        return False
