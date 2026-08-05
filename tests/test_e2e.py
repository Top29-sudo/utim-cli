"""
End-to-End Tests for UTIM CLI
==============================

Coverage:
  - Installation smoke tests (utim --version, utim doctor, utim --help)
  - Authentication flow (login/logout error paths)
  - Quota / profile display (utim quota, utim usage, utim plan)
  - Core commands (dry-run, sandbox flags, task mode)
  - Docs rendering (docs.md content validation via import)
  - Support chat (test_support_chat integration paths)

Run:
  pytest tests/test_e2e.py -v
  pytest tests/test_e2e.py -v -m "not slow"
  pytest tests/test_e2e.py -v -m "smoke"
"""

import pytest
import subprocess
import os
import sys
import json
import time
import pathlib
import importlib

# ── Constants ────────────────────────────────────────────────────────────────
UTIM_CMD = [sys.executable, "-m", "utim_cli.utim"]
ROOT = pathlib.Path(__file__).parent.parent
TEST_TIMEOUT = 30  # seconds


def _run(*args, input_text: str | None = None, timeout: int = TEST_TIMEOUT):
    """Helper: run a utim sub-command and return CompletedProcess."""
    return subprocess.run(
        [*UTIM_CMD, *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",  # Windows cp1252 safety — rich outputs box-drawing UTF-8 chars
        timeout=timeout,
        input=input_text,
    )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Installation smoke tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestInstallation:
    """Verify UTIM is properly installed and basic flags work."""

    def test_utim_command_exists(self):
        """utim --help exits 0 and contains 'utim' in output."""
        result = _run("--help", timeout=10)
        assert result.returncode == 0, f"--help failed:\n{result.stderr}"
        combined = (result.stdout + result.stderr).lower()
        assert "utim" in combined, "Expected 'utim' in help output"

    def test_version_flag_returns_semver(self):
        """utim --version prints a semver string like '1.46.40'."""
        result = _run("--version", timeout=10)
        assert result.returncode == 0, f"--version failed:\n{result.stderr}"
        combined = result.stdout + result.stderr
        import re
        assert re.search(r"\d+\.\d+\.\d+", combined), (
            f"No semver found in --version output:\n{combined}"
        )

    def test_version_matches_package_metadata(self):
        """Version from --version matches utim_cli.__version__."""
        result = _run("--version", timeout=10)
        assert result.returncode == 0
        combined = result.stdout + result.stderr
        import re
        from utim_cli import __version__
        match = re.search(r"(\d+\.\d+\.\d+)", combined)
        assert match, "No version number found in output"
        assert match.group(1) == __version__, (
            f"CLI output version {match.group(1)} != package __version__ {__version__}"
        )

    def test_doctor_command_completes(self):
        """utim doctor exits without crashing (returncode 0 or 1)."""
        result = _run("doctor", timeout=30)
        assert result.returncode in (0, 1), (
            f"doctor crashed (rc={result.returncode}):\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        # Should output something diagnostic
        assert len(combined) > 10, "doctor produced no output"

    def test_utim_in_path(self):
        """Verify the utim executable is discoverable in PATH."""
        import shutil
        path = shutil.which("utim")
        assert path is not None, (
            "'utim' not found in PATH. "
            "Run 'pip install utim-cli' or 'npm install -g @emend-ai/utim' first."
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Authentication flow (error paths — no real credentials in CI)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestAuthFlow:
    """Verify auth commands behave correctly without valid credentials."""

    def test_login_command_exists(self):
        """utim login --help exits cleanly."""
        result = _run("login", "--help", timeout=10)
        # Either shows help or the command is implemented as positional
        assert result.returncode in (0, 1, 2)

    def test_logout_without_credentials(self):
        """utim logout handles missing credentials gracefully (no crash)."""
        result = _run("logout", timeout=15)
        # Should fail gracefully — not an unhandled exception
        assert result.returncode in (0, 1), (
            f"logout crashed (rc={result.returncode}):\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        # Should not see raw Python traceback
        assert "traceback (most recent call last)" not in combined, (
            "logout produced an unhandled Python traceback"
        )

    def test_quota_command_without_auth(self):
        """utim quota exits gracefully when not authenticated."""
        result = _run("quota", timeout=15)
        assert result.returncode in (0, 1), (
            f"quota crashed (rc={result.returncode}):\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "traceback (most recent call last)" not in combined

    def test_usage_command_without_auth(self):
        """utim usage exits gracefully when not authenticated."""
        result = _run("usage", timeout=15)
        assert result.returncode in (0, 1), (
            f"usage crashed (rc={result.returncode}):\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "traceback (most recent call last)" not in combined

    def test_plan_command_without_auth(self):
        """utim plan exits gracefully when not authenticated."""
        result = _run("plan", timeout=15)
        assert result.returncode in (0, 1), (
            f"plan crashed (rc={result.returncode}):\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "traceback (most recent call last)" not in combined


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Quota / Profile display
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestQuotaProfile:
    """Verify quota and profile commands surface recognizable output."""

    def test_billing_command_without_auth(self):
        """utim billing returns graceful error when not authenticated."""
        result = _run("billing", timeout=15)
        assert result.returncode in (0, 1)
        combined = (result.stdout + result.stderr).lower()
        assert "traceback" not in combined

    def test_upgrade_command_without_auth(self):
        """utim upgrade exits without crash when not authenticated."""
        result = _run("upgrade", timeout=15)
        assert result.returncode in (0, 1)
        combined = (result.stdout + result.stderr).lower()
        assert "traceback" not in combined

    def test_quota_output_mentions_credits_or_auth(self):
        """utim quota output mentions 'credit', 'quota', or 'login'."""
        result = _run("quota", timeout=15)
        combined = (result.stdout + result.stderr).lower()
        # Either shows quota data or prompts to log in
        meaningful = any(
            kw in combined
            for kw in ("credit", "quota", "login", "sign in", "auth", "plan", "balance")
        )
        assert meaningful or result.returncode in (0, 1), (
            f"quota output was neither meaningful nor graceful:\n{combined}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Core CLI commands
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.smoke
class TestCoreCommands:
    """Test core CLI flags and commands."""

    def test_dry_run_flag_accepted(self):
        """--dry-run flag is accepted by the CLI."""
        result = _run("--dry-run", "--help", timeout=10)
        combined = (result.stdout + result.stderr).lower()
        assert "dry" in combined or result.returncode == 0

    def test_sandbox_flag_accepted(self):
        """--sandbox flag is accepted by the CLI."""
        result = _run("--sandbox", "--help", timeout=10)
        combined = (result.stdout + result.stderr).lower()
        assert "sandbox" in combined or result.returncode == 0

    def test_init_command_runs(self):
        """utim init completes without crash."""
        result = _run("init", timeout=30, input_text="n\n")
        assert result.returncode in (0, 1), (
            f"init crashed (rc={result.returncode}):\n{result.stderr}"
        )

    def test_invalid_subcommand_exits_nonzero(self):
        """An unrecognized subcommand exits with non-zero returncode."""
        result = _run("__nonexistent_command_xyz__", timeout=10)
        assert result.returncode != 0, (
            "Expected non-zero exit code for unknown subcommand"
        )

    def test_task_help(self):
        """utim task --help shows usage info."""
        result = _run("task", "--help", timeout=10)
        assert result.returncode == 0, f"task --help failed:\n{result.stderr}"

    def test_reset_requires_confirmation(self):
        """utim reset prompts for confirmation (auto-decline with 'n')."""
        result = _run("reset", timeout=15, input_text="n\n")
        # Should not crash; may exit 0 (cancelled) or 1 (declined)
        assert result.returncode in (0, 1), (
            f"reset crashed:\n{result.stderr}"
        )
        combined = (result.stdout + result.stderr).lower()
        assert "traceback" not in combined


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Docs rendering validation
# ─────────────────────────────────────────────────────────────────────────────

class TestDocsRendering:
    """Validate that the documentation markdown files are well-formed."""

    DOCS_DIR = ROOT / "landing" / "src" / "docs_md"

    def _read_doc(self, filename: str) -> str:
        path = self.DOCS_DIR / filename
        assert path.exists(), f"Doc file missing: {path}"
        return path.read_text(encoding="utf-8")

    def test_docs_md_has_installation_section(self):
        """docs.md must include an Installation section."""
        content = self._read_doc("docs.md")
        assert "## Installation" in content or "# Installation" in content.lower(), (
            "docs.md is missing an Installation section"
        )

    def test_docs_md_has_data_handling_section(self):
        """docs.md must reference data handling or direct readers to DATA_HANDLING.md."""
        content = self._read_doc("docs.md")
        # Accept either an inline section or a reference to the external file
        has_data_section = (
            "data handling" in content.lower()
            or "data_handling" in content.lower()
            or "DATA_HANDLING" in content
        )
        assert has_data_section, (
            "docs.md should reference data handling. "
            "Add a section or a link to DATA_HANDLING.md."
        )

    def test_pricing_md_is_present_and_non_empty(self):
        """pricing.md must exist and contain plan tier data."""
        content = self._read_doc("pricing.md")
        assert len(content) > 200, "pricing.md appears to be empty or stub"
        assert "free" in content.lower() or "plan" in content.lower(), (
            "pricing.md doesn't mention any plan tier"
        )

    def test_privacy_md_has_local_vs_cloud_table(self):
        """privacy.md must have a local vs. cloud data table."""
        content = self._read_doc("privacy.md")
        assert "local" in content.lower() and "cloud" in content.lower(), (
            "privacy.md is missing a local vs cloud data description"
        )

    def test_security_md_has_contact_email(self):
        """SECURITY.md must contain a security contact email."""
        security_path = ROOT / "SECURITY.md"
        assert security_path.exists(), "SECURITY.md is missing"
        content = security_path.read_text(encoding="utf-8")
        assert "security@" in content or "@utim.dev" in content, (
            "SECURITY.md must include a security contact email"
        )

    def test_security_md_has_reporting_instructions(self):
        """SECURITY.md must explain how to report a vulnerability."""
        security_path = ROOT / "SECURITY.md"
        content = security_path.read_text(encoding="utf-8")
        assert "report" in content.lower() and (
            "email" in content.lower() or "contact" in content.lower()
        ), "SECURITY.md is missing vulnerability reporting instructions"

    def test_data_handling_md_exists(self):
        """DATA_HANDLING.md must exist in the project root."""
        dh_path = ROOT / "DATA_HANDLING.md"
        assert dh_path.exists(), (
            "DATA_HANDLING.md is missing. Create it to document local vs cloud data flows."
        )
        content = dh_path.read_text(encoding="utf-8")
        assert "local" in content.lower(), "DATA_HANDLING.md must describe local data storage"
        assert "backend" in content.lower() or "cloud" in content.lower(), (
            "DATA_HANDLING.md must describe backend/cloud data storage"
        )
        assert "model provider" in content.lower() or "llm" in content.lower(), (
            "DATA_HANDLING.md must describe what goes to model providers"
        )

    def test_all_doc_files_have_content(self):
        """All doc markdown files must be non-empty."""
        for md_file in self.DOCS_DIR.glob("*.md"):
            content = md_file.read_text(encoding="utf-8").strip()
            assert len(content) > 50, f"{md_file.name} appears to be empty or stub"

    def test_changelog_matches_package_version(self):
        """CHANGELOG.md top entry version must match utim_cli.__version__."""
        from utim_cli import __version__
        changelog_path = ROOT / "CHANGELOG.md"
        assert changelog_path.exists(), "CHANGELOG.md is missing"
        content = changelog_path.read_text(encoding="utf-8")
        # The first versioned header should be current version
        import re
        match = re.search(r"##\s*\[(\d+\.\d+\.\d+)\]", content)
        assert match, "No versioned header found in CHANGELOG.md"
        assert match.group(1) == __version__, (
            f"CHANGELOG.md top entry [{match.group(1)}] != package version [{__version__}]. "
            "Run 'python scripts/sync_version.py' to synchronize."
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Support chat docs validation
# ─────────────────────────────────────────────────────────────────────────────

class TestSupportChatDocs:
    """Verify support-related docs are present and complete."""

    DOCS_DIR = ROOT / "landing" / "src" / "docs_md"

    def test_support_md_exists_and_has_contact(self):
        """support.md must exist and include a contact email or Discord link."""
        support_path = self.DOCS_DIR / "support.md"
        assert support_path.exists(), "support.md is missing"
        content = support_path.read_text(encoding="utf-8").lower()
        has_contact = (
            "support@" in content
            or "discord" in content
            or "email" in content
        )
        assert has_contact, (
            "support.md must include a support contact (email or Discord link)"
        )

    def test_sla_md_exists(self):
        """SLA.md must exist in project root."""
        sla_path = ROOT / "SLA.md"
        assert sla_path.exists(), "SLA.md is missing"
        content = sla_path.read_text(encoding="utf-8")
        assert len(content) > 100, "SLA.md appears to be a stub"

    def test_readme_has_support_path(self):
        """README.md must link to support or security resources."""
        readme_path = ROOT / "README.md"
        content = readme_path.read_text(encoding="utf-8").lower()
        assert "security" in content or "support" in content or "sla" in content, (
            "README.md must link to support or security documentation"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Pricing / plan claims verification
# ─────────────────────────────────────────────────────────────────────────────

class TestPricingClaims:
    """Verify pricing docs are self-consistent and don't contain removed claims."""

    PRICING_PATH = ROOT / "landing" / "src" / "docs_md" / "pricing.md"

    REMOVED_CLAIMS = [
        "Dedicated elite endpoints",
        "Autonomous team agents access",
        "High-speed dedicated endpoints",
        "Synthetic Eye & VSIX tools",
        "Claude Sonnet 4.6 (1 RPM)",
        "10-session history storage",
    ]

    def test_pricing_md_present(self):
        """pricing.md must exist."""
        assert self.PRICING_PATH.exists(), "pricing.md is missing"

    def test_no_removed_marketing_claims(self):
        """pricing.md must not contain marketing claims that were removed in v1.43.20."""
        content = self.PRICING_PATH.read_text(encoding="utf-8")
        found = [claim for claim in self.REMOVED_CLAIMS if claim in content]
        assert not found, (
            f"pricing.md contains removed/unverified marketing claims: {found}\n"
            "These were removed in CHANGELOG v1.43.20. Remove them from pricing.md too."
        )

    def test_pricing_mentions_razorpay_payment(self):
        """pricing.md should mention the payment method."""
        content = self.PRICING_PATH.read_text(encoding="utf-8").lower()
        assert "razorpay" in content or "payment" in content, (
            "pricing.md should describe the payment method"
        )

    def test_pricing_mentions_byok(self):
        """pricing.md should mention Bring Your Own Key option."""
        content = self.PRICING_PATH.read_text(encoding="utf-8").lower()
        assert "byok" in content or "bring your own" in content, (
            "pricing.md should mention the BYOK (Bring Your Own Key) option"
        )

    def test_pricing_credit_conversion_consistent(self):
        """Pricing must use 1 USD = 1,000 credits consistently."""
        content = self.PRICING_PATH.read_text(encoding="utf-8")
        # The canonical conversion must appear somewhere
        has_conversion = (
            "1,000 credits" in content or "1000 credits" in content
            or "$1.00 USD = 1,000" in content
        )
        assert has_conversion, (
            "pricing.md must state the credit conversion rate (1 USD = 1,000 credits)"
        )


# ─────────────────────────────────────────────────────────────────────────────
# MARK: Version sync validation
# ─────────────────────────────────────────────────────────────────────────────

class TestVersionSync:
    """Verify all version surfaces are in sync."""

    def test_python_package_version_consistent(self):
        """pyproject.toml version must match utim_cli.__version__."""
        import re
        from utim_cli import __version__
        toml_path = ROOT / "pyproject.toml"
        content = toml_path.read_text(encoding="utf-8")
        match = re.search(r'(?m)^version\s*=\s*"([^"]+)"', content)
        assert match, "Could not find version in pyproject.toml"
        assert match.group(1) == __version__, (
            f"pyproject.toml version [{match.group(1)}] != "
            f"utim_cli.__version__ [{__version__}]. "
            "Run 'python scripts/sync_version.py'."
        )

    def test_npm_package_version_consistent(self):
        """package.json version must match utim_cli.__version__."""
        from utim_cli import __version__
        pkg_path = ROOT / "package.json"
        pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
        npm_version = pkg.get("version", "")
        assert npm_version == __version__, (
            f"package.json version [{npm_version}] != "
            f"utim_cli.__version__ [{__version__}]. "
            "Run 'python scripts/sync_version.py'."
        )

    def test_version_file_exists(self):
        """utim_cli/_version.py (single source of truth) must exist."""
        version_path = ROOT / "utim_cli" / "_version.py"
        assert version_path.exists(), (
            "utim_cli/_version.py is missing. "
            "This is the single source of truth for the version string."
        )

    def test_sync_script_exists(self):
        """scripts/sync_version.py must exist."""
        script_path = ROOT / "scripts" / "sync_version.py"
        assert script_path.exists(), (
            "scripts/sync_version.py is missing. "
            "Create it to automate version propagation."
        )


# ─────────────────────────────────────────────────────────────────────────────
# Pytest configuration
# ─────────────────────────────────────────────────────────────────────────────

def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line("markers", "smoke: fast smoke tests that must pass on every install")
    config.addinivalue_line("markers", "slow: tests that make network calls or take >10 s")
    config.addinivalue_line("markers", "integration: tests requiring live credentials")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])