# UTIM CLI Complete Documentation

This page is the complete operating manual for UTIM CLI, the local-first autonomous developer agent for terminal-based software engineering.

UTIM stands for "You Think It, I Make It." It is designed to run inside a project folder, understand the workspace, plan changes, edit files, run local commands, validate results, and keep a reversible record of the work.

## What UTIM CLI is

UTIM CLI is a Python-based command line agent with a Rich and prompt_toolkit terminal interface. It is packaged as the `utim` command and runs on Python 3.9 or newer.

It can:

- Read, inspect, and summarize a codebase.
- Write files and patch existing files.
- Run shell commands with confirmation and sandbox controls.
- Validate Python, JSON, JavaScript, and TypeScript edits before writing.
- Maintain undo, redo, and rewind history for agent changes.
- Persist conversation state and local workspace intelligence in `.utim/`.
- Connect to hosted UTIM account services for login, quota, billing, model routing, and support.
- Connect to external tools through Model Context Protocol (MCP) servers.
- Use optional semantic memory, web search, image analysis, image generation, and Blender automation when dependencies and credentials are available.

UTIM is not a browser-only coding assistant. The actual code execution happens locally on the developer machine where the CLI is installed.

## Platform Availability & Installation

UTIM CLI is cross-platform and runs natively on Windows, macOS, Linux, and Android devices (via Termux).

### 1. Windows (PowerShell / CMD)
```bash
npm install -g @emend-ai/utim
```
Or via PowerShell installer script:
```powershell
iwr https://utim.dev/install.ps1 | iex
```

### 2. macOS & Linux (zsh / bash)
```bash
npm install -g @emend-ai/utim
```
Or via cURL installer script:
```bash
curl -fsSL https://utim.dev/install.sh | bash
```

### 3. Android Devices (Termux)
Install Termux from F-Droid, then run the multi-step installation command flow:
```bash
pkg update -y && pkg install nodejs python -y && npm install -g @emend-ai/utim
```

The Python source package can also be installed from a local checkout:

```bash
pip install .
```

For the full optional feature set from source:

```bash
pip install ".[full]"
```

Optional dependency groups:

- `search`: Scrapy, Scrapy Playwright, BeautifulSoup.
- `images`: Pillow image utilities.
- `parsers`: tree-sitter based code parsing.
- `full`: search, image, and parser dependencies together.

Requirements: Node.js 18+ and Python 3.9+.

## First run

Start UTIM inside a project folder:

```bash
cd my-project
utim
```

On startup UTIM initializes local workspace state by creating `.utim/` when needed. The bootstrap step sets up local storage, default project rules, default skill files, and the local SQLite intelligence database.

Sign in before sending prompts:

```bash
utim login
```

Inside the interactive terminal, `/login` performs the same login flow.

## Command line entrypoints

### `utim`

Starts the interactive terminal UI.

Useful options:

```bash
utim --dry-run
utim --sandbox
utim --sandbox-image ubuntu:22.04
utim --version
```

- `--dry-run`: simulates file edits and command execution without mutating the workspace.
- `--sandbox`: enables intelligent local sandboxing for risky terminal command proposals.
- `--sandbox-image`: legacy parameter retained for compatibility.
- `--version`: prints the installed UTIM version.

### `utim task "<prompt>"`

Runs one autonomous task and exits:

```bash
utim task "Fix the failing checkout tests"
utim task "Add profile settings page" --dry-run
utim task "Refactor the auth module" --sandbox
```

In an interactive terminal, file writes and risky commands can ask for confirmation. In non-interactive contexts, UTIM avoids hanging on prompts and handles approvals programmatically according to its mode.

### `utim doctor`

Runs diagnostics for:

- Python runtime and platform.
- Required dependencies.
- Optional feature dependencies.
- `.utim/` workspace state.
- UTIM API connectivity.
- OpenRouter connectivity.
- MCP server command availability.

### `utim init`

Initializes `.utim/`, the local database, project rules, and default local skills.

### `utim reset`

Clears the local `.utim` workspace cache after confirmation. This is intended for local state repair. It does not remove arbitrary project files.

### Account and billing commands

```bash
utim login
utim logout
utim usage
utim quota
utim plan
utim billing
utim upgrade
```

- `login`: authenticates the CLI and stores account credentials.
- `logout`: clears account credentials while preserving preferences and custom models.
- `usage`: shows live quota usage and refill details.
- `quota`: shows monthly quota and plan details.
- `plan`: fetches available subscription plans.
- `billing`: shows active billing profile details.
- `upgrade`: creates a subscription checkout link.

## Interactive slash commands

Slash commands are available inside the fullscreen UTIM terminal.

| Command | Purpose |
| --- | --- |
| `/about` | Shows version and product information. |
| `/auth` | Adds or updates an OpenRouter API key. |
| `/balance` | Shows credit balance and active plan details. |
| `/clear` | Clears active conversation and turn history. |
| `/doctor` | Runs diagnostics inside a scrollable terminal dialog. |
| `/help` | Lists available slash commands. |
| `/hint <text>` | Caches hidden guidance for the next user prompt. |
| `/login` | Starts the account login flow. |
| `/logout` | Signs out and clears stored account credentials. |
| `/mcp` | Opens the MCP server manager. |
| `/model` | Opens the model and provider selector. |
| `/new` | Starts a fresh chat session and clears active session state. |
| `/quit` | Exits UTIM. |
| `/redo` | Re-applies the last undone action. |
| `/report` | Creates a redacted diagnostic support bundle under `.utim_tmp/`. |
| `/chatrestore` | Toggles automatic session restoration on startup. |
| `/resume` | Lists, saves, or loads previous conversations. |
| `/rewind` | Restores workspace state to an earlier turn. |
| `/share` | Packages chat and workspace context for sharing. |
| `/status` | Shows active session statistics. |
| `/tools` | Enables or disables built-in tools and MCP tools. |
| `/undo` | Reverts the last agent action. |
| `/usage` | Opens quota usage and refill details. |
| `/rate` | Rates the last response and submits feedback. |
| `/feedbacks` | Admin-only feedback dashboard. |

## Core workflow

UTIM follows a stateful developer loop:

1. Read the user prompt.
2. Discover workspace context.
3. Retrieve project rules, local skills, and relevant memory.
4. Build a plan or checklist.
5. Invoke tools such as file readers, edits, shell commands, MCP tools, web search, image tools, or subagents.
6. Validate edits before writing when syntax checks are supported.
7. Show diffs or confirmations depending on mode.
8. Persist session state, turn history, and rollback data.
9. Offer verification commands or self-heal failures when enabled.

The loop is local-first: the codebase stays on the developer machine, while model calls and account services use configured providers and UTIM API services.

## Workspace files and directories

### `.utim/`

Persistent local workspace directory.

Common contents:

- `config.json`: local project config overrides.
- `utim_local.db`: local SQLite conversation and session database.
- `session_state.json`: active session state used for restoration.
- `AGENTS.md`: generated project-scoped operating rules.
- `UTIM.md`: generated default agent identity and operating guidance.
- `analytical_rules.md`: generated analytical framework.
- `skills/`: default local skills such as CLI UX, terminal UI, software architecture, MCP, async Python, LLM orchestration, and web design.
- `vector_db/`: local vector database when semantic memory is enabled.
- `experiences.json`: local experience memory when available.
- `mcp.json`: MCP server configuration when configured.

### `.utim_tmp/`

Temporary and support workspace directory.

Common contents:

- `backups/`: file snapshots used by undo, redo, and rewind.
- report bundles created by `/report`.
- generated metadata such as knowledge graph files and vector metadata.

### `~/.utim/`

Global user configuration directory.

Common contents:

- global `config.json`.
- account credentials and preferences.
- global logs.
- custom model definitions.

Local config overrides global config. Credentials are cleared by logout, while preferences and custom model entries are kept.

## Configuration

Important environment variables:

| Variable | Purpose |
| --- | --- |
| `UTIM_SERVER_URL` | Overrides the hosted UTIM API URL. |
| `UTIM_WEB_URL` | Overrides the hosted website URL used by auth flows. |
| `OPENROUTER_API_KEY` | Uses a local OpenRouter key. |
| `OPENROUTER_BASE_URL` | Overrides the OpenRouter-compatible base URL. |
| `UTIM_API_KEY` | Alternate API key lookup used by reflection paths. |
| `UTIM_EMAIL` | Overrides local email label in local-only paths. |
| `UTIM_DRY_RUN` | Enables dry-run mode when set to true-like values. |
| `UTIM_DEBUG` | Enables debug behavior when set to true-like values. |
| `UTIM_FALLBACK_MODELS` | Comma-separated fallback model list. |
| `UTIM_KEEP_TURNS` | Number of recent turns to keep in full context. |
| `UTIM_COMPRESSION` | Enables or disables adaptive context compression. |
| `UTIM_BLENDER_PATH` | Explicit Blender executable path. |
| `UTIM_ENABLE_REGRESSION_TESTS` | Enables regression testing loop when configured. |
| `TAVILY_API_KEY` | Enables Tavily-backed web search when available. |
| `NVIDIA_API_KEY` | Enables NVIDIA image/model routes when available. |

## Models and providers

UTIM provides a wide variety of official AI models, including both free and paid-tier options, optimized for autonomous workflows, code generation, and chat.

**Available Models Include:**

### Free Tier Models
- `cohere/north-mini-code:free`
- `google/gemma-4-26b-a4b-it:free`
- `google/gemma-4-31b-it:free`
- `inclusionai/ling-3.0-flash:free`
- `nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free`
- `nvidia/nemotron-nano-12b-v2-vl:free`
- `openai/gpt-oss-20b:free`
- `openrouter/free`
- `poolside/laguna-m.1:free`
- `poolside/laguna-s-2.1:free`
- `poolside/laguna-xs.2:free`

### Paid Tier Models (Hobby / Pro / Max / Ultimate)
- `aion-labs/aion-3.0`
- `aion-labs/aion-3.0-mini`
- `anthropic/claude-fable-5`
- `anthropic/claude-opus-4.5`
- `anthropic/claude-opus-4.6`
- `anthropic/claude-opus-4.7`
- `anthropic/claude-opus-4.8`
- `anthropic/claude-sonnet-4.5`
- `anthropic/claude-sonnet-4.6`
- `anthropic/claude-sonnet-5`
- `black-forest-labs/flux.2-flex`
- `black-forest-labs/flux.2-klein-4b`
- `black-forest-labs/flux.2-max`
- `black-forest-labs/flux.2-pro`
- `bytedance-seed/seedream-4.5`
- `deepseek/deepseek-r1`
- `deepseek/deepseek-v4-flash`
- `deepseek/deepseek-v4-pro`
- `google/gemini-2.5-flash-image`
- `google/gemini-3-pro-image`
- `google/gemini-3-pro-image-preview`
- `google/gemini-3.1-flash-image`
- `google/gemini-3.1-flash-image-preview`
- `google/gemini-3.1-pro-preview`
- `google/gemini-3.1-pro-preview-customtools`
- `google/gemini-3.5-flash`
- `google/gemini-3.6-flash`
- `inclusionai/ling-2.6-1t`
- `inclusionai/ling-2.6-flash`
- `krea/krea-2-large`
- `krea/krea-2-medium`
- `krea/krea-2-medium-turbo`
- `kwaipilot/kat-coder-air-v2.5`
- `kwaipilot/kat-coder-pro-v2`
- `kwaipilot/kat-coder-pro-v2.5`
- `meta/muse-spark-1.1`
- `microsoft/mai-image-2.5`
- `minimax/minimax-m2.5`
- `minimax/minimax-m2.7`
- `minimax/minimax-m3`
- `moonshotai/kimi-k2.5`
- `moonshotai/kimi-k2.6`
- `moonshotai/kimi-k2.7-code`
- `moonshotai/kimi-k3`
- `nex-agi/nex-n2-mini`
- `nex-agi/nex-n2-pro`
- `openai/gpt-5-image`
- `openai/gpt-5-image-mini`
- `openai/gpt-5.3-codex`
- `openai/gpt-5.4`
- `openai/gpt-5.4-mini`
- `openai/gpt-5.5`
- `openai/gpt-5.6-luna`
- `openai/gpt-5.6-luna-pro`
- `openai/gpt-5.6-sol`
- `openai/gpt-5.6-sol-pro`
- `openai/gpt-5.6-terra`
- `openai/gpt-5.6-terra-pro`
- `openai/gpt-image-1`
- `openai/gpt-image-1-mini`
- `openai/gpt-image-2`
- `qwen/qwen3.6-plus`
- `qwen/qwen3.7-max`
- `qwen/qwen3.7-plus`
- `recraft/recraft-v3`
- `recraft/recraft-v4`
- `recraft/recraft-v4-pro`
- `recraft/recraft-v4-pro-vector`
- `recraft/recraft-v4-vector`
- `recraft/recraft-v4.1`
- `recraft/recraft-v4.1-pro`
- `recraft/recraft-v4.1-pro-vector`
- `recraft/recraft-v4.1-utility`
- `recraft/recraft-v4.1-utility-pro`
- `recraft/recraft-v4.1-vector`
- `sourceful/riverflow-v2-fast`
- `sourceful/riverflow-v2-pro`
- `sourceful/riverflow-v2.5-fast`
- `sourceful/riverflow-v2.5-pro`
- `stepfun/step-3.7-flash`
- `thinkingmachines/inkling`
- `x-ai/grok-4.20`
- `x-ai/grok-4.3`
- `x-ai/grok-4.5`
- `x-ai/grok-build-0.1`
- `x-ai/grok-imagine-image-quality`
- `xiaomi/mimo-v2-pro`
- `xiaomi/mimo-v2.5`
- `xiaomi/mimo-v2.5-pro`
- `z-ai/glm-4.7`
- `z-ai/glm-5`
- `z-ai/glm-5-turbo`
- `z-ai/glm-5.1`
- `z-ai/glm-5.2`

UTIM also supports:

- Hosted UTIM/OpenRouter-backed models.
- Bring-your-own-key models through OpenAI-compatible endpoints.
- Separate model choices for the main agent and subagents.

Use `/model` to:

- Select the active model.
- Add custom providers.
- Add custom OpenAI-compatible models.
- Store custom model context windows.
- Delete custom models or providers.
- Configure subagent models for web search, project planning, image analysis, image generation, Blender vision, and Blender code generation.

Custom model entries include:

- `model_id`
- `provider_name`
- `base_url`
- `api_key`
- `context_window`

When keyring is available, UTIM stores custom provider keys there; otherwise it can store them in config and warns through logs.

## Credit and quota model

UTIM uses credits for hosted model usage.

General conversion:

- `1 USD = 1,000 credits`.

Quota surfaces:

- `/usage` and `utim usage`: live usage and refill details.
- `/balance`: balance and plan summary.
- `utim quota`: monthly quota and plan details.
- `utim plan`: plan comparison.
- `utim billing`: current billing profile.
- `utim upgrade`: subscription checkout.

Quota concepts:

- Free plans have refill and monthly allowance behavior.
- Paid plans can use five-hour quota, quota bank, and bonus quota.
- Bonus quota is consumed before active quota and bank quota.
- Top-ups and subscription actions are processed through hosted billing services.

Exact plan names, prices, and model allowlists can change, so the live pricing page and `utim plan` command are the source of truth.

## Built-in tools

The agent can call built-in local tools. Tool access can be toggled through `/tools`.

Important tools include:

- `read_file`: reads full files or line ranges, preserving beginning and end sections for very large files.
- `write_file`: writes files with syntax validation and rollback snapshots.
- `edit_file`: performs targeted string replacements or replacement batches.
- `run_command`: executes terminal commands, with timeout, safety checks, dry-run, and sandbox behavior.
- `list_directory`: lists directory contents.
- `web_search`: performs web research using available search routes.
- `plan_project`: delegates planning work to a planning subagent.
- `analyze_image`: analyzes local screenshots or images.
- `generate_image`: creates image assets through configured image models.
- `project_res`: performs deeper project resolution and architecture analysis.
- `blender_create_object`: creates procedural Blender objects.
- `blender_agent_create_from_image`: converts image understanding into Blender scene generation.

Default disabled tools include the Blender tools until enabled, because they require heavier local dependencies and a Blender installation.

## Data handling

UTIM is a local-first tool. Understanding where your data goes is important.

### Data that stays on your machine

The following never leaves your local filesystem:

- Source code files you read or write.
- Vector memory and project embeddings (`~/.utim/memory/`, `.utim/vector_db/`).
- Configuration and API keys (`~/.utim/config.json`, OS keyring).
- Session state and undo stack (`.utim/session_state.json`).
- MCP server configurations (`~/.utim/mcp_registry.json`).

### Data sent to UTIM backend

When you are logged in, UTIM contacts `api.utim.dev` for:

- Authentication (Firebase JWT validation).
- Quota accounting — **token counts only**, not prompt text.
- Optional cloud chat history sync (disable with `"sync_history": false` in config).
- Subscription and plan status.

The UTIM backend never sees the content of your prompts or source files.

### Data sent to model providers

When you send a prompt, it is forwarded to the LLM provider you have configured
(OpenRouter, OpenAI, Anthropic, Google, or your BYOK endpoint). The payload includes
your message text, the system prompt, injected memory snippets, and any file content
the agent explicitly reads. Each provider's own privacy policy governs retention.

For the full data-handling reference including retention periods, GDPR rights, and
provider policy links, see the `DATA_HANDLING.md` document in the installation directory.

## Safety model

UTIM is designed around reversible local changes and visible control.

Safety features:

- Dry-run mode for simulated actions.
- Sandbox mode for risky commands.
- Syntax validation before supported file writes.
- Backup snapshots before mutations.
- Undo, redo, and rewind.
- Confirmation flows for mutating operations in interactive mode.
- Non-interactive behavior that avoids hanging automation.
- Sensitive diagnostic report redaction.
- Tool-level enable and disable controls.

The CLI still operates with the permissions of the user running it. Treat it like a powerful local developer tool: run it in the intended workspace and review high-impact changes.

## Undo, redo, and rewind

UTIM tracks agent-applied edits as turns.

- `/undo`: restores files changed by the last agent turn.
- `/redo`: re-applies the last undone turn.
- `/rewind`: restores the workspace to a specific earlier turn.

Rollback data is stored locally in session state and `.utim_tmp/backups/`. Starting a new session with `/new` clears active session state so the next launch starts fresh.

## Session management

UTIM persists active state so the CLI can restore interrupted work.

Use:

- `/resume`: load or manage previous conversations.
- `/chatrestore`: toggle automatic session state restoration.
- `/new`: begin a clean session.
- `/clear`: clear active visible chat and turn history.

Local conversation records are stored in SQLite through SQLAlchemy.

Core conversation fields include:

- conversation id
- user id
- model id
- title
- messages JSON
- turn history JSON
- redo history JSON
- token usage input
- token usage output
- created and updated timestamps

SQLite uses WAL mode and normal sync mode for safer concurrent local writes.

## Semantic memory and RAG

When optional dependencies are installed, UTIM can use local semantic memory.

Components:

- ChromaDB persistent vector store.
- Sentence Transformers embeddings.
- Offline deterministic mock embeddings if model download is unavailable.
- Generated skill and project-rule documents.
- Experience feedback and reflection records.

Typical retrieval sources:

- `.utim/AGENTS.md`
- `.utim/UTIM.md`
- `.utim/analytical_rules.md`
- `.utim/skills/*/SKILL.md`
- `.agents/skills/*/SKILL.md`
- previous experience and reflection data

The bootstrap system creates default local skills for terminal UI, architecture, MCP development, CLI UX, premium web design, LLM orchestration, and async Python.

## Context pruning and compression

UTIM manages long conversations with adaptive context pruning.

Behavior:

- Recent user turns are preserved.
- Tool results with code, errors, and tracebacks receive higher importance.
- Lower-importance old messages can be pruned first.
- When appropriate, discarded content can be compressed into a dense technical summary using fallback models.
- Fallback models can be overridden with `UTIM_FALLBACK_MODELS`.

Config controls:

- `UTIM_KEEP_TURNS`
- `UTIM_COMPRESSION`

## MCP integration

MCP lets UTIM connect external tools through a standard protocol.

Use `/mcp` to install, configure, list, and connect MCP servers.

Use `/tools` to enable or disable exposed MCP tools.

Configured servers are read from `.utim/mcp.json` and related config. MCP clients spawn subprocesses, manage stdio or compatible transports, validate tool schemas, and expose remote tools to the orchestrator.

The bundled registry includes common categories such as:

- SQLite
- PostgreSQL
- GitHub
- GitLab
- filesystem
- search providers
- automation tools

MCP server health is checked by `/doctor`.

## Web search

UTIM has a web-search tool path for research and documentation lookup.

Available routes can include:

- Tavily API when `TAVILY_API_KEY` is configured.
- LLM-assisted web search through configured model routes.
- Scrapy and Scrapy-Playwright crawlers when optional search dependencies are installed.

Search results are converted into agent-readable context before use.

## Image and visual tools

When the relevant dependencies and model access are available, UTIM supports:

- image analysis
- screenshot interpretation
- image generation
- visual QA workflows
- Blender scene/object generation

`analyze_image` reads local images and sends relevant context to a vision-capable model. `generate_image` routes image generation through configured model providers. Blender tools use `UTIM_BLENDER_PATH`, stored Blender config, common Windows paths, or `PATH` discovery.

## Knowledge graph

With parser dependencies installed, UTIM can build a project knowledge graph.

It uses tree-sitter parsers for supported languages to extract:

- functions
- classes
- imports
- calls
- dependency relationships

The graph can be written under `.utim_tmp/knowledge_graph.json` and used to reason about change impact.

## Reflection and feedback

UTIM can collect feedback and turn outcomes to improve future behavior.

Related commands:

- `/rate`
- `/feedbacks` for admin users

The reflection system can extract lessons from successful or failed runs, store them in local memory, and later retrieve relevant guidance for similar prompts.

## Sharing and support bundles

### `/share`

Packages chat context and workspace data for collaboration through the UTIM sharing flow.

### `/report`

Creates a redacted support zip bundle under `.utim_tmp/`. The report path is shown after creation. Report generation is intended for troubleshooting and avoids exposing obvious secrets.

## Common workflows

### Feature development

```text
Add password reset flow with email token validation.
```

UTIM should inspect the app structure, identify auth modules, plan changes, edit files, and suggest or run tests.

### Bug fixing

```text
Fix the TypeError in the checkout tests and run the smallest relevant test.
```

UTIM should inspect the failing path, patch the cause, and verify with targeted commands.

### Refactoring

```text
Refactor the API client into a typed service layer without changing public behavior.
```

UTIM should map call sites, keep blast radius controlled, and preserve tests.

### Documentation

```text
Update the README to include installation, environment variables, and troubleshooting.
```

UTIM should inspect current docs, avoid duplicating stale details, and update the right files.

### UI work

```text
Make the pricing page mobile-ready and verify the cards do not overlap.
```

UTIM should inspect existing styles, preserve the design system, and run a build or visual check where available.

## Troubleshooting

### Login required before prompts

Run:

```bash
utim login
```

Then restart `utim` or retry the prompt.

### Missing optional feature

Install the full feature group from source:

```bash
pip install ".[full]"
```

Or install only the relevant optional group.

### MCP server not found

Run:

```bash
utim doctor
```

Then confirm the configured command exists on `PATH` and required environment variables are set.

### Blender tools unavailable

Install Blender and set:

```bash
UTIM_BLENDER_PATH=/absolute/path/to/blender
```

Or configure the path in UTIM config.

### State feels stale

Inside UTIM:

```text
/new
```

Or use:

```bash
utim reset
```

`utim reset` asks for confirmation and clears local `.utim` cache.

### Build or test commands are risky

Start with:

```bash
utim --dry-run
utim --sandbox
```

Then review proposed changes before allowing real writes or command execution.

## Business readiness checklist

This website and CLI are close to a public beta posture, but production readiness should be judged across product, security, billing, support, and release operations.

Ready signals already present:

- A real CLI entrypoint and package metadata.
- Versioned Python package configuration.
- Interactive and task-mode workflows.
- Account login and logout.
- Quota, billing, plan, usage, and upgrade commands.
- Diagnostics through `utim doctor` and `/doctor`.
- Redacted support bundle generation.
- Local undo, redo, rewind, and session restoration.
- MCP extension path.
- Optional dependency groups for advanced features.
- Website pages for docs, pricing, support, privacy, terms, refund, and license.

Gaps resolved:

- ✅ **Version synchronization**: `utim_cli/_version.py` is the single source of truth. `scripts/sync_version.py` propagates to `package.json`, `pyproject.toml`, and `CHANGELOG.md`. Version is tested in `tests/test_smoke_install.py`.
- ✅ **Security policy**: `SECURITY.md` now contains `security@utim.dev`, disclosure timeline, scope, bug bounty terms, and per-surface data handling summary.
- ✅ **Data-handling docs**: `DATA_HANDLING.md` documents what stays local, what goes to UTIM backend, and what goes to model providers. Privacy.md and docs.md now include inline summaries.
- ✅ **Stale marketing claims**: Removed unsubstantiated claims in CHANGELOG v1.43.20.
- ✅ **E2E test coverage**: `tests/test_e2e.py` covers auth, quota, docs rendering, support docs, pricing claims, and version sync. `tests/test_smoke_install.py` covers both npm and pip install paths.
- ✅ **Bundle size warnings**: `landing/vite.config.js` now uses `manualChunks` to split Firebase, Three.js, Framer Motion, React, and Markdown into separate async chunks.

Remaining gaps (still to resolve):

- Add automated CI pipeline that builds the landing site and runs the Python test suite on every push.
- Add a migration and recovery guide for `.utim/` and `.utim_tmp/`.
- Add uptime, incident, and status-page expectations if selling paid plans.
- Confirm mobile viewport visual QA from a real device (capture screenshots in CI).

Business-ready verdict:

UTIM is suitable for technical beta users and early adopters. For paid production customers, finish the documentation/version synchronization, security policy, automated release checks, support operations, and billing verification tests before positioning it as fully enterprise-ready.

---

## Referral Program

UTIM has a built-in referral system that lets you earn perpetual discounts on any paid plan just by sharing your unique referral link.

### How It Works

Every UTIM account has an 8-character unique referral code (e.g. `a1b2c3d4`) and a shareable referral URL of the form:

```
https://utim.dev/auth?ref=<your-code>
```

When someone signs up using your link, they are automatically linked to you as your referee. Every time a referee purchases or renews a paid subscription, your discount on that specific plan increases by **2%**.

### Discount Rules

| Rule | Detail |
|------|--------|
| Discount per referee purchase | +2% |
| Maximum discount | 100% (plan is completely free) |
| Discount scope | Per plan — discounts are plan-specific |
| Stacking | Yes — each new referee purchase stacks |
| Renewals | Yes — renewal payments stack the discount again |
| Transfer | No — discounts cannot be transferred between plans |

**Example:**

- You refer user B → B buys Hobby → you get 2% off Hobby
- You refer user C → C buys Hobby → you now get 4% off Hobby
- You refer user D → D buys Pro → you also get 2% off Pro (separately)
- When B renews next month, you get another 2% discount (now 6% off Hobby). Every purchase (first-time or renewal) by a referred user stacks a 2% discount for you.
- If you (User A) purchase the plan, the stacked discount is consumed and applied to your bill.
- After purchase, your discount resets to 0% and starts stacking again when a referred user renews or a new referee purchases the same plan.

### Where to Find Your Referral Link

Visit [utim.dev/referral](https://utim.dev/referral) while logged in. The page shows:

- Your unique referral code and link (with copy buttons)
- Total referrals, active discounts, and a per-plan discount breakdown
- Progress bars showing how close each plan is to 100% free
- A top referrers leaderboard

### Discounts on the Pricing Page

When you open the pricing checkout, any active referral discounts are automatically applied to the displayed price. Plans where you have earned a discount show the original price crossed out alongside the discounted price and a green `% OFF (Referrals)` badge.

### Referring Someone

Share your referral link directly:

```
https://utim.dev/auth?ref=<your-code>
```

When the new user registers through your link, the referral code is pre-filled in the signup form. The system links the account automatically after registration.

Existing users can also manually enter your code in the referral code field on the registration form, or visit their referral dashboard to check their referral status.

### Earning Discounts

Discounts are credited automatically the moment a payment is verified. No manual redemption is required. The discount is applied at checkout on your next billing cycle — prices on the pricing page update in real time after you log in.

### Abuse Policy

The referral system is monitored for fraudulent activity. Self-referrals are blocked. Creating duplicate accounts to generate referrals is a violation of UTIM's Terms of Service and may result in account suspension and discount reversal.

