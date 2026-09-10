"""Isolated background Blender process used by the MCP transport integration test."""
import os
from pathlib import Path
import sys
import time

import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, os.environ.get("BLENDER_COPILOT_ADDON_DIR", str(root / "addons")))
import blender_copilot

test_dir = Path(os.environ["BLENDER_COPILOT_TEST_DIR"])
bpy.ops.wm.save_as_mainfile(filepath=str(test_dir / "transport.blend"))
blender_copilot.register()
assert blender_copilot.bridge._server, blender_copilot.bridge.last_error
try:
    (test_dir / "ready").touch()
    deadline = time.monotonic() + 120
    # Background --python scripts do not pump Blender's UI event loop.
    while time.monotonic() < deadline and not (test_dir / "stop").exists():
        if (test_dir / "restart").exists():
            blender_copilot.bridge.stop()
            blender_copilot.bridge.start()
            (test_dir / "restart").unlink()
        blender_copilot.bridge.drain()
        time.sleep(0.02)
finally:
    blender_copilot.unregister()
