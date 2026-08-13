# Project-Scoped Rules and Guidelines for UTIM CLI

Welcome to the UTIM CLI development workspace. Follow these rules and activate the corresponding workspace-scoped skills based on your current task.

## Available Workspace Skills

You MUST read the corresponding `SKILL.md` file using the file viewer tool before implementing features in these domains:

1. **Terminal UI (TUI) Design**: [.agents/skills/terminal-ui-design/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/terminal-ui-design/SKILL.md)
   - *Use when*: Modifying interactive menus, Rich console logs, layouts, and `prompt_toolkit` inputs.
2. **Software Architecture**: [.agents/skills/software-architecture/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/software-architecture/SKILL.md)
   - *Use when*: Designing new Python modules, modifying state/orchestrator files, or refactoring codebase structures.
3. **MCP Server Development**: [.agents/skills/mcp-server-development/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/mcp-server-development/SKILL.md)
   - *Use when*: Writing new MCP servers, modifying connection pools, or handling stdio protocol wrappers.
4. **CLI UX Patterns**: [.agents/skills/cli-ux-patterns/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/cli-ux-patterns/SKILL.md)
   - *Use when*: Refining CLI prompts, progress indicators, non-interactive (TTY) handling, and user confirmations.
5. **Premium Web Design**: [.agents/skills/web-design-premium/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/web-design-premium/SKILL.md)
   - *Use when*: Coding web interfaces, using HSL colors, glassmorphism UI, transitions, or applying SEO tags.
6. **LLM Orchestration**: [.agents/skills/llm-orchestration/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/llm-orchestration/SKILL.md)
   - *Use when*: Editing LLM prompting context, parser loops, tools injection, token pruner, or semantic vector DB memory retrieval.
7. **Asynchronous Python (asyncio)**: [.agents/skills/async-python/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/async-python/SKILL.md)
   - *Use when*: Implementing asynchronous background tasks, reading subprocess streams, or thread safety locks.
8. **Creative Scrollytelling**: [.agents/skills/creative-scrollytelling/SKILL.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/skills/creative-scrollytelling/SKILL.md)
   - *Use when*: Coding typography-driven entrance effects, split-door opening screens, and kinetic viewport animations.

## Tool Usage Rules

- **Grep Search Alternation**: Always pass `"IsRegex": true` when executing `grep_search` with multi-keyword pipe (`|`) queries (e.g. `Laguna|Gemma|GPT`). See [.agents/rules/grep_search_rule.md](file:///C:/Users/user/Desktop/New%20folder/New%20folder/.agents/rules/grep_search_rule.md).
