# Single source of truth for the UTIM version.
#
# BUMP PROCESS
# ─────────────────────────────────────────────────────────────────────────────
#  1. Edit VERSION below.
#  2. Run `python scripts/sync_version.py` — it writes the same string into
#     package.json, pyproject.toml, and the CHANGELOG header for you.
#  3. Commit as "chore: bump version to X.Y.Z".
#
# DO NOT edit __version__ in __init__.py directly — that file now imports
# from here so every surface stays in sync automatically.
# ─────────────────────────────────────────────────────────────────────────────

VERSION = "2.1.0"
