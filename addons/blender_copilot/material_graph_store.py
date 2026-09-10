"""Persistent Graph Code source; reads never bootstrap or overwrite source."""
import hashlib
import os
from pathlib import Path
import re
import tempfile

import bpy


def get_graph_code_root():
    addon = bpy.context.preferences.addons.get(__package__)
    root = addon.preferences.graph_code_root if addon else ""
    if root.strip():
        return Path(bpy.path.abspath(root))
    if bpy.data.filepath:
        return Path(bpy.data.filepath).parent / "blender_copilot_graphs"
    return Path.home() / ".blender-copilot" / "graphs"


def get_material_graph_path(material):
    bound = getattr(material, "copilot_graph_code_path", "").strip()
    if bound:
        return Path(bpy.path.abspath(bound))
    safe = re.sub(r"[^a-zA-Z0-9._-]+", "_", material.name).strip("._") or "material"
    digest = hashlib.sha256(material.name.encode()).hexdigest()[:12]
    return get_graph_code_root() / f"{safe}-{digest}.py"


def read_material_graph(material):
    path = get_material_graph_path(material)
    return path.read_text(encoding="utf-8") if path.exists() else None


def atomic_write(path, code):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(code.rstrip() + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def write_material_graph(material, code):
    path = get_material_graph_path(material)
    atomic_write(path, code)
    material.copilot_graph_code_path = str(path)
    return str(path)


def write_material_graph_draft(material, code):
    path = Path(str(get_material_graph_path(material)) + ".draft.py")
    atomic_write(path, code)
    return str(path)
