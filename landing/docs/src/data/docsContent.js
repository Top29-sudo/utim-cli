// Exhaustive End-to-End Operational Process Documentation Dataset for UTIM CLI (docs.utim.dev)

export const docsCategories = [
  {
    title: "🚀 GETTING STARTED",
    items: [
      { id: "overview", name: "1. What UTIM CLI Is", badge: "Core" },
      { id: "installation", name: "2. Platform Setup & Installation", badge: "Setup" },
      { id: "first-run", name: "3. First Run & Account Auth", badge: "Auth" },
    ]
  },
  {
    title: "⚡ CLI & EXECUTION ENGINE",
    items: [
      { id: "entrypoints", name: "4. CLI Entrypoints & Flags", badge: "Commands" },
      { id: "slash-commands", name: "5. Slash Commands Matrix (25+)", badge: "Interactive" },
    ]
  },
  {
    title: "🤖 SUBAGENTS & SWARMS",
    items: [
      { id: "subagents", name: "6. Subagent Architecture & IPC", badge: "Multi-Agent" },
    ]
  },
  {
    title: "🔌 MCP INTEGRATION",
    items: [
      { id: "mcp", name: "7. Model Context Protocol (MCP)", badge: "Tools" },
    ]
  },
  {
    title: "🧠 INTELLIGENCE & MEMORY",
    items: [
      { id: "rag-memory", name: "8. Local Vector Memory & RAG", badge: "ChromaDB" },
      { id: "time-travel", name: "9. Reversible History & Rewind", badge: "Reversible" },
      { id: "workspace", name: "10. Local Workspace State (.utim/)", badge: "State" },
    ]
  },
  {
    title: "💰 COMPUTE QUOTA & BYOK",
    items: [
      { id: "models-catalog", name: "11. Models & Provider Catalog", badge: "Registry" },
      { id: "quota-pricing", name: "12. Compute Quota & BYOK Setup", badge: "Quota" },
      { id: "referral-program", name: "13. Referral Discount Stacking (+2%)", badge: "Earn" },
    ]
  },
  {
    title: "🛡️ DATA PRIVACY & SAFETY",
    items: [
      { id: "data-privacy", name: "14. Data Privacy & Local Boundaries", badge: "Privacy" },
      { id: "safety-model", name: "15. Safety Model & Sandboxing", badge: "Sandbox" },
    ]
  },
  {
    title: "🛠️ WORKFLOWS & DIAGNOSTICS",
    items: [
      { id: "customizations", name: "16. Customizations, Skills & Rules", badge: "Skills" },
      { id: "web-search", name: "17. Web Search Automation", badge: "Search" },
      { id: "visual-vision", name: "18. Vision & Image Generation", badge: "Multimodal" },
      { id: "ast-graph", name: "19. Tree-Sitter AST & Knowledge Graph", badge: "AST" },
      { id: "sharing-redeem", name: "20. Sharing & Support Bundles", badge: "Share" },
      { id: "workflows", name: "21. Common Developer Workflows", badge: "Workflows" },
      { id: "troubleshooting", name: "22. Troubleshooting & Diagnostics", badge: "Fixes" },
    ]
  },
  {
    title: "⚖️ LEGAL & EULA",
    items: [
      { id: "eula-license", name: "23. Emend AI Proprietary EULA (Non-MIT)", badge: "Legal" },
      { id: "sla-compliance", name: "24. SLA & Business Readiness", badge: "Compliance" },
      { id: "changelog", name: "25. Full Version Release Notes", badge: "Changelog" },
    ]
  }
];

export const platformInstallCommands = {
  windows: [
    { title: "NPM Global Package Installer (Recommended)", cmd: "npm install -g @emend-ai/utim", shell: "powershell" },
    { title: "Direct PowerShell One-Liner Execution Script", cmd: "Set-ExecutionPolicy Bypass -Scope Process -Force; iwr https://utim.dev/install.ps1 | iex", shell: "powershell" },
    { title: "Python Pip Installer (Python >= 3.9)", cmd: 'pip install "utim[full]"', shell: "cmd" }
  ],
  mac: [
    { title: "NPM Global Package Installer", cmd: "npm install -g @emend-ai/utim", shell: "bash" },
    { title: "cURL Terminal Direct One-Liner Script", cmd: "curl -fsSL https://utim.dev/install.sh | bash", shell: "zsh" },
    { title: "Python Pip Installer (Python >= 3.9)", cmd: 'pip install "utim[full]"', shell: "zsh" }
  ],
  termux: [
    { title: "Step 1: Update Environment & Install Node.js + Python", cmd: "pkg update -y && pkg install nodejs python -y", shell: "bash" },
    { title: "Step 2: Install Global UTIM CLI Binary", cmd: "npm install -g @emend-ai/utim", shell: "bash" },
    { title: "Step 3: Grant Termux Storage Permission & Launch", cmd: "termux-setup-storage && utim", shell: "bash" }
  ],
  source: [
    { title: "Standard CLI Installation from Source Checkout", cmd: "git clone https://github.com/Top29-sudo/utim-cli.git && cd utim-cli && pip install .", shell: "bash" },
    { title: "Full Extra Package Suite (Search, Vision, Tree-Sitter Parsers)", cmd: 'pip install ".[full]"', shell: "bash" }
  ]
};

export const slashCommandsList = [
  { cmd: "/login", desc: "Authenticates terminal with UTIM account credentials & syncs 5-hour quota refills.", category: "Auth" },
  { cmd: "/logout", desc: "Signs out and clears local account token cache while preserving workspace settings.", category: "Auth" },
  { cmd: "/undo", desc: "Reverts the most recent file mutation snapshotted by the agent turn.", category: "Reversible" },
  { cmd: "/redo", desc: "Re-applies the last undone turn file modification.", category: "Reversible" },
  { cmd: "/rewind", desc: "Restores conversation turns, context memory, and workspace diffs to an earlier checkpoint.", category: "Reversible" },
  { cmd: "/share", desc: "Zips session history and generates an encrypted collaboration web URL.", category: "Share" },
  { cmd: "/quotashare", desc: "Transfers subscription credits or Quota Bank balance to another user directly from CLI.", category: "Billing" },
  { cmd: "/redeem", desc: "Claims bonus credits using a promotional or referral redemption code.", category: "Billing" },
  { cmd: "/mcp", desc: "Opens the interactive Model Context Protocol (MCP) server manager dialog.", category: "Tools" },
  { cmd: "/model", desc: "Opens the model selector dialog to choose main agent and subagent LLM models.", category: "Models" },
  { cmd: "/byok", desc: "Configures Bring Your Own Key custom provider API keys (OpenAI, Anthropic, Gemini, Ollama).", category: "BYOK" },
  { cmd: "/goal", desc: "Enables extra-thorough goal mode for long-running autonomous task execution.", category: "Modes" },
  { cmd: "/schedule", desc: "Schedules background timer notifications or recurring cron jobs.", category: "Modes" },
  { cmd: "/plan", desc: "Generates step-by-step execution blueprint before applying code mutations.", category: "Planning" },
  { cmd: "/grill-me", desc: "Starts interactive design interview to resolve ambiguous user specifications.", category: "Planning" },
  { cmd: "/teamwork-preview", desc: "Launches multi-agent swarm visualizer preview for large projects.", category: "Swarm" },
  { cmd: "/learn", desc: "Persists user corrections or project conventions into AGENTS.md.", category: "Memory" },
  { cmd: "/status", desc: "Displays live compute node status, quota bank, and 5-hour slot fill percentage.", category: "Status" },
  { cmd: "/compact", desc: "Prunes older chat history to save context tokens while keeping core technical context.", category: "Context" },
  { cmd: "/history", desc: "Inspects transcript turn history and tool execution log timestamps.", category: "History" },
  { cmd: "/doctor", desc: "Runs diagnostic checks inside a scrollable terminal dialog.", category: "Diagnostics" },
  { cmd: "/tools", desc: "Enables or disables built-in local tools and MCP tool handlers.", category: "Tools" },
  { cmd: "/clear", desc: "Clears active terminal viewport screen while keeping conversation state.", category: "Session" },
  { cmd: "/new", desc: "Starts a fresh chat session and clears active turn history.", category: "Session" },
  { cmd: "/exit", desc: "Safely terminates CLI session and releases subagent thread locks.", category: "System" }
];

export const cliFlagsList = [
  { flag: "--dry-run", desc: "Simulates file edits and command execution without mutating the workspace disk files." },
  { flag: "--sandbox", desc: "Enables intelligent local sandboxing for risky terminal command proposals." },
  { flag: "--sandbox-image <image>", desc: "Specifies container image for sandbox execution (default: ubuntu:22.04)." },
  { flag: "--version", desc: "Prints the installed UTIM CLI version binary metadata." },
  { flag: "--debug", desc: "Enables verbose debug log outputs and API request tracebacks." }
];

export const detailedArticles = {
  overview: {
    title: "1. What UTIM CLI Is — Technical Architecture Overview",
    lead: "UTIM CLI is a local-first autonomous software engineering agent built for modern terminal environments. Engineered as a state-machine orchestrator, UTIM operates directly inside your local repository directories without requiring cloud IDE lock-in or remote code uploads.",
    sections: [
      {
        heading: "Full End-to-End State Machine Execution Process",
        text: "Stage 1: Workspace Scanning & AST Parsing\nUpon receiving a prompt, UTIM scans local files, parses Abstract Syntax Trees via Tree-Sitter, and extracts symbol definitions.\n\nStage 2: Vector RAG Memory Search\nQueries local ChromaDB vector database (.utim/chroma/) to pull semantically relevant code context.\n\nStage 3: Multi-Step Plan Blueprinting\nGenerates an explicit task implementation checklist prior to file editing.\n\nStage 4: Pre-Write Syntax Validation\nVerifies code patches against Python AST, JSON schemas, or TS compiler before touching disk.\n\nStage 5: Differential Snapshot Commit\nCaptures a differential file diff in .utim/intelligence.db to enable instant /undo, /redo, and /rewind.\n\nStage 6: User Confirmation & Shell Execution\nProposes shell commands with interactive user dialogs and optional Docker sandboxing.",
        code: { lang: "bash", cmd: "cd /path/to/my-project && utim" }
      },
      {
        heading: "Emend AI Proprietary EULA & Commercial Licensing",
        text: "UTIM CLI is proprietary software owned exclusively by Emend AI. It is NOT open-source software under the MIT License. Commercial use (in corporate repositories, paid freelance projects, or proprietary client codebases) requires an active Paid Subscription (Hobby $7/mo, Pro $25/mo, Max $55/mo, Ultimate $110/mo) or an active Bring Your Own Key (BYOK) provider configuration. The Free Tier is strictly intended for personal learning, non-commercial evaluation, and open-source contributions.",
        callout: { type: "important", title: "Non-MIT Proprietary License Notice", text: "UTIM CLI is proprietary software owned by Emend AI. Commercial deployment requires a paid plan or active BYOK key configuration." }
      }
    ]
  },
  installation: {
    title: "2. Platform Setup & Installation Guide",
    lead: "Complete cross-platform installation manual for Windows, macOS, Linux, and Android Termux environments.",
    sections: [
      {
        heading: "Full End-to-End Installation & Linking Process",
        text: "Stage 1: Prerequisites Check\nVerify Node.js 18+ or Python 3.9+ is installed in environment.\n\nStage 2: Global Package Download & Extraction\nNPM or Pip downloads global binary package @emend-ai/utim from registry.\n\nStage 3: Binary Linking & PATH Registration\nLinks utim CLI executable to global system PATH (e.g. C:\\Program Files\\nodejs\\utim or /usr/local/bin/utim).\n\nStage 4: Initial Environment Verification\nRun utim --version to confirm binary linkage and version metadata.",
        code: { lang: "powershell", cmd: "npm install -g @emend-ai/utim\nutim --version" }
      }
    ]
  },
  "first-run": {
    title: "3. First Run & Account Authentication",
    lead: "Initializing local workspace directories and authenticating terminal sessions with UTIM account keys.",
    sections: [
      {
        heading: "Full End-to-End Authentication & Keyring Process",
        text: "Stage 1: Launch Authentication Command\nRun utim login or type /login in the interactive prompt.\n\nStage 2: Device Code Handshake\nCLI generates a unique 8-character device verification code and opens your browser to https://utim.dev/auth/device.\n\nStage 3: Server Identity Verification\nUser approves terminal session in web browser console.\n\nStage 4: Keyring Deposit (AES-256)\nAuth server returns an encrypted JWT ID Token. The CLI stores the token inside your OS secure keyring (Windows Credential Manager / macOS Keychain / SecretService).\n\nStage 5: Live Quota Sync\nCLI fetches live active quota allocations (100 credits/5 hrs) and displays session initialization summary.",
        code: { lang: "bash", cmd: "utim login" }
      }
    ]
  },
  entrypoints: {
    title: "4. CLI Entrypoints & Command Line Flags",
    lead: "Detailed reference for interactive TUI mode, headless autonomous execution, and command line arguments.",
    sections: [
      {
        heading: "Full End-to-End Headless Task Process (utim task)",
        text: "Stage 1: CLI Invocation\nDeveloper triggers: utim task '<prompt>'\n\nStage 2: Context Extraction & Plan Generation\nUTIM loads local project rules (AGENTS.md), indexes relevant source files, and constructs execution steps without rendering interactive TUI windows.\n\nStage 3: Execution & Validation Loop\nMutates targeted files, validates syntax compilation, runs configured test suites, and exits cleanly with return code 0 on success (or code 1 on failure).",
        code: { lang: "bash", cmd: 'utim task "Fix failing unit tests in tests/auth.test.py"' }
      }
    ]
  },
  "slash-commands": {
    title: "5. Slash Commands Reference Matrix (25+ Commands)",
    lead: "Complete operational manual for all 25+ interactive slash commands in the UTIM TUI prompt.",
    sections: [
      {
        heading: "Full Operational Process for Interactive Slash Commands",
        text: "Stage 1: Command Prefix Detection\nTyping / in prompt activates autocompletion matrix for 25+ built-in slash commands.\n\nStage 2: Argument Parsing & Validation\nCLI parses command name and parameters (e.g. /quotashare 50 user@example.com).\n\nStage 3: Handler Dispatch & Execution\nOrchestrator routes command to appropriate module (auth, reversible history, billing gateway, model selector).\n\nStage 4: State Synchronization & Viewport Refresh\nUpdates CLI state cache and renders feedback banner in viewport."
      }
    ]
  },
  subagents: {
    title: "6. Subagent Swarm Architecture & IPC Protocol",
    lead: "Multi-agent swarm orchestration for parallel codebase research, planning, and task execution.",
    sections: [
      {
        heading: "Full End-to-End Subagent Invocation Process",
        text: "Stage 1: Subagent Task Dispatch\nParent orchestrator emits invoke_subagent tool call with subagent specs (TypeName, Role, Prompt).\n\nStage 2: Background Thread Spawning\nA dedicated execution thread is allocated with isolated memory state and restricted tool permissions.\n\nStage 3: Async IPC Progress Streaming\nSubagent streams status messages to parent context via JSON-Line messaging queues without blocking parent execution.\n\nStage 4: Subagent Join & Context Synthesis\nUpon completion, subagent delivers structured synthesis result back to parent agent context window.",
        code: { lang: "json", cmd: '{\n  "action": "invoke_subagent",\n  "Subagents": [\n    {\n      "TypeName": "research",\n      "Role": "API Inspector",\n      "Prompt": "Survey all route handlers in src/routes/"\n    }\n  ]\n}' }
      }
    ]
  },
  mcp: {
    title: "7. Model Context Protocol (MCP) Integration",
    lead: "Connecting external databases, desktop tools, and browser automation drivers via Model Context Protocol (MCP).",
    sections: [
      {
        heading: "Full End-to-End MCP Handshake Process",
        text: "Stage 1: Configuration Discovery\nOn startup, UTIM reads .agents/mcp_config.json from workspace root.\n\nStage 2: Subprocess Transport Handshake\nCLI launches configured server binary (e.g. npx @modelcontextprotocol/server-sqlite) in an isolated subprocess with redirected stdio pipes.\n\nStage 3: JSON-RPC Initialization Handshake\nUTIM sends initialize request exchanging protocol versions and capability declarations.\n\nStage 4: Dynamic Tool Registration & Execution\nServer registers available tool functions directly into UTIM's active tool schema.",
        code: { lang: "json", cmd: '{\n  "mcpServers": {\n    "sqlite": {\n      "command": "npx",\n      "args": ["-y", "@modelcontextprotocol/server-sqlite", "--db-path", "./data.db"]\n    }\n  }\n}' }
      }
    ]
  },
  "rag-memory": {
    title: "8. Local Vector Memory & ChromaDB RAG Engine",
    lead: "Local-first semantic code indexing, vector embedding, and context retrieval system.",
    sections: [
      {
        heading: "Full End-to-End Vector Indexing Process",
        text: "Stage 1: AST Chunking\nSource files are parsed into semantic symbol blocks (functions, classes, modules).\n\nStage 2: Local Embedding Generation\nComputes 384-dimensional vector embeddings locally using all-MiniLM-L6-v2.\n\nStage 3: ChromaDB Storage\nPersists embeddings to .utim/chroma/ with HNSW graph indexing.\n\nStage 4: Cosine Similarity Context Retrieval\nPerforms sub-10ms similarity queries to inject relevant code definitions into prompt context windows.",
        code: { lang: "bash", cmd: "ls -la .utim/chroma/" }
      }
    ]
  },
  "time-travel": {
    title: "9. Reversible History & Time Travel (/undo, /redo, /rewind)",
    lead: "Differential git-tree snapshot backup engine for instant rollback and time travel state recovery.",
    sections: [
      {
        heading: "Full End-to-End Snapshot Creation & Reversion Process",
        text: "Stage 1: Pre-Mutation Differential Capture\nBefore editing any file, UTIM captures raw file bytes and computes unified diff against git HEAD, writing snapshot row into .utim/intelligence.db.\n\nStage 2: Reversion Invocation (/undo or /rewind)\nDeveloper types /undo or /rewind <turn_id>.\n\nStage 3: Disk Restoration & Cache Eviction\nCLI restores target file bytes from snapshot storage, invalidates cached vector embeddings for modified files, and resets chat turn index.",
        code: { lang: "bash", cmd: "/undo\n/rewind 4" }
      }
    ]
  },
  workspace: {
    title: "10. Local Workspace State Directory (.utim/)",
    lead: "Anatomy of the local .utim/ intelligence directory and persistent data stores.",
    sections: [
      {
        heading: "Full Workspace File Structure & Schema Process",
        text: "Stage 1: Directory Setup\nCreates .utim/ folder layout on first execution.\n\nStage 2: SQLite Database Initialization\nCreates tables in .utim/intelligence.db (sessions, turns, tool_calls, ast_symbols).\n\nStage 3: AGENTS.md Rule Evaluation\nParses AGENTS.md rules file and prepends project guidelines to system prompt context.",
        code: { lang: "text", cmd: ".utim/\n├── intelligence.db    # SQLite database storing session history, AST graphs, and tool logs\n├── chroma/            # Local ChromaDB vector database directory containing embeddings\n├── sessions/          # JSON Lines chat transcripts for audit and /share exports\n└── AGENTS.md          # Persistent workspace rules and project conventions" }
      }
    ]
  },
  "models-catalog": {
    title: "11. Models & Provider Catalog",
    lead: "Comprehensive catalog of supported main agent and subagent models across Free, Paid, and BYOK providers.",
    sections: [
      {
        heading: "Full End-to-End Model Routing Process",
        text: "Stage 1: Model Selection Invocation (/model)\nUser opens model picker dialog or configures subagent model.\n\nStage 2: Credit Accounting Multiplier Check\nServer calculates token credit costs based on model multiplier (10x discount for Free models vs 1x for paid models).\n\nStage 3: Request Proxy Routing\nRoutes completion payload via UTIM server proxy or BYOK provider endpoint.",
        table: [
          { key: "Cohere North Mini", val: "cohere/north-mini-code:free (128k context window, specialized code generation)" },
          { key: "Claude 3.5 Sonnet", val: "anthropic/claude-3.5-sonnet (200k context window, premier coding benchmark leader)" }
        ]
      }
    ]
  },
  "quota-pricing": {
    title: "12. Compute Quotas, 5-Hour Refills & Credit Recalculation Engine",
    lead: "Complete guide to credit accounting, 5-hour refill slots, Rollover Quota Bank, dynamic token recalculation, plan downgrade settlement, and Bring Your Own Key setup.",
    sections: [
      {
        heading: "Full End-to-End Quota & Credit Recalculation Process",
        text: "Stage 1: 5-Hour Slot Recalculation\nEvery 5 hours, the server recalculates the active slot capacity (100 credits for Free tier, or fractional plan quota). Unused slot credits from the preceding cycle automatically roll over into the Rollover Quota Bank (storing up to 2 months' capacity).\n\nStage 2: Strict Deduction Priority Cascade\nCredit deductions per turn execute in strict priority sequence:\n  1. Bonus Quota (top-ups / downgrade conversions - consumed first)\n  2. Five-Hour Slot Quota (active cycle allocation)\n  3. Quota Bank (rollover reserves - consumed when active 5h slot is depleted)\n\nStage 3: Dynamic Token Pricing & Priority Discount Recalculation\n- Free Models (:free): Billed at $0.02 / 1M in & $0.03 / 1M out for Free tier accounts. Billed at $0.002 / 1M in & $0.003 / 1M out (10x priority discount) for all Paid subscribers.\n- Premium Models: Billed at $1.00 USD = 1,000 credits. Exact token counts (prompt + completion) are recalculated per turn plus a flat 5% platform markup.\n\nStage 4: Plan Downgrade & Tier Change Balance Recalculation\nWhen downgrading or switching plans mid-cycle, remaining credits are recalculated: 50% of the remaining balance is converted into non-expiring Bonus Quota so credits are never lost.\n\nStage 5: BYOK Zero-Deduction Override (/byok)\nConfiguring custom provider keys routes completion requests directly to your provider, bypassing UTIM credit recalculation entirely.",
        code: { lang: "bash", cmd: "utim usage\nutim /byok\nutim /quotashare" }
      }
    ]
  },
  "referral-program": {
    title: "13. Stackable Referral Discount Program (+2% per Referee)",
    lead: "Earn permanent stacked subscription discounts up to 100% free by referring developers.",
    sections: [
      {
        heading: "Full End-to-End Referral Tracking Process",
        text: "Stage 1: Referral Link Generation\nUser generates unique code/link in profile page.\n\nStage 2: Referee Sign-up & Conversion\nReferee enters referral code during registration or subscription checkout.\n\nStage 3: Stacked Discount Calculation\nServer adds +2% permanent recurring discount to referrer's subscription profile.\n\nStage 4: Lifetime Free Unlocking\nReaching 50 active referees grants 100% free lifetime access.",
        code: { lang: "bash", cmd: "utim /redeem" }
      }
    ]
  },
  "data-privacy": {
    title: "14. Data Privacy & Local Boundaries",
    lead: "Local-first data governance: your source code never leaves your local workstation.",
    sections: [
      {
        heading: "Full End-to-End Privacy Protection Process",
        text: "Stage 1: File Isolation\nCode parsing, vector embeddings, and file mutations execute 100% on local disk.\n\nStage 2: Zero Remote Storage\nNo prompt text or source code files are saved on UTIM cloud servers.\n\nStage 3: Telemetry Anonymization\nOnly anonymous token count tallies are transmitted for credit billing verification.",
        callout: { type: "info", title: "Local-First Guarantee", text: "Code indexing, vector generation, and AST parsing are executed locally on your device." }
      }
    ]
  },
  "safety-model": {
    title: "15. Safety Model & Sandboxing Architecture",
    lead: "Interactive confirmation dialogs, command blacklisting, and Docker container sandboxing.",
    sections: [
      {
        heading: "Full End-to-End Command Sandboxing Process",
        text: "Stage 1: Command Interception\nAgent proposes shell command execution (e.g. npm test, rm -rf).\n\nStage 2: Safety Boundary Analysis\nCLI checks command string against system blacklist and risk categories.\n\nStage 3: Interactive User Dialog\nDisplays command string in terminal prompt requesting Y/N confirmation.\n\nStage 4: Sandbox Container Execution (--sandbox)\nIf --sandbox flag is enabled, executes command inside isolated Docker container.",
        code: { lang: "bash", cmd: "utim --sandbox --sandbox-image ubuntu:22.04" }
      }
    ]
  },
  customizations: {
    title: "16. Customizations, Skills & Rules Engine",
    lead: "Tailor agent behavior with project rules (AGENTS.md) and custom workflow skills (SKILL.md).",
    sections: [
      {
        heading: "Full End-to-End Skill Discovery & Rule Injection Process",
        text: "Stage 1: AGENTS.md Rule Extraction\nReads AGENTS.md from project root and prepends rules to system prompt.\n\nStage 2: SKILL.md Discovery\nScans .agents/skills/ for skill directories and parses YAML frontmatter.\n\nStage 3: Dynamic Skill Tool Injection\nLoads helper scripts and references into active agent memory on demand.",
        code: { lang: "markdown", cmd: "# AGENTS.md\n- Always write TypeScript strict types for API routes.\n- Use HSL color variables for CSS styling.\n- Never delete failing unit tests." }
      }
    ]
  },
  "web-search": {
    title: "17. Web Search Automation & Web Scraping",
    lead: "Automated web browsing, documentation scraping, and Tavily integration.",
    sections: [
      {
        heading: "Full End-to-End Web Search Process",
        text: "Stage 1: Search Query Dispatch\nAgent calls web_search tool with search terms.\n\nStage 2: Headless Playwright / Scrapy Launch\nLaunches headless browser instance to query search engines or target URLs.\n\nStage 3: DOM Markdown Conversion\nExtracts body text, converts HTML to clean markdown, and strips navigation boilerplate.\n\nStage 4: Context Delivery\nFeeds extracted technical documentation back to LLM context window.",
        code: { lang: "bash", cmd: "utim task 'Search latest Next.js 15 app router docs and update layout.jsx'" }
      }
    ]
  },
  "visual-vision": {
    title: "18. Vision & Multimodal Image Processing",
    lead: "Multimodal image inspection, PIL downscaling, and synthetic image generation.",
    sections: [
      {
        heading: "Full Multimodal Image Compression Process",
        text: "Stage 1: Image Reading\nread_file loads binary file bytes from disk.\n\nStage 2: PIL Downscaling & Compression (compress_image_base64)\nIf file size > 1 MB or max dimension > 1600px, Pillow resizes image to max 1600px and converts RGBA/P to RGB JPEG with quality 82.\n\nStage 3: Base64 Payload Safety\nReduces payload size from ~20 MB down to ~250 KB, preventing HTTP 413 errors and socket connection drops during LLM request submission.",
        code: { lang: "bash", cmd: "utim task 'Inspect screenshot.png and fix layout'" }
      }
    ]
  },
  "ast-graph": {
    title: "19. Tree-Sitter AST & Code Knowledge Graph",
    lead: "Abstract Syntax Tree code parsing for Python, JS, TS, Go, Rust, Java, and C++.",
    sections: [
      {
        heading: "Full End-to-End AST Parsing Process",
        text: "Stage 1: Tree-Sitter Grammar Initialization\nLoads language grammar for target file extension.\n\nStage 2: Concrete Syntax Tree (CST) Generation\nParses file into hierarchical AST nodes.\n\nStage 3: Symbol Definition Slicing\nExtracts start_line and end_line for classes, functions, and methods.\n\nStage 4: Targeted Code Reading\nAllows read_file symbol_name queries to return precise 30-line code blocks rather than 3,000-line text dumps.",
        code: { lang: "bash", cmd: "utim task 'Refactor calculate_route function in router.py'" }
      }
    ]
  },
  "sharing-redeem": {
    title: "20. Session Sharing, Teammate Transfers & Code Redemption (/share, /quotashare, /redeem)",
    lead: "Complete end-to-end operational manual detailing exact execution steps, server verification protocols, database state updates, and error handling for session sharing, quota transfers, and promotional code redemptions.",
    sections: [
      {
        heading: "Full End-to-End Operational Process for Code Redemption (/redeem)",
        text: "Stage 1: Authentication Verification\nBefore accepting a redemption request, the CLI verifies that an active account token exists in the local OS keyring. If unauthenticated, the CLI halts and prompts: 'Authentication required. Please run utim login first.'\n\nStage 2: Input Methods\nDevelopers can invoke redemption via two methods:\n  Method A (Direct CLI Command): utim /redeem WELCOME2026 or utim redeem WELCOME2026\n  Method B (Interactive Modal Dialog): Type /redeem in the TUI prompt without arguments to open the interactive input dialog box.\n\nStage 3: Server API Payload & Handshake\nThe CLI constructs a signed HTTP POST request to the primary credit gateway:\n  Endpoint: https://api.utim.dev/api/v1/quota/redeem\n  Headers: Authorization: Bearer <ID_TOKEN>, X-UTIM-Install-ID: <INSTALL_ID>\n  Payload: {\"code\": \"WELCOME2026\", \"install_id\": \"inst_8a92f1\", \"timestamp\": 1786289000}\n\nStage 4: Server Database Validation Logic\nThe server backend executes atomic database transaction checks against the promo_codes table:\n  1. Existence Check: Verifies the code exists and is marked as active.\n  2. Expiration Check: Verifies current server timestamp < code.expires_at.\n  3. Redemption Cap Check: Ensures code.current_redemptions < code.max_redemptions.\n  4. User Multi-Use Guard: Queries user_redemptions DB table to ensure user_id has not already claimed this code.\n\nStage 5: Credit Settlement & State Synchronization\nUpon successful validation, the backend executes an atomic SQL transaction:\n  - Increments user's Rollover Quota Bank (e.g. +500 credits) or updates subscription plan tier.\n  - Writes transaction audit row in user_transactions table with code metadata.\n  - Returns JSON response: {\"success\": true, \"credits_added\": 500, \"new_balance\": 1450, \"message\": \"Code WELCOME2026 successfully redeemed!\"}.\n  - CLI updates local cache in .utim/intelligence.db and displays green success banner.\n\nStage 6: Error Code & Exception Handling\n  - HTTP 400 Bad Request: Code format invalid or whitespace corruption.\n  - HTTP 404 Not Found: Code does not exist in database.\n  - HTTP 409 Conflict: Code has already been redeemed by this account.\n  - HTTP 410 Gone: Promotional campaign has expired.\n  - HTTP 429 Rate Limit: Exceeded maximum 5 redemption attempts per hour (prevents brute-force guessing).",
        code: { lang: "bash", cmd: "utim /redeem WELCOME2026" }
      },
      {
        heading: "Full End-to-End Operational Process for Teammate Quota Share (/quotashare)",
        text: "Stage 1: Transfer Authorization\nSender invokes: /quotashare <AMOUNT> <RECIPIENT_EMAIL>\n\nStage 2: Balance Check\nCLI verifies sender's local Rollover Quota Bank balance >= AMOUNT.\n\nStage 3: Server Settlement Transaction\nCLI sends POST request to https://api.utim.dev/api/v1/quota/transfer:\n  - Server deducts AMOUNT from sender's user_quotas table.\n  - Server credits AMOUNT to recipient's user_quotas table.\n  - Server sends notification email to recipient.",
        code: { lang: "bash", cmd: "utim /quotashare 100 teammate@company.com" }
      },
      {
        heading: "Full End-to-End Operational Process for Session Sharing (/share)",
        text: "Stage 1: Packaging & Anonymization\nCLI reads session log from .utim/sessions/<SESSION_ID>.jsonl and strips sensitive API keys and tokens.\n\nStage 2: Encryption & Cloud Upload\nCLI encrypts transcript payload using AES-GCM 256 with a locally generated key fragment.\n\nStage 3: Share Link Generation\nCLI uploads encrypted blob to UTIM Share Vault and outputs share URL:\n  Output: https://utim.dev/share/sess_9f82a1b4c5d6#key=e8f9...",
        code: { lang: "bash", cmd: "utim /share" }
      }
    ]
  },
  workflows: {
    title: "21. Common Developer Workflows",
    lead: "Step-by-step guides for everyday engineering tasks.",
    sections: [
      {
        heading: "Full End-to-End Feature Implementation Lifecycle",
        text: "Stage 1: Prompt Specification\nDeveloper prompts UTIM with task description.\n\nStage 2: Plan Construction (/plan)\nAgent generates step-by-step modification checklist.\n\nStage 3: Context Retrieval\nInspects code files via AST parsing and ChromaDB vector search.\n\nStage 4: Code Patching & Validation\nApplies edits with pre-write syntax compilation validation.\n\nStage 5: Test Execution & Verification\nRuns local test suites (pytest, npm test) and commits reversible snapshot.",
        code: { lang: "bash", cmd: "utim task 'Add user profile settings page with password reset modal'" }
      }
    ]
  },
  troubleshooting: {
    title: "22. Troubleshooting & Diagnostics",
    lead: "Resolving encoding issues, terminal display bugs, connection errors, and state corruption.",
    sections: [
      {
        heading: "Full Diagnostic Check Process (utim doctor)",
        text: "Stage 1: Environment Audit\nChecks Node.js version, Python extras, Git PATH configuration.\n\nStage 2: Security & Keyring Check\nVerifies OS keyring read/write permissions.\n\nStage 3: Network & Proxy Verification\nTests HTTPS connection to https://api.utim.dev and OpenRouter.\n\nStage 4: Workspace State Health\nValidates SQLite database integrity (.utim/intelligence.db) and ChromaDB vector store.",
        code: { lang: "bash", cmd: "utim doctor" }
      }
    ]
  },
  "eula-license": {
    title: "23. Emend AI Proprietary End User License Agreement (EULA)",
    lead: "Full End User License Agreement governing installation, usage, and commercial licensing.",
    sections: [
      {
        heading: "Full Proprietary License Compliance Process",
        text: "Stage 1: License Scope Verification\nVerifies UTIM CLI is proprietary software owned by Emend AI.\n\nStage 2: Commercial Work Enforcement\nCommercial repositories require Paid Subscription or active BYOK setup.\n\nStage 3: IP Protection & Code Ownership\nUser retains 100% full ownership of generated code.",
        callout: { type: "important", title: "Commercial Use Requirement", text: "Paid subscription or active BYOK setup required for commercial software engineering." }
      }
    ]
  },
  "sla-compliance": {
    title: "24. Service Level Agreement & Business Readiness",
    lead: "99.9% API uptime commitment, enterprise security, and compliance benchmarks.",
    sections: [
      {
        heading: "Full SLA Monitoring & Credit Claim Process",
        text: "Stage 1: Uptime Monitoring\nServer status tracked continuously at 99.9% monthly target.\n\nStage 2: SLA Breach Notification\nIn event of unscheduled outage exceeding SLA, user submits claim.\n\nStage 3: Service Credit Deposit\nApproved claims receive credit deposits directly to Rollover Quota Bank.",
        table: [
          { key: "API Availability SLA", val: "99.9% monthly uptime target with status page tracking." },
          { key: "Data Retention", val: "Zero prompt storage policy on completion proxy servers." }
        ]
      }
    ]
  },
  changelog: {
    title: "25. Full Version Release Notes & Changelog",
    lead: "Complete release history for UTIM CLI from v1.0.0 to v2.1.3.",
    sections: [
      {
        heading: "v2.1.3 (Current Stable)",
        text: "- Minor modifications and Bug fixes"
      },
      {
        heading: "v2.1.2",
        text: "- Fixed `grep_search` auto-regex promotion bug where literal searches containing regex characters failed.\n- Made `ripgrep` an automatic dependency with bundled fallback binary.\n- Increased context compression interval from 25 to 35 iterations.\n- Reduced batch poll interval from 5s to 0.3s for faster Batch API results.\n- Cleaned up feedback error messages to exclude verbose HTTPS Connection Pool details."
      },
      {
        heading: "v2.1.1",
        text: "- Fixed high-resolution image upload connection drops with automatic PIL JPEG downscaling.\n- Added dedicated docs.utim.dev website portal in landing/docs/.\n- Updated legal documentation to Emend AI Proprietary EULA (Non-MIT).\n- Fixed Lucide React icon name collisions."
      }
    ]
  }
};
