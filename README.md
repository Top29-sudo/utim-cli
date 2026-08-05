# UTIM CLI Agent: Enterprise Coder Assistant

UTIM is an agentic developer CLI assistant designed to automate coding tasks directly inside your local terminal, featuring robust safety controls, self-healing quality gates, and local-first semantic memory.

---

## 🚀 Quick Start

### 1. Installation

**Recommended: Automated Installer (UNIX / macOS / Android Termux)**
Use the automated installation script, which detects your environment (such as Termux) and automatically installs build dependencies (like `rust`, `clang`, and `binutils`) and configures correct API levels:

```bash
curl -sL https://raw.githubusercontent.com/emendai/utim/main/install.sh | bash
```

**Alternative: Local Installation (from source)**
```bash
# Basic installation
pip install .

# Recommended: Full installation (includes semantic vector RAG & web search)
pip install ".[full]"
```

### 2. Provider & Model Configuration
Start the chat session:
```bash
utim
```
On first run, UTIM checks for `.utim/config.json`. If it does not exist, it runs a provider and model configuration wizard. You can configure:
- **Default Providers**: OpenRouter, OpenAI, custom servers, etc.
- **Model Picker**: Press `Ctrl+M` in the chat terminal at any time to configure, pick, add, or delete LLMs.

---

## ⚡ Main CLI Commands

- **`utim`**: Starts the interactive chat terminal (TUI).
- **`utim task "<prompt>"`**: Executes a single task autonomously from the command line and exits. In an interactive terminal (`stdin` is a TTY) file writes and commands prompt for confirmation; when piped/scripted they run in auto-accept mode.
- **`utim --dry-run`**: Starts the session in **Dry-Run Mode** (all code modifications and shell commands are simulated, not written/executed).
- **`utim --sandbox`**: Runs all mutating shell command proposals in the intelligent local sandbox (untrusted commands will block until approved).
- **`utim doctor`** / **`utim init`** / **`utim reset`**: Administrative commands for state diagnosis, initialization, and factory resets.

---

## 🛠️ In-Chat Slash Commands

Inside the interactive chat terminal, type these slash commands for direct workspace control:

- **`/undo`**: Reverts the last assistant action, restoring files to their exact "before" state and rolling back messages.
- **`/redo`**: Re-applies the last undone turn, re-writing files and restoring conversation logs.
- **`/rewind <turn_index>`**: Rolls back the entire session to a specific conversation turn.
- **`/doctor`**: Run diagnostics on environment variables, Python version, dependencies, API model connections, and MCP server status.
- **`/report`**: Generates a support bundle under `.utim_tmp/report_bundle.zip` (automatically redacts secrets, passwords, or personal names/files).
- **`/reset`**: Wipes the current chat history without deleting persistent local vector memory.

---

## 🧠 Architecture & How it Works

1. **Local Memory (`.utim/memory.json` & ChromaDB)**: 
   - Global user preferences, rules, and facts are synced to a semantic vector database (`.utim_tmp/vector_db`).
   - Relevant memories are dynamically fetched via semantic similarity (RAG) and injected into the system prompt context, preventing prompt bloating.
2. **Undo/Redo Stack & Session State**:
   - Every file change (writes, batch string edits, moves, deletions) computes a diff snapshot.
   - The entire stack is serialized dynamically to `.utim/session_state.json`. You can close your shell, shut down your computer, and resume later with intact rollback features.
3. **Workspace Boundary & Safety Controls**:
   - Prior to writing files, UTIM performs **Pre-Commit Syntax Checks** (AST compilation for Python, JSON loads, JS/TS checks).
   - If tests are available (`pytest`, `npm test`, etc.), UTIM runs them in a background **Regression testing loop**, prompting the model to self-heal code errors if assertions fail.
   - **Interactive TUI mode** (`utim`): every file mutation shows an interactive diff dialog; the developer accepts, edits, or rejects individual hunks before they are applied.
   - **CLI task mode** (`utim task`): when running in a real terminal, destructive operations (`rm`, package installs, `>` redirects) prompt for `y/n` confirmation. When stdin is piped/non-interactive all edits are auto-accepted.
   - **Sandbox mode** (`utim --sandbox`): classifies every terminal command as safe or risky and blocks risky commands until explicitly approved.

---

## ⚠️ What this Tool Can and Cannot Do

### Can Do:
- Read, write, and patch codebases safely.
- Install and coordinate custom MCP (Model Context Protocol) servers.
- Self-heal syntax and test errors before files are written.
- Revert any file modification instantly.

### Cannot Do:
- **No Remote Code Execution**: Runs locally on your machine.
- **Unverified Sensitive Reads Blocked**: Reading files or memory matching sensitive keys (like passwords, secret codes, or personal data) is blocked unless verified via your configured verification code.
- **No Auto-Deletions**: Any command that deletes files outside the working directory is blocked automatically.

---

## 📋 Compatibility Matrix

| Component | Minimum Version | Recommended Version | Notes |
|-----------|-----------------|---------------------|-------|
| **Python** | 3.10 | 3.11+ | 3.10 required for asyncio features |
| **pip** | 21.0 | 23.0+ | For modern dependency resolution |
| **Node.js** | 18.0 | 20.0+ | Only if using MCP servers |
| **Operating System** | | | |
| - Windows | 10 (1903+) | 11 | PowerShell or CMD required |
| - macOS | 11 (Big Sur) | 14 (Sonoma) | Terminal.app or iTerm2 |
| - Linux | Ubuntu 20.04 | Ubuntu 22.04+ | Any modern distro with bash |
| **Terminals** | | | |
| - Windows Terminal | 1.0 | 1.19+ | Full color support |
| - iTerm2 | 3.4+ | 3.5+ | Recommended on macOS |
| - VS Code Terminal | 1.70+ | 1.85+ | Full support |
| **Required Tools** | | | |
| - git | 2.30 | 2.40+ | For undo/redo and diffs |
| - Docker | 20.10 | 24.0+ | Optional, for sandbox mode |

### Supported LLM Providers

| Provider | API Type | Models Supported |
|----------|----------|------------------|
| OpenRouter | REST | Claude, GPT, Gemini, Mistral, etc. |
| OpenAI | REST | GPT-4o, GPT-4 Turbo, GPT-3.5 |
| Anthropic | REST | Claude 3.5, 3, 2 |
| Google AI | REST | Gemini 1.5 Pro/Flash |
| Azure OpenAI | REST | GPT-4, GPT-3.5 |
| Ollama | Local | Llama 3, Mistral, CodeLlama |
| Custom Server | REST | Any OpenAI-compatible API |

---

## 📄 Related Documentation

- [📖 Full Documentation](https://utim.dev/docs)
- [🔒 Security Policy](SECURITY.md) — vulnerability reporting, security@utim.dev
- [🗄️ Data Handling Reference](DATA_HANDLING.md) — what stays local, what goes to backend, what goes to model providers
- [📊 SLA & Support](SLA.md)
- [🛡️ Privacy Policy](landing/src/docs_md/privacy.md)

## 📦 Installation Methods

### npm (recommended — works without Python pre-installed)
```bash
npm install -g @emend-ai/utim
```

### pip (from PyPI)
```bash
pip install utim-cli
# Full install with optional features (web search, images, parsers)
pip install "utim-cli[full]"
```

Desktop installs include the normal SDK/MCP path automatically. Mobile/Termux
installs keep those native-heavy pieces optional to avoid `pydantic-core`; use
`utim-cli[mcp]` or `utim-cli[legacy-agent]` only if you explicitly need them.
Do not install `utim_cli/server/requirements.txt` unless you are deploying the
server.

### Source install (development)
```bash
git clone https://github.com/emendai/utim.git
cd utim
pip install -e ".[full]"
```

### Smoke-test your install
```bash
utim --version     # Should print the current version
utim doctor        # Runs diagnostics — all checks should pass
```

See [INSTALLATION_VERIFICATION.md](INSTALLATION_VERIFICATION.md) for detailed verification steps and troubleshooting.

## 🔢 Version

UTIM uses a single canonical version defined in [`utim_cli/_version.py`](utim_cli/_version.py).
Run `python scripts/sync_version.py` to propagate a version bump to all surfaces
(`package.json`, `pyproject.toml`, `CHANGELOG.md`) before releasing.
