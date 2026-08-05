import sys
import pathlib
sys.path.append(str(pathlib.Path(__file__).parent.parent))

from utim_cli.server.router import get_changelog
import json

releases = get_changelog()
if releases:
    print(f"LATEST VERSION: {releases[0]['version']}")
    print(f"DATE: {releases[0]['date']}")
    print(f"CHANGES: {json.dumps(releases[0]['changes'], indent=2)}")
else:
    print("No releases found!")
