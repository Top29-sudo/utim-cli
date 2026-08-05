# Security Policy

## Overview

UTIM CLI takes the security of your local machine and data seriously.
This document describes our supported versions, how to report vulnerabilities responsibly,
and the scope of our security commitments.

---

## Supported Versions

| Version  | Security Support     |
| -------- | -------------------- |
| 1.46.x   | ✅ Active (current)  |
| 1.45.x   | ✅ Security fixes    |
| < 1.45   | ❌ End-of-life       |

Always run the latest patch release:

```bash
pip install --upgrade utim-cli
# or
npm install -g @emend-ai/utim
```

---

## Reporting a Vulnerability

> **Please do NOT open a public GitHub issue for security vulnerabilities.**
> Public disclosure before a patch is released puts all users at risk.

### Primary contact

**Email**: security@utim.dev  
**Response SLA**: We acknowledge every report within **48 business hours**.

### What to include

A good vulnerability report helps us reproduce and fix the issue faster:

1. **Description** – A clear, concise explanation of the vulnerability.
2. **Steps to reproduce** – Exact commands, config, or code snippet that triggers the issue.
3. **Impact** – What can an attacker achieve? Data exfiltration? Privilege escalation? Code execution?
4. **Affected version** – Output of `utim --version`.
5. **Operating system and Python version** – Output of `utim doctor`.
6. **Suggested fix** (optional) – Patch or mitigation idea.

### Encrypted reports

For highly sensitive reports, you may encrypt your email using our PGP key.
Contact security@utim.dev first to request the key fingerprint.

---

## Vulnerability Disclosure Timeline

| Phase                    | Target SLA         |
| ------------------------ | ------------------ |
| Acknowledgement          | ≤ 48 business hours|
| Initial triage           | ≤ 5 business days  |
| Critical fix released    | ≤ 7 days           |
| High fix released        | ≤ 30 days          |
| Public disclosure        | After patch ships  |

We follow [coordinated vulnerability disclosure (CVD)](https://cheatsheetseries.owasp.org/cheatsheets/Vulnerability_Disclosure_Cheat_Sheet.html).
Reporters who follow responsible disclosure will be credited in the release notes unless they prefer anonymity.

---

## Security Architecture

### Data Handled Locally (Your Machine Only)

The following data **never leaves your machine**:

| Data                               | Location                              |
| ---------------------------------- | ------------------------------------- |
| Source code files                  | Your working directory                |
| Vector embeddings / project memory | `~/.utim/memory/` or `.utim/`         |
| Config file and API keys           | `~/.utim/config.json`                 |
| MCP tool configurations            | `~/.utim/mcp_registry.json`           |
| Session state and undo stack       | `.utim/session_state.json`            |
| Local chat history                 | `~/.utim/chats/`                      |

### Data Sent to UTIM Backend

| Data                   | Purpose                              | Encrypted  |
| ---------------------- | ------------------------------------ | ---------- |
| Firebase auth token    | Session authentication               | ✅ TLS     |
| Credit consumption log | Quota accounting                     | ✅ TLS     |
| Cloud chat history     | Cross-device session persistence     | ✅ TLS     |
| Subscription status    | Feature access control               | ✅ TLS     |

### Data Sent to Model Providers

When you send a prompt, the **prompt text and relevant context** are forwarded to the active
LLM provider (e.g., OpenRouter, OpenAI, Anthropic, Google). Source code snippets included in
a prompt are processed by that provider subject to their own privacy policy.

UTIM does **not** automatically include full repository contents — only the context you or the
agent explicitly selects for a turn. Using `--dry-run` or `--sandbox` mode does not reduce what
is sent to model providers; those flags only control local file writes and command execution.

### Key Security Controls

- **API keys** are stored in the OS keyring when available; otherwise they fall back to
  `~/.utim/config.json` with a `0600` permission advisory. Keys are never transmitted to UTIM
  servers — only to the specific provider endpoint they belong to.
- **Sandbox mode** (`--sandbox`) classifies every terminal command as safe or risky before
  execution and blocks risky commands until explicitly approved.
- **Sensitive-read guard** blocks `read_file` calls on paths that match known sensitive
  patterns (passwords, secret keys, personal data) unless unlocked with your verification code.
- **Pre-commit validation** runs AST/JSON/JS syntax checks before any file is written.
- **Workspace boundary** prevents the agent from deleting files outside the working directory.
- **All server communication** uses HTTPS/TLS 1.2+.
- **No keystroke or screen telemetry** is collected.

---

## Scope

Security reports are accepted for:

- UTIM CLI (`utim-cli` pip package, `@emend-ai/utim` npm package)
- UTIM web application (utim.dev)
- UTIM backend API (api.utim.dev)

Out of scope:

- Vulnerabilities in third-party LLM providers (report to them directly)
- Issues requiring physical access to the machine
- Social engineering attacks
- Denial-of-service against free-tier rate limits

---

## Bug Bounty

We currently operate a **good-faith acknowledgment program** (no monetary rewards yet).
Critical vulnerability reporters receive public credit in the release notes and, at maintainer
discretion, complimentary Pro plan access for 3 months.

---

## Security Best Practices for Users

1. **Never share your API key or UTIM auth token** — it provides full account access.
2. **Use environment variables** (e.g., `UTIM_API_KEY`) instead of hard-coding keys in config.
3. **Review every command proposal** before approving, especially in CI/CD pipelines.
4. **Keep UTIM updated** — `pip install --upgrade utim-cli` — to receive security patches.
5. **Use `--sandbox` mode** when running UTIM on unfamiliar or untrusted codebases.
6. **Rotate your API key** immediately if you suspect it has been leaked.

---

*Last updated: July 2026 | Contact: security@utim.dev*