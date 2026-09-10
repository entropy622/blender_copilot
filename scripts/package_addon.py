"""Build an installable Blender add-on ZIP without caches or old chat files."""
from pathlib import Path
import ast
from zipfile import ZipFile, ZIP_DEFLATED

root = Path(__file__).resolve().parents[1]
tree = ast.parse((root / "addons/blender_copilot/__init__.py").read_text(encoding="utf-8"))
info = next(ast.literal_eval(node.value) for node in tree.body if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "bl_info" for t in node.targets))
version = ".".join(map(str, info["version"]))
destination = root / "dist" / f"blender_copilot-{version}.zip"
destination.parent.mkdir(exist_ok=True)
with ZipFile(destination, "w", ZIP_DEFLATED) as archive:
    for path in sorted((root / "addons" / "blender_copilot").glob("*.py")):
        archive.write(path, "blender_copilot/" + path.name)
    archive.write(root / "LICENSE", "blender_copilot/LICENSE")
print(destination)
