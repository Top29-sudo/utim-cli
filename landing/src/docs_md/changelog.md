# Changelog

## [2.2.1] - 2026-08-13

### 🛠️ Fixes & Minor Polish
- **TUI Input Divider Line**: Updated input area horizontal divider line to extend full width across the terminal screen (`shutil.get_terminal_size().columns`) with line-wrap protection.
- **Subagent Swarm Visualizer Mobile Responsiveness**: Added mobile responsive breakpoint styles (`.st-swarm-canvas`), card container bounds, text truncation, and flex badge anchors (`DISPATCHER`, `DONE`, etc.) to prevent layout overflow on mobile screens.
- **OS-Specific Requirements Architecture**: Added dedicated lightweight requirement files (`requirements_android.txt`, `requirements_windows.txt`, `requirements_desktop.txt`, `requirements_full.txt`) and updated installer scripts (`install.sh`, `setup_utim1.py`) to select pure-Python requirements for Android/Termux without PyPI binary wheel dependencies.
- **Reflection Pipeline Primary Model**: Updated reflection and experience extraction model fallback chain to use `openrouter/free` as the primary model (`REFLECTION_PRIMARY_MODEL`).
- **Correction Fast-Path Engine**: Removed keyword-matching gate on correction detection, delegating judgment directly to the reflection LLM for zero false negatives.

## [2.2.0] - 2026-08-13

### 🛠️ Fixes
- Modified interface

## [2.1.2] - 2026-08-10

### 🛠️ Fixes
- **Fixed `grep_search` auto-regex promotion bug**: Queries containing regex metacharacters (`|`, `\`, `*`, etc.) were silently auto-promoted to regex mode even when `is_regex=False`, causing literal searches to fail with "No matches found." Now `is_regex=False` always means literal search, matching the documented "Literal-first semantics."
- **Made ripgrep an automatic dependency**: Added `ripgrep>=0.13.0` to core dependencies in `pyproject.toml` and `requirements.txt`. The `_grep_find_ripgrep()` function now falls back to the `ripgrep` PyPI package (which bundles a prebuilt binary) when ripgrep isn't found on the system PATH, ensuring fast searches work out of the box.
- **Increased context compression interval from 25 to 35 iterations**: Reduced compression frequency to conserve context resources and improve performance during long agent sessions.
- **Reduced batch poll interval from 5s to 0.3s**: Improved responsiveness of batch status checks in `BatchAPIProcessor.poll_and_retrieve_results()`.
- **Cleaned up network error messages in feedback dialog**: Stripped verbose `HTTPSConnectionPool` technical details from error messages, now showing clean messages like "Connection timed out. Please check your network and try again."

## [2.1.1] - 2026-08-06

### 🛠️ Fixes
- **Enhanced `grep_search` reliability**: Fixed broken auto-regex promotion, ripgrep flag bugs (`-max-count` → `--max-count`), single-file `--with-filename` handling, Windows drive-letter colon parsing, and fallback file-list mode counting. Added dual-engine architecture (cached ripgrep fast-path + multithreaded Python fallback), binary-file sniffing, symlink-cycle protection, expanded noise filtering, and multi-encoding support.

## [2.1.0] - 2026-08-05

### ⚡ Performance
- **Added `UTIM_LITE_MODE=1` for low-spec PCs**: Skip loading heavy ML models (ChromaDB, sentence-transformers, MiniLM embeddings, local Qwen/torch download). CLI now starts instantly with no model-download lag. Enabled by default for users on `bin\utimlite.cmd`.
- **New `utimlite` launcher** alongside `utim` (full mode) — `bin\utimlite.cmd` sets `UTIM_LITE_MODE=1` and runs the same app with a lightweight backend.
- **Heavy dependencies are now opt-in**: `chromadb` + `sentence-transformers` moved out of core deps into the new `memory` extra (`pip install "utim-cli[memory]"`). Core install is now 11 lightweight deps only.

### 🛠️ Fixes
- **Fixed Parasail `400 'Expecting value: char 200'` error**: Python's `json.dumps` emits `NaN`/`Infinity` which strict providers (Parasail) reject with a JSON parse error. Added recursive `_sanitize_json()` in `client_utils.py` and wired it into `proxy_openrouter_request()` so every outbound LLM payload is now strict-JSON-safe (non-finite floats → `null`).
- **Fixed `Wrong color format 'dim'` crash in publish dialog** (carried from 2.0.4).

### 🔐 Security Hardening
- **CLI signature middleware** with HMAC-SHA256 per-build secrets, install-id binding, and atomic nonce consumption (replay-attack resistant).
- **Pluggable CAPTCHA** (reCAPTCHA / Turnstile / hCaptcha) on `/auth/*` endpoints.
- **OpenRouter attribution centralized** via `OPENROUTER_HEADERS` and propagated to all client entry points (`proxy_openrouter_request`, `orchestrator.py` streaming path, `agent.py` ReActAgent, `server/routes/completion_routes.py` primary `/completions` server path, `server/router.py`, `security_routes.py`).
- **Audit logging** with automatic PII/sensitive-data sanitization.
- **Body-stream caching middleware** + atomic nonce DB updates bound to `(install_id, ip)`.
- **`provision_build.py`** for release-time secret generation/rotation.
- **Hardened CORS**: replaced permissive `*.utim.dev` regex with explicit allowlist (`www.utim.dev`, `api.utim.dev`).
- **Request size limits**: 4MB default, 16MB marketplace; **web search sandboxing** (64KB response cap, 500-char query limit, host allow-list).
- **Fixed abort-then-print bug** in `orchestrator.abort()`: removed premature `self.cancel_event.clear()` that re-enabled stream printing after abort — event now stays set until turn-reset paths clear it.

## [2.0.4] - 2026-08-05

### 🛠️ Fixes
- **Fixed `Wrong color format 'dim'` crash in publish dialog**: Corrected style strings in `utim_cli/tui/publish_dialog.py` to use `class:dim fg:#hex` format instead of `dim fg:#hex`, preventing the `ValueError: Wrong color format 'dim'` crash when using prompt_toolkit 3.0.40+.

## [2.0.3] - 2026-08-04

### 🛠️ Fixes
- **Fixed `Wrong color format 'dim'` crash in marketplace TUI**: `prompt_toolkit` does not accept the `dim` modifier as a free-floating token before a color, nor `class:dim` as a literal inline style. All `f"dim {_MUTED}"` / `f"dim {_FG}"` style strings in `utim_cli/tui/marketplace_dialog.py` have been rewritten to `f"fg:{_MUTED}"` / `f"fg:{_FG}"`, and the `[dim]…[/dim]` markup parser now drops the `dim` token instead of emitting the unsafe `class:dim` class string. `/marketplace` no longer crashes on Windows when rendering info/hint/status rows.

## [2.0.2] - 2026-08-04

### 🛠️ Fixes
- Minor bug fixes.

## [2.0.1] - 2026-08-04 - Bugfix & Adaptive Iteration Budget

### 🛠️ Fixes
- **Fixed `unhashable type: 'slice'` crash in `_get_display_arg`**: `run_command` args are now defensively coerced to strings (handles malformed LLM args that arrive as list/dict instead of str).
- **Fixed thinking spinner persisting after response ends**: `STATE["thinking_topic"]` is cleared immediately after the response completes, so the spinner stops instead of animating through the entire response-end compression.
- **Response-end compression now runs in a background thread**: The elapsed-time rule prints instantly; context compression happens silently behind the scenes without blocking the UI.

### 🧠 Adaptive Iteration Budget (Window-Aware)
- **Removed hardcoded "45 iterations max" from system directives**: The iteration budget is now computed at runtime from the model's context window.
- **Budget scales with context window** using the same buckets as compression intervals:
  - `< 200k` context: budget `25`
  - `200k – 500k` context: budget `35`
  - `500k – 1M` context: budget `40`
  - `1M+` context: budget `45`
- **One-shot milestone warnings**: Mid-task warning, "5 iterations left" urgent warning, and "+5 granted" notice each fire exactly once per model/iteration (tracked via `_milestones_fired` set) instead of repeating on every request.

## [2.0.0] - 2026-08-04 - UTIM V2.0 RELEASE

### 🚀 Major Release: UTIM V2.0 — Creators Ecosystem & Adaptive Intelligence

UTIM V2.0 brings a massive architectural leap, introducing the global Creators Marketplace ecosystem, dynamic context compression scaling, script-based miniagents, and modular workspace skills.

### 🏪 Creators Marketplace
- **Creators Ecosystem**: Browse, search, install, purchase, and publish custom skills and script-based miniagents globally directly from the CLI (`/marketplace`).
- **Publisher Profile & Wallet**: Built-in profile management (`display_name`, `bio`, `avatar_emoji`), earnings tracking, UPI/Bank payout withdrawal requests, and admin approval workflows.
- **Action-Gated Profile Setup**: Instant unauthenticated browsing for all users. Profile setup is required strictly when purchasing, reviewing, installing, or publishing extensions.
- **Clean Full-Screen Dialogs**: Upgraded all text prompt inputs to full-screen TUI buffers to prevent stdout text leakage into terminal scrollback.

### 🧠 Dynamic Context Compression Based on Model's Context Window
- **Adaptive Compression Scaling**: Context compression automatically adjusts its periodic iteration interval based on the model's context window:
  - **`< 200k` context**: every `10` iterations
  - **`200k – 500k` context**: every `20` iterations
  - **`500k – 1M` context**: every `30` iterations
  - **`1M+` context**: every `45` iterations
- **Real-Time Model Detection**: Switching models dynamically recalculates both compression thresholds and iteration intervals in real-time.
- **Folder Size-Based Miniagent Model Selection**: Miniagents dynamically select primary models based on package folder size (`inclusionai/ling-3.0-flash:free` for <100KB, `nvidia/nemotron-3-ultra-550b-a55b:free` for 100-150KB, `deepseek/deepseek-v4-flash-0731` for 150-300KB, and `openai/gpt-5.6-luna-pro` for ≥300KB).

### 🤖 Create Miniagents
- **Interactive Miniagents Manager**: Full TUI wizard (`/miniagents`) to view, design, test, and delete script-based executable miniagent tools.
- **`@miniagents` Prompt Integration**: AI-assisted architecture prompt guides UTIM to craft complete `agent.json`, `agent.py` / `agent.js`, and `README.md` files.

### 🎯 Create Skills
- **Modular Workspace Skills**: Interactive skills manager (`/skills`) to author domain-specific guidance packs (`SKILL.md`).
- **`@skills` Tagging & Context Injection**: Tag `@<skill>` or `@skills` to inject context-aware guidelines into LLM prompts on demand.
- **Strict Skill Validation**: Enforcement of strict directory structure for published skills (ONLY `SKILL.md` and `README.md` allowed; no extra files or subdirectories).
- **Skill Security Scanning Suite**: Configured `inclusionai/ling-3.0-flash:free` (primary) and `deepseek/deepseek-v4-flash-0731` (fallback) for skill verification checks.

## [1.48.5] - 2026-07-25

### Fixed
- **Minor Bug Fixes & Modifications**: Resolved TUI thinking indicator rendering issues, fixed dialog loop upon cancellation, improved chat tag distinction with timestamps, and fixed per-session usage tracking across conversation resumes and web UI displays.

## [1.48.4] - 2026-07-25

### Fixed
- **Minor Bug Fixes**: Under-the-hood optimization and resolution of minor dependency issues.

## [1.48.3] - 2026-07-25

### Fixed
- **Blender 3D Tools**: Fully restored normal functionality and re-enabled the local Blender asset generation workflow and agent scripts.
- **Windows Shell Sanitization**: Resolved issues with Unix commands like `mkdir -p` and `rm -rf` failing on native Windows PowerShell by introducing automatic translation to `New-Item` and `Remove-Item`.
- **Command Redirection Safeguards**: Automatically blocks Bash-style here-docs (`<<`) on Windows with a helpful prompt to guide models to use proper file-write tools.
- **UI Abort and Confirmation Fixes**: Removed the 30-second background timeout on confirmation dialogs to prevent thread synchronization freeze states. Fixed signal-handling bugs so pressing Ctrl+C or Esc immediately cancels active HTTP streams and releases the CLI layout.

## [1.48.2] - 2026-07-23
- **Minor Bug Fixes**: Under-the-hood optimization and resolution of minor dependency issues.

## [1.48.1] - 2026-07-23

### Fixed
- **Minor Bug Fixes**: Under-the-hood optimization and resolution of minor dependency issues.

## [1.48.0] - 2026-07-23

### Added
- **Quota Sharing & Redeem Code Ecosystem**: Added `/quotashare` menu action and `/redeem` command. Allows users to share their rollover Quota Bank and regular subscription credits. Supports direct credit transfer to referred referees as well as generating non-expiring secure redeem codes (`UTIM-XXXX-XXXX-XXXX`).

## [1.47.16] - 2026-07-21

### Added
- **New General Models (`google/gemini-3.6-flash` & `poolside/laguna-s-2.1:free`)**: Registered Google's next-gen `google/gemini-3.6-flash` and Poolside's free `poolside/laguna-s-2.1:free` model into the UTIM model registry with OpenRouter pricing and 5% platform markup.
- **Krea 2 Image Subagent & Reasoning Modes**: Added `krea/krea-2-medium-turbo`, `krea/krea-2-medium`, and `krea/krea-2-large` image generation models with 5% OpenRouter pricing markup. Consolidated image subagent selection into a single `"Krea 2 image"` model entry that dynamically maps reasoning modes:
  - **Low Reasoning**: uses `krea/krea-2-medium-turbo` in background.
  - **Medium Reasoning**: uses `krea/krea-2-medium` in background.
  - **High Reasoning**: uses `krea/krea-2-large` in background.

## [1.47.15] - 2026-07-21

### Fixed
- **Command Title & Argument Alias Resolution**: Updated `_manual_confirm_internal` in `utim.py` to extract all possible command argument aliases (`CommandLine`, `cmd`, `script`, `shell`, `command`, `commands`, `TargetFile`, `file`) from model tool calls. Fixes an issue where models using `CommandLine` or `cmd` produced empty target command titles inside confirmation panels.
- **Command Confirmation Rendering & ANSI Key Handling**: Added `sys.__stdout__.flush()` to ensure the confirmation panel and options render immediately on screen without requiring keypresses or Enter. Fixed Windows ANSI escape sequence parsing (`\x1b[A` / `\x1b[B`) in `_read_arrow_choice`, resolving an issue where pressing Up or Down Arrow triggered immediate false command rejection.
- **Command Confirmation UI Thread Isolation**: Wrapped manual confirmation dialogs (`_manual_confirm`) inside `_run_in_terminal_safe()` so `prompt_toolkit` cleanly suspends its main layout rendering loop during command approvals. Fixes terminal freezes and input collisions, restoring smooth arrow-key navigation (`Up`/`Down`/`j`/`k`/`w`/`s`), instant `Enter` selection, and hotkey support (`y` for Accept, `n`/`q` for Reject).
- **Command Safety Classification Rules**: Refactored `analyze_command_safety` so that non-destructive commands (`python app.py`, `npm run dev`, `npm install`, `pip install`, `git commit`, `git push`, `curl`, `node`, etc.) are classified as **SAFE**. Commands are marked **RISKY** strictly if they perform file, directory, untracked git file, or process deletion/removal operations (`rm`, `del`, `rd`, `rmdir`, `remove-item`, `unlink`, `rmtree`, `git clean`, `kill`, `taskkill`, `os.remove`, `shutil.rmtree`, or python scripts containing deletion operations).
- **Project-Relative Path Resolution**: Added `resolve_project_path` helper across all file tools (`read_file`, `write_file`, `edit_file`, `list_directory`, `view_symbol`, `view_file_outline`, `run_command`). Fixes Windows path resolution where LLM-emitted paths starting with leading slashes (e.g. `/social-media-manager/src/app.py` or `/src/index.js`) were mapped to the drive root `C:\` instead of the user's active project working directory.

## [1.47.14] - 2026-07-21

### Added
- **Command Approval 60s Auto-Decline Timeout**: Interactive terminal command and file edit confirmation prompts (`_manual_confirm`) now automatically decline after 60 seconds of inactivity (`timeout_seconds=60.0`). Prevents the agent from hanging indefinitely when users are away from their terminal while performing other tasks.
- **Background Command Execution & Detach Mechanics**: Added `is_background` and `wait_seconds` parameters to `run_command` so long-running servers and background tasks (`npm run dev`, `vite`, `python server.py`) capture initial output (default 5s) and continue in the background without blocking the agent. Added `Ctrl+B` keybinding for interactive command detachment, along with process management tools (`list_background_processes`, `get_background_output`, `send_background_input`, `stop_background_process`).

### Fixed
- **Live System Prompt Hint Injection**: Updated `/hint` command handling to inject live pending user directives directly into the system prompt on the very next model call/iteration, ensuring mid-turn hints immediately guide active reasoning and tool selection.
- **Empty Model Response Fallback**: Added explicit fallback response string when a model returns both empty text and no tool calls, preventing empty output errors.

## [1.47.13] - 2026-07-21

### Added
- **Background Command Execution & Detach Mechanics**: Added `is_background` and `wait_seconds` parameters to `run_command` so long-running servers and background tasks (`npm run dev`, `vite`, `python server.py`) capture initial output (default 5s) and continue in the background without blocking the agent. Added `Ctrl+B` keybinding for interactive command detachment, along with process management tools (`list_background_processes`, `get_background_output`, `send_background_input`, `stop_background_process`).

### Fixed
- **Live System Prompt Hint Injection**: Updated `/hint` command handling to inject live pending user directives directly into the system prompt on the very next model call/iteration, ensuring mid-turn hints immediately guide active reasoning and tool selection.
- **OpenRouter Reasoning & Temperature Normalization**: Formatted `reasoning` payload as `{"effort": "..."}` matching OpenRouter API schema without extra `"enabled": true` property. Omitted default `temperature` overrides on reasoning models to prevent OpenRouter from returning `HTTP 400 Bad Request`.
- **BYOK Model Tool Calling Preservation**: Guaranteed tool calling array (`tools`) is 100% preserved for all tool-capable models (including `minimaxai/minimax-m3`, `thinkingmachines/inkling`, `deepseek-r1`, `o1`, `claude-3.5-sonnet`, `gpt-4o`).
- **HTTP 400 Rich Markup Error Message Formatting**: Wrapped HTTP 400 error message text with `rich.markup.escape`, ensuring exact backend API error messages are cleanly printed in red console logs.

## [1.47.12] - 2026-07-21

### Fixed
- **Event Loop Rich Markup Escape Import**: Moved `from rich.markup import escape` to top-level module imports in `utim_cli/utim.py`. Resolves `NameError: name 'escape' is not defined` when pressing `Enter` to submit typed or pasted prompts in the terminal input field.

## [1.47.11] - 2026-07-20

### Fixed
- **Termux Pure-Python Architecture Validation**: Finalized pure-Python dependency isolation in `pyproject.toml` and `requirements.txt`. Confirmed 100% feature parity for MCP tools and HTTP LLM completions on Android Termux without requiring native C/Rust compilers or `pydantic-core`.

## [1.47.10] - 2026-07-20

### Fixed
- **Android Termux Pure-Python Decoupling**: Completely removed legacy `mcp` and `openai` package declarations from core `dependencies` in `pyproject.toml` and `requirements.txt`. UTIM CLI's native `PurePythonMCPSession` (line-delimited JSON-RPC stdio) and HTTP completions require zero C/Rust dependencies, eliminating all `pydantic-core`, `jiter`, `rpds-py`, and `greenlet` wheel build attempts on Android Termux.
- **Termux Installer & Setup Optimization**: Removed legacy `pydantic` and Rust build tool download steps from npm installer (`bin/utim.js`), leveraging pure-Python stdio client on Android Termux.
- **Rich Markup Exception Fix**: Escaped dynamic user prompts, topics, and message previews rendered in history view to prevent `rich.markup.MarkupError` on unclosed brackets.
- **Tool Loop False-Positive Fix**: Updated failure detection in `orchestrator.py` to prevent reading source code containing words like "error" or "failed" from triggering false tool loop warnings.

## [1.47.9] - 2026-07-20

### Fixed
- **Android Termux Zero-Rust Installation**: Updated `install.sh` and expanded platform dependency markers in `pyproject.toml` and `requirements.txt` across all Linux ARM architectures (`armv7l`, `armv8l`, `arm`, `aarch64`). This prevents `pip` from attempting to build Rust wheels for `pydantic-core`, `jiter`, `rpds-py`, or `greenlet`, allowing UTIM CLI to install in seconds on Termux.

## [1.47.8] - 2026-07-20

### Added
- **Android Termux Pure-Python Architecture**: Implemented pure-Python line-delimited JSON-RPC stdio client fallback (`PurePythonMCPSession`) for Model Context Protocol (MCP) servers, enabling 100% feature parity on Android Termux without requiring Rust compilation or `pydantic-core`.
- **Web Support Assistant Disclaimer & Installation Flow**: Added glassmorphism notice bar and 4-step installation visual guide on landing website to distinguish web support chat from local CLI agent.
- **Enhanced Cognitive Reflection Pipeline**: Replaced single-turn random skill creation with a 5-request interaction buffering engine. Analyzes full interaction trajectories across turns (detecting silent tool calling and file format assumption complaints like image PDFs vs text PDFs), with strict usefulness filtering to prevent storing junk data.
- **RAG-Based Skill Creation & Intelligent Hold-Back Architecture**: Implemented RAG skill synthesis over ChromaDB Vector Memory. Enforces a minimum threshold ($\ge 3$ accumulated experiences across sessions), an LLM usability/cohesion evaluation (`is_sufficiently_usable`), and cooldown stride tracking to hold back skill creation until technical patterns are mature and genuinely usable.

### Fixed
- **Device Sign-In Unauthenticated Flow**: Fixed device authorization flow on `https://utim.dev/activate?code=XXXX-XXXX`. Auto-redirects unauthenticated users to `/auth` with a countdown while preserving the device code, bouncing them back to `/activate` automatically after sign-in to complete terminal authorization without broken loops.

## [1.47.6] - 2026-07-19

### Added
- **Asynchronous Local LLM Setup**: Moved the local Qwen model downloading and setup pipeline into a background daemon thread, allowing UTIM to run completions instantly via Cloud API during initial setup/installation without blocking user queries.

## [1.47.5] - 2026-07-19

### Optimized
- **Instant startup / rules summarization**: Prioritized Cloud API completion calls (via UTIM completions server or direct OpenRouter) over local Qwen LLM execution in `summarize_experiences_with_model`. This completely eliminates the 1m 49s latency caused by importing PyTorch/Transformers and loading the 0.5B model from scratch, falling back to local execution only in offline mode.

## [1.47.4] - 2026-07-19

### Fixed
- **Completions Server Routing bypass**: Re-engineered model endpoint resolution to respect the user's active UTIM plan subscription and selected completions source (`"main_model_source": "utim"`), preventing local environment variables (like `OPENROUTER_API_KEY`) from silently hijacking completions routing.

## [1.47.3] - 2026-07-19

### Added
- **Startup Skills Injector**: Integrated a dynamic workspace-wide scanning system to catalog available skills and inject their exact names, descriptions, and absolute paths directly into the system prompt on startup, preventing redundant recursive searches and enabling instant, direct skill file reading.
- **Fast Deletion in Skills Manager**: Bypassed the typing confirmation dialog when deleting custom skills inside the interactive `/skills` menu, allowing instant deletion of custom skill folders.

### Fixed
- **Cancellation Socket Deadlock**: Structured a thread-safe connection binder within the LLM orchestration loop that exposes the active stream response object, allowing keyboard cancellation handlers (`Esc` and `Ctrl+C`) to abort the socket connection immediately and release the prompt queue lock, resolving a deadlock that froze subsequent user requests.

## [1.47.2] - 2026-07-18

### Fixed
- **UnboundLocalError in Command Output Renderer**: Pre-initialized stdout and stderr lines lists in `_render_result` to prevent runtime exception on commands yielding empty output.
- **Chunk-Boundary Unicode Decode Errors**: Upgraded `read_file` tool to slice trailing incomplete bytes during UTF-8 checks, preventing decoding failures on split multi-byte character boundaries.
- **Reflection Engine Skill Creation Guardrail**: Restructured reflection engine to only create new skill files when at least 3 substantial guidelines (each >= 40 characters) are suggested, preventing clutter from useless "one-liner" skills.
- **Console Status Spinner Fallback**: Patched the `console.status` spinner in `utim.py` to check for legacy Windows CMD/conhost and non-UTF-8 environments, dynamically falling back to ASCII `line` spinners instead of unicode dots.
- **Support Chat Model Casing**: Updated frontend support assistant to target `openrouter/free` exclusively to maintain service reliability.

## [1.47.1] - 2026-07-18

### Added
- **Referral Program**: Launched a full referral system. Referrers earn a 2% per-plan discount for each referred user who purchases a subscription. Discounts stack per-plan up to 100% (fully free). Every payment renewal by a referee adds another 2%. Referral dashboard available at `/referral` with live discount breakdown, progress bars, copy-ready referral link/code, and a leaderboard.
- **Instant Server-Side Deletion**: Connected client share deletion to a new `DELETE /shares/delete/{share_id}` server endpoint to destroy shared zip packages and metadata instantly when removed from the CLI dashboard.
- **Custom Exclude Checklist Option**: Embedded a dynamic `[ Add custom files/folders... ]` checkbox directly into the share wizard to prompt for custom omits only when selected, rather than asking unconditionally.
- **Exclusion Path Root Validation**: Added validation to reject and display warnings for typed/pasted custom paths that fall outside the current workspace root directory.
- **Ctrl+D Dashboard Shortcut**: Resolved key collision where pressing `D` got typed in the default-focused search bar by binding `Ctrl+D` globally to delete the active share.

### Fixed
- **Content Security Policy Alignment**: Added `https://ipapi.co` and `https://analytics.google.com` to Netlify's `connect-src` CSP header rules, allowing the website frontend to complete geolocated IP checking and analytics telemetry during startup without throwing console errors or blocking the AI chat component.
- **Unicode Markdown Rendering Fallbacks**: Patched Rich's markdown rule, table, and list item components to detect legacy Command Prompt terminals and fallback to safe ASCII representations (`*` for bullets, `-` for rules, and `+--+` for table grids) instead of throwing UnicodeEncodeErrors or printing replacement boxes.
- **Unicode Fallback Spinners**: Re-engineered all loading/thinking spinners and progress bar characters to detect legacy Windows CMD/conhost terminals and non-UTF-8 console environments, falling back to clean ASCII patterns (`['|', '/', '-', '\\']` and `[#---]`) to prevent rendering boxes/question marks.
- **Graceful Prompt-Toolkit Dialog Exits**: Introduced a safe-exit mechanism to catch and prevent unhandled `Application.exit()` loop exceptions.
- **NameError in share_tui.py**: Added typing imports to fix NameError in interactive dialogs.
- **Server upload limit**: Raised file upload threshold from 25MB to 1GB and enforced plan-specific limits.
- **Bonus quota tracking**: Fixed regular quota deduction when prioritizing bonus credit quota.
- **Bonus limit display**: Standardized bonus quota percent relative to maximum allowed plan capacity and added available vs max credits indicator.
- **Quota preference override**: Fixed schema bug to honor X-Preferred-Quota client header.

## [1.47.0] - 2026-07-17

### Added
- **Multi-Language File Outliner**: Re-engineered `view_file_outline` to support Python, JavaScript, TypeScript, HTML, CSS, JSON, and Markdown. It uses dedicated structural parsers and token matching to cleanly output class names, function definitions, HTML IDs/tags, and CSS classes without throwing SyntaxErrors. This lets non-Python web applications benefit from token-saving structural navigation.
- **Global Tools Expansion State**: Transitioned `Ctrl+O` to use a global toggled state (`STATE["tools_expanded"]`). This ensures all previous, current, and future tool call boxes respect the toggled collapse/expand mode, preventing layout fragmentation or broken boxes when navigating or printing new tool results.
- **Inline Ctrl+O Tool Expansions**: Re-engineered the `Ctrl+O` keypress handler. Instead of launching a full-screen scrollable sub-application that clears the screen, it now performs an inline, in-place toggle of the last executed tool's results directly in the terminal scrollback history. It uses cursor-up and line-erasing ANSI escape sequences to smoothly redraw the panel between collapsed and expanded states without screen pollution.
- **Persistent Session Memory Checkpointing**: Integrated structured external task memory log (`.utim/session_summary.md`) that logs completed step objectives and file change lists on every successful turn. Injects this running summary directly into system instructions to prevent context amnesia, loops, and work duplication.
- **Safety-Net Context Auto-Compression**: Demoted auto-compression to a safety net, removing the hard-coded caps (12k/32k) and message-count triggers. Auto-compression now dynamically scales to 90% of the model's actual physical context window, allowing models to fully use their capacity.
- **Markdown-Aware ANSI Token Streaming**: Engineered a hybrid chunk streaming processor. Text is received in chunks, parsed into complete logical blocks (like lines or table segments), pre-rendered using Rich's Markdown compiler to align columns and apply styles, and then streamed to the screen character-by-character while keeping ANSI escape codes atomic to ensure a smooth, beautiful, and flicker-free visual output.
- **Raised Context Compression Caps**: Raised context compression thresholds (64k for small models and 120k for large models) to utilize the model's actual context window capacity, preventing loop cycles and amnesia bugs during file editing.

### Changed
- **Flicker-Free Line-Buffered Streaming**: Restored line-buffered stdout streaming to completely eliminate terminal double-buffering flickering while keeping the prompt_toolkit event loop active for command typing and prompt queueing.
- **Auto Word Wrapping**: Integrated automatic markdown-aware word wrapping for streamed responses, keeping words whole while preserving code block layout.
- **TUI Cursor & Selection Enhancements**: Added custom keybindings for `Ctrl+A`, `Backspace`, and `Delete` to allow selecting and clearing the entire input field in one keypress.
- **Accidental History-Load Prevention**: Refined Up/Down arrow keys to only trigger history loading when the cursor is at the prompt boundary, preventing accidental clearing of typed prompts.
- **Balanced Speed & Safety**: Updated core directives to prioritize fast compiler/test checks (`run_command`) over expensive file re-reads (`read_file`).

### Fixed
- **Aborted Task Response Resurrection**: Resolved a bug where aborting a task and immediately submitting a new prompt would clear the cancellation event globally, causing the still-exiting background thread to ignore the cancel state and print its output later. Added a thread lock (`_run_queue_lock`) to serialize background task executions, forcing new tasks to wait until the aborted thread finishes winding down and exits before starting.
- **Instant Agent Halts after Tool Confirmation**: Resolved background task thread collisions during interactive Arrow-key menu confirmations. Ignored prompt_toolkit keypresses (Enter, Arrows, Esc, Ctrl+C) and temporarily marked the input field as read-only while the confirmation menu is capturing keys via `msvcrt.getwch()`. Furthermore, print tracebacks for all unhandled task execution exceptions to make background stops transparent.
- **Glitchy/Broken Live Streaming Text**: Replaced high-frequency character-by-character Rich stdout writes and console flushes with line-by-line printing. This prevents prompt_toolkit's `patch_stdout` from invoking thousands of terminal redraws per second, resolving truncation, cutoffs, and empty responses.
- **Dynamic Global Tool Expansion Toggle**: Re-engineered `Ctrl+O` to flip the global `STATE["tools_expanded"]` and trigger a clean session history redraw. This redraws all visible previous, current, and future tool call boxes in the correct toggled state without leaving fragmented or broken layout boxes.
- **Select-All Deletion**: Updated Backspace and Delete keybindings to directly clear selection ranges when selection is active, ensuring prompt-toolkit's selection state behaves naturally.
- **Rich Console Native Character Streaming**: Replaced direct raw `sys.stdout.write` with Rich Console output slices. Pre-rendered lines are converted into Rich `Text` objects via `Text.from_ansi` and printed character-by-character using `self.console.print(char_text, end="")`. This resolves character truncation, cursor jumps, and missing chunks on Windows systems by allowing Rich to handle the platform-specific terminal API translation.
- **Rich-Native Markdown Wrapping**: Removed manual textwrap.wrap preprocessing from the markdown streaming buffer. Relying on Rich's native layout rendering preserves markdown syntax characters, leading list indentation spaces, and avoids cutting off prefix letters or inserting hard line breaks inside paragraphs.

## [1.46.40] - 2026-07-14

### Changed
- **Blender Tool Maintenance**: Disabled the Blender 3D tool and added an "Under Maintenance" note in the tools dialog while the pipeline is restructured.


## [1.46.39] - 2026-07-13

### Added
- **Server Completions Search Proxy**: Implemented `/completions/search` search proxy to securely query Tavily via Railway-configured keys, enabling zero-config web search on CLI clients.
- **Config Collision Resolution**: Fixed home-directory path resolution collision that caused settings (like `/chatrestore` and subagent models) to overwrite and revert.
- **Quota Endpoint UnboundLocalError Fix**: Resolved server crash on `/quota` endpoint for non-free plan users.
- **Model Selector UI Refactor**: Removed duplicate sentinel prepending blocks in the subagent model selection dialog.


## [1.46.38] - 2026-07-12

### Added
- **True Per-User Rate Limiting**: Migrated rate limiting to API key-based validation to ensure independent 30 req/min/user buckets.
- **Decoupled Quota UI**: Separated monthly free credits from purchased bonus credits into two distinct rows in `utim quota`.
- **Resumed Tool Call History**: Fixed a critical state restoration bug that skipped rendering in-progress tool calls and generated image panels upon resuming a session.
- **Silent Image Generation**: Suppressed verbose debug logs and prompt expander outputs during image gen.
- **Fair Image Billing**: Fixed OpenRouter mock-token overcharging by setting image generations to a flat 50 credits ($0.05).


## [1.46.37] - 2026-07-12
- **Separate Bonus/Monthly Quota Checks**: Decoupled monthly free usage from purchased bonus credits on the backend so bonus usage doesn't permanently lock out standard 5-hour free refills.
- **Friendly Bonus Exhausted Tips**: Added CLI prompts instructing users to switch to available free models (or run `utim reset`) when their premium bonus credits are fully exhausted.
- **Non-Fatal Wheel Failures**: Updated installer to treat mobile/Termux precompiled wheel failures as non-fatal, allowing clean fallback to source compilation.
- **Client SSL Bypass Flags**: Added `--ssl-verify` / `--no-ssl-verify` client flags to help debug/bypass certificate issues.
## [1.46.36] - 2026-07-12

### Added
- **Reciprocal Server URL Fallbacks**: Integrated automatic fallback routing in the request session patcher to dynamically swap and retry calls between `api.utim.dev` and `utim-cli-production.up.railway.app` in case of connection timeouts or proxy blocking errors.

## [1.46.35] - 2026-07-11

### Added
- **Instant SSL Verification Toggle**: Upgraded the `/sslverify` session patcher to dynamically apply and remove the `verify=False` wrapper live on the running `requests.Session` class, eliminating the need to restart the CLI when toggling proxy security.

### Fixed
- **CLI Tips Correctness**: Refined all CLI and ReAct Agent usage tips to only feature verified, public commands and actual hotkeys, removing any references to internal or hidden commands.

## [1.46.34] - 2026-07-11

### Added
- **Expanded Rotating Tips System**: Expanded the CLI helper system with 18 pre-written tips covering shortcut keybinds, proxy configuration, model switching, and chat management. Updated rotation logic to advance the tip every 3 requests rather than on every turn to prevent rapid text cycling.
- **Strict Disabled Tools Directives**: Rewrote system prompt directives to inject a hard "zero tools available" warning when all tools are turned off, prompting the agent to correctly answer "I currently don't have any tools".

### Fixed
- **Silent Tool Call Blocking**: Fixed tool execution dispatch to silently deny disabled tools to the user (instead of displaying console warning panels) while quietly returning a reject instruction to the model.
- **Zero-Bypass MCP Execution Guard**: Extended the orchestrator's disabled tools validator to cover MCP sessions and custom tool routes before any early return execution paths can be taken.

## [1.46.33] - 2026-07-11

### Added
- **Global User-Agent Shielding**: Upgraded request session patches to inject browser-like User-Agents (`Chrome/120.0.0.0`) on all outbound HTTP calls, bypassing proxy and WAF rate-limiting.
- **Added /sslverify command**: Integrated a local slash command `/sslverify` to toggle SSL verification directly from the CLI input prompt without needing to edit config files manually.

### Fixed
- **BYOK & Custom Model Wizard Input Lag**: Fixed a bug where prompt inputs (e.g. entering provider number or API key) were buffered/hidden during the wizard flows. Decoupled input prompt streams in `_safe_prompt` by writing directly to `sys.__stdout__` and reading from `sys.__stdin__` to bypass `prompt_toolkit` interceptors.
- **Improved API Auth Error Feedback**: Added specialized HTTPError handlers in the BYOK model discovery flow to catch 401 (Unauthorized) and 403 (Forbidden) response codes and print clear, actionable explanations instead of generic request tracebacks.
- **Website GitHub Link Removal**: Removed GitHub project URLs, core repository connection cards, and community links from the landing pages and pricing documents.

## [1.46.31] - 2026-07-11

### Added
- **Dynamic Console Glyph Fallbacks**: Detected legacy Windows terminals (where `WT_SESSION` is not set) and automatically fell back to standard ASCII symbols (`>` and `->`) instead of unicode characters (`❯`, `▶`, and `➔`) to prevent `⍰` or empty box rendering issues.
- **SSL Verification Control**: Added `verify_ssl` config key and `UTIM_VERIFY_SSL` environment variable to support disabling SSL verification. This resolves "server unreachable" errors caused by corporate firewalls or proxies that intercept HTTPS traffic.

### Fixed
- **Model Selection Dialog Crash**: Fixed an `AttributeError` crash on the model list dialog screen (main agent or subagent picker) when the user's local `user_plan` config value is missing or explicitly `null`.
- **Global Config Null-Safety Improvements**: Fixed multiple potential crashes across the tools dialog, share manager, and usage dashboard when keys like `disabled_tools`, `mcpServers`, `role`, or `user_plan` are missing or set to `null` in config files.
- **Server Upload Limit & Connection Resets**: Increased the `/shares/upload` workspace file sharing size limit from 4MB to 25MB on the server. Added stream consumption middleware handlers to prevent connection termination resets and `SSLEOFError` crashes on the client during larger uploads.
- **Modern prompt_toolkit Style Crash**: Fixed a crash (`ValueError: Wrong color format 'dim'`) on lists with scrolling indicators (like the model dialog or history dialog) when run on newer versions of `prompt_toolkit` (3.0.40+) by correcting the shorthand styling `'dim fg:#f9e2af'` to `'class:dim fg:#f9e2af'`.

## [1.46.29] - 2026-07-11

### Fixed
- **Feedbacks Dialog Markup Crash**: Wrapped all dynamic user-provided strings (emails, comments, and chat history) inside `rich.markup.escape` in `feedback_dialog.py` to prevent `MarkupError` crashes when logs contain unescaped brackets or console style tags.
- **Event Loop run_in_terminal Coroutine Warnings**: Wrapped the main-thread `run_in_terminal` callback in `asyncio.ensure_future` inside `utim.py` to prevent task destruction and `never awaited` coroutine warnings.
- **Free Node Pricing Description**: Updated the Free tier pricing widget and documentation pages to reflect the correct 5-hour refill limit (100 credits/$0.10 value) and 3,000 monthly credits limit (with no stacking).

## [1.46.28] - 2026-07-11

### Added
- **Intelligent Experience Compression**: Replaced simple per-experience truncation/token-cutoff logic with advanced LLM-based context compression (utilizing `poolside/laguna-xs-2.1:free`, `cohere/north-mini-code:free`, and `openrouter/free`). When relevant lessons exceed 5,000 tokens, the LLM dynamically compresses them into a concise bullet-point summary, which is cached to prevent per-iteration latency.
- **Aborted Turn Progress & Reflection**: Ensured aborted responses preserve partial progress and trigger a background reflection phase to extract lessons from failed/interrupted runs.

### Fixed
- **Redundancy Filter Correction**: Fixed the experience retrieval redundancy filter to only deduplicate exact matches rather than checking substrings, preventing the silent dropping of detailed shell/PowerShell lessons.
- **Filtered MCP Notification Context**: Updated MCP notifications to filter out disabled tools, preventing the agent from trying to call disabled MCP tools.
- **Research File XML Cleanup**: Fixed the codebase research subagent to forbid and automatically strip hallucinated XML tool-calling syntax in its markdown reports.

## [1.46.27] - 2026-07-10

### Fixed
- **Image Generation Quota Bypass**: Fixed the image generation tool to bypass the monthly base credit check when the user has a positive bonus credit balance.
- **Piped Output Formatting**: Corrected command output formatting and token usage tracking when the CLI is run in a piped or non-TTY environment.

### Changed
- **Model Pricing Docs**: Replaced static tables on the documentation page with an interactive component providing category filter chips and capabilities search for all UTIM models.

## [1.46.26] - 2026-07-09

### Added
- **OpenRouter Models Addition**: Added `aion-labs/aion-3.0`, `aion-labs/aion-3.0-mini`, `x-ai/grok-4.5`, `openai/gpt-5.6-luna-pro`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-terra-pro`, `openai/gpt-5.6-terra`, `openai/gpt-5.6-sol-pro`, and `openai/gpt-5.6-sol` to the CLI's `/model` selector list.

## [1.46.24] - 2026-07-09

### Added
- **Interactive Learnt Verification Questions**: Integrated a feedback reflection loop that analyzes low-rated chats (under 4 stars) to extract candidate lessons and draft clarifying questions. The CLI will dynamically ask the user confirmation questions in future runs when matching contexts are detected to verify or reject the learned patterns.

## [1.46.23] - 2026-07-09

### Fixed
- **Feedback Details Crash**: Resolved a critical AttributeError crash when selecting a feedback entry in the `/feedbacks` dashboard. The UI now gracefully handles and parses `chat_history` payload data under all serialization conditions.

## [1.46.22] - 2026-07-09

### Fixed
- **Instant Ctrl+C Interruption**: Halts execution instantly (within 100ms) on Ctrl+C or Escape, outputting `⊘  Aborted.` directly and avoiding delay/retry loops.
- **Event Loop TUI Crashes**: Fixed `RuntimeWarning: coroutine was never awaited` warnings and thread-safety crashes in `run_in_terminal` when running async dialogs from background tasks.
- **Tools Dialog Text Overflow**: Added dynamic word wrapping in the tools configuration dialog to prevent long descriptions from spilling off-screen.
- **Corrected Tool Name in Injected Prompt**: Fixed the active workspace skills recommendation message injected into the system prompt to correctly refer to the `read_file` tool.
- **Decoupled Tool Gating**: Restructured disabled tools filtering to only apply to the main user agent, preserving normal tool capabilities for background subagents.

## [1.46.21] - 2026-07-07

### Added
- **Relationship-based Experience Memory**: Integrated advanced pattern learning (`ExperienceManager` and `ExperienceNode`) with the LLM reflection phase. Learns object/relationship patterns (like the chair/stool/wall analogy) and automatically injects structured `[RELATIONSHIP EXPERIENCE INSIGHTS]` into the system prompt for matching tasks.

### Fixed
- **Agent XML Tool-Calling**: Integrated a robust XML tool-call parser to intercept streaming custom-tool commands, cleaning XML tags from output text and translating tool names/parameters (e.g., mapping `shell`/`bash`/`cmd` to `run_command` and `view_file` to `read_file`).
- **Windows Subprocess Unicode Crashes**: Specified `encoding="utf-8"` and `errors="replace"` across all `subprocess.run` calls (test runner, compiler syntax checks, and Blender execution) to prevent `UnicodeDecodeError` ANSI/`cp1252` crashes on Windows.
- **Opt-in Regression Tests**: Made the automated regression test runner opt-in (disabled by default) via `"enable_regression_tests": true` or `UTIM_ENABLE_REGRESSION_TESTS=1`.
- **Directory Read Failures**: Upgraded `read_file` to gracefully return a directory suggestion instead of throwing a `PermissionError` when given a directory path.
- **Repetitive Greeting Responses**: Shortened system prompt responses for casual greetings/inputs to prevent the agent from repeating its long introduction intro.

## [1.46.20] - 2026-07-07

### Fixed
- **TUI focus checks and dialog crashes:** Changed layout focus checks from manual lambda wrappers to prompt-toolkit's native `has_focus` filter across `/mcp` and `/share` menus to fix keyboard dropouts and Down arrow navigation issues.
- **TUI helper NameError and Silent Failures:** Resolved a `NameError` crash in `/mcp` due to missing `_prompt_input` imports, added missing imports in `/autoupdate`, and imported `datetime` to fix the silent date-parsing age bugs in `/resume`.

## [1.46.19] - 2026-07-07

### Fixed
- **TUI Dialog exit/scroll crashes on Python 3.13:** Fixed remaining `dim yellow` and `dim #585b70` style string parsing exceptions that crashed prompt-toolkit when scrolling list viewports or returning from the `/share` and `/resume` dashboards under Python 3.13+.

## [1.46.18] - 2026-07-07

### Fixed
- **TUI Rendering Crash on Python 3.13:** Fixed a critical `ValueError: Wrong color format 'dim'` exception that crashed prompt-toolkit during rendering of `/mcp`, `/share`, `/model`, `/history`, and `/tools` dialogs under Python 3.13+.
- **Import/Cache and Mock Test Failures:** Fixed pytest suite errors including non-existent `TOOL_FUNCTIONS` imports in the fallback parser, incorrect mock parameters, and `get_admin_user` environment variable caching failures.

### Added
- **Pay As You Go on Pricing Page:** Added a fully interactive checkout Top-Up component card directly on the main Pricing Page under the new "Pay As You Go" tier selector.

## [1.46.17] - 2026-07-06

### Fixed
- **Bugs fixed:** Fixed a critical Windows auto-restart bug where directory paths containing spaces (e.g., 'New folder') would cause command line arguments to split and crash with a file-not-found error on startup.

### Added
- **Multi-Platform Shell Detection & Terminal Closures:** Spawns UTIM in a clean, fresh, normal terminal window/tab (persisting open shell via `/k` command) instead of double-printing startup sequences in the same terminal. Traversing the parent process tree identifies and terminates the parent shell (PowerShell/CMD on Windows, Terminal on macOS, SIGHUP on Linux) to cleanly close the old tab.
- **Isolated Testing Configuration:** Prevented test runs (`pytest`) from mutating the developer's global `~/.utim/config.json` configuration file by automatically isolating test session files inside a temporary directory.
- **Immediate Process Exit on Login**: Prevented old parent processes from continuing execution or printing GUEST state warning lines by calling immediate process termination (`os._exit(0)`) once the new UTIM console window is successfully launched.

## [1.44.2] - 2026-07-02

### Fixed
- **MCP Server Hang:** Fixed an issue where installing MCP servers (like Figma) without the `--stdio` flag would hang the CLI indefinitely. Added a 60-second initialization timeout and updated the preset registry to include required flags automatically.
- **Model Selection Crash:** Fixed an issue where the CLI would crash instantly when trying to open the `/model` selector on a production npm install due to an excluded server module.
- **Image Subagent Config:** Separated the Image Generation model and the Prompt Expander LLM in the subagent configuration UI, allowing users to configure both independently.
- **Minor:** Minor Bug Fixes

## [1.43.20] - 2026-07-01

### Added
- **Local-Global Experience Vector DB Sync**: UTIM now carries the ChromaDB experience database across project folders automatically. On startup, the previous project's `experiences.json`, `vector_db`, and vector metadata files are copied to the current folder — deleted from the old folder only after a successful paste. Last active folder is persisted server-side so the sync survives PC restarts.
- **BYOK Provider Disconnection (key `x`)**: Press `x` in the model selector to view a list of connected custom providers and disconnect them. All associated models are removed from the model list instantly.
- **Bring Your Own Key (BYOK) for Free Users**: Free-tier users can now connect any OpenAI-compatible provider using their own API key. BYOK models bypass UTIM quota limits and plan gating entirely.
- **Dynamic Changelog & Version API**: `/api/changelog` parses `CHANGELOG.md` at request time and returns structured JSON. `/health` version field is also derived from `CHANGELOG.md` dynamically — deploying a new changelog auto-updates both the website changelog page and version badge.
- **Changelog Tab on Website**: The terminal website now includes a `↻ Changelog` tab that fetches live release notes from the Railway server on load.
- **Features Page Redesign**: The Features tab now displays a 9-card animated grid with per-feature glow icons, numbered labels, colored tags, and spring entrance animations — matching the full terminal aesthetic of the site.
- **Last Project Folder Persistence**: Server stores each user's last active project directory in the database. Survives PC restarts and is used to drive the cross-folder experience DB sync.
- **`GET /api/auth/last-folder` and `POST /api/auth/last-folder` Endpoints**: New authenticated REST endpoints to read/write a user's last active project folder path.

### Changed
- **Plan Upgrade Credit Transition**: Free plan credit allowance ($1.00) is zeroed out instead of rolling over to the new paid plan's quota bank on upgrade.
- **Hobby Plan Model Access**: Hobby plan `allowed_models` corrected to `"all"` so users can access the full model registry (not just free-tier models).
- **BYOK Model Gating Bypass**: Orchestrator pre-flight checks now skip plan gating and UTIM credit checks for custom BYOK models since they use user-owned keys.
- **Pricing Page Claims Cleaned**: Removed unsubstantiated marketing claims (`Dedicated elite endpoints`, `Autonomous team agents access`, `High-speed dedicated endpoints`, `All premium models (GPT-4o, Claude)`, `Synthetic Eye & VSIX tools`, `Claude Sonnet 4.6 (1 RPM)`, `10-session history storage`) from all pricing tier feature lists.

### Fixed
- **BYOK Flow Display Bug**: Rewrote Add/Delete/BYOK-import dialogs to run on `sys.__stdout__` with `prompt_toolkit.prompt()` so they are never swallowed by the alt-screen buffer.
- **Double-Exit Crash (TUI)**: Wrapped all keyboard exit callbacks (`ENTER`/`ESC`/`q`/`CTRL+C`) in `try...except` blocks to prevent double-fire tracebacks.
- **`/changelog` Route No Longer Shows Legacy Page**: All website routes (including `/changelog`) now correctly map to the `<PowershellUI />` terminal component. Legacy standalone page removed.

---

