import os
import json
import re
import textwrap
import time
from utim_cli.config import config

def _safe_prompt(prompt_text: str, color: str = None, is_password: bool = False) -> str:
    """Bulletproof replacement for prompt_toolkit's prompt() when nested inside run_in_terminal context.
    Prevents asyncio / nest_asyncio event loop crashes on Python 3.13.
    Writes directly to the original stdout and reads from the original stdin to bypass prompt_toolkit's interceptors.
    """
    import sys
    import getpass
    
    # Render with ANSI color if specified
    if color:
        color_clean = color.lstrip('#')
        if len(color_clean) == 6:
            r = int(color_clean[0:2], 16)
            g = int(color_clean[2:4], 16)
            b = int(color_clean[4:6], 16)
            ansi_prefix = f"\x1b[38;2;{r};{g};{b}m"
            ansi_suffix = "\x1b[0m"
        else:
            ansi_prefix = ""
            ansi_suffix = ""
        styled_prompt = f"{ansi_prefix}{prompt_text}{ansi_suffix}"
    else:
        styled_prompt = prompt_text
        
    out_stream = sys.__stdout__ if sys.__stdout__ else sys.stdout
    out_stream.write(styled_prompt)
    out_stream.flush()
    
    try:
        if is_password:
            val = getpass.getpass("", stream=out_stream)
        else:
            if sys.__stdin__ and hasattr(sys.__stdin__, "readline"):
                val = sys.__stdin__.readline()
                if not val:
                    raise EOFError()
                val = val.rstrip('\r\n')
            else:
                val = input()
        return val
    except (KeyboardInterrupt, EOFError):
        raise KeyboardInterrupt


REASONING_MODELS = {
    "deepseek/deepseek-r1",
    "openai/gpt-5.5",
    "openai/gpt-5.4",
    "anthropic/claude-fable-5",
    "thinkingmachines/inkling",
    "moonshotai/kimi-k3",
    "meta/muse-spark-1.1",
    "xiaomi/mimo-v2.5-pro",
    "deepseek/deepseek-v4-pro",
    "x-ai/grok-4.3",
    "qwen/qwen3.7-max",
    "krea/krea-2",
    "krea-2",
}

_REASONING_MODELS_CACHE = None

def model_supports_reasoning(model_id: str) -> bool:
    global _REASONING_MODELS_CACHE
    if not model_id:
        return False
    model_id_lower = str(model_id).lower().strip()

    # 1. Populate cache from live OpenRouter metadata (models.txt) if available
    if _REASONING_MODELS_CACHE is None:
        _REASONING_MODELS_CACHE = set()
        try:
            import json, os
            root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            models_txt_path = os.path.join(root_dir, "models.txt")
            if not os.path.exists(models_txt_path):
                models_txt_path = "models.txt"
            if os.path.exists(models_txt_path):
                with open(models_txt_path, "r", encoding="utf-8") as f:
                    data = json.load(f).get("data", [])
                for m in data:
                    mid = m.get("id", "").lower()
                    supp = m.get("supported_parameters", []) or []
                    tags = m.get("tags", []) or []
                    if ("reasoning" in supp or "include_reasoning" in supp or "reasoning_effort" in supp or
                        "reasoning" in m or "reasoning" in tags or "thinking" in tags):
                        _REASONING_MODELS_CACHE.add(mid)
        except Exception:
            pass

    # If the model is in our live cache, use exact capability data
    if _REASONING_MODELS_CACHE:
        if model_id_lower in _REASONING_MODELS_CACHE or f"openrouter/{model_id_lower}" in _REASONING_MODELS_CACHE:
            return True

    # 2. Fallback check for explicit reasoning model indicators
    # (Do NOT include generic words like "pro", "flash", "lite", "claude", "gemini", "qwen")
    strict_reasoning_keywords = [
        "-r1", "/r1", "reasoning", "thinking", "thought", "o1-", "o3-", "o4-",
        "deepseek-r1", "deepseek-v3.2", "deepseek-v4", "nemotron-3-nano-omni-30b-a3b-reasoning",
        "krea-2"
    ]
    return any(kw in model_id_lower for kw in strict_reasoning_keywords) or model_id_lower in REASONING_MODELS

def init_model_settings(model_id: str):
    from utim_cli.config import config
    from utim_cli.server.models import get_max_output_tokens
    settings = config.get(f"model_settings_{model_id}")
    if not settings or not isinstance(settings, dict):
        is_reasoning = model_supports_reasoning(model_id)
        default_settings = {
            "temperature": 0.3 if not is_reasoning else 1.0,
            "max_tokens": get_max_output_tokens(model_id),
        }
        if is_reasoning:
            default_settings["reasoning_enabled"] = True
            default_settings["reasoning_effort"] = "medium"
        config.set(f"model_settings_{model_id}", default_settings)

def _prompt_reasoning_effort_dialog(model_id: str):
    from utim_cli.utim import _run_list_dialog, console
    from utim_cli.config import config
    import time
    
    rows = [
        {"name": "None", "value": "none", "desc": "Disable reasoning completely (raw responses without chain-of-thought)"},
        {"name": "Minimal", "value": "minimal", "desc": "Very short reasoning path to minimize token usage"},
        {"name": "Low", "value": "low", "desc": "Low reasoning effort for faster replies"},
        {"name": "Medium", "value": "medium", "desc": "Standard balanced reasoning effort (default)"},
        {"name": "High", "value": "high", "desc": "High reasoning effort for complex coding and math problems"},
        {"name": "XHigh", "value": "xhigh", "desc": "Extra high reasoning effort for deep multi-step exploration"},
        {"name": "Max", "value": "max", "desc": "Maximum allowed reasoning effort (highest thinking depth)"}
    ]
    
    def render_row(idx, row, selected):
        style = "fg:#00f0ff bold" if selected else ""
        arrow = "➔ " if selected else "  "
        return [
            (style, f"  {arrow}{row['name']:<10}"),
            ("class:dim", f" — {row['desc']}\n\n")
        ]
        
    action, selected_idx = _run_list_dialog(
        rows,
        render_row,
        title=f"Set Reasoning Effort for {model_id}",
        legend="Use ↑↓ to navigate, Enter to select, Escape/q to use default (medium)"
    )
    
    effort = "medium"
    if action == "select" and selected_idx is not None:
        effort = rows[selected_idx]["value"]
        
    settings = config.get(f"model_settings_{model_id}") or {}
    settings["reasoning_effort"] = effort
    config.set(f"model_settings_{model_id}", settings)
    console.print(f"\n[bold green]✓ Reasoning effort for {model_id} set to '{effort}'[/bold green]\n")
    time.sleep(1.0)

def _prompt_dialog(title: str, prompt_text: str = "> ") -> str:
    """A small interactive prompt dialog using prompt_toolkit.
    Avoids all Windows console raw/cooked mode issues by using prompt-toolkit's own input system.
    """
    from prompt_toolkit import Application
    from prompt_toolkit.layout import Layout, HSplit, Window
    from prompt_toolkit.layout.controls import FormattedTextControl
    from prompt_toolkit.widgets import TextArea
    from prompt_toolkit.key_binding import KeyBindings
    from prompt_toolkit.styles import Style as PTStyle
    from utim_cli.utim import _flush_stdin_buffer
    
    _flush_stdin_buffer()
    
    result = [None]
    
    # Text input area
    input_box = TextArea(
        multiline=False,
        prompt=prompt_text,
        focus_on_click=True,
    )
    
    kb = KeyBindings()
    
    @kb.add('enter')
    def _enter(e):
        result[0] = input_box.text
        e.app.exit()
        
    @kb.add('escape')
    @kb.add('q')
    @kb.add('c-c')
    def _quit(e):
        e.app.exit()
        
    # Title display window
    title_win = Window(
        content=FormattedTextControl([
            ('bold #42bcf5', f'\n  {title}\n'),
            ('class:dim', '  Press Enter to submit, Escape/Ctrl+C to cancel\n\n')
        ]),
        height=4
    )
    
    layout = Layout(
        HSplit([
            title_win,
            input_box,
            Window(height=1) # padding
        ])
    )
    
    style = PTStyle.from_dict({
        '': 'fg:#cdd6f4',
    })
    
    app = Application(
        layout=layout,
        key_bindings=kb,
        style=style,
        full_screen=True,
    )
    
    app.run()
    
    if result[0] is None:
        raise KeyboardInterrupt
        
    return result[0]


def _dialog_modelsettings(orchestrator):
    from utim_cli.utim import _run_list_dialog, console
    from utim_cli.config import config
    import time
    
    model_id = orchestrator.model_id
    
    try:
        while True:
            init_model_settings(model_id)
            settings = config.get(f"model_settings_{model_id}") or {}
            is_reasoning = model_supports_reasoning(model_id)
            
            rows = []
            rows.append({
                "key": "temperature",
                "name": "Temperature",
                "value": settings.get("temperature", 0.3 if not is_reasoning else 1.0),
                "desc": "Control randomness (0.0 to 2.0). Lower is more deterministic."
            })
            from utim_cli.server.models import get_max_output_tokens
            max_possible = get_max_output_tokens(model_id)
            rows.append({
                "key": "max_tokens",
                "name": f"Max Output Tokens (Model Limit: {max_possible:,})",
                "value": settings.get("max_tokens", max_possible),
                "desc": f"Maximum completion tokens model can generate per response (Hardware Max: {max_possible:,})."
            })
            
            if is_reasoning:
                rows.append({
                    "key": "reasoning_enabled",
                    "name": "Reasoning Enabled",
                    "value": settings.get("reasoning_enabled", True),
                    "desc": "Enable or disable internal thinking/chain-of-thought."
                })
                rows.append({
                    "key": "reasoning_effort",
                    "name": "Reasoning Effort",
                    "value": settings.get("reasoning_effort", "medium"),
                    "desc": "Thinking budget effort level (low, medium, high, max)."
                })
                
            rows.append({
                "key": "done",
                "name": "Save & Exit",
                "value": "",
                "desc": "Return to the chat session"
            })
            
            def render_row(idx, row, selected):
                style = "fg:#00f0ff bold" if selected else ""
                arrow = "➔ " if selected else "  "
                
                if row["key"] == "done":
                    return [
                        (style, f"  {arrow}{row['name']:<24}"),
                        ("class:dim", f" — {row['desc']}\n\n")
                    ]
                else:
                    val_style = "fg:#a6e3a1 bold" if selected else "fg:#a6e3a1"
                    return [
                        (style, f"  {arrow}{row['name']:<24}"),
                        (val_style, f"[{row['value']}]"),
                        ("class:dim", f" — {row['desc']}\n\n")
                    ]
                    
            action, selected_idx = _run_list_dialog(
                rows,
                render_row,
                title=f"Model Settings: {model_id}",
                legend="Use ↑↓ to navigate, Enter to modify, Escape/q to exit"
            )
            
            if not action or action != "select" or selected_idx is None:
                break
                
            selected_row = rows[selected_idx]
            if selected_row["key"] == "done":
                break
                
            key = selected_row["key"]
            if key == "temperature":
                try:
                    val_str = _prompt_dialog(
                        title=f"Modify Temperature (Current: {selected_row['value']})",
                        prompt_text="Enter new value (0.0 to 2.0): "
                    ).strip()
                    if val_str:
                        try:
                            val = float(val_str)
                            if 0.0 <= val <= 2.0:
                                settings["temperature"] = val
                                config.set(f"model_settings_{model_id}", settings)
                                console.print(f"[green]✓ Temperature updated to {val}[/green]")
                            else:
                                console.print("[red]✗ Error: Temperature must be between 0.0 and 2.0[/red]")
                        except ValueError:
                            console.print("[red]✗ Error: Invalid number[/red]")
                except KeyboardInterrupt:
                    console.print("\n[yellow]⚠ Cancelled temperature change.[/yellow]\n")
                time.sleep(1.0)
                
            elif key == "max_tokens":
                try:
                    from utim_cli.server.models import get_max_output_tokens
                    max_possible = get_max_output_tokens(model_id)
                    val_str = _prompt_dialog(
                        title=f"Modify Max Output Tokens (Model Max: {max_possible:,})",
                        prompt_text=f"Enter token limit (Current: {selected_row['value']:,}, Model Max: {max_possible:,}): "
                    ).strip()
                    if val_str:
                        try:
                            val = int(val_str)
                            if val > 0:
                                settings["max_tokens"] = val
                                config.set(f"model_settings_{model_id}", settings)
                                console.print(f"[green]✓ Max Output Tokens updated to {val}[/green]")
                            else:
                                console.print("[red]✗ Error: Value must be greater than 0[/red]")
                        except ValueError:
                            console.print("[red]✗ Error: Invalid integer[/red]")
                except KeyboardInterrupt:
                    console.print("\n[yellow]⚠ Cancelled max output tokens change.[/yellow]\n")
                time.sleep(1.0)
                
            elif key == "reasoning_enabled":
                current_val = selected_row["value"]
                new_val = not current_val
                settings["reasoning_enabled"] = new_val
                config.set(f"model_settings_{model_id}", settings)
                console.print(f"\n[green]✓ Reasoning Enabled toggled to {new_val}[/green]")
                time.sleep(0.5)
                
            elif key == "reasoning_effort":
                effort_rows = [
                    {"name": "None", "value": "none", "desc": "Disable reasoning completely"},
                    {"name": "Minimal", "value": "minimal", "desc": "Very short reasoning path"},
                    {"name": "Low", "value": "low", "desc": "Low reasoning effort for faster replies"},
                    {"name": "Medium", "value": "medium", "desc": "Standard balanced reasoning effort"},
                    {"name": "High", "value": "high", "desc": "High reasoning effort for complex coding/math"},
                    {"name": "XHigh", "value": "xhigh", "desc": "Extra high reasoning effort for deep exploration"},
                    {"name": "Max", "value": "max", "desc": "Maximum allowed reasoning effort"}
                ]
                def render_eff(i, r, s):
                    st = "fg:#00f0ff bold" if s else ""
                    ar = "➔ " if s else "  "
                    return [
                        (st, f"  {ar}{r['name']:<10}"),
                        ("class:dim", f" — {r['desc']}\n\n")
                    ]
                    
                eff_act, eff_idx = _run_list_dialog(
                    effort_rows,
                    render_eff,
                    title="Select Reasoning Effort",
                    legend="↑↓ Navigate  Enter Select  q Cancel"
                )
                if eff_act == "select" and eff_idx is not None:
                    effort_val = effort_rows[eff_idx]["value"]
                    settings["reasoning_effort"] = effort_val
                    config.set(f"model_settings_{model_id}", settings)
                    console.print(f"\n[green]✓ Reasoning Effort set to {effort_val}[/green]")
                    time.sleep(0.5)
    except KeyboardInterrupt:
        pass


def _dialog_model(orchestrator):
    """Interactive settings to choose between Main Agent and Sub-Agents configuration."""
    from utim_cli.config import config
    from utim_cli.utim import _run_mcp_search_list_dialog

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
                (bg or 'class:dim', f"      {row['desc']}\n"),
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
    from utim_cli.config import config
    from utim_cli.utim import _run_list_dialog, console, _run_mcp_search_list_dialog, DEFAULT_MODEL

    subagent_menu_index = 0

    while True:
        def _cur(key, default):
            val = config.get(key)
            if val == "__non_agent__":
                return "Non-Agent Tool (direct mode)"
            if val == "__none__":
                return "None (main agent writes prompt)"
            return val or default

        rows = [
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
            {"key": "blender_3d", "label": "🧊 Tripo 3D Generator Model (blender_3d)",
             "desc": f"Currently: {_cur('subagent_model_blender_3d', 'Default (v3.1)')}"},
            {"key": "blender_3d_mode", "label": "⚙️ Tripo 3D Generation Mode (auto/manual)",
             "desc": f"Currently: {config.get('subagent_model_blender_3d_mode', 'auto').upper()}"},
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
                (bg or 'class:dim', f"      {row['desc']}\n"),
            ]

        action, idx = _run_mcp_search_list_dialog(
            rows, _render,
            title="Configure Sub-Agent Models",
            legend="ENTER to select, ESC/Q to go back",
            search_prompt=" 🔍 Search Subagents: ",
            search_title="Filter Subagents",
            list_title="Available Subagents",
            initial_index=subagent_menu_index
        )

        if action != "select" or rows[idx]["key"] == "back":
            return

        subagent_menu_index = idx
        key = rows[idx]["key"]
        if key == "blender_3d_mode":
            current_mode = config.get("subagent_model_blender_3d_mode", "auto")
            new_mode = "manual" if current_mode == "auto" else "auto"
            config.set("subagent_model_blender_3d_mode", new_mode)
            console.print(f"\n[bold green]✓ Tripo 3D Generation Mode set to {new_mode.upper()}[/bold green]\n")
            time.sleep(1.0)
            continue
            
        _dialog_model_main(orchestrator, target=f"subagent_{key}")


def _dialog_model_main(orchestrator, target="main"):
    """Main model picker — dynamically fetches and filters OpenRouter models, keeping custom models."""
    from utim_cli.config import config
    from utim_cli.utim import DEFAULT_MODEL
    from utim_cli.utim import _run_search_list_dialog, console, custom_theme
    import time

    if target == "subagent_blender_3d":
        primary_models = [
            {"model_id": "v3.1", "desc": "Tripo H3.1 - H Series model, Ultra-high fidelity (default)", "tags": ["tripo", "recommended"], "source": "utim"},
            {"model_id": "p1", "desc": "Tripo P1 - P Series model, Optimized for low-poly game assets", "tags": ["tripo"], "source": "utim"},
            {"model_id": "rigging", "desc": "Tripo Rigging - Auto-rigging model for skeletal structures", "tags": ["tripo"], "source": "utim"},
            {"model_id": "animation", "desc": "Tripo Animation - Retarget preset animations to rigged models", "tags": ["tripo"], "source": "utim"},
        ]
        models = primary_models
        
        current_model = config.get("subagent_model_blender_3d") or "v3.1"
        current_item = None
        for item in models:
            if item["model_id"] == current_model:
                current_item = item
                break
        if current_item:
            models.remove(current_item)
            models.insert(0, current_item)
            
        def render_model(i, m, sel):
            bg = 'bg:#a6e3a1 bold #1e1e2e' if sel else ''
            mid = m['model_id']
            display_id = mid.upper()
            
            current_mark = ''
            if config.get("subagent_model_blender_3d", "v3.1") == mid:
                current_mark = '  ◀ current'
                
            style = bg or 'fg:#cdd6f4'
            desc_style = bg or 'fg:#585b70'
            
            desc_width = max(24, min(72, (console.size.width or 100) - 10))
            text = m["desc"]
            import textwrap
            desc_lines = textwrap.wrap(text, width=desc_width) or [""]
            desc_text = "".join(f"     {line}\n" for line in desc_lines) + "\n"
            return [
                (style, f"  {display_id:<12}"),
                (style, f"{current_mark}\n"),
                (desc_style, desc_text),
            ]
            
        title_str = 'Select Tripo 3D Generator Model\n\n[bold white]  MODEL        STATUS          DESCRIPTION[/bold white]'
        action, idx = _run_search_list_dialog(
            models, render_model,
            title=title_str,
            legend="Use ↑↓ to navigate, Enter to select, Escape/q to cancel",
            search_prompt=" 🔍 Search Tripo Models: ",
            search_title="Filter Models",
            list_title="Available Engines"
        )
        if action == 'select' and idx is not None:
            selected_model = models[idx]["model_id"]
            config.set("subagent_model_blender_3d", selected_model)
            config.set("subagent_model_blender_3d_source", "utim")
            console.print(f"\n[bold #f9e2af]✓ blender_3d subagent model set to {selected_model}[/bold #f9e2af]\n")
            time.sleep(1.0)
        return

    # ── Define allowed primary and helper models based on target ──────────────
    plan_name = str(config.get("user_plan") or "free").lower()
    is_paid_plan = (plan_name != "free")

    # Check if they have active bonus credits live (to unlock premium models)
    if not is_paid_plan and config.get("api_key"):
        try:
            from utim_cli.auth import SERVER_URL
            import requests
            resp = requests.get(
                f"{SERVER_URL}/quota",
                headers={"X-API-Key": config.get("api_key")},
                timeout=3.0,
            )
            if resp.status_code == 200:
                quota = resp.json()
                if (quota.get("free_bonus_balance") or 0.0) > 0.0:
                    is_paid_plan = True
        except Exception:
            pass

    if target == 'main':
        approved_set = {
            DEFAULT_MODEL
        }
        if is_paid_plan:
            approved_set.update({
                "anthropic/claude-sonnet-4.6",
                "anthropic/claude-sonnet-4.5",
                "anthropic/claude-sonnet-5",
                "anthropic/claude-opus-4.5",
                "anthropic/claude-opus-4.6",
                "anthropic/claude-opus-4.7",
                "anthropic/claude-opus-4.8",
                "anthropic/claude-fable-5",
                "inclusionai/ling-2.6-flash",
                "inclusionai/ling-2.6-1t",
                "xiaomi/mimo-v2.5",
                "xiaomi/mimo-v2.5-pro",
                "deepseek/deepseek-v4-flash",
                "deepseek/deepseek-v4-flash-0731",
                "deepseek/deepseek-v4-pro",
                "deepseek/deepseek-r1",
                "openai/gpt-5.5",
                "openai/gpt-5.4",
                "openai/gpt-5.4-mini",
                "openai/gpt-5.3-codex",
                "moonshotai/kimi-k2.6",
                "moonshotai/kimi-k2.7-code",
                "moonshotai/kimi-k2.5",
                "moonshotai/kimi-k3",
                "google/gemini-3.1-pro-preview-customtools",
                "google/gemini-3.5-flash",
                "google/gemini-3.6-flash",
                "minimax/minimax-m2.7",
                "minimax/minimax-m2.5",
                "minimax/minimax-m3",
                "kwaipilot/kat-coder-pro-v2",
                "z-ai/glm-5.1",
                "z-ai/glm-5-turbo",
                "z-ai/glm-4.7",
                "z-ai/glm-5",
                "z-ai/glm-5.2",
                "nex-agi/nex-n2-pro",
                "x-ai/grok-4.3",
                "x-ai/grok-4.20",
                "x-ai/grok-build-0.1",
                "qwen/qwen3.7-max",
                "qwen/qwen3.7-plus",
                "qwen/qwen3.6-plus",
                "stepfun/step-3.7-flash",
                "thinkingmachines/inkling",
                "meta/muse-spark-1.1",
                "poolside/laguna-s-2.1:free",
            })
    elif target.startswith('subagent_') and target not in ('subagent_image_gen', 'subagent_blender_vision', 'subagent_analyze_image', 'subagent_blender_code'):
        approved_set = {
            DEFAULT_MODEL,
            "google/gemma-4-31b-it:free",
            "poolside/laguna-s-2.1:free",
            "openrouter/free",
        }
        if is_paid_plan:
            approved_set.update({
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
                "google/gemini-3.6-flash",
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
                "x-ai/grok-4.20",
                "x-ai/grok-build-0.1",
                "moonshotai/kimi-k2.5",
                "thinkingmachines/inkling",
                "moonshotai/kimi-k3",
                "meta/muse-spark-1.1",
                "poolside/laguna-s-2.1:free",
            })
    elif target == "subagent_image_gen":
        # subagent_image_gen
        approved_set = {
            "sourceful/riverflow-v2.5-fast",
            "black-forest-labs/flux.2-klein-4b",
            "krea/krea-2",
        }
        if is_paid_plan:
            approved_set.update({
                "krea/krea-2",
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
                "google/gemini-3.1-flash-image-preview",
                "openai/gpt-image-2"
            })

    elif target in ("subagent_blender_vision", "subagent_analyze_image"):
        approved_set = {
            "google/gemma-4-31b-it:free",
            "google/gemma-4-26b-a4b-it:free",
            "nvidia/nemotron-nano-12b-v2-vl:free",
            "openrouter/free",
        }
        if is_paid_plan:
            approved_set.update({
                "google/gemini-3.5-flash",
                "google/gemini-3.1-pro-preview",
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
        "deepseek/deepseek-v4-flash-0731": (0, "Very low"),
        "deepseek/deepseek-v4-pro": (1, "Low"),
        "openai/gpt-5.5": (4, "Very high"),
        "inclusionai/ling-2.6-1t": (1, "Low"),
        "moonshotai/kimi-k2.6": (2, "Medium"),
        "openai/gpt-5.3-codex": (4, "Very high"),
        "google/gemini-3.1-pro-preview-customtools": (2, "Medium"),
        "openai/gpt-5.4": (3, "High"),
        "minimax/minimax-m2.7": (2, "Medium"),
        "kwaipilot/kat-coder-pro-v2": (1, "Low"),
        "kwaipilot/kat-coder-air-v2.5": (0, "Very low"),
        "kwaipilot/kat-coder-pro-v2.5": (1, "Low"),
        "z-ai/glm-5.1": (2, "Medium"),
        "anthropic/claude-fable-5": (4, "Very high"),
        "nex-agi/nex-n2-pro": (2, "Medium"),
        "nex-agi/nex-n2-mini": (0, "Very low"),
        "minimax/minimax-m3": (1, "Low"),
        "moonshotai/kimi-k2.7-code": (2, "Medium"),
        "deepseek/deepseek-r1": (2, "Medium"),
        "x-ai/grok-4.3": (2, "Medium"),
        "google/gemini-3.5-flash": (3, "High"),
        "google/gemini-3.6-flash": (2, "Medium"),
        "poolside/laguna-s-2.1:free": (0, "Very low"),
        "krea/krea-2": (2, "Medium"),
        "krea/krea-2-medium-turbo": (1, "Low"),
        "krea/krea-2-medium": (2, "Medium"),
        "krea/krea-2-large": (3, "High"),
        "qwen/qwen3.7-max": (3, "High"),
        "stepfun/step-3.7-flash": (1, "Low"),
        "thinkingmachines/inkling": (0, "Very low"),
        "moonshotai/kimi-k3": (1, "Low"),
        "meta/muse-spark-1.1": (0, "Very low"),
        
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
        "sourceful/riverflow-v2.5-pro": (3, "High"),
        "google/gemini-3-pro-image": (3, "High"),
        "openai/gpt-image-1": (2, "Medium"),
        "openai/gpt-image-1-mini": (2, "Medium"),
        "google/gemini-2.5-flash-image": (2, "Medium"),
        "openai/gpt-5-image": (2, "Medium"),
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
        "deepseek/deepseek-v4-flash-0731": ("DeepSeek V4 Flash 0731 — Ultra-fast MoE coding and reasoning model by DeepSeek.", []),
        "deepseek/deepseek-v4-pro": ("DeepSeek flagship MoE and reasoning model.", []),
        "openai/gpt-5.5": ("Next-gen frontier reasoning model by OpenAI.", []),
        "inclusionai/ling-2.6-1t": ("Large context agent model by InclusionAI.", []),
        "moonshotai/kimi-k2.6": ("High-capability multimodal model by Moonshot AI.", []),
        "openai/gpt-5.3-codex": ("Premium OpenAI model optimized for deep coding tasks.", []),
        "google/gemini-3.1-pro-preview-customtools": ("Gemini model optimized for complex tool calling.", []),
        "openai/gpt-5.4": ("Advanced reasoning and analysis model by OpenAI.", []),
        "minimax/minimax-m2.7": ("High-performance chat and coding model by MiniMax.", []),
        "kwaipilot/kat-coder-pro-v2": ("Coding-focused assistant by KwaiPilot.", []),
        "kwaipilot/kat-coder-air-v2.5": ("Fast, high-efficiency coding model by KwaiPilot.", []),
        "kwaipilot/kat-coder-pro-v2.5": ("Flagship advanced coding and reasoning model by KwaiPilot.", []),
        "z-ai/glm-5.1": ("Highly intelligent model by Z-AI.", []),
        "anthropic/claude-fable-5": ("Ultra-premium reasoning and creative writer by Anthropic.", []),
        "nex-agi/nex-n2-pro": ("Fast coding and chat model by Nex-AGI.", []),
        "nex-agi/nex-n2-mini": ("Highly efficient agentic MoE model by Nex-AGI.", []),
        "minimax/minimax-m3": ("Multimodal assistant by MiniMax.", []),
        "moonshotai/kimi-k2.7-code": ("Open-weights coder model by Moonshot AI.", []),
        "deepseek/deepseek-r1": ("DeepSeek reasoning model with advanced chain-of-thought.", []),
        "x-ai/grok-4.3": ("Frontier reasoning model with real-time knowledge by xAI.", []),
        "google/gemini-3.5-flash": ("Fast, multimodal and agentic model by Google.", []),
        "google/gemini-3.6-flash": ("Google next-gen high-speed multimodal and reasoning model.", ["premium"]),
        "poolside/laguna-s-2.1:free": ("Free coding and reasoning model by Poolside.", ["free"]),
        "krea/krea-2": ("Krea 2 text-to-image generator (supports Low, Medium, High reasoning modes).", ["premium", "image"]),
        "krea/krea-2-medium-turbo": ("Krea 2 Medium Turbo text-to-image generator.", ["premium", "image"]),
        "krea/krea-2-medium": ("Krea 2 Medium text-to-image generator.", ["premium", "image"]),
        "krea/krea-2-large": ("Krea 2 Large text-to-image generator.", ["premium", "image"]),
        "qwen/qwen3.7-max": ("Flagship agentic and reasoning model by Qwen.", []),
        "stepfun/step-3.7-flash": ("Cost-effective multimodal assistant by StepFun.", []),
        "thinkingmachines/inkling": ("Large-context, code-optimized reasoning model by Thinking Machines Lab.", ["premium"]),
        "moonshotai/kimi-k3": ("Frontier-class reasoning MoE model by Moonshot AI.", ["premium", "reasoning"]),
        "meta/muse-spark-1.1": ("Multimodal reasoning and agentic model by Meta Superintelligence Labs.", ["premium", "multimodal"]),
        
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

    # ── Build model list: server catalog is primary, local data is fallback ───
    # The server /models/catalog endpoint returns models grouped by tool target.
    # We fetch it here and use the appropriate list for this dialog target.
    live_descs = {}
    all_openrouter_raw = []
    root_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    models_txt_path = os.path.join(root_dir, "models.txt")
    if not os.path.exists(models_txt_path):
        models_txt_path = "models.txt"

    if os.path.exists(models_txt_path):
        try:
            with open(models_txt_path, "r", encoding="utf-8") as f:
                d = json.load(f)
            all_openrouter_raw.extend(d.get("data", []) if isinstance(d, dict) else d)
        except Exception:
            pass

    # ── Fetch server catalog ──────────────────────────────────────────────────
    from utim_cli.constants import SERVER_URL
    server_catalog: dict = {}
    try:
        import requests as _req
        cat_resp = _req.get(f"{SERVER_URL.rstrip('/')}/models/catalog", timeout=5)
        if cat_resp.status_code == 200:
            server_catalog = cat_resp.json() or {}
    except Exception:
        pass

    # Determine which catalog list to use for this target
    _target_to_catalog_key = {
        "main":                    "main_agent",
        "subagent_plan_project":   "plan_project",
        "subagent_analyze_image":  "analyze_image",
        "subagent_blender_vision": "analyze_image",
        "subagent_image_gen":      "image_gen",
        "subagent_generate_image": "main_agent",
    }

    catalog_key = _target_to_catalog_key.get(target, "main_agent")

    # Inject server catalog models into approved_set and live_descs
    if server_catalog:
        catalog_models = server_catalog.get(catalog_key, [])
        # For targets not in the map, use main_agent (all text_chat models)
        if not catalog_models:
            catalog_models = server_catalog.get("main_agent", [])

        for sm in catalog_models:
            mid = sm.get("model_id")
            if not mid or mid.startswith("~"):
                continue
            desc = sm.get("description") or sm.get("name") or mid
            caps = sm.get("capabilities", [])
            s_tags = sm.get("tags", [])
            live_descs[mid] = desc

            is_m_free = sm.get("is_free", False) or mid.endswith(":free")
            # Always add catalog models from server to approved_set (server already filtered by capability)
            if not is_paid_plan:
                if is_m_free:
                    approved_set.add(mid)
                    # Update model_descs with server description if not already set
                    if mid not in model_descs:
                        model_descs[mid] = (desc, list(s_tags))
            else:
                approved_set.add(mid)
                if mid not in model_descs:
                    model_descs[mid] = (desc, list(s_tags))

        # For free plan, also check all_text models for free ones
        if not is_paid_plan and target not in ("subagent_image_gen", "subagent_generate_image"):
            for sm in server_catalog.get("all_text", []):
                mid = sm.get("model_id")
                if not mid or mid.startswith("~"):
                    continue
                if sm.get("is_free", False) or mid.endswith(":free"):
                    approved_set.add(mid)
                    desc = sm.get("description") or sm.get("name") or mid
                    live_descs[mid] = desc
                    if mid not in model_descs:
                        model_descs[mid] = (desc, list(sm.get("tags", [])))
    else:
        # Fallback: use old /models list + local model_descs
        try:
            import requests as _req
            server_resp = _req.get(f"{SERVER_URL.rstrip('/')}/models", timeout=4)
            if server_resp.status_code == 200:
                s_data = server_resp.json()
                if isinstance(s_data, list) and s_data:
                    for sm in s_data:
                        mid = sm.get("model_id")
                        if not mid:
                            continue
                        caps = sm.get("capabilities", [])
                        s_tags = sm.get("tags", [])
                        has_vis = "vision" in caps or "vision" in s_tags
                        ctx_k = (sm.get("context_window", 128000) or 128000) // 1000
                        live_descs[mid] = sm.get("description") or f"[{'Vision' if has_vis else 'Text'}] Server model ({ctx_k}k ctx)"
                        if mid in model_descs or mid in recommended_set or mid == DEFAULT_MODEL:
                            is_m_free = (mid.endswith(":free") or ":free" in mid or sm.get("is_free", False))
                            if not is_paid_plan:
                                if is_m_free and target != "subagent_image_gen":
                                    approved_set.add(mid)
                            else:
                                approved_set.add(mid)
        except Exception:
            pass


    try:
        import requests
        resp = requests.get("https://openrouter.ai/api/v1/models", timeout=4)
        if resp.status_code == 200:
            all_openrouter_raw.extend(resp.json().get("data", []))
    except Exception:
        pass

    for rm in all_openrouter_raw:
        mid = rm.get("id")
        if not mid:
            continue
        if mid in model_descs:
            live_descs[mid] = rm.get("description", "")
        
        # Only add to approved_set if it is part of UTIM's curated model_descs or recommended list
        if mid in model_descs or mid in recommended_set:
            if not is_paid_plan:
                if (mid.endswith(":free") or ":free" in mid) and target != "subagent_image_gen":
                    approved_set.add(mid)
            else:
                approved_set.add(mid)

    def is_image_output_model(mid: str, tags: list) -> bool:
        mid_lower = mid.lower()
        if "image" in tags:
            return True
        image_kws = ["flux", "riverflow", "recraft", "krea", "-image", "imagine", "mai-image"]
        return any(kw in mid_lower for kw in image_kws)

    primary_models = []
    for mid in approved_set:
        desc_val, tags_val = model_descs.get(mid, (live_descs.get(mid, "Fast, efficient model."), []))
        # Tag any free model with 'free' tag dynamically
        if mid.endswith(":free") or ":free" in mid:
            if "free" not in tags_val:
                tags_val = list(tags_val) + ["free"]

        # Main agent and non-image subagents only accept models that output text!
        if target != "subagent_generate_image" and target != "subagent_image_gen":
            if is_image_output_model(mid, tags_val):
                continue
                
        primary_models.append({
            "model_id": mid,
            "desc": desc_val,
            "tags": tags_val,
            "source": "utim"
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
    current_source = None
    if target == 'main':
        current_model = orchestrator.model_id
        current_source = getattr(orchestrator, 'model_source', None) or config.get("main_model_source")
    elif target.startswith('subagent_'):
        subkey = target.split('_', 1)[1]
        current_model = config.get(f"subagent_model_{subkey}")
        current_source = config.get(f"subagent_model_{subkey}_source")

    def _normalize_source(source: str | None) -> str:
        return "utim" if source in (None, "", "openrouter") else source

    if current_model in ("__non_agent__", "__none__"):
        current_source = "sentinel"
    else:
        current_source = _normalize_source(current_source)

    if current_model:
        current_item = None
        for item in models:
            if item["model_id"] == current_model and _normalize_source(item.get("source")) == current_source:
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
        source = _normalize_source(m.get('source'))

        def _compact_desc(text: str, width: int) -> list[str]:
            text = re.sub(r"\s+", " ", str(text or "Fast, efficient model.")).strip()
            text = re.sub(r"\bThis model\b", "It", text, flags=re.IGNORECASE)
            parts = re.split(r"(?<=[.!?])\s+", text)
            compact = parts[0] if parts and parts[0] else text
            if len(compact) < 48 and len(parts) > 1:
                compact = f"{compact} {parts[1]}"
            max_chars = max(width, min(120, width * 2))
            if len(compact) > max_chars:
                compact = compact[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:")
                compact += "..."
            return textwrap.wrap(
                compact,
                width=width,
                max_lines=2,
                placeholder="...",
                break_long_words=False,
            ) or [""]

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
                desc_width = max(24, min(54, (console.size.width or 100) - 62))
                desc_lines = _compact_desc(m['desc'], desc_width)
                desc_text = f" {desc_lines[0]}{current_mark}\n"
                for extra in desc_lines[1:]:
                    desc_text += f"{'':<55}{extra}\n"
                desc_text += "\n"
                return [
                    (sentinel_style, f"  {label:<26}"),
                    (sentinel_style, f"{'':<12}"),
                    (sentinel_style, f"{'':<14}"),
                    (desc_style, desc_text),
                ]
            else:
                desc_width = max(24, min(72, (console.size.width or 100) - 10))
                desc_lines = _compact_desc(m['desc'], desc_width)
                desc_text = "".join(f"     {line}\n" for line in desc_lines) + "\n"
                return [
                    (sentinel_style, f"  {label}"),
                    (sentinel_style, f"{current_mark}\n"),
                    (desc_style, desc_text),
                ]

        # Clean display ID (remove provider prefix and ':free' suffix)
        display_id = mid
        if source == 'utim':
            display_id = mid.split('/', 1)[-1]
            if display_id.endswith(':free'):
                display_id = display_id[:-5]
                
        if mid in ("krea/krea-2", "krea-2"):
            display_id = "Krea 2 image"
        elif display_id == "gemini-3.1-pro-preview-customtools":
            display_id = "gemini-3.1-pro-preview"
        elif "qwen3-next-80b" in display_id.lower() or "qwen3-next-80b" in mid.lower():
            display_id = "Qwen3 Next 80B"
        else:
            display_id = display_id.replace('-', ' ')
            if display_id:
                display_id = display_id[0].upper() + display_id[1:]

        
        current = ''
        if target == 'main' and mid == orchestrator.model_id and source == current_source:
            current = '  ◀ current'
        elif target.startswith('subagent_') and mid == config.get(f"subagent_model_{target.split('_', 1)[1]}") and source == current_source:
            current = '  ◀ current'

        desc = m.get("desc", "Fast, efficient model for daily tasks.")

        # Determine explicit vision capability from models.txt / MODEL_REGISTRY
        from utim_cli.tools import is_model_vision_capable
        vis_tag = "[Vision: True]" if is_model_vision_capable(mid) else "[Vision: False]"
        full_desc = f"{vis_tag} {desc}"

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

            desc_width = max(24, min(54, (console.size.width or 100) - 62))
            desc_lines = _compact_desc(full_desc, desc_width)
            desc_text = f" {desc_lines[0]}{current}\n"
            for extra in desc_lines[1:]:
                desc_text += f"{'':<55}{extra}\n"
            desc_text += "\n"

            return [
                (style,      col_model),
                (cost_style, col_cost),
                (rec_style,  col_rec),
                (desc_style, desc_text),
            ]
        else:
            desc_width = max(24, min(72, (console.size.width or 100) - 10))
            desc_lines = _compact_desc(full_desc, desc_width)
            desc_text = "".join(f"     {line}\n" for line in desc_lines) + "\n"
            return [
                (style,      f"  {display_id}"),
                (style,      f"{current}\n"),
                (desc_style, desc_text),
            ]

    title_str = 'Select Model  [dim](List Mode: a=Add  b=BYOK  d=Delete  x=Disconnect | Direct: Ctrl+A/B/D/X)[/dim]'
    if is_paid_plan:
        title_str = 'Select Model  [dim](List Mode: a=Add  b=BYOK  d=Delete  x=Disconnect | Direct: Ctrl+A/B/D/X)[/dim]\n\n[bold white]  MODEL                      COST        TAGS          DESCRIPTION[/bold white]'

    action, idx = _run_search_list_dialog(
        models, render_model,
        title=title_str,
        legend='↑↓ Navigate  Enter Select  a Add  b BYOK  d Delete  x Disconnect  Ctrl+A/B/D/X Direct  q Cancel',
        extra_keys={'a': 'add_custom', 'b': 'byok_import', 'd': 'delete_custom', 'x': 'disconnect_provider'},
        search_title="Filter Models",
        list_title="Available Models"
    )

    if action == 'select':
        selected_model = models[idx]['model_id']
        source = _normalize_source(models[idx].get('source'))
        label = '[yellow](custom)[/yellow] ' if source == 'custom' else ''
        if target == 'main':
            orchestrator.model_id = selected_model
            orchestrator.model_source = source
            config.set("main_model", selected_model)
            config.set("main_model_source", source)
            console.print(f"\n[bold #f9e2af]✓ Main Agent model set to {label}{selected_model}[/bold #f9e2af]\n")
            
            # Initialize settings for the chosen model instantly
            init_model_settings(selected_model)
            
            # Prompt user for reasoning effort if model supports reasoning
            if model_supports_reasoning(selected_model):
                _prompt_reasoning_effort_dialog(selected_model)
                
            # Update compression threshold for new model
            try:
                orchestrator._update_model_threshold(orchestrator.model_id)
            except Exception:
                pass

        elif target.startswith('subagent_'):
            subkey = target.split('_', 1)[1]
            config.set(f"subagent_model_{subkey}", selected_model)
            config.set(f"subagent_model_{subkey}_source", source)
            console.print(f"\n[bold #f9e2af]✓ {subkey} subagent model set to {label}{selected_model}[/bold #f9e2af]\n")

            # Initialize settings for the chosen model
            init_model_settings(selected_model)

            # Prompt user for reasoning effort if model supports reasoning
            if model_supports_reasoning(selected_model):
                _prompt_reasoning_effort_dialog(selected_model)

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
    from rich.console import Console as RichConsole
    from utim_cli.utim import custom_theme
    

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

    try:
        choice = _safe_prompt("\n  Provider number [9]: ", color="#cba6f7").strip() or "9"
    except (EOFError, KeyboardInterrupt):
        byok_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if choice in PROVIDER_PRESETS:
        provider_name, base_url_preset = PROVIDER_PRESETS[choice]
    else:
        provider_name, base_url_preset = "Custom", ""

    byok_console.print(f"\n[bold]Provider:[/bold] [#cba6f7]{provider_name}[/#cba6f7]")

    # Base URL
    if not base_url_preset:
        url_placeholder = "https://..."
        try:
            base_url = _safe_prompt(f"  Base URL [{url_placeholder}]: ", color="#cba6f7").strip()
        except (EOFError, KeyboardInterrupt):
            byok_console.print("\n[dim]Cancelled.[/dim]\n")
            return

        if not base_url:
            byok_console.print("\n[red]Base URL is required.[/red]\n")
            return

        # Display name override
        try:
            pname_input = _safe_prompt(f"  Provider display name [{provider_name}]: ", color="#cba6f7").strip()
            if pname_input:
                provider_name = pname_input
        except (EOFError, KeyboardInterrupt):
            byok_console.print("\n[dim]Cancelled.[/dim]\n")
            return
    else:
        base_url = base_url_preset

    # API key (hidden input)
    byok_console.print(
        f"\n  [dim]API key for [bold]{provider_name}[/bold] "
        "(stored securely in config.json — input hidden):[/dim]"
    )
    try:
        api_key = _safe_prompt("  API Key (Enter to skip): ", color="#cba6f7", is_password=True).strip()
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
        err_msg = str(e)
        if isinstance(e, requests.exceptions.HTTPError):
            code = e.response.status_code if e.response is not None else "?"
            if code == 401 or str(code) == "401":
                err_msg = "HTTP 401 Unauthorized: The API key you entered was rejected by the provider. Please verify that your API key is correct and active."
            elif code == 403 or str(code) == "403":
                err_msg = "HTTP 403 Forbidden: Access denied by the provider. Please check your account permissions/billing."
        byok_console.print(f"\n[red]❌ Failed to fetch models: {err_msg}[/red]\n")
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
    from utim_cli.utim import console, _transient_status, custom_theme
    """Interactive wizard to add a model from any OpenAI-compatible provider."""
    import sys
    import time
    from rich.console import Console as RichConsole
    

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

    try:
        choice = _safe_prompt("\n  Provider number [8]: ", color="#42bcf5").strip() or "8"
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if choice in PROVIDER_PRESETS:
        provider_name, base_url_preset = PROVIDER_PRESETS[choice]
    else:
        provider_name, base_url_preset = "Custom", ""

    add_console.print(f"\n[bold]Provider:[/bold] [#42bcf5]{provider_name}[/#42bcf5]")

    # Base URL
    if not base_url_preset:
        url_placeholder = "https://..."
        try:
            base_url = _safe_prompt(f"  Base URL [{url_placeholder}]: ", color="#42bcf5").strip()
        except (EOFError, KeyboardInterrupt):
            add_console.print("\n[dim]Cancelled.[/dim]\n")
            return

        if not base_url:
            add_console.print("\n[red]Base URL is required.[/red]\n")
            return

        # Provider name (allow override)
        try:
            pname_input = _safe_prompt(f"  Provider display name [{provider_name}]: ", color="#42bcf5").strip()
            if pname_input:
                provider_name = pname_input
        except (EOFError, KeyboardInterrupt):
            add_console.print("\n[dim]Cancelled.[/dim]\n")
            return
    else:
        base_url = base_url_preset

    # API key (hidden input)
    add_console.print(
        f"\n  [dim]API key for [bold]{provider_name}[/bold] "
        "(stored in config.json — input hidden):[/dim]"
    )
    try:
        api_key = _safe_prompt("  API Key (Enter to skip): ", color="#42bcf5", is_password=True).strip()
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    # Model ID
    add_console.print(
        "\n  [dim]Model identifier sent in the API request "
        "(e.g. gpt-4o, llama-3.3-70b-versatile, mistral-large-latest)[/dim]"
    )
    try:
        model_id = _safe_prompt("  Model ID: ", color="#42bcf5").strip()
    except (EOFError, KeyboardInterrupt):
        add_console.print("\n[dim]Cancelled.[/dim]\n")
        return

    if not model_id:
        add_console.print("\n[red]Model ID is required.[/red]\n")
        return

    # Context window
    try:
        ctx_raw = _safe_prompt("  Context window tokens [128000]: ", color="#42bcf5").strip()
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
        switch = _safe_prompt("  Switch to this model now? [Y/n]: ", color="#42bcf5").strip().lower()
    except (EOFError, KeyboardInterrupt):
        switch = "n"

    if switch in ("", "y", "yes"):
        orchestrator.model_id = model_id
        orchestrator.model_source = "custom"
        config.set("main_model", model_id)
        config.set("main_model_source", "custom")
        try:
            orchestrator._update_model_threshold(model_id)
        except Exception:
            pass
        add_console.print(f"\n[bold #a6e3a1]✓ Now using {model_id}[/bold #a6e3a1]\n")
    else:
        add_console.print("\n[dim]Model saved. Use /model to select it anytime.[/dim]\n")


def _dialog_delete_custom_model(orchestrator, model_id: str):
    from utim_cli.utim import console, _transient_status, custom_theme
    """Confirm and delete a custom model by model_id."""
    import sys
    import time
    from rich.console import Console as RichConsole
    

    del_console = RichConsole(file=sys.__stdout__, highlight=False, theme=custom_theme)
    time.sleep(0.05)

    del_console.print(f"\n[yellow]Delete custom model [bold]{model_id}[/bold]?[/yellow]")
    try:
        confirm = _safe_prompt("  Type 'yes' to confirm: ", color="#f38ba8").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""

    if confirm == "yes":
        removed = config.remove_custom_model(model_id)
        if removed:
            del_console.print(f"\n[bold #a6e3a1]✓ Removed {model_id}[/bold #a6e3a1]\n")
            # If the deleted model was active, reset to default
            if orchestrator.model_id == model_id and (getattr(orchestrator, "model_source", None) or config.get("main_model_source")) == "custom":
                from utim_cli.constants import DEFAULT_MODEL
                orchestrator.model_id = DEFAULT_MODEL
                orchestrator.model_source = "utim"
                config.set("main_model", DEFAULT_MODEL)
                config.set("main_model_source", "utim")
                del_console.print(f"[dim]Switched back to {DEFAULT_MODEL}[/dim]\n")
        else:
            del_console.print("[yellow]Model not found in custom list.[/yellow]\n")
    else:
        del_console.print("\n[dim]Cancelled.[/dim]\n")





def _dialog_disconnect_provider(orchestrator):
    from utim_cli.utim import console, _transient_status, _run_list_dialog, custom_theme, DEFAULT_MODEL
    """Confirm and delete all custom models associated with a provider (disconnect provider)."""
    import sys
    import time
    from rich.console import Console as RichConsole
    

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

    try:
        choice = _safe_prompt("\n  Disconnect provider number: ", color="#f38ba8").strip()
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
        confirm = _safe_prompt("  Type 'yes' to confirm: ", color="#f38ba8").strip().lower()
    except (EOFError, KeyboardInterrupt):
        confirm = ""

    if confirm == "yes":
        removed_count = config.remove_custom_provider(selected["name"], selected["url"])
        disc_console.print(
            f"\n[bold #a6e3a1]✓ Disconnected {selected['name']} and removed {removed_count} models![/bold #a6e3a1]\n"
        )
        # If active model was deleted, reset to DEFAULT_MODEL
        active_model = orchestrator.model_id
        active_source = getattr(orchestrator, "model_source", None) or config.get("main_model_source")
        active_still_exists = any(m["model_id"] == active_model for m in config.custom_models)
        if active_source == "custom" and not active_still_exists and active_model not in [DEFAULT_MODEL, "anthropic/claude-sonnet-4.6"]:
            is_custom_removed = True
            # Hardcoded check since we cannot import utim_cli.server in production CLI builds
            # (as the server module is excluded from the package in pyproject.toml)
            if active_model.startswith("openai/") or active_model.startswith("anthropic/") or active_model.startswith("google/") or active_model.startswith("cohere/"):
                is_custom_removed = False
            
            if is_custom_removed:
                orchestrator.model_id = DEFAULT_MODEL
                orchestrator.model_source = "utim"
                config.set("main_model", DEFAULT_MODEL)
                config.set("main_model_source", "utim")
                disc_console.print(f"[dim]Active model removed. Switched back to cohere/north-mini-code:free[/dim]\n")
    else:
        disc_console.print("\n[dim]Cancelled.[/dim]\n")


