# UTIM Data Handling Reference

This document is the definitive guide to **what data UTIM touches, where it goes, and who can see it**.
Read this before deploying UTIM in a team or enterprise environment.

---

## Quick Summary

| Data category                | Where it lives        | Who can access it           |
| ---------------------------- | --------------------- | --------------------------- |
| Your source code files       | Your machine only     | You only                    |
| Project memory / embeddings  | Your machine only     | You only                    |
| Config & API keys            | Your machine only     | You only                    |
| Auth token (Firebase JWT)    | UTIM backend          | UTIM auth service           |
| Quota / credit logs          | UTIM backend          | Your account only           |
| Cloud chat history           | UTIM backend          | Your account only           |
| LLM prompt text              | Model provider        | Subject to provider policy  |

---

## 1. Data That Stays Local (Never Leaves Your Machine)

UTIM is a **local-first** tool. The items below are stored exclusively under your user home
directory or your project directory:

### 1.1 Source Code and Files

UTIM reads and writes files in your working directory. This data is **never uploaded** to UTIM
servers. When you include a code snippet in a prompt, it goes directly from your machine to the
LLM provider you have configured — UTIM servers never see it.

### 1.2 Vector Memory and Embeddings

| Location                      | Contents                                    |
| ----------------------------- | ------------------------------------------- |
| `~/.utim/memory/`             | Global user preference embeddings           |
| `.utim/vector_db/`            | Project-specific semantic memory (ChromaDB) |
| `.utim/experiences.json`      | Learned lessons from previous tasks         |

All embeddings are generated locally or via the embedding model you configure. UTIM servers
never receive raw embeddings or the source text used to generate them.

### 1.3 Configuration and Secrets

| File                          | Contents                                    |
| ----------------------------- | ------------------------------------------- |
| `~/.utim/config.json`         | Provider URLs, model selection, preferences |
| OS keyring (if available)     | API keys for custom BYOK providers          |
| Environment variables         | `UTIM_API_KEY`, `OPENROUTER_API_KEY`, etc.  |
| `~/.utim/mcp_registry.json`   | MCP server configurations                   |

API keys are **never transmitted to UTIM servers**. They are sent only to the specific API
endpoint they are meant for (e.g., `api.openai.com`, `openrouter.ai`).

### 1.4 Session State and Undo Stack

| File                          | Contents                                    |
| ----------------------------- | ------------------------------------------- |
| `.utim/session_state.json`    | Undo/redo stack (file diff snapshots)       |
| `.utim/chat_history.json`     | Local copy of the current session messages  |
| `.utim_tmp/`                  | Temporary build artefacts and logs          |

---

## 2. Data Sent to UTIM Backend (api.utim.dev)

UTIM connects to its hosted backend for account management and quota. The backend runs on
[Railway](https://railway.app) with a PostgreSQL database.

### 2.1 Authentication

- On `utim login`, your browser opens a Firebase authentication flow. Firebase issues a JWT
  that the CLI stores locally in `~/.utim/config.json` (under `auth_token`).
- Every API call to `api.utim.dev` presents this JWT in the `Authorization` header.
- The backend validates the JWT against Firebase and looks up your account record.
- **No passwords are ever stored by UTIM** — Firebase handles credential management.

### 2.2 Quota and Credit Accounting

- After each LLM completion, the CLI sends the **token count** (not the prompt text) to
  `api.utim.dev/api/usage` to deduct credits from your balance.
- The backend stores: user ID, model ID, timestamp, input tokens, output tokens, credit cost.
- **Prompt content is never sent to UTIM servers for accounting purposes.**

### 2.3 Cloud Chat History (Optional Sync)

- If you are logged in, conversation turns can be synced to the cloud to enable
  cross-device session restoration via `/resume`.
- You can disable this in `~/.utim/config.json` by setting `"sync_history": false`.
- Chat history is stored in the UTIM PostgreSQL database, scoped to your user ID.
- You can permanently delete your history via the web profile page or by closing your account.

### 2.4 Last Active Project Folder

- UTIM records your last active directory (path string only) on the backend to enable
  cross-machine experience database sync on startup.
- Only the directory path is stored — no file contents or directory listings.

### 2.5 Subscription and Plan Status

- Subscription tier, payment status, and plan expiry are stored and managed server-side.
- Payment processing is handled by [Razorpay](https://razorpay.com) — UTIM servers never
  store raw card or UPI details.

---

## 3. Data Sent to Model Providers

When you send a prompt, UTIM forwards it to the configured LLM provider. The payload typically
includes:

| Component                    | Sent?  | Notes                                            |
| ---------------------------- | ------ | ------------------------------------------------ |
| Your message text            | ✅ Yes | Always, by design                                |
| System prompt                | ✅ Yes | Includes injected memory snippets and rules      |
| Injected memory snippets     | ✅ Yes | Relevant lessons fetched from local vector DB    |
| Prior conversation turns     | ✅ Yes | Up to the model's context window limit           |
| File contents you reference  | ✅ Yes | Only files the agent explicitly reads            |
| Your local API key           | ✅ Yes | Sent to the provider in the `Authorization` header|
| Your UTIM auth token         | ❌ No  | Never sent to model providers                    |
| Your email address           | ❌ No  | Never sent to model providers                    |

### Provider-Specific Policies

| Provider        | Data retention policy link                                           |
| --------------- | -------------------------------------------------------------------- |
| OpenRouter      | [Privacy Policy](https://openrouter.ai/privacy) — zero-retention    |
| OpenAI          | [Privacy Policy](https://openai.com/policies/privacy-policy)        |
| Anthropic       | [Privacy Policy](https://www.anthropic.com/privacy)                 |
| Google (Gemini) | [Privacy Policy](https://policies.google.com/privacy)               |
| Ollama (local)  | Runs entirely on your machine — no external data transfer            |

> **Recommendation**: For sensitive codebases, use a BYOK Ollama or self-hosted endpoint
> so prompts never leave your network.

---

## 4. Telemetry

UTIM does **not** collect:
- Keystrokes or terminal input
- Screen contents or screenshots
- File contents outside of explicit agent reads
- Usage patterns, command frequency, or feature flags

UTIM **does** collect (only when you are logged in):
- Token counts per completion (for quota accounting — see §2.2)
- Session start/end timestamps (for plan enforcement)

You can verify what is sent by running UTIM with a local network proxy (e.g., mitmproxy) or
by inspecting the `utim_cli/auth.py` and `utim_cli/orchestrator.py` source code directly.

---

## 5. Data Retention and Deletion

| Data type            | Retention period              | Deletion mechanism                     |
| -------------------- | ----------------------------- | -------------------------------------- |
| Cloud chat history   | Until account deletion        | Profile page → Delete History           |
| Usage logs           | 12 months minimum             | Account deletion purges all logs       |
| Auth tokens (local)  | Until `utim logout`           | `utim logout` clears `~/.utim/config.json` |
| Local memory / DB    | Indefinite (your disk)        | `utim reset` or manual deletion        |
| Account + all data   | Immediate on request          | Profile page → Delete Account           |

---

## 6. GDPR / Privacy Rights

Depending on your location you may have rights including:
- **Access**: Request an export of your cloud data (email support@utim.dev).
- **Correction**: Update your profile via the web UI.
- **Deletion**: Delete your account from the web profile page.
- **Portability**: Request a JSON export of your chat history.
- **Opt-out**: Disable cloud sync (`"sync_history": false` in config).

---

## 7. Contact

Questions about data handling:

- **Email**: privacy@utim.dev
- **Security issues**: security@utim.dev (see [SECURITY.md](SECURITY.md))
- **Discord**: [discord.com/invite/wGB7M8pMEy](https://discord.com/invite/wGB7M8pMEy)

---

*Last updated: July 2026*
