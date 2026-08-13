# UTIM CLI Features

## 01 Autonomous Agent Loop
Think-act-observe cycle with structured checklist planning. UTIM breaks tasks into steps, executes code, runs builds, and self-heals failures — all without lifting a finger.
- **Tags:** Planning, Self-healing, Auto-accept

## 02 Full System Control
Runs shell commands, installs packages, spawns dev servers, and reads/writes your entire codebase directly on your machine. Dry-run & sandbox mode for safe exploration.
- **Tags:** Shell, Sandbox, Dry-run

## 03 Visual Analysis Engine
Analyzes screenshots and images using vision AI. Detects layout bugs, UI inconsistencies, and generates assets via AI image generation — all from the CLI.
- **Tags:** Screenshots, Image Gen, UI QA

## 04 Semantic Vector Memory
ChromaDB-backed RAG memory stores facts, conventions, and project history. Relevant context is automatically embedded into the prompt — no more re-explaining your stack.
- **Tags:** ChromaDB, RAG, Embeddings

## 05 Undo / Redo / Rewind
Every file change is diffed and snapshotted to session state. Roll back any edit, redo it, or rewind to any conversation turn — even after restarting your machine.
- **Tags:** /undo, /rewind, Diff snapshots

## 06 MCP Tool Ecosystem
Connects to any Model Context Protocol server — databases, GitHub, Figma, Slack, Playwright browser automation — with a curated registry of 200+ pre-configured servers.
- **Tags:** MCP, Playwright, GitHub

## 07 Bring Your Own Key
Connect any OpenAI-compatible provider using your own API keys. BYOK models bypass UTIM quota limits entirely and persist across project folders automatically.
- **Tags:** BYOK, Custom Models, No Limits

## 08 Share & Collaborate
Instantly zip and share your workspace, session history, and conversation context with teammates. Secure shareable links generated from the CLI in one command.
- **Tags:** /share, Zip Export, Team Link

## 09 Workspace Custom Skills
Auto-embed local SKILL.md guidelines into your context via local ChromaDB RAG. Saves prompt tokens and gives UTIM context-aware project rules without re-prompting.
- **Tags:** SKILL.md, AGENTS.md, Rules

## 10 Quota Sharing & Redeem Codes
Share your rollover Quota Bank and regular subscription credits with your referred teammates directly from the CLI, or generate non-expiring, secure redeem codes to distribute or claim later.
- **Tags:** /quotashare, /redeem, Collaboration

## 11 Models and Providers

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
