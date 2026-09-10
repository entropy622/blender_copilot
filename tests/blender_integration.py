"""Run in Blender 5.2: --background --factory-startup --python this_file."""
import os
from pathlib import Path
import sys
import tempfile
from concurrent.futures import Future

import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "addons"))
os.environ["BLENDER_COPILOT_PORT"] = "19878"
state_directory = tempfile.TemporaryDirectory()
os.environ["BLENDER_COPILOT_STATE_DIR"] = state_directory.name
import blender_copilot
from blender_copilot import tool_api as api, graph_snapshot as graphs, executor

CODE = '''ResetMaterial()
output = OutputMaterial()
noise = NoiseTexture(scale=6.0)
ramp = ColorRamp(stops=[(0.0, (0.1, 0.05, 0.02, 1.0)), (1.0, (0.8, 0.4, 0.1, 1.0))], interpolation="CONSTANT")
surface = PrincipledBSDF(metallic=0.8, roughness=0.3)
Link(noise, "Fac", ramp, "Fac")
Link(ramp, "Color", surface, "Base Color")
Link(surface, "BSDF", output, "Surface")
'''


def expect_error(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except Exception:
        return
    raise AssertionError("Expected failure")


blender_copilot.register()
try:
    assert not hasattr(bpy.types.Scene, "copilot_prompt_text")
    with tempfile.TemporaryDirectory() as directory:
        # Store beside a temporary blend path, without writing the user's scene.
        bpy.ops.wm.save_as_mainfile(filepath=str(Path(directory) / "test.blend"))
        result = api.create_material("测试铜", CODE, "Cube")
        material = bpy.data.materials[result["material_name"]]
        assert bpy.data.objects["Cube"].active_material == material
        assert len(material.node_tree.nodes) == 4
        assert material.node_tree.nodes["Color Ramp"].color_ramp.interpolation == "CONSTANT"
        live = api.get_material_graph(material.name)
        before = graphs.snapshot(material)
        count = len(bpy.data.materials)
        api.validate_graph_code(material.name, live["code"])
        assert len(bpy.data.materials) == count
        assert graphs.snapshot(material) == before
        api.apply_graph_code(material.name, live["code"], live["revision"])
        assert graphs.snapshot(material) == before, "Existing export must replay without moving nodes or losing links"
        source = Path(live["source_path"]).read_bytes()
        bad = CODE + '\nSetInput(surface, "NoSuchSocket", 1.0)\n'
        expect_error(api.apply_graph_code, material.name, bad, live["revision"], True)
        assert graphs.snapshot(material) == before
        assert Path(live["source_path"]).read_bytes() == source
        assert Path(live["source_path"] + ".draft.py").exists()
        expect_error(api.validate_graph_code, material.name, CODE)
        expect_error(api.apply_graph_code, material.name, CODE, "stale", True)
        for invalid in ['import os', 'x = __builtins__', 'x = OutputMaterial.__class__', 'OutputMaterial = 1', 'x = 1\nx()', 'for x in []: pass', 'SetProperty(OutputMaterial(), "not_a_property", 1)']:
            expect_error(api.validate_graph_code, material.name, invalid)
        math = api.get_node_schema("ShaderNodeMath")
        assert len([s for s in math["inputs"] if s["name"] == "Value"]) >= 2
        code = '''ResetMaterial()
a = Math(operation="MULTIPLY")
SetInput(a, 0, 2.0)
SetInput(a, 1, 3.0)
v = Value(value=0.7)
Link(v, 0, a, 1)
'''
        api.apply_graph_code(material.name, code, live["revision"], True)
        math_node = material.node_tree.nodes["Math"]
        assert math_node.inputs[0].default_value == 2.0
        assert math_node.inputs[1].is_linked and not math_node.inputs[0].is_linked
        live = api.get_material_graph(material.name)
        api.validate_graph_code(material.name, live["code"])
        # Existing group references must survive roundtrip with exposed input values.
        group = bpy.data.node_groups.new("ExternalShaderGroup", "ShaderNodeTree")
        group.interface.new_socket(name="Tint", in_out="INPUT", socket_type="NodeSocketColor")
        node = material.node_tree.nodes.new("ShaderNodeGroup")
        node.node_tree = group
        node.inputs[0].default_value = (0.2, 0.4, 0.6, 1.0)
        node.location = (725, 125)
        live = api.get_material_graph(material.name)
        api.apply_graph_code(material.name, live["code"], live["revision"])
        assert node.node_tree == group and tuple(node.location) == (725, 125)
        # Fail creation without leaving a material behind.
        expect_error(api.create_material, "Failed", 'Node("NotANode")')
        assert bpy.data.materials.get("Failed") is None
        expect_error(api.create_material, material.name, CODE)
        # A cancelled, queued request must never mutate Blender later.
        cancelled = Future()
        cancelled.cancel()
        blender_copilot.bridge._pending.put(({"tool": "create_material", "arguments": {"material_name": "Cancelled", "code": CODE}}, cancelled))
        blender_copilot.bridge.drain()
        assert bpy.data.materials.get("Cancelled") is None
        # Compile and render the shipped shader example with the real renderer.
        example = (root / "examples/copper.py").read_text(encoding="utf-8")
        api.create_material("ExampleCopper", example, "Cube")
        bpy.context.scene.render.engine = "CYCLES"
        bpy.context.scene.cycles.device = "CPU"
        bpy.context.scene.cycles.samples = 4
        bpy.context.scene.render.resolution_x = 64
        bpy.context.scene.render.resolution_y = 64
        bpy.context.scene.render.resolution_percentage = 100
        bpy.context.scene.render.filepath = str(Path(directory) / "copper.png")
        bpy.ops.render.render(write_still=True)
        assert (Path(directory) / "copper.png").stat().st_size > 100
        print("BLENDER_INTEGRATION_OK", bpy.app.version_string)
finally:
    blender_copilot.unregister()
    assert not bpy.app.timers.is_registered(blender_copilot.bridge.drain)
    assert not blender_copilot.bridge.connection_path().exists()
    state_directory.cleanup()
