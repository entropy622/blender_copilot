"""Real SDK client -> packaged Blender add-on HTTP MCP, without external server."""
import asyncio
import json
import os
from pathlib import Path
import httpx
from zipfile import ZipFile
import subprocess
import sys
import tempfile
import time
import unittest

from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]
BLENDER = os.environ.get("BLENDER_EXECUTABLE", "blender")


class MCPIntegration(unittest.TestCase):
    def test_real_agent_workflow(self):
        with tempfile.TemporaryDirectory() as directory:
            addon_dir = Path(directory) / "addons"
            with ZipFile(ROOT / "dist/blender_copilot-0.4.0.zip") as archive:
                archive.extractall(addon_dir)
            env = dict(os.environ, BLENDER_COPILOT_PORT="19879", BLENDER_COPILOT_TEST_DIR=directory,
                       BLENDER_COPILOT_STATE_DIR=directory, BLENDER_COPILOT_ADDON_DIR=str(addon_dir))
            with open(Path(directory) / "blender.log", "w", encoding="utf-8") as log:
                process = subprocess.Popen([BLENDER, "--background", "--factory-startup", "--python-exit-code", "1", "--python", str(ROOT / "tests/blender_host.py")], env=env, stdout=log, stderr=subprocess.STDOUT)
                try:
                    deadline = time.monotonic() + 40
                    while not (Path(directory) / "ready").exists():
                        if process.poll() is not None or time.monotonic() > deadline:
                            self.fail("Blender failed to start: " + (Path(directory) / "blender.log").read_text(encoding="utf-8"))
                        time.sleep(0.1)
                    connection = json.loads((Path(directory) / "bridge-19879.json").read_text())
                    headers = {"Authorization": "Bearer " + connection["token"], "Accept": "application/json, text/event-stream"}
                    url = connection["url"]
                    self.assertEqual(httpx.post(url, json={}, trust_env=False).status_code, 401)
                    for method in [httpx.get, httpx.delete]:
                        self.assertEqual(method(url, headers=headers, trust_env=False).status_code, 405)
                    self.assertEqual(httpx.post(url, headers={**headers, "Origin": "https://evil.example"}, json={}, trust_env=False).status_code, 403)
                    self.assertEqual(httpx.post(url, headers={**headers, "MCP-Protocol-Version": "invalid"}, json={}, trust_env=False).status_code, 400)
                    self.assertEqual(httpx.post(url, headers=headers, json={"jsonrpc": "2.0", "method": "notifications/initialized"}, trust_env=False).status_code, 202)
                    self.assertEqual(httpx.post(url, headers=headers, json=[], trust_env=False).status_code, 400)
                    response = httpx.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": {"name": "missing"}}, trust_env=False)
                    self.assertEqual(response.json()["error"]["code"], -32602)
                    response = httpx.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 3, "method": "tools/call", "params": {"name": "validate_graph_code", "arguments": {"material_name": "Material", "code": "x", "allow_reset": "false"}}}, trust_env=False)
                    self.assertEqual(response.json()["error"]["code"], -32602)
                    asyncio.run(self.workflow(url, headers))
                    (Path(directory) / "restart").touch()
                    deadline = time.monotonic() + 10
                    while (Path(directory) / "restart").exists():
                        self.assertLess(time.monotonic(), deadline)
                        time.sleep(0.1)
                    self.assertEqual(json.loads((Path(directory) / "bridge-19879.json").read_text())["token"], connection["token"])
                    response = httpx.post(url, headers=headers, json={"jsonrpc": "2.0", "id": 1, "method": "ping"}, trust_env=False)
                    self.assertEqual(response.json()["result"], {})
                finally:
                    (Path(directory) / "stop").touch()
                    try:
                        process.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                self.assertEqual(process.returncode, 0)
                self.assertFalse((Path(directory) / "bridge-19879.json").exists())

    async def workflow(self, url, headers):
        async with httpx.AsyncClient(headers=headers, trust_env=False) as client, streamable_http_client(url, http_client=client) as (reader, writer, _):
            async with ClientSession(reader, writer) as session:
                await session.initialize()
                tools = await session.list_tools()
                self.assertEqual(len(tools.tools), 7)

                async def call(name, **arguments):
                    result = await session.call_tool(name, arguments)
                    self.assertFalse(result.isError, result.content)
                    return json.loads(result.content[0].text)

                status = await call("blender_status")
                self.assertTrue(status["blender_version"].startswith("5.2"))
                await call("get_node_schema", node_type="ShaderNodeBsdfPrincipled")
                code = 'ResetMaterial()\no = OutputMaterial()\ns = PrincipledBSDF(base_color=(0.8, 0.1, 0.05, 1.0), roughness=0.3)\nLink(s, "BSDF", o, "Surface")'
                await call("create_material", material_name="MCP_Red", code=code, object_name="Cube")
                materials = await call("list_materials")
                self.assertIn("MCP_Red", [m["name"] for m in materials["materials"]])
                graph = await call("get_material_graph", material_name="MCP_Red")
                patch = 's = Existing("Principled BSDF")\nSetInput(s, "Roughness", 0.75)'
                await call("validate_graph_code", material_name="MCP_Red", code=patch)
                await call("apply_graph_code", material_name="MCP_Red", code=patch, expected_revision=graph["revision"])
                edited = await call("get_material_graph", material_name="MCP_Red")
                surface = next(n for n in edited["graph"]["nodes"] if n["type"] == "ShaderNodeBsdfPrincipled")
                self.assertEqual(next(s["value"] for s in surface["inputs"] if s["name"] == "Roughness"), 0.75)
                error = await session.call_tool("apply_graph_code", {"material_name": "MCP_Red", "code": patch, "expected_revision": graph["revision"]})
                self.assertTrue(error.isError)


if __name__ == "__main__":
    unittest.main()
