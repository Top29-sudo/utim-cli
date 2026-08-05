"""
Clean Install Smoke Tests for UTIM CLI
=======================================

These tests verify both install paths work and produce a functional CLI:

  npm install -g @emend-ai/utim    (npm wrapper path)
  pip install utim-cli             (Python PyPI path)
  pip install .                    (source install path)

The tests here are fast, self-contained checks that can be run immediately
after any install without requiring network credentials or a live account.

Usage:
  # After source install
  pytest tests/test_smoke_install.py -v

  # After npm install -g @emend-ai/utim (in a separate environment)
  pytest tests/test_smoke_install.py -v -m smoke

  # Run only the fastest subset
  pytest tests/test_smoke_install.py -v -m "smoke and not slow"
"""

import os
import sys
import json
import re
import shutil
import pathlib
import subprocess
import importlib

import pytest

UTIM_CMD = "utim"
ROOT = pathlib.Path(__file__).parent.parent
TIMEOUT = 30


def _run(*args, input_text: str | None = None, timeout: int = TIMEOUT):
    """Run utim sub-command, return CompletedProcess."""
    return subprocess.run(
        [UTIM_CMD, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # Windows cp1252 safety — rich outputs UTF-8 box-drawing chars
        timeout=timeout,
        input=input_text,
        env={**os.environ, "UTIM_NO_AUTOUPDATE": "1"},  # suppress update checks
    )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Executable presence
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestExecutablePresence:
    """Verify the utim executable is available and callable."""

    def test_utim_in_path(self):
        """'utim' must be discoverable via shutil.which (i.e. in PATH)."""
        exe = shutil.which(UTIM_CMD)
        assert exe is not None, (
            f"'{UTIM_CMD}' not found in PATH.\n"
            "For npm install: npm install -g @emend-ai/utim\n"
            "For pip install: pip install utim-cli"
        )

    def test_utim_is_executable(self):
        """The utim binary must be executable."""
        exe = shutil.which(UTIM_CMD)
        if exe:
            assert os.access(exe, os.X_OK), f"'{exe}' is not executable"

    def test_help_exits_zero(self):
        """utim --help must exit with code 0."""
        result = _run("--help", timeout=10)
        assert result.returncode == 0, (
            f"utim --help returned {result.returncode}:\n{result.stderr}"
        )

    def test_help_contains_utim_branding(self):
        """utim --help output must mention UTIM."""
        result = _run("--help", timeout=10)
        combined = (result.stdout + result.stderr).lower()
        assert "utim" in combined, (
            f"utim --help output doesn't mention 'utim':\n{combined}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Version consistency
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestVersionConsistency:
    """Verify the version is reported consistently across all surfaces."""

    def _get_cli_version(self) -> str:
        result = _run("--version", timeout=10)
        combined = result.stdout + result.stderr
        match = re.search(r"(\d+\.\d+\.\d+)", combined)
        assert match, f"No semver found in --version output:\n{combined}"
        return match.group(1)

    def test_version_flag_returns_semver(self):
        """utim --version must output a semver string."""
        version = self._get_cli_version()
        assert re.match(r"^\d+\.\d+\.\d+$", version), (
            f"'{version}' is not a valid semver string"
        )

    def test_cli_version_matches_python_package(self):
        """utim --version must match utim_cli.__version__."""
        try:
            from utim_cli import __version__ as pkg_version
        except ImportError:
            pytest.skip("utim_cli Python package not installed in this environment")

        cli_version = self._get_cli_version()
        assert cli_version == pkg_version, (
            f"CLI reports v{cli_version} but Python package is v{pkg_version}. "
            "Run 'python scripts/sync_version.py' to synchronize."
        )

    def test_pyproject_version_matches_package(self):
        """pyproject.toml version must match utim_cli.__version__."""
        toml_path = ROOT / "pyproject.toml"
        if not toml_path.exists():
            pytest.skip("pyproject.toml not found (npm-only install)")

        try:
            from utim_cli import __version__ as pkg_version
        except ImportError:
            pytest.skip("utim_cli not importable")

        content = toml_path.read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
        assert match, "No version found in pyproject.toml"
        assert match.group(1) == pkg_version, (
            f"pyproject.toml version [{match.group(1)}] != "
            f"utim_cli.__version__ [{pkg_version}]"
        )

    def test_npm_package_version_matches_python(self):
        """package.json version must match utim_cli.__version__."""
        pkg_path = ROOT / "package.json"
        if not pkg_path.exists():
            pytest.skip("package.json not found")

        try:
            from utim_cli import __version__ as pkg_version
        except ImportError:
            pytest.skip("utim_cli not importable")

        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        npm_version = pkg.get("version", "")
        assert npm_version == pkg_version, (
            f"package.json version [{npm_version}] != "
            f"utim_cli.__version__ [{pkg_version}]"
        )

    def test_changelog_top_entry_matches_package(self):
        """CHANGELOG.md top version entry must match the installed package version."""
        changelog_path = ROOT / "CHANGELOG.md"
        if not changelog_path.exists():
            pytest.skip("CHANGELOG.md not found")

        try:
            from utim_cli import __version__ as pkg_version
        except ImportError:
            pytest.skip("utim_cli not importable")

        content = changelog_path.read_text(encoding="utf-8")
        match = re.search(r"##\s*\[(\d+\.\d+\.\d+)\]", content)
        assert match, "No versioned entry in CHANGELOG.md"
        assert match.group(1) == pkg_version, (
            f"CHANGELOG.md top entry [{match.group(1)}] != "
            f"package version [{pkg_version}]. "
            "Run 'python scripts/sync_version.py' to synchronize."
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Python import health
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestPythonImports:
    """Verify the Python package imports cleanly after install."""

    def test_utim_cli_importable(self):
        """import utim_cli must succeed."""
        import utim_cli  # noqa: F401

    def test_version_attribute_set(self):
        """utim_cli.__version__ must be a non-empty string."""
        from utim_cli import __version__
        assert isinstance(__version__, str) and len(__version__) > 0, (
            f"__version__ is empty or wrong type: {__version__!r}"
        )

    def test_version_file_importable(self):
        """utim_cli._version must be importable and have VERSION."""
        try:
            from utim_cli._version import VERSION
            assert isinstance(VERSION, str) and re.match(r"^\d+\.\d+\.\d+$", VERSION), (
                f"_version.VERSION is not a valid semver: {VERSION!r}"
            )
        except ImportError:
            pytest.fail("utim_cli._version could not be imported")

    def test_core_modules_importable(self):
        """Key utim_cli sub-modules must import without errors."""
        modules = [
            "utim_cli.config",
            "utim_cli.tools",
            "utim_cli.auth",
        ]
        for module in modules:
            try:
                importlib.import_module(module)
            except ImportError as exc:
                pytest.fail(f"Failed to import {module}: {exc}")


# ─────────────────────────────────────────────────────────────────────────────
# MARK: npm wrapper smoke tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestNpmWrapper:
    """Verify the npm wrapper bin/utim.js is syntactically valid."""

    def test_bin_script_exists(self):
        """bin/utim.js must exist."""
        bin_path = ROOT / "bin" / "utim.js"
        assert bin_path.exists(), (
            "bin/utim.js is missing — npm install will not work"
        )

    def test_bin_script_has_shebang(self):
        """bin/utim.js must start with a Node.js shebang."""
        bin_path = ROOT / "bin" / "utim.js"
        if not bin_path.exists():
            pytest.skip("bin/utim.js not found")
        first_line = bin_path.read_text(encoding="utf-8").splitlines()[0]
        assert first_line.startswith("#!/usr/bin/env node") or "node" in first_line, (
            "bin/utim.js is missing a Node.js shebang"
        )

    def test_postinstall_script_exists(self):
        """scripts/postinstall.js must exist (required by package.json)."""
        script_path = ROOT / "scripts" / "postinstall.js"
        assert script_path.exists(), (
            "scripts/postinstall.js is missing — npm postinstall hook will fail"
        )

    def test_npm_package_json_has_required_fields(self):
        """package.json must have name, version, bin, and files fields."""
        pkg_path = ROOT / "package.json"
        assert pkg_path.exists(), "package.json not found"
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        assert "name" in pkg, "package.json missing 'name'"
        assert "version" in pkg, "package.json missing 'version'"
        assert "bin" in pkg, "package.json missing 'bin'"
        assert "files" in pkg, "package.json missing 'files' (npm publish will include everything)"

    def test_npm_files_list_includes_bin(self):
        """package.json 'files' must include the bin script."""
        pkg_path = ROOT / "package.json"
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        files = pkg.get("files", [])
        has_bin = any("bin" in f for f in files)
        assert has_bin, (
            f"package.json 'files' list {files} does not include 'bin/utim.js'"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Source pip install smoke tests
# ─────────────────────────────────────────────────────────────────────────────

class TestSourceInstall:
    """Verify source-install artefacts are present and well-formed."""

    def test_pyproject_toml_exists(self):
        """pyproject.toml must exist."""
        assert (ROOT / "pyproject.toml").exists(), "pyproject.toml is missing"

    def test_pyproject_has_required_fields(self):
        """pyproject.toml must have name, version, and scripts entry."""
        content = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        assert 'name = "utim-cli"' in content, "pyproject.toml missing name"
        assert re.search(r'(?m)^version\s*=', content), "pyproject.toml missing version"
        assert "utim" in content, "pyproject.toml missing scripts entry for utim"

    def test_setup_py_exists(self):
        """setup.py must exist for legacy tool compatibility."""
        assert (ROOT / "setup.py").exists(), (
            "setup.py is missing — some older tools require it"
        )

    def test_manifest_in_exists(self):
        """MANIFEST.in should exist to control sdist contents."""
        assert (ROOT / "MANIFEST.in").exists(), (
            "MANIFEST.in is missing — sdist may be missing files"
        )

    def test_requirements_txt_is_parseable(self):
        """requirements.txt must be parseable (no syntax errors)."""
        req_path = ROOT / "requirements.txt"
        if not req_path.exists():
            pytest.skip("requirements.txt not found")
        lines = req_path.read_text(encoding="utf-8").splitlines()
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            # Should look like a pip requirement: name[extra]>=version
            assert re.match(r"^[a-zA-Z0-9_\-\.]+", line), (
                f"Suspicious line in requirements.txt: {line!r}"
            )

    def test_doctor_exits_cleanly_after_source_install(self):
        """utim doctor should complete without a Python traceback after source install."""
        result = _run("doctor", timeout=30)
        combined = (result.stdout + result.stderr).lower()
        assert "traceback (most recent call last)" not in combined, (
            f"utim doctor produced a traceback:\n{result.stderr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: First-run bootstrap
# ─────────────────────────────────────────────────────────────────────────────

class TestFirstRunBootstrap:
    """Verify UTIM can bootstrap ~/.utim/ safely."""

    def test_utim_dir_is_writable(self):
        """~/.utim/ directory must be writable."""
        utim_dir = pathlib.Path.home() / ".utim"
        utim_dir.mkdir(parents=True, exist_ok=True)
        assert utim_dir.is_dir(), f"{utim_dir} could not be created"
        assert os.access(utim_dir, os.W_OK), f"{utim_dir} is not writable"

    def test_init_does_not_crash(self):
        """utim init should not raise an unhandled exception."""
        result = _run("init", timeout=20, input_text="n\n")
        combined = (result.stdout + result.stderr).lower()
        assert "traceback (most recent call last)" not in combined, (
            f"utim init raised an unhandled exception:\n{result.stderr}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pytest markers
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    config.addinivalue_line("markers", "smoke: fast install validation tests")
    config.addinivalue_line("markers", "slow: tests that may take >10 s")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
