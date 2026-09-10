"""Exercise the configured Blender HTTP MCP endpoint against the user's running Blender."""
import asyncio
import json
from pathlib import Path
import sys
import tomllib

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

ROOT = Path(__file__).resolve().parents[1]


async def main():
    config = tomllib.loads((Path.home() / ".codex/config.toml").read_text(encoding="utf-8"))["mcp_servers"]["blender_graph"]
    async with httpx.AsyncClient(headers=config.get("http_headers", {}), trust_env=False) as client, streamable_http_client(config["url"], http_client=client) as (reader, writer, _):
        async with ClientSession(reader, writer) as session:
            await session.initialize()
            print("Discovered tools:", len((await session.list_tools()).tools))

            async def call(name, **args):
                result = await session.call_tool(name, args)
                if result.isError:
                    raise RuntimeError(result.content)
                return json.loads(result.content[0].text)

            print("Blender:", (await call("blender_status"))["blender_version"])
            name = "GraphCode_Weathered_Copper"
            code = (ROOT / "examples/weathered_copper.py").read_text(encoding="utf-8")
            if "--verify-only" not in sys.argv:
                await call("create_material", material_name=name, code="ResetMaterial()\no = OutputMaterial()\ns = PrincipledBSDF()\nLink(s, 'BSDF', o, 'Surface')", object_name="GraphCode_Patina_Sphere")
                current = await call("get_material_graph", material_name=name)
                print("Validation:", await call("validate_graph_code", material_name=name, code=code, allow_reset=True))
                print("Applied:", await call("apply_graph_code", material_name=name, code=code, expected_revision=current["revision"], allow_reset=True))
            live = await call("get_material_graph", material_name=name)
            assert len(live["graph"]["nodes"]) == 19
            assert live["source_code"].strip() == code.strip()
            output = ROOT / "artifacts/weathered-copper"
            output.mkdir(parents=True, exist_ok=True)
            (output / "live-graph.json").write_text(json.dumps(live, ensure_ascii=False, indent=2), encoding="utf-8")
            print("Verified nodes:", len(live["graph"]["nodes"]), "links:", len(live["graph"]["links"]))


if __name__ == "__main__":
    asyncio.run(main())
