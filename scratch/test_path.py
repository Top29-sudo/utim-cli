import os
import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))
from utim_cli.server.router import _find_changelog_path

path = _find_changelog_path()
print(f"Path: {path}")
if path:
    with open(path, "r", encoding="utf-8") as f:
        print(f"File begins with: {repr(f.read(100))}")
else:
    print("No path found!")
