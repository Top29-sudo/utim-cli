"""
UTIM Build Secret Provisioner
==============================

Run at release time (NOT at runtime). Generates a fresh per-build HMAC
secret, inserts it into the `client_builds` DB table (so the server can
verify requests signed with it), and prints the secret in a form safe
to embed into the CLI build pipeline as the `UTIM_CLI_HMAC_SECRET`
environment variable.

Usage (locally or in CI):
    export DATABASE_URL=postgresql://...
    export UTIM_CLI_VERSION=2.0.5
    python -m utim_cli.server.provision_build \\
        --version 2.0.5 \\
        --keep-previous 2          # keep last 2 build secrets active for rotation
        --retire-after-days 90

What this does:
  1. Generate `secrets.token_urlsafe(32)` as the new build secret.
  2. INSERT into client_builds(version, hmac_secret, is_active, expires_at).
  3. Mark the oldest active build as is_active=False so the active set
     only contains the N most recent builds (for safe rotation).
  4. Print the NEW secret to stdout (pipe into your CI secret store; the
     CLI build will embed it).
  5. ALSO print a comma-separated list of ALL currently-active secrets
     that should be exported as `UTIM_CLI_HMAC_SECRETS` on the server.
     This way the server keeps verifying old clients during the
     rolling-update window.

Why both the DB row AND the env var?
  - DB row: source of truth, survives restarts, versioned per build.
  - Env var: zero-DB cold-start path; the server can boot and verify
    requests even before init_db() runs (e.g. after a wipe).
"""
from __future__ import annotations

import argparse
import datetime
import os
import secrets
import sys
from typing import List

from .db import SessionLocal, ClientBuild, Base, engine


def _ensure_table() -> None:
    """Make sure client_builds exists (idempotent)."""
    Base.metadata.create_all(bind=engine, tables=[ClientBuild.__table__])


def provision(version: str, keep_previous: int, retire_after_days: int) -> dict:
    """Insert a new active build row, retire the oldest if needed, return
    the new row plus the list of all active secrets."""
    _ensure_table()

    new_secret = secrets.token_urlsafe(32)
    expires_at = datetime.datetime.utcnow() + datetime.timedelta(days=retire_after_days)

    db = SessionLocal()
    try:
        # 1. Insert new active row
        row = ClientBuild(
            version=version,
            hmac_secret=new_secret,
            is_active=True,
            expires_at=expires_at,
            created_at=datetime.datetime.utcnow(),
        )
        db.add(row)
        db.commit()
        db.refresh(row)

        # 2. Gather all currently-active rows, sort newest first
        active = (
            db.query(ClientBuild)
            .filter(ClientBuild.is_active == True)  # noqa: E712
            .order_by(ClientBuild.created_at.desc())
            .all()
        )
        now = datetime.datetime.utcnow()
        active = [r for r in active if r.expires_at is None or r.expires_at > now]

        # 3. Deactivate anything beyond the keep_previous window
        for old in active[keep_previous:]:
            old.is_active = False
        db.commit()

        # 4. Final active list (after deactivation)
        active = (
            db.query(ClientBuild)
            .filter(ClientBuild.is_active == True)  # noqa: E712
            .order_by(ClientBuild.created_at.desc())
            .all()
        )
        secrets_list: List[str] = [r.hmac_secret for r in active if r.hmac_secret]

        return {
            "version": version,
            "new_secret": new_secret,
            "build_id": row.id,
            "expires_at": expires_at.isoformat() + "Z",
            "all_active_secrets": secrets_list,
            "all_active_versions": [r.version for r in active],
        }
    finally:
        db.close()


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description="Provision a new UTIM CLI build secret + register it with the server."
    )
    p.add_argument(
        "--version",
        default=os.environ.get("UTIM_CLI_VERSION", "0.0.0"),
        help="Semver of the new build (default: $UTIM_CLI_VERSION)",
    )
    p.add_argument(
        "--keep-previous",
        type=int,
        default=int(os.environ.get("UTIM_KEEP_PREVIOUS_BUILDS", "2")),
        help="How many previous build secrets to keep ACTIVE simultaneously (for rotation)",
    )
    p.add_argument(
        "--retire-after-days",
        type=int,
        default=int(os.environ.get("UTIM_BUILD_RETIRE_DAYS", "90")),
        help="Days until the new build secret expires (default 90)",
    )
    p.add_argument(
        "--quiet",
        action="store_true",
        help="Print only the new secret (for piping into CI secret stores)",
    )
    args = p.parse_args(argv)

    if not os.environ.get("DATABASE_URL") and not os.environ.get("UTIM_SQLITE_PATH"):
        print("ERROR: DATABASE_URL (or UTIM_SQLITE_PATH) must be set.", file=sys.stderr)
        return 2

    try:
        result = provision(args.version, args.keep_previous, args.retire_after_days)
    except Exception as exc:
        print(f"ERROR: provision failed: {exc}", file=sys.stderr)
        return 1

    if args.quiet:
        # Just the new secret on stdout — safe to pipe into a secret store.
        print(result["new_secret"])
        return 0

    print("=" * 72)
    print(f"UTIM Build Secret Provisioned")
    print("=" * 72)
    print(f"  build_id       : {result['build_id']}")
    print(f"  version        : {result['version']}")
    print(f"  expires_at     : {result['expires_at']}")
    print(f"  active builds  : {len(result['all_active_secrets'])}")
    print(f"  active versions: {', '.join(result['all_active_versions'])}")
    print()
    print("─" * 72)
    print("NEW BUILD SECRET (embed into CLI build env as UTIM_CLI_HMAC_SECRET):")
    print("─" * 72)
    print(result["new_secret"])
    print()
    print("─" * 72)
    print("ALL ACTIVE SECRETS (export on server as UTIM_CLI_HMAC_SECRETS):")
    print("─" * 72)
    print(",".join(result["all_active_secrets"]))
    print()
    print("─" * 72)
    print("Suggested CI workflow:")
    print("─" * 72)
    print(f"  export UTIM_CLI_HMAC_SECRET={result['new_secret']}")
    print(f"  export UTIM_CLI_HMAC_SECRETS={','.join(result['all_active_secrets'])}")
    print(f"  export UTIM_CLI_VERSION={result['version']}")
    print("  # ... then run your CLI build (PyInstaller, etc.) ...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
