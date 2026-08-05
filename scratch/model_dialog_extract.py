def _dialog_model(orchestrator):
    """Interactive settings to choose between Main Agent and Sub-Agents configuration."""
    from .config import config

    while True:
        main_model = orchestrator.model_id

        rows = [
            {"key": "main", "label": "🤖 Configure Main Agent Model", "desc": f"Currently: {main_model}"},
            {"key": "sub_menu", "label": "🧠 Configure Sub-Agent Models...", "desc": "Configure models for specific subagents (Investigator, Search, Planner, Expander)"},
            {"key": "back", "label": "Back to Chat", "desc": "Return to the previous screen"}
        ]

        def _render(idx, row, selected):
            bg = 'bg:#1e1e2e' if selected else ''
            if row["key"] == "back":
                fg = 'bold #f38ba8' if selected else '#f38ba8'
            elif row["key"] == "main":
                fg = 'bold #89b4fa' if selected else '#89b4fa'
            else:
                fg = 'bold #a6e3a1' if selected else '#a6e3a1'
            return [
                (bg, '  ➔ ' if selected else '    '),
                (bg or fg, f"{row['label']}\n"),
                (bg or 'dim', f"      {row['desc']}\n"),
            ]

        action, idx = _run_mcp_search_list_dialog(
            rows, _render,
            title="Model Settings Selection",
            legend="ENTER to select, ESC/Q to return to chat",
            search_prompt=" 🔍 Search Options: ",
            search_title="Filter Options",
            list_title="Available Model Configurations"
        )

        if action != "select" or rows[idx]["key"] == "back":
            return

        key = rows[idx]["key"]
        if key == "main":
            _dialog_model_main(orchestrator, target="main")
        elif key == "sub_menu":
            _dialog_subagents_menu(orchestrator)

def _dialog_subagents_menu(orchestrator):
    from .config import config

    while True:
        def _cur(key, default):
            val = config.get(key)
            if val == "__non_agent__":
                return "Non-Agent Tool (direct mode)"
            if val == "__none__":
                return "None (main agent writes prompt)"
            return val or default

        rows = [
            {"key": "project_res", "label": "🔍 Codebase Investigator (project_res)",
             "desc": f"Currently: {_cur('subagent_model_project_res', f'Default ({DEFAULT_MODEL})')}"},
            {"key": "web_search", "label": "🌐 Deep Research Agent (web_search)",
             "desc": f"Currently: {_cur('subagent_model_web_search', f'Default ({DEFAULT_MODEL})')}"},
            {"key": "plan_project", "label": "📋 Planner Agent (plan_project)",
             "desc": f"Currently: {_cur('subagent_model_plan_project', f'Default ({DEFAULT_MODEL})')}"},
            {"key": "generate_image", "label": "🎨 Prompt Expander Model (generate_image)",
             "desc": f"Currently: {_cur('subagent_model_generate_image', f'Default ({DEFAULT_MODEL})')}"},
            {"key": "image_gen", "label": "🖼️ Image Generator Model (image_gen)",
             "desc": f"Currently: {_cur('subagent_model_image_gen', 'Default (openrouter/free)')}"},
            {"key": "analyze_image", "label": "👁️ Image Analyzer Agent (analyze_image)",
             "desc": f"Currently: {_cur('subagent_model_analyze_image', 'Default (google/gemini-3.1-flash-image)')}"},
            {"key": "blender_vision", "label": "📦 Blender Vision Analyzer (blender_vision)",
             "desc": f"Currently: {_cur('subagent_model_blender_vision', 'Default (google/gemini-3.1-flash-image)')}"},
            {"key": "blender_code", "label": "⚙️ Blender Script Writer (blender_code)",
             "desc": f"Currently: {_cur('subagent_model_blender_code', f'Default ({DEFAULT_MODEL})')}"},
            {"key": "back", "label": "Back to Main Model Settings", "desc": "Return to the previous screen"}
        ]

        def _render(idx, row, selected):
            bg = 'bg:#1e1e2e' if selected else ''
            if row["key"] == "back":
                fg = 'bold #f38ba8' if selected else '#f38ba8'
            elif row["key"].startswith("blender"):
                fg = 'bold #cba6f7' if selected else '#cba6f7'
            else:
                fg = 'bold #a6e3a1' if selected else '#a6e3a1'
            return [
                (bg, '  ➤ ' if selected else '    '),
                (bg or fg, f"{row['label']}\n"),
                (bg or 'dim', f"      {row['desc']}\n"),
            ]

        action, idx = _run_mcp_search_list_dialog(
            rows, _render,
            title="Configure Sub-Agent Models",
            legend="ENTER to select, ESC/Q to go back",
            search_prompt=" 🔍 Search Subagents: ",
            search_title="Filter Subagents",
            list_title="Available Subagents"
        )

        if action != "select" or rows[idx]["key"] == "back":
            return

        key = rows[idx]["key"]
        _dialog_model_main(orchestrator, target=f"subagent_{key}")


def _dialog_model_main(orchestrator, target="main"):
    """Main model picker — dynamically fetches and filters OpenRouter models, keeping custom models."""
    from .config import config  # local import avoids circular issues at module load

    # ── Define allowed primary and helper models based on target ──────────────
    plan_name = config.get("user_plan", "free").lower()
    is_paid_plan = (plan_name != "free")

    if target == 'main':
        approved_set = {
            DEFAULT_MODEL
        }
        if is_paid_plan:
            approved_set.update({
                "recraft/recraft-v4.1",
                "recraft/recraft-v4.1-pro",
                "recraft/recraft-v4.1-utility",
                "recraft/recraft-v4.1-utility-pro",
                "recraft/recraft-v4.1-vector",
                "recraft/recraft-v4.1-pro-vector",
                "x-ai/grok-imagine-image-quality",
                "microsoft/mai-image-2.5",
                "sourceful/riverflow-v2.5-fast",
                "sourceful/riverflow-v2.5-pro",
                "google/gemini-3-pro-image",
                "google/gemini-3.1-flash-image",
                "openai/gpt-image-1",
                "openai/gpt-image-1-mini",
                "openai/gpt-image-2",
                "google/gemini-2.5-flash-image",
                "openai/gpt-5-image",
                "openai/gpt-5-image-mini",
                "google/gemini-3-pro-image-preview",
                "black-forest-labs/flux.2-pro",
                "black-forest-labs/flux.2-flex",
                "black-forest-labs/flux.2-max",
                "bytedance-seed/seedream-4.5",
                "black-forest-labs/flux.2-klein-4b",
                "sourceful/riverflow-v2-fast",
                "sourceful/riverflow-v2-pro",
                "anthropic/claude-sonnet-4.6",
                "inclusionai/ling-2.6-flash",
                "xiaomi/mimo-v2.5",
                "xiaomi/mimo-v2.5-pro",
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4-pro",
                "openai/gpt-5.5",
                "inclusionai/ling-2.6-1t",
                "moonshotai/kimi-k2.6",
                "openai/gpt-5.3-codex",
                "google/gemini-3.1-pro-preview-customtools",
                "openai/gpt-5.4",
                "minimax/minimax-m2.7",
                "kwaipilot/kat-coder-pro-v2",
                "z-ai/glm-5.1",
                "anthropic/claude-fable-5",
                "nex-agi/nex-n2-pro",
                "minimax/minimax-m3",
                "moonshotai/kimi-k2.7-code",
                "deepseek/deepseek-r1",
                "x-ai/grok-4.3",
                "google/gemini-3.5-flash",
                "qwen/qwen3.7-max",
                "stepfun/step-3.7-flash",
            
                "anthropic/claude-sonnet-4.5",
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-opus-4.5",
                "anthropic/claude-opus-4.6",
                "anthropic/claude-opus-4.7",
                "anthropic/claude-opus-4.8",
                "anthropic/claude-sonnet-5",
                "z-ai/glm-5-turbo",
                "z-ai/glm-4.7",
                "z-ai/glm-5",
                "z-ai/glm-5.2",
                "qwen/qwen3.7-plus",
                "qwen/qwen3.7-max",
                "qwen/qwen3.6-plus",
                "openai/gpt-5.4-mini",
                "minimax/minimax-m2.5",
                "x-ai/grok-4.20",
                "x-ai/grok-build-0.1",
                "moonshotai/kimi-k2.5",
})
    elif target.startswith('subagent_') and target not in ('subagent_image_gen', 'subagent_blender_vision', 'subagent_analyze_image', 'subagent_blender_code'):
        approved_set = {
            DEFAULT_MODEL,
            "google/gemma-4-31b-it:free",
            "openrouter/free",
        }
        if is_paid_plan:
            approved_set.update({
                "recraft/recraft-v4.1",
                "recraft/recraft-v4.1-pro",
                "recraft/recraft-v4.1-utility",
                "recraft/recraft-v4.1-utility-pro",
                "recraft/recraft-v4.1-vector",
                "recraft/recraft-v4.1-pro-vector",
                "x-ai/grok-imagine-image-quality",
                "microsoft/mai-image-2.5",
                "sourceful/riverflow-v2.5-fast",
                "sourceful/riverflow-v2.5-pro",
                "google/gemini-3-pro-image",
                "google/gemini-3.1-flash-image",
                "openai/gpt-image-1",
                "openai/gpt-image-1-mini",
                "openai/gpt-image-2",
                "google/gemini-2.5-flash-image",
                "openai/gpt-5-image",
                "openai/gpt-5-image-mini",
                "google/gemini-3-pro-image-preview",
                "black-forest-labs/flux.2-pro",
                "black-forest-labs/flux.2-flex",
                "black-forest-labs/flux.2-max",
                "bytedance-seed/seedream-4.5",
                "black-forest-labs/flux.2-klein-4b",
                "sourceful/riverflow-v2-fast",
                "sourceful/riverflow-v2-pro",
                DEFAULT_MODEL,
                "anthropic/claude-sonnet-4.6",
                "inclusionai/ling-2.6-flash",
                "xiaomi/mimo-v2.5",
                "xiaomi/mimo-v2.5-pro",
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4-pro",
                "openai/gpt-5.5",
                "inclusionai/ling-2.6-1t",
                "moonshotai/kimi-k2.6",
                "openai/gpt-5.3-codex",
                "google/gemini-3.1-pro-preview-customtools",
                "openai/gpt-5.4",
                "minimax/minimax-m2.7",
                "kwaipilot/kat-coder-pro-v2",
                "z-ai/glm-5.1",
                "anthropic/claude-fable-5",
                "nex-agi/nex-n2-pro",
                "minimax/minimax-m3",
                "moonshotai/kimi-k2.7-code",
                "deepseek/deepseek-r1",
                "x-ai/grok-4.3",
                "google/gemini-3.5-flash",
                "qwen/qwen3.7-max",
                "stepfun/step-3.7-flash",
            
                "anthropic/claude-sonnet-4.5",
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-opus-4.5",
                "anthropic/claude-opus-4.6",
                "anthropic/claude-opus-4.7",
                "anthropic/claude-opus-4.8",
                "anthropic/claude-sonnet-5",
                "z-ai/glm-5-turbo",
                "z-ai/glm-4.7",
                "z-ai/glm-5",
                "z-ai/glm-5.2",
                "qwen/qwen3.7-plus",
                "qwen/qwen3.7-max",
                "qwen/qwen3.6-plus",
                "openai/gpt-5.4-mini",
                "minimax/minimax-m2.5",
                "x-ai/grok-4.20",
                "x-ai/grok-build-0.1",
                "moonshotai/kimi-k2.5",
})
    elif target == "subagent_image_gen":
        # subagent_image_gen
        approved_set = {
            "sourceful/riverflow-v2.5-fast",
            "black-forest-labs/flux.2-klein-4b",
        }
        if is_paid_plan:
            approved_set.update({
                "recraft/recraft-v4.1",
                "recraft/recraft-v4.1-pro",
                "recraft/recraft-v4.1-utility",
                "recraft/recraft-v4.1-utility-pro",
                "recraft/recraft-v4.1-vector",
                "recraft/recraft-v4.1-pro-vector",
                "x-ai/grok-imagine-image-quality",
                "microsoft/mai-image-2.5",
                "sourceful/riverflow-v2.5-fast",
                "sourceful/riverflow-v2.5-pro",
                "google/gemini-3-pro-image",
                "google/gemini-3.1-flash-image",
                "openai/gpt-image-1",
                "openai/gpt-image-1-mini",
                "openai/gpt-image-2",
                "google/gemini-2.5-flash-image",
                "openai/gpt-5-image",
                "openai/gpt-5-image-mini",
                "google/gemini-3-pro-image-preview",
                "black-forest-labs/flux.2-pro",
                "black-forest-labs/flux.2-flex",
                "black-forest-labs/flux.2-max",
                "bytedance-seed/seedream-4.5",
                "black-forest-labs/flux.2-klein-4b",
                "sourceful/riverflow-v2-fast",
                "sourceful/riverflow-v2-pro",
                "black-forest-labs/flux.2-flex",
                "openai/gpt-5-image-mini",
                "google/gemini-3-pro-image-preview",
                "black-forest-labs/flux.2-max",
                "black-forest-labs/flux.2-klein-4b",
                "sourceful/riverflow-v2-fast",
                "sourceful/riverflow-v2-pro",
                "google/gemini-3.1-flash-image-preview",
                "sourceful/riverflow-v2.5-fast",
                "google/gemini-3.1-flash-image",
                "openai/gpt-image-2"
            })

    elif target in ("subagent_blender_vision", "subagent_analyze_image"):
        approved_set = {
            "google/gemma-4-31b-it:free",
        }
        if is_paid_plan:
            approved_set.update({
                "google/gemini-3.1-flash-image",
                "google/gemini-3-pro-image",
                "google/gemini-3-pro-image-preview",
                "openai/gpt-5-image",
                "openai/gpt-5-image-mini",
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-opus-4.6",
                "xiaomi/mimo-v2.5",
                "xiaomi/mimo-v2.5-pro",
                "openai/gpt-5.3-codex",
                "openai/gpt-5.4",
                "x-ai/grok-4.3",
            })

    elif target == "subagent_blender_code":
        approved_set = {
            DEFAULT_MODEL,
        }
        if is_paid_plan:
            approved_set.update({
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-opus-4.6",
                "openai/gpt-5.3-codex",
                "openai/gpt-5.4",
                "openai/gpt-5.5",
                "deepseek/deepseek-v4-pro",
                "moonshotai/kimi-k2.7-code",
                "x-ai/grok-4.3",
                "minimax/minimax-m2.7",
                "google/gemini-3.5-flash",
            })
    
    else:
        approved_set = {DEFAULT_MODEL}

    # Cost hierarchy for paid plans
    cost_hierarchy = {
        DEFAULT_MODEL: (0, "Very low"),
        "anthropic/claude-sonnet-4.6": (3, "High"),
        "inclusionai/ling-2.6-flash": (0, "Very low"),
        "xiaomi/mimo-v2.5": (0, "Very low"),
        "xiaomi/mimo-v2.5-pro": (2, "Medium"),
        "deepseek/deepseek-v4-flash": (0, "Very low"),
        "deepseek/deepseek-v4-pro": (1, "Low"),
        "openai/gpt-5.5": (4, "Very high"),
        "inclusionai/ling-2.6-1t": (1, "Low"),
        "moonshotai/kimi-k2.6": (2, "Medium"),
        "openai/gpt-5.3-codex": (4, "Very high"),
        "google/gemini-3.1-pro-preview-customtools": (2, "Medium"),
        "openai/gpt-5.4": (3, "High"),
        "minimax/minimax-m2.7": (2, "Medium"),
        "kwaipilot/kat-coder-pro-v2": (1, "Low"),
        "z-ai/glm-5.1": (2, "Medium"),
        "anthropic/claude-fable-5": (4, "Very high"),
        "nex-agi/nex-n2-pro": (2, "Medium"),
        "minimax/minimax-m3": (1, "Low"),
        "moonshotai/kimi-k2.7-code": (2, "Medium"),
        "deepseek/deepseek-r1": (2, "Medium"),
        "x-ai/grok-4.3": (2, "Medium"),
        "google/gemini-3.5-flash": (3, "High"),
        "qwen/qwen3.7-max": (3, "High"),
        "stepfun/step-3.7-flash": (1, "Low"),
        
        # Free NVIDIA models:
        
        # Image models:
        "black-forest-labs/flux.2-flex": (3, "High"),
        "black-forest-labs/flux.2-max": (3, "High"),
        "black-forest-labs/flux.2-klein-4b": (1, "Low"),
        "sourceful/riverflow-v2-fast": (2, "Medium"),
        "sourceful/riverflow-v2-pro": (4, "Very high"),
        "sourceful/riverflow-v2.5-fast": (0, "Very low"),
        "google/gemini-3-pro-image-preview": (2, "Medium"),
        "google/gemini-3.1-flash-image-preview": (1, "Low"),
        "google/gemini-3.1-flash-image": (1, "Low"),
        "openai/gpt-5-image-mini": (2, "Medium"),
        "openai/gpt-image-2": (4, "Very high"),
    
        "recraft/recraft-v4.1": (2, "Medium"),
        "recraft/recraft-v4.1-pro": (3, "High"),
        "recraft/recraft-v4.1-utility": (2, "Medium"),
        "recraft/recraft-v4.1-utility-pro": (3, "High"),
        "recraft/recraft-v4.1-vector": (2, "Medium"),
        "recraft/recraft-v4.1-pro-vector": (3, "High"),
        "x-ai/grok-imagine-image-quality": (2, "Medium"),
        "microsoft/mai-image-2.5": (2, "Medium"),
        "sourceful/riverflow-v2.5-fast": (2, "Medium"),
        "sourceful/riverflow-v2.5-pro": (3, "High"),
        "google/gemini-3-pro-image": (3, "High"),
        "google/gemini-3.1-flash-image": (2, "Medium"),
        "openai/gpt-image-1": (2, "Medium"),
        "openai/gpt-image-1-mini": (2, "Medium"),
        "openai/gpt-image-2": (2, "Medium"),
        "google/gemini-2.5-flash-image": (2, "Medium"),
        "openai/gpt-5-image": (2, "Medium"),
        "openai/gpt-5-image-mini": (2, "Medium"),
        "google/gemini-3-pro-image-preview": (3, "High"),
        "black-forest-labs/flux.2-pro": (3, "High"),
        "black-forest-labs/flux.2-flex": (2, "Medium"),
        "black-forest-labs/flux.2-max": (3, "High"),
        "bytedance-seed/seedream-4.5": (2, "Medium"),
        "black-forest-labs/flux.2-klein-4b": (2, "Medium"),
        "sourceful/riverflow-v2-fast": (2, "Medium"),
        "sourceful/riverflow-v2-pro": (3, "High"),
        "anthropic/claude-sonnet-4.5": (3, "High"),
        "anthropic/claude-sonnet-4.6": (3, "High"),
        "anthropic/claude-opus-4.5": (3, "High"),
        "anthropic/claude-opus-4.6": (3, "High"),
        "anthropic/claude-opus-4.7": (3, "High"),
        "anthropic/claude-opus-4.8": (3, "High"),
        "anthropic/claude-sonnet-5": (2, "Medium"),
        "z-ai/glm-5-turbo": (2, "Medium"),
        "z-ai/glm-4.7": (1, "Low"),
        "z-ai/glm-5": (1, "Low"),
        "z-ai/glm-5.2": (1, "Low"),
        "qwen/qwen3.7-plus": (1, "Low"),
        "qwen/qwen3.7-max": (2, "Medium"),
        "qwen/qwen3.6-plus": (1, "Low"),
        "openai/gpt-5.4-mini": (1, "Low"),
        "minimax/minimax-m2.5": (0, "Very low"),
        "x-ai/grok-4.20": (2, "Medium"),
        "x-ai/grok-build-0.1": (2, "Medium"),
        "moonshotai/kimi-k2.5": (1, "Low"),
}

    # Clean description mapping for supported models
    model_descs = {
        DEFAULT_MODEL: ("Default free coding & agent orchestration model.", ["default"]),
        "anthropic/claude-sonnet-4.6": ("Primary premium model for main agent and reasoning tasks.", ["premium"]),
        "inclusionai/ling-2.6-flash": ("Fast, cost-effective agent model by InclusionAI.", []),
        "xiaomi/mimo-v2.5": ("Highly capable multimodal model by Xiaomi.", []),
        "xiaomi/mimo-v2.5-pro": ("Xiaomi flagship multimodal and reasoning model.", []),
        "deepseek/deepseek-v4-flash": ("Ultra-fast, cost-effective model by DeepSeek.", []),
        "deepseek/deepseek-v4-pro": ("DeepSeek flagship MoE and reasoning model.", []),
        "openai/gpt-5.5": ("Next-gen frontier reasoning model by OpenAI.", []),
        "inclusionai/ling-2.6-1t": ("Large context agent model by InclusionAI.", []),
        "moonshotai/kimi-k2.6": ("High-capability multimodal model by Moonshot AI.", []),
        "openai/gpt-5.3-codex": ("Premium OpenAI model optimized for deep coding tasks.", []),
        "google/gemini-3.1-pro-preview-customtools": ("Gemini model optimized for complex tool calling.", []),
        "openai/gpt-5.4": ("Advanced reasoning and analysis model by OpenAI.", []),
        "minimax/minimax-m2.7": ("High-performance chat and coding model by MiniMax.", []),
        "kwaipilot/kat-coder-pro-v2": ("Coding-focused assistant by KwaiPilot.", []),
        "z-ai/glm-5.1": ("Highly intelligent model by Z-AI.", []),
        "anthropic/claude-fable-5": ("Ultra-premium reasoning and creative writer by Anthropic.", []),
        "nex-agi/nex-n2-pro": ("Fast coding and chat model by Nex-AGI.", []),
        "minimax/minimax-m3": ("Multimodal assistant by MiniMax.", []),
        "moonshotai/kimi-k2.7-code": ("Open-weights coder model by Moonshot AI.", []),
        "deepseek/deepseek-r1": ("DeepSeek reasoning model with advanced chain-of-thought.", []),
        "x-ai/grok-4.3": ("Frontier reasoning model with real-time knowledge by xAI.", []),
        "google/gemini-3.5-flash": ("Fast, multimodal and agentic model by Google.", []),
        "qwen/qwen3.7-max": ("Flagship agentic and reasoning model by Qwen.", []),
        "stepfun/step-3.7-flash": ("Cost-effective multimodal assistant by StepFun.", []),
        
        # Free NVIDIA models:
        
        # Image models:
        "black-forest-labs/flux.2-flex": ("Flexible text-to-image generator by Black Forest Labs.", []),
        "black-forest-labs/flux.2-max": ("Flagship premium text-to-image generator by Black Forest Labs.", []),
        "black-forest-labs/flux.2-klein-4b": ("Lightweight, fast image generation model by Black Forest Labs.", []),
        "sourceful/riverflow-v2-fast": ("Fast, high-fidelity graphic generator by Sourceful.", []),
        "sourceful/riverflow-v2-pro": ("High-end graphic generator for marketing and web design by Sourceful.", []),
        "sourceful/riverflow-v2.5-fast": ("Free graphic generator model by Sourceful.", []),
        "google/gemini-3-pro-image-preview": ("Google frontier multimodal and image generation model.", []),
        "google/gemini-3.1-flash-image-preview": ("Google cost-effective multimodal and image model.", []),
        "google/gemini-3.1-flash-image": ("Google stable image and multimodal vision model.", []),
        "openai/gpt-5-image-mini": ("OpenAI high-speed multimodal and image model.", []),
        "openai/gpt-image-2": ("OpenAI advanced image synthesis and editing model.", []),
    
        "anthropic/claude-sonnet-4.5": ("Anthropic: Claude Sonnet 4.5.", []), 
        "anthropic/claude-sonnet-4.6": ("Anthropic: Claude Sonnet 4.6.", []), 
        "anthropic/claude-opus-4.5": ("Anthropic: Claude Opus 4.5.", []), 
        "anthropic/claude-opus-4.6": ("Anthropic: Claude Opus 4.6.", []), 
        "anthropic/claude-opus-4.7": ("Anthropic: Claude Opus 4.7.", []), 
        "anthropic/claude-opus-4.8": ("Anthropic: Claude Opus 4.8.", []), 
        "anthropic/claude-sonnet-5": ("Anthropic: Claude Sonnet 5.", []), 
        "z-ai/glm-5-turbo": ("Z.ai: GLM 5 Turbo.", []), 
        "z-ai/glm-4.7": ("Z.ai: GLM 4.7.", []), 
        "z-ai/glm-5": ("Z.ai: GLM 5.", []), 
        "z-ai/glm-5.2": ("Z.ai: GLM 5.2.", []), 
        "qwen/qwen3.7-plus": ("Qwen: Qwen3.7 Plus.", []), 
        "qwen/qwen3.7-max": ("Qwen: Qwen3.7 Max.", []), 
        "qwen/qwen3.6-plus": ("Qwen: Qwen3.6 Plus.", []), 
        "openai/gpt-5.4-mini": ("OpenAI: GPT-5.4 Mini.", []), 
        "minimax/minimax-m2.5": ("MiniMax: MiniMax M2.5.", []), 
        "x-ai/grok-4.20": ("xAI: Grok 4.20.", []), 
        "x-ai/grok-build-0.1": ("xAI: Grok Build 0.1.", []), 
        "moonshotai/kimi-k2.5": ("MoonshotAI: Kimi K2.5.", []), 
}

    recommended_set = set()
    if plan_name == "free":
        recommended_set = {
            DEFAULT_MODEL,
        }
    elif plan_name == "hobby":
        recommended_set = {
            DEFAULT_MODEL,
            "kwaipilot/kat-coder-pro-v2",
            "minimax/minimax-m3",
            "inclusionai/ling-2.6-1t",
            "deepseek/deepseek-v4-pro",
            "deepseek/deepseek-r1",
            "moonshotai/kimi-k2.6",
            "moonshotai/kimi-k2.7-code",
            "sourceful/riverflow-v2.5-fast",
            "black-forest-labs/flux.2-klein-4b",
            "google/gemini-3.1-flash-image-preview",
            "google/gemini-3.1-flash-image"
        }
    elif plan_name in ("pro", "team"):
        recommended_set = {
            "anthropic/claude-sonnet-4.6",
            "xiaomi/mimo-v2.5-pro",
            "minimax/minimax-m2.7",
            "z-ai/glm-5.1",
            "nex-agi/nex-n2-pro",
            "x-ai/grok-4.3",
            "google/gemini-3.1-pro-preview-customtools",
            "google/gemini-3.5-flash",
            "qwen/qwen3.7-max",
            "openai/gpt-5.4",
            "openai/gpt-5.5",
            "google/gemini-3-pro-image-preview",
            "openai/gpt-5-image-mini",
            "sourceful/riverflow-v2-fast"
        }
    else:
        # Max, Enterprise, Ultimate (allowance $45 - $100 per month)
        recommended_set = {
            "openai/gpt-5.5",
            "openai/gpt-5.3-codex",
            "anthropic/claude-fable-5",
            "anthropic/claude-opus-4.6",
            "google/gemini-3.1-pro-preview-customtools",
            "x-ai/grok-4.3",
            "qwen/qwen3.7-max",
            "black-forest-labs/flux.2-flex",
            "black-forest-labs/flux.2-max",
            "sourceful/riverflow-v2-pro",
            "openai/gpt-image-2"
        }

    # ── Build model list from approved_set (live API enriches descriptions) ──
    # We build from approved_set so dialog always shows all curated models,
    # even if OpenRouter's live API doesn't return them (new/delayed models).
    live_descs = {}
    try:
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=6)
        resp.raise_for_status()
        for rm in resp.json().get("data", []):
            mid = rm.get("id")
            if mid:
                live_descs[mid] = rm.get("description", "")
    except Exception:
        pass  # Offline — use local descriptions only

    primary_models = []
    for mid in approved_set:
        desc_val, tags_val = model_descs.get(mid, (live_descs.get(mid, "Fast, efficient model."), []))
        primary_models.append({
            "model_id": mid,
            "desc": desc_val,
            "tags": tags_val,
            "source": "openrouter"
        })

    # Sort based on cost hierarchy
    primary_models = sorted(primary_models, key=lambda x: (cost_hierarchy.get(x["model_id"], (9, ""))[0], x["model_id"]))

    # ── Prepend user-defined custom models ───────────────────────────────────
    custom_entries = [
        {
            "model_id": m["model_id"],
            "tags": ["custom", m.get("provider_name", "")],
            "source": "custom",
            "desc": f"Custom model via {m.get('provider_name', 'Custom')}."
        }
        for m in config.custom_models
    ]
    models = custom_entries + primary_models

    # ── Inject sentinel options for subagent targets ───────────────────────────
    # "Non-Agent Tool" — disables the LLM loop, tool runs in simple direct mode
    # "None" — only available for generate_image, so main agent writes the prompt
    _BLENDER_TARGETS = ('subagent_blender_vision', 'subagent_blender_code')
    if target.startswith('subagent_') and target not in ('subagent_image_gen',) + _BLENDER_TARGETS:
        non_agent_desc = (
            "Disable the LLM subagent loop. Tool runs in direct/simple mode (e.g. web search = raw results, "
            "codebase investigator = file content only, planner = task list from main agent)."
        )
        sentinel_label = "🚫  Non-Agent Tool  (direct mode)"
        if target in ("subagent_generate_image",):
            sentinel_label = "⬜  None  (main agent writes the image prompt)"
            non_agent_desc = "Disable the prompt expander entirely — the main agent writes the image prompt directly."
        models.insert(0, {
            "model_id": "__non_agent__",
            "desc": non_agent_desc,
            "tags": ["sentinel"],
            "source": "sentinel",
            "label": sentinel_label,
        })
    if target == 'subagent_generate_image':
        # Also offer a 2nd sentinel: __none__ = no prompt expander at all
        models.insert(0, {
            "model_id": "__none__",
            "desc": "Disable the prompt expander entirely — the main agent writes the image prompt directly.",
            "tags": ["sentinel"],
            "source": "sentinel",
            "label": "⬜  None  (main agent writes prompt directly)",
        })

    # Hoist the currently selected model to the top of the list so it is highlighted by default
    current_model = None
    if target == 'main':
        current_model = orchestrator.model_id
    elif target.startswith('subagent_'):
        subkey = target.split('_', 1)[1]
        current_model = config.get(f"subagent_model_{subkey}")

    if current_model:
        current_item = None
        for item in models:
            if item["model_id"] == current_model:
                current_item = item
                break
        if current_item:
            models.remove(current_item)
            models.insert(0, current_item)

    if not models:
        console.print("\n[red]No models available.[/red]\n")
        return

    def render_model(i, m, sel):
        bg  = 'bg:#a6e3a1 bold #1e1e2e' if sel else ''
        mid = m['model_id']
        source = m.get('source', 'openrouter')

        # Sentinel items: Non-Agent Tool / None
        if source == 'sentinel':
            label = m.get('label', mid)
            sentinel_style = 'bg:#f9e2af bold #1e1e2e' if sel else 'bold #f9e2af'
            desc_style = bg or 'fg:#585b70'
            current_mark = ''
            subkey = target.split('_', 1)[1] if target.startswith('subagent_') else ''
            if config.get(f"subagent_model_{subkey}") == mid:
                current_mark = '  ◀ current'
            if is_paid_plan:
                return [
                    (sentinel_style, f"  {label:<26}"),
                    (sentinel_style, f"{'':<12}"),
                    (sentinel_style, f"{'':<14}"),
                    (desc_style, f" {m['desc']}{current_mark}\n\n"),
                ]
            else:
                return [
                    (sentinel_style, f"  {label}"),
                    (sentinel_style, f"{current_mark}\n"),
                    (desc_style, f"     {m['desc']}\n\n"),
                ]

        # Clean display ID (remove provider prefix and ':free' suffix)
        display_id = mid
        if source == 'openrouter':
            display_id = mid.split('/', 1)[-1]
            if display_id.endswith(':free'):
                display_id = display_id[:-5]
                
        if display_id == "gemini-3.1-pro-preview-customtools":
            display_id = "gemini-3.1-pro-preview"
            
        display_id = display_id.replace('-', ' ')
        if display_id:
            display_id = display_id[0].upper() + display_id[1:]

        
        current = ''
        if target == 'main' and mid == orchestrator.model_id:
            current = '  ◀ current'
        elif target.startswith('subagent_') and mid == config.get(f"subagent_model_{target.split('_', 1)[1]}"):
            current = '  ◀ current'

        desc = m.get("desc", "Fast, efficient model for daily tasks.")

        style      = bg or ('fg:#f9e2af' if source == 'custom' else 'fg:#cdd6f4')
        desc_style = bg or 'fg:#585b70'

        if is_paid_plan:
            cost_label = cost_hierarchy.get(mid, (0, "Very low"))[1]
            col_model = f"  {display_id:<26}"
            col_cost  = f"{cost_label:<12}"
            
            rec_text = ' [recommended]' if mid in recommended_set else ''
            rec_style = bg or 'fg:#a6e3a1 bold'
            col_rec   = f"{rec_text:<14}"

            cost_style = style
            if not sel:
                if cost_label == "Very low":
                    cost_style = "fg:#a6e3a1"
                elif cost_label == "Low":
                    cost_style = "fg:#89dceb"
                elif cost_label == "Medium":
                    cost_style = "fg:#f9e2af"
                elif cost_label == "High":
                    cost_style = "fg:#fab387"
                else:
                    cost_style = "fg:#f38ba8"

            return [
                (style,      col_model),
                (cost_style, col_cost),
                (rec_style,  col_rec),
                (desc_style, f" {desc}{current}\n\n"),
            ]
        else:
            return [
                (style,      f"  {display_id}"),
                (style,      f"{current}\n"),
                (desc_style, f"     {desc}\n\n"),
            ]

    title_str = 'Select Model  [dim](a=Add Custom  b=BYOK Import  d=Delete Custom  x=Disconnect Provider  q=Cancel)[/dim]'
    if is_paid_plan:
        title_str = 'Select Model  [dim](a=Add Custom  b=BYOK Import  d=Delete Custom  x=Disconnect Provider)[/dim]\n\n[bold white]  MODEL                      COST        TAGS          DESCRIPTION[/bold white]'

    action, idx = _run_list_dialog(
        models, render_model,
        title=title_str,
        legend='↑↓ Navigate  Enter Select  a Add custom  b BYOK Import  d Delete  x Disconnect Provider  q Cancel',
        extra_keys={'a': 'add_custom', 'b': 'byok_import', 'd': 'delete_custom', 'x': 'disconnect_provider'},
    )

    if action == 'select':
        selected_model = models[idx]['model_id']
        source = models[idx].get('source', 'openrouter')
        label = '[yellow](custom)[/yellow] ' if source == 'custom' else ''
        
        if target == 'main':
            orchestrator.model_id = selected_model
            console.print(f"\n[bold #f9e2af]✓ Main Agent model set to {label}{selected_model}[/bold #f9e2af]\n")
            # Update compression threshold for new model
            try:
                orchestrator._update_model_threshold(orchestrator.model_id)
            except Exception:
                pass
        elif target.startswith('subagent_'):
            subkey = target.split('_', 1)[1]
            config.set(f"subagent_model_{subkey}", selected_model)
            console.print(f"\n[bold #f9e2af]✓ {subkey} subagent model set to {label}{selected_model}[/bold #f9e2af]\n")

    elif action == 'add_custom':
        _dialog_add_custom_model(orchestrator)

    elif action == 'byok_import':
        _dialog_byok_import(orchestrator)

    elif action == 'delete_custom':
        if models and idx < len(models):
            target_item = models[idx]
            if target_item.get('source') == 'custom':
                _dialog_delete_custom_model(orchestrator, target_item['model_id'])
            else:
                console.print("\n[yellow]Only custom models can be deleted.[/yellow]\n")

    elif action == 'disconnect_provider':
        _dialog_disconnect_provider(orchestrator)


def _dialog_byok_import(orchestrator):
    """Bring Your Own Key (BYOK) wizard to auto-fetch models from v1/models endpoint."""
    import sys
    import time
    import requests
    from prompt_toolkit import prompt as ptk_prompt
    from prompt_toolkit.styles import Style as PTStyle
    from rich.console import Console as RichConsole
    from .config import config

    # Write directly to the real stdout to avoid buffering after alternate-screen restore
    byok_console = RichConsole(file=sys.__stdout__, highlight=False, theme=custom_theme)
    time.sleep(0.05)

    byok_console.print(
        "\n[bold #cba6f7]╭─ Bring Your Own Key (BYOK) ─────────────────────────────────────╮[/bold #cba6f7]"
        "\n[bold #cba6f7]│[/bold #cba6f7]  Paste your provider's base URL and API key.                  [bold #cba6f7]│[/bold #cba6f7]"
        "\n[bold #cba6f7]│[/bold #cba6f7]  [dim]UTIM will fetch all models from {base_url}/models and add   [/dim][bold #cba6f7]│[/bold #cba6f7]"
        "\n[bold #cba6f7]│[/bold #cba6f7]  [dim]them to your custom list automatically.                    [/dim][bold #cba6f7]│[/bold #cba6f7]"
        "\n[bold #cba6f7]╰─────────────────────────────────────────────────────────────────╯[/bold #cba6f7]\n"
    )

    PROVIDER_PRESETS = {
        "1": ("OpenAI",       "https://api.openai.com/v1"),
        "2": ("Groq",         "https://api.groq.com/openai/v1"),
        "3": ("Together AI",  "https://api.together.xyz/v1"),
        "4": ("Mistral",      "https://api.mistral.ai/v1"),
        "5": ("Fireworks AI", "https://api.fireworks.ai/inference/v1"),
        "6": ("OpenRouter",   "https://openrouter.ai/api/v1"),
        "7": ("Ollama",       "http://localhost:11434/v1"),
        "8": ("LM Studio",    "http://localhost:1234/v1"),
        "9": ("Custom",       ""),
    }

    byok_console.print("[bold]Choose provider preset (or press Enter for Custom):[/bold]")
    for k, (name, url) in PROVIDER_PRESETS.items():
        url_hint = f"[dim]{url}[/dim]" if url else "[dim]enter manually[/dim]"
        byok_console.print(f"  [bold #cba6f7]{k}[/bold #cba6f7]  {name}  {url_hint}")

    pt_style = PTStyle.from_dict({'': '#cba6f7'})

    try:
        choice = ptk_prompt("\n  Provider number [9]: ", style=pt_style).strip() or "9"
    except (EOFError, KeyboardInterrupt):
        byok_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if choice in PROVIDER_PRESETS:
        provider_name, base_url_preset = PROVIDER_PRESETS[choice]
    else:
        provider_name, base_url_preset = "Custom", ""

    byok_console.print(f"\n[bold]Provider:[/bold] [#cba6f7]{provider_name}[/#cba6f7]")

    # Base URL
    url_placeholder = base_url_preset or "https://..."
    try:
        base_url = ptk_prompt(f"  Base URL [{url_placeholder}]: ", style=pt_style).strip() or base_url_preset
    except (EOFError, KeyboardInterrupt):
        byok_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if not base_url:
        byok_console.print("\n[red]Base URL is required.[/red]\n")
        return

    # Display name override
    try:
        pname_input = ptk_prompt(f"  Provider display name [{provider_name}]: ", style=pt_style).strip()
        if pname_input:
            provider_name = pname_input
    except (EOFError, KeyboardInterrupt):
        byok_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # API key (hidden input)
    byok_console.print(
        f"\n  [dim]API key for [bold]{provider_name}[/bold] "
        "(stored securely in config.json — input hidden):[/dim]"
    )
    try:
        api_key = ptk_prompt("  API Key (Enter to skip): ", is_password=True, style=pt_style).strip()
    except (EOFError, KeyboardInterrupt):
        byok_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # Fetch models
    url = base_url.rstrip("/")
    if not url.endswith("/models"):
        url = f"{url}/models"

    byok_console.print(f"\n  [dim]Fetching model list from [bold]{url}[/bold]...[/dim]")
    headers = {}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    try:
        if "openrouter.ai" in url:
            headers["HTTP-Referer"] = "https://utim.dev"
            headers["X-Title"] = "UTIM CLI Client"

        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        byok_console.print(f"\n[red]❌ Failed to fetch models: {e}[/red]\n")
        return

    model_list = []
    if isinstance(data, dict) and "data" in data and isinstance(data["data"], list):
        model_list = data["data"]
    elif isinstance(data, list):
        model_list = data
    else:
        if isinstance(data, dict):
            for val in data.values():
                if isinstance(val, list):
                    model_list = val
                    break

    if not model_list:
        byok_console.print("\n[red]❌ Could not parse any models from the endpoint response.[/red]\n")
        return

    byok_console.print(f"\n[bold #a6e3a1]✓ Successfully fetched {len(model_list)} models![/bold #a6e3a1]")

    imported_count = 0
    for item in model_list:
        m_id = None
        if isinstance(item, dict):
            m_id = item.get("id") or item.get("name") or item.get("model")
        elif isinstance(item, str):
            m_id = item

        if not m_id:
            continue

        # Add each model to custom config list
        entry = {
            "model_id":       m_id,
            "provider_name":  provider_name,
            "base_url":       base_url,
            "api_key":        api_key,
            "context_window": 128_000,
        }
        config.add_custom_model(entry)
        imported_count += 1

    byok_console.print(f"[bold #a6e3a1]✓ Imported {imported_count} models to your custom list![/bold #a6e3a1]\n")



def _dialog_add_custom_model(orchestrator):
    """Interactive wizard to add a model from any OpenAI-compatible provider."""
    import sys
    import time
    from prompt_toolkit import prompt as ptk_prompt
    from prompt_toolkit.styles import Style as PTStyle
    from rich.console import Console as RichConsole
    from .config import config

    # Use sys.__stdout__ directly to bypass buffering after alternate-screen restore
    add_console = RichConsole(file=sys.__stdout__, highlight=False, theme=custom_theme)
    time.sleep(0.05)

    add_console.print(
        "\n[bold #42bcf5]╭─ Add Custom Model ──────────────────────────────────────────╮[/bold #42bcf5]"
        "\n[bold #42bcf5]│[/bold #42bcf5]  Add any model that exposes an OpenAI-compatible API.        [bold #42bcf5]│[/bold #42bcf5]"
        "\n[bold #42bcf5]│[/bold #42bcf5]  [dim]Examples: OpenAI, Anthropic (via proxy), Groq, Ollama,   [/dim][bold #42bcf5]│[/bold #42bcf5]"
        "\n[bold #42bcf5]│[/bold #42bcf5]  [dim]Together AI, Mistral, LM Studio, vLLM, etc.              [/dim][bold #42bcf5]│[/bold #42bcf5]"
        "\n[bold #42bcf5]╰─────────────────────────────────────────────────────────────╯[/bold #42bcf5]\n"
    )

    PROVIDER_PRESETS = {
        "1": ("OpenAI",       "https://api.openai.com/v1"),
        "2": ("Groq",         "https://api.groq.com/openai/v1"),
        "3": ("Together AI",  "https://api.together.xyz/v1"),
        "4": ("Mistral",      "https://api.mistral.ai/v1"),
        "5": ("Fireworks AI", "https://api.fireworks.ai/inference/v1"),
        "6": ("Ollama",       "http://localhost:11434/v1"),
        "7": ("LM Studio",    "http://localhost:1234/v1"),
        "8": ("Custom",       ""),
    }

    add_console.print("[bold]Choose provider (or press Enter for Custom):[/bold]")
    for k, (name, url) in PROVIDER_PRESETS.items():
        url_hint = f"[dim]{url}[/dim]" if url else "[dim]enter manually[/dim]"
        add_console.print(f"  [bold #42bcf5]{k}[/bold #42bcf5]  {name}  {url_hint}")

    pt_style = PTStyle.from_dict({'': '#42bcf5'})

    try:
        choice = ptk_prompt("\n  Provider number [8]: ", style=pt_style).strip() or "8"
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if choice in PROVIDER_PRESETS:
        provider_name, base_url_preset = PROVIDER_PRESETS[choice]
    else:
        provider_name, base_url_preset = "Custom", ""

    add_console.print(f"\n[bold]Provider:[/bold] [#42bcf5]{provider_name}[/#42bcf5]")

    # Base URL
    url_placeholder = base_url_preset or "https://..."
    try:
        base_url = ptk_prompt(f"  Base URL [{url_placeholder}]: ", style=pt_style).strip() or base_url_preset
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if not base_url:
        add_console.print("\n[red]Base URL is required.[/red]\n")
        return

    # Provider name (allow override)
    try:
        pname_input = ptk_prompt(f"  Provider display name [{provider_name}]: ", style=pt_style).strip()
        if pname_input:
            provider_name = pname_input
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # API key (hidden input)
    add_console.print(
        f"\n  [dim]API key for [bold]{provider_name}[/bold] "
        "(stored in config.json — input hidden):[/dim]"
    )
    try:
        api_key = ptk_prompt("  API Key (Enter to skip): ", is_password=True, style=pt_style).strip()
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # Model ID
    add_console.print(
        "\n  [dim]Model identifier sent in the API request "
        "(e.g. gpt-4o, llama-3.3-70b-versatile, mistral-large-latest)[/dim]"
    )
    try:
        model_id = ptk_prompt("  Model ID: ", style=pt_style).strip()
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if not model_id:
        add_console.print("\n[red]Model ID is required.[/red]\n")
        return

    # Context window
    try:
        ctx_raw = ptk_prompt("  Context window tokens [128000]: ", style=pt_style).strip()
        context_window = int(ctx_raw) if ctx_raw else 128_000
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return
    except ValueError:
        context_window = 128_000

    entry = {
        "model_id":       model_id,
        "provider_name":  provider_name,
        "base_url":       base_url,
        "api_key":        api_key,
        "context_window": context_window,
    }

    config.add_custom_model(entry)

    add_console.print(
        f"\n[bold #a6e3a1]✓ Custom model saved![/bold #a6e3a1]\n"
        f"  [dim]Model ID :[/dim] [bold]{model_id}[/bold]\n"
        f"  [dim]Provider  :[/dim] {provider_name}\n"
        f"  [dim]Base URL  :[/dim] {base_url}\n"
        f"  [dim]Context   :[/dim] {context_window:,} tokens\n"
    )

    # Ask if user wants to switch to this model now
    try:
        switch = ptk_prompt("  Switch to this model now? [Y/n]: ", style=pt_style).strip().lower()
    except (EOFError, KeyboardInterrupt):
        switch = "n"

    if switch in ("", "y", "yes"):
        orchestrator.model_id = model_id
        try:
            orchestrator._update_model_threshold(model_id)
        except Exception:
            pass
        add_console.print(f"\n[bold #a6e3a1]✓ Now using {model_id}[/bold #a6e3a1]\n")
    else:
        add_console.print("\n[dim]Model saved. Use /model to select it anytime.[/dim]\n")


def _dialog_delete_custom_model(orchestrator, model_id: str):
    """Confirm and delete a custom model by model_id."""
    import sys
    import time
    from prompt_toolkit import prompt as ptk_prompt
    from prompt_toolkit.styles import Style as PTStyle
    from rich.console import Console as RichConsole
    from .config import config

    del_console = RichConsole(file=sys.__stdout__, highlight=False, theme=custom_theme)
    time.sleep(0.05)

    del_console.print(f"\n[yellow]Delete custom model [bold]{model_id}[/bold]?[/yellow]")
    try:
        confirm = ptk_prompt(
            "  Type 'yes' to confirm: ",
            style=PTStyle.from_dict({'': '#f38ba8'})
        ).strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""

    if confirm == "yes":
        removed = config.remove_custom_model(model_id)
        if removed:
            del_console.print(f"\n[bold #a6e3a1]✓ Removed {model_id}[/bold #a6e3a1]\n")
            # If the deleted model was active, reset to default
            if orchestrator.model_id == model_id:
                from utim_cli.server.models import DEFAULT_MODEL
                orchestrator.model_id = DEFAULT_MODEL
                del_console.print(f"[dim]Switched back to {DEFAULT_MODEL}[/dim]\n")
        else:
            del_console.print("[yellow]Model not found in custom list.[/yellow]\n")
    else:
        del_console.print("\n[dim]Cancelled.[/dim]\n")





def _dialog_disconnect_provider(orchestrator):
    """Confirm and delete all custom models associated with a provider (disconnect provider)."""
    import sys
    import time
    from prompt_toolkit import prompt as ptk_prompt
    from prompt_toolkit.styles import Style as PTStyle
    from rich.console import Console as RichConsole
    from .config import config

    disc_console = RichConsole(file=sys.__stdout__, highlight=False, theme=custom_theme)
    time.sleep(0.05)

    custom_models = config.custom_models
    if not custom_models:
        disc_console.print("\n[yellow]No custom providers found.[/yellow]\n")
        return

    # Find unique providers (by provider_name and base_url)
    providers = []
    seen = set()
    for m in custom_models:
        p_name = m.get("provider_name", "Custom")
        b_url = m.get("base_url", "")
        key = (p_name, b_url)
        if key not in seen:
            seen.add(key)
            providers.append({
                "name": p_name,
                "url": b_url,
                "count": sum(1 for x in custom_models if x.get("provider_name") == p_name and x.get("base_url") == b_url)
            })

    disc_console.print(
        "\n[bold #f38ba8]╭─ Disconnect BYOK Provider ──────────────────────────────────────╮[/bold #f38ba8]"
        "\n[bold #f38ba8]│[/bold #f38ba8]  Select a provider to remove all of its imported models.       [bold #f38ba8]│[/bold #f38ba8]"
        "\n[bold #f38ba8]╰─────────────────────────────────────────────────────────────────╯[/bold #f38ba8]\n"
    )

    disc_console.print("[bold]Available Providers:[/bold]")
    for idx, p in enumerate(providers, 1):
        url_hint = f"[dim]{p['url']}[/dim]" if p['url'] else "[dim]local[/dim]"
        disc_console.print(f"  [bold #f38ba8]{idx}[/bold #f38ba8]  {p['name']} ({p['count']} models)  {url_hint}")

    pt_style = PTStyle.from_dict({'': '#f38ba8'})
    try:
        choice = ptk_prompt("\n  Disconnect provider number: ", style=pt_style).strip()
    except (EOFError, KeyboardInterrupt):
        disc_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if not choice.isdigit() or not (1 <= int(choice) <= len(providers)):
        disc_console.print("\n[red]Invalid choice.[/red]\n")
        return

    selected = providers[int(choice) - 1]
    disc_console.print(
        f"\n[yellow]This will disconnect [bold]{selected['name']}[/bold] "
        f"and delete all of its {selected['count']} models from UTIM.[/yellow]"
    )
    try:
        confirm = ptk_prompt("  Type 'yes' to confirm: ", style=pt_style).strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""

    if confirm == "yes":
        removed_count = config.remove_custom_provider(selected["name"], selected["url"])
        disc_console.print(
            f"\n[bold #a6e3a1]✓ Disconnected {selected['name']} and removed {removed_count} models![/bold #a6e3a1]\n"
        )
        # If active model was deleted, reset to DEFAULT_MODEL
        active_model = orchestrator.model_id
        active_still_exists = any(m["model_id"] == active_model for m in config.custom_models)
        if not active_still_exists and active_model not in [DEFAULT_MODEL, "anthropic/claude-sonnet-4.6"]:
            is_custom_removed = True
            # Hardcoded check since we cannot import utim_cli.server in production CLI builds
            # (as the server module is excluded from the package in pyproject.toml)
            if active_model.startswith("openai/") or active_model.startswith("anthropic/") or active_model.startswith("google/") or active_model.startswith("cohere/"):
                is_custom_removed = False
            
            if is_custom_removed:
                orchestrator.model_id = DEFAULT_MODEL
                disc_console.print(f"[dim]Active model removed. Switched back to cohere/north-mini-code:free[/dim]\n")
    else:
        disc_console.print("\n[dim]Cancelled.[/dim]\n")


from utim_cli.tui.mcp_dialog import _dialog_mcp, _dialog_mcp_manage, _dialog_mcp_install
from utim_cli.tui.tools_dialog import _dialog_tools



