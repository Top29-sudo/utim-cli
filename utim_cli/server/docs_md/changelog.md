# Changelog

## [1.47.16] - 2026-07-21

### Added
- **New General Models (`google/gemini-3.6-flash` & `poolside/laguna-s-2.1:free`)**: Registered Google's next-gen `google/gemini-3.6-flash` and Poolside's free `poolside/laguna-s-2.1:free` model into the UTIM model registry with OpenRouter pricing and 5% platform markup.
- **Krea 2 Image Subagent & Reasoning Modes**: Added `krea/krea-2-medium-turbo`, `krea/krea-2-medium`, and `krea/krea-2-large` image generation models with 5% OpenRouter pricing markup. Consolidated image subagent selection into a single `"Krea 2 image"` model entry that dynamically maps reasoning modes:
  - **Low Reasoning**: uses `krea/krea-2-medium-turbo` in background.
  - **Medium Reasoning**: uses `krea/krea-2-medium` in background.
  - **High Reasoning**: uses `krea/krea-2-large` in background.

## [1.47.2] - 2026-07-18

### Fixed
- **UnboundLocalError in Command Output Renderer**: Pre-initialized stdout and stderr lines lists in `_render_result` to prevent runtime exception on commands yielding empty output.
- **Chunk-Boundary Unicode Decode Errors**: Upgraded `read_file` tool to slice trailing incomplete bytes during UTF-8 checks, preventing decoding failures on split multi-byte character boundaries.
- **Reflection Engine Skill Creation Guardrail**: Restructured reflection engine to only create new skill files when at least 3 substantial guidelines (each >= 40 characters) are suggested, preventing clutter from useless "one-liner" skills.
- **Console Status Spinner Fallback**: Patched the `console.status` spinner in `utim.py` to check for legacy Windows CMD/conhost and non-UTF-8 environments, dynamically falling back to ASCII `line` spinners instead of unicode dots.
- **Support Chat Model Casing**: Updated frontend support assistant to target `openrouter/free` exclusively to maintain service reliability.

## [1.47.1] - 2026-07-18

### Added
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

