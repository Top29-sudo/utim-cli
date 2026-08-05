# UTIM CLI Build Secret Provisioning

## Overview

Every official UTIM CLI build is signed by an HMAC-SHA256 secret that the
server also knows. The server keeps a list of *currently valid* secrets in
the `client_builds` DB table so it can verify requests from any of the last
few releases simultaneously (graceful rotation).

## Secret lifecycle

1. **Generation** (build server, not in this repo):
   ```bash
   openssl rand -hex 32  # 256-bit secret
   ```
2. **Bake into the binary**: the secret is base64-injected into the build at
   link time via a small Python `build_secrets.py` script that writes it to
   `utim_cli/_build_secrets.py` (a `.gitignore`-d file, never committed).
3. **Register on the server** via either:
   * `UTIM_CLI_HMAC_SECRETS` env var (comma-separated) on Railway — fast,
     restart-required, fine for emergency rotation
   * direct DB insert into `client_builds`:
     ```sql
     INSERT INTO client_builds
       (id, build_version, channel, hmac_secret, is_active, created_at, notes)
     VALUES (gen_random_uuid()::text, '2.0.4', 'stable',
             '<hex secret>', true, now(),
             'Release 2.0.4 — supersedes 2.0.3');
     ```
4. **Rotation**: ship release N+1 with a new secret; old builds keep working
   because the server accepts ANY active secret. After ≥1 minor release, set
   `is_active=false` (or delete) the old row to force upgrades.

## Field reference

| Column            | Purpose                                                |
|-------------------|--------------------------------------------------------|
| `build_version`   | e.g. `"2.0.4"` — used for telemetry, NOT for matching  |
| `channel`         | `stable` / `beta` / `dev` — for future per-channel rules |
| `hmac_secret`     | the 64-char hex string (NOT a hash — stored as-is)     |
| `is_active`       | `false` immediately rejects the corresponding build    |
| `expires_at`      | NULL = never expires; else auto-rejected past that time|
| `notes`           | free-form changelog / roll-forward reason              |

## Already-installed clients

There is no live "phone home for new secret" mechanism in the current design
(this avoids a covert tracking channel and a dependency on the server being
reachable for the CLI to start). Clients always use the secret baked into
*their* build. When a release is published:

* Old secrets remain valid for at least one minor release cycle.
* Users who skip releases are gently forced to upgrade by the server
  eventually marking the old row `is_active=false` (operator decision).
* Emergency revocation: set `is_active=false` AND remove from
  `UTIM_CLI_HMAC_SECRETS` env var. The server restarts and the old secret
  is no longer accepted.

## Local development

Set `UTIM_CLI_HMAC_SECRET=<any 32-byte hex>` in your shell before running the
CLI. The client falls back to a deterministic per-install-id derived value
when no secret is configured — those requests are *rejected* by the server
once enforcement is on, which is the correct behaviour.

## Why not public-key (Ed25519)?

HMAC is symmetric, so the server secret equals the client secret. The
compromise scenario is: server breach → attacker can forge CLI requests. This
is acceptable because:

* the server already has full DB access (it can forge anything)
* rotating is trivial: one DB row update
* PKI requires distributing a CA chain inside every binary, which has its own
  trust-on-first-use problems

If the threat model changes, swap `hmac.compare_digest(hmac(...))` for
`ed25519.Ed25519PublicKey.from_bytes(...).verify(...)` — the rest of the
flow (challenge, canonical string, headers) is unchanged.
