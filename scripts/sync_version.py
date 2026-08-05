#!/usr/bin/env python3
"""
sync_version.py – UTIM version synchronization tool
=====================================================
Reads the canonical VERSION from  utim_cli/_version.py  and writes that
string into every location that needs it:

  • utim_cli/__init__.py  (__version__ line)
  • pyproject.toml        (version = "…")
  • package.json          (root, "version": "…")
  • CHANGELOG.md          (updates the first entry date to today if stale)

Run this script once before every release commit:

    python scripts/sync_version.py

It is idempotent – running it multiple times has no side effects.
"""

import re
import sys
import json
import pathlib
from datetime import date

ROOT = pathlib.Path(__file__).parent.parent

# ── Load canonical version ────────────────────────────────────────────────────
version_file = ROOT / "utim_cli" / "_version.py"
namespace: dict = {}
exec(version_file.read_text(encoding="utf-8"), namespace)  # noqa: S102
VERSION = namespace["VERSION"]
print(f"[sync_version] Canonical version: {VERSION}")


def patch_file(path: pathlib.Path, pattern: str, replacement: str) -> bool:
    """Replace the first occurrence of *pattern* in *path* with *replacement*.
    Returns True when a change was made."""
    text = path.read_text(encoding="utf-8")
    new_text = re.sub(pattern, replacement, text, count=1)
    if new_text != text:
        path.write_text(new_text, encoding="utf-8")
        print(f"[sync_version]   updated {path.relative_to(ROOT)}")
        return True
    print(f"[sync_version]   no change needed in {path.relative_to(ROOT)}")
    return False


# ── 1. utim_cli/__init__.py ───────────────────────────────────────────────────
patch_file(
    ROOT / "utim_cli" / "__init__.py",
    r'__version__\s*=\s*"[^"]+"',
    f'__version__ = "{VERSION}"',
)

# ── 2. pyproject.toml ─────────────────────────────────────────────────────────
patch_file(
    ROOT / "pyproject.toml",
    r'(?m)^version\s*=\s*"[^"]+"',
    f'version = "{VERSION}"',
)

# ── 3. Root package.json ──────────────────────────────────────────────────────
pkg_path = ROOT / "package.json"
pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
if pkg.get("version") != VERSION:
    pkg["version"] = VERSION
    pkg_path.write_text(json.dumps(pkg, indent=2) + "\n", encoding="utf-8")
    print(f"[sync_version]   updated package.json")
else:
    print(f"[sync_version]   no change needed in package.json")

# ── 4. CHANGELOG.md – update date on latest entry if stale ───────────────────
changelog_path = ROOT / "CHANGELOG.md"
changelog_text = changelog_path.read_text(encoding="utf-8")
today = date.today().isoformat()
# Match the first versioned header, e.g. ## [1.46.28] - 2026-07-10
pattern = rf"(##\s*\[{re.escape(VERSION)}\])\s*-\s*\d{{4}}-\d{{2}}-\d{{2}}"
replacement = rf"\1 - {today}"
new_changelog = re.sub(pattern, replacement, changelog_text, count=1)
if new_changelog != changelog_text:
    changelog_path.write_text(new_changelog, encoding="utf-8")
    print(f"[sync_version]   updated CHANGELOG.md date to {today}")
else:
    # If version not in changelog at all, warn
    if f"[{VERSION}]" not in changelog_text:
        print(
            f"[sync_version] WARNING: [{VERSION}] not found in CHANGELOG.md – "
            "add a release entry before publishing."
        )
    else:
        print(f"[sync_version]   CHANGELOG.md already up to date")

patch_file(
    ROOT / "utim_cli" / "utim.py",
    r'\[bold #cba6f7\]v[\d\.]+\[/bold #cba6f7\]',
    f'[bold #cba6f7]v{VERSION}[/bold #cba6f7]',
)
patch_file(
    ROOT / "utim_cli" / "utim.py",
    r'\[dim\]v[\d\.]+\[/dim\]',
    f'[dim]v{VERSION}[/dim]',
)
patch_file(
    ROOT / "utim_cli" / "utim.py",
    r'current_ver\s*=\s*"[^"]+"',
    f'current_ver = "{VERSION}"',
)

# ── 6. Copy CHANGELOG.md to landing website's docs_md ─────────────────────────
landing_changelog_path = ROOT / "landing" / "src" / "docs_md" / "changelog.md"
if landing_changelog_path.parent.exists():
    try:
        # Use either new_changelog or changelog_text
        current_cl_text = new_changelog if 'new_changelog' in locals() else changelog_text
        landing_changelog_path.write_text(current_cl_text, encoding="utf-8")
        print(f"[sync_version]   synchronized landing/src/docs_md/changelog.md")
    except Exception as e:
        print(f"[sync_version] WARNING: failed to sync landing changelog: {e}")

# ── 7. landing/src/components/PowershellUI/index.jsx ──────────────────────────
jsx_path = ROOT / "landing" / "src" / "components" / "PowershellUI" / "index.jsx"
if jsx_path.exists():
    patch_file(
        jsx_path,
        r"version\s*=\s*'[\d\.]+'",
        f"version = '{VERSION}'",
    )
    patch_file(
        jsx_path,
        r"useState\('[\d\.]+'\)",
        f"useState('{VERSION}')",
    )
    patch_file(
        jsx_path,
        r"getInitialHistory\(user,\s*userProfile,\s*'[\d\.]+'\)",
        f"getInitialHistory(user, userProfile, '{VERSION}')",
    )

# ── 8. Copy CHANGELOG.md to utim_cli/server/CHANGELOG.md ──────────────────────
server_changelog_path = ROOT / "utim_cli" / "server" / "CHANGELOG.md"
if server_changelog_path.parent.exists():
    try:
        current_cl_text = new_changelog if 'new_changelog' in locals() else changelog_text
        server_changelog_path.write_text(current_cl_text, encoding="utf-8")
        print(f"[sync_version]   synchronized utim_cli/server/CHANGELOG.md")
    except Exception as e:
        print(f"[sync_version] WARNING: failed to sync server changelog: {e}")

print(f"\n[sync_version] Done. All surfaces now report v{VERSION}.\n")
