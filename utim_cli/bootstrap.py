"""
UTIM Bootstrap Module
Auto-creates the .utim folder structure, custom skills, and local database on first run.
"""

import os
from pathlib import Path
from utim_cli.config import get_utim_dir

UTIM_DIR = get_utim_dir()


def initialize_utim() -> str:
    """Initialize .utim directory, local SQLite database, and auto-create custom skills/rules if they don't exist."""
    try:
        from utim_cli.backup import restore_state
        restore_state()
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", "Failed to restore state during initialization", e)
        
    UTIM_DIR.mkdir(exist_ok=True)
    
    # 1. Initialize local_utim database using SQLAlchemy init_db
    try:
        from utim_cli.local_db import init_local_db
        init_local_db(silent=True)
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", "Failed to initialize SQLite local database", e)
        
    # 2. Write analytical_rules.md if not exists
    _write_analytical_rules_md()
    
    # 3. Write UTIM.md if not exists
    _write_utim_md()
    
    # 4. Auto-create skills directory and default skills/rules
    _write_skills_and_agents()
    
    # 5. Sync global/local experience database across project folders
    try:
        from utim_cli.config import config
        api_key = config.get("api_key")
        if api_key:
            _sync_global_experience(api_key, os.getcwd())
    except Exception:
        pass
    
    db_path = UTIM_DIR / 'utim_local.db'
    return str(db_path)


def _sync_global_experience(api_key: str, current_folder: str):
    """
    Track which project folder the user is currently in (server-side record only).
    Since .utim is now global (~/.utim), there is no need to copy experience files
    between project folders — they are always available from the shared location.
    """
    import requests
    from utim_cli.auth import SERVER_URL

    try:
        requests.post(
            f"{SERVER_URL}/auth/last-folder",
            headers={"X-API-Key": api_key},
            json={"folder_path": current_folder},
            timeout=5
        )
    except Exception:
        pass

def _write_skills_and_agents():
    """Create the empty skills/ directory inside ~/.utim/. Skills are built by the reflection engine."""
    try:
        skills_dir = UTIM_DIR / 'skills'
        skills_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", "Failed to create skills directory in ~/.utim/", e)

def _write_default_design_md(md_path: Path):
    content = """# Premium Web Design System (Aesthetics Cheat-Sheet)
Use this guide to build modern, beautiful, and "award-winning" web interfaces. Apply these principles, variables, and recipes to wow the user.

---

## 1. Typography
*   **Body & UI**: 'Outfit', sans-serif (clean, rounded, premium feel).
*   **Headings**: 'Bricolage Grotesque', sans-serif (vibrant, high-agency design).

## 2. Color Palette (Clean Dark/Light HSL)
- Primary HSL colors, gradients, and custom themes to prevent generic looks.
"""
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception:
        pass

def _write_analytical_rules_md():
    """Write the analytical_rules.md file to .utim folder if not exists."""
    md_path = UTIM_DIR / 'analytical_rules.md'
    if md_path.exists():
        return
        
    content = """# Enhanced Analytical Framework for UTIM AI

## Core Principle: GOAL-FIRST ANALYSIS
Always start by identifying the TRUE objective, then work backwards to feasible actions.
"""
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", f"Failed to write analytical rules markdown to {md_path}", e)

def _write_utim_md():
    """Create an empty UTIM.md in ~/.utim/ if it doesn't exist. Populated by the reflection engine."""
    md_path = UTIM_DIR / 'UTIM.md'
    if md_path.exists():
        return
    try:
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write('')
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", f"Failed to create UTIM.md at {md_path}", e)

def scan_available_skills():
    """
    Scans ~/.utim/skills, .utim/skills, and .agents/skills for directories containing SKILL.md.
    Skills listed in config['disabled_skills'] are excluded.
    Returns:
        dict: A dictionary mapping skill_name to dict containing path, name, description, and keywords.
    """
    import os
    from pathlib import Path
    import yaml
    from utim_cli.config import config as _cfg

    disabled: list = _cfg.get("disabled_skills") or []
    if not isinstance(disabled, list):
        disabled = []

    skills = {}
    paths_to_check = [
        UTIM_DIR / 'skills',
        UTIM_DIR / 'agentskills',
        Path.home() / '.utim' / 'skills',
        Path.home() / '.utim' / 'agentskills',
        Path('.utim/skills'),
        Path('.utim/agentskills'),
        Path('.agents/skills'),
    ]
    
    for base_dir in paths_to_check:
        if not base_dir.exists():
            continue
        for name in os.listdir(base_dir):
            skill_dir = base_dir / name
            if skill_dir.is_dir():
                skill_md = skill_dir / 'SKILL.md'
                if skill_md.exists():
                    # Avoid duplicates
                    if name in skills:
                        continue
                    # Skip disabled skills
                    if name in disabled:
                        continue
                        
                    description = ""
                    frontmatter_name = name
                    content = ""
                    try:
                        with open(skill_md, 'r', encoding='utf-8') as f:
                            content = f.read()
                        if content.startswith('---'):
                            parts = content.split('---', 2)
                            if len(parts) >= 3:
                                ydata = yaml.safe_load(parts[1])
                                if ydata:
                                    description = ydata.get('description', '')
                                    frontmatter_name = ydata.get('name', name)
                    except Exception:
                        pass
                        
                    # Generate keywords from description and name
                    words = set()
                    # 1. Words from name
                    for word in name.replace('-', ' ').replace('_', ' ').split():
                        if len(word) > 2:
                            words.add(word.lower())
                    # 2. Words from description
                    stop_words = {
                        "and", "the", "a", "of", "to", "for", "in", "on", "with", "is", "this", "when", "focus",
                        "that", "are", "from", "these", "those", "by", "an", "at", "or", "as", "be", "your", "our",
                        "their", "guidelines", "design", "patterns", "focusing", "within", "system",
                        "terminal", "cli", "agent", "development", "workspace", "programming", "python", "code",
                        "codebase", "files", "tools", "user", "developer", "task", "project", "run", "running",
                        "implement", "implementing", "highly", "polished", "covers", "options", "status", "updates",
                        "prevention", "activate", "refining", "flows", "input/output"
                    }
                    for word in description.replace(',', ' ').replace('.', ' ').replace('(', ' ').replace(')', ' ').split():
                        w = word.lower().strip()
                        if len(w) > 2 and w not in stop_words:
                            words.add(w)
                            
                    skills[name] = {
                        "path": skill_md,
                        "name": frontmatter_name,
                        "description": description,
                        "keywords": list(words),
                        "content": content
                    }
    return skills

def get_rag_context(user_prompt: str = "") -> str:
    """Get RAG context string for system prompt injection by matching user_prompt keywords to skills."""
    try:
        from utim_cli.state import STATE
        STATE["injected_contexts"] = []
        
        skills = scan_available_skills()
        matched_skills = []
        user_prompt_lower = user_prompt.lower()
        
        for skill_name, skill_info in skills.items():
            matched = False
            if any(kw in user_prompt_lower for kw in skill_info["keywords"]):
                matched = True
            if not matched:
                if skill_name.replace("-", " ") in user_prompt_lower or skill_name in user_prompt_lower:
                    matched = True
            if matched:
                matched_skills.append(skill_name)
                
        # If no keywords matched, default to AGENTS.md
        if not matched_skills:
            agents_path = UTIM_DIR / 'AGENTS.md'
            if not agents_path.exists():
                from pathlib import Path
                agents_path = Path('.agents/AGENTS.md')
            if agents_path.exists():
                with open(agents_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                STATE["injected_contexts"].append(content)
                return f"\n### PROJECT RULES & GUIDELINES ###\n{content}\n"
            return ""
            
        context = ""
        for skill_name in matched_skills[:2]: # Load top 2 matched skills
            skill_info = skills[skill_name]
            content = skill_info["content"]
            if content.startswith('---'):
                parts = content.split('---', 2)
                if len(parts) >= 3:
                    content = parts[2].strip()
            STATE["injected_contexts"].append(content)
            context += f"\n### RELEVANT CORE SKILL: {skill_name.upper()} ###\n{content[:1500]}\n"
            
        return context
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", "Failed to get RAG context from skills", e)
        return ""

def get_subagent_rag_context(subagent_name: str, query: str = "") -> str:
    """Get RAG context string for the specified sub-agent prompt injection by reading from markdown skill files directly."""
    try:
        # Map subagent name to the most relevant skill file
        mapping = {
            "plan_project": "llm-orchestration",
            "web_search": "cli-ux-patterns",
            "generate_image": "web-design-premium"
        }
        skill_name = mapping.get(subagent_name)
        if not skill_name:
            return ""
        
        skills = scan_available_skills()
        if skill_name in skills:
            skill_path = skills[skill_name]["path"]
        else:
            skill_path = UTIM_DIR / 'skills' / skill_name / 'SKILL.md'
            if not skill_path.exists():
                skill_path = UTIM_DIR / 'agentskills' / skill_name / 'SKILL.md'
            if not skill_path.exists():
                skill_path = Path('.agents/skills') / skill_name / 'SKILL.md'
        if not skill_path.exists():
            return ""
            
        with open(skill_path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Strip YAML frontmatter if present
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                content = parts[2].strip()
                
        # Return a formatted summary context
        context = f"\n\n### SUB-AGENT {subagent_name.upper()} SKILLS & FRAMEWORK (from {skill_name}) ###\n"
        if len(content) > 1500:
            context += content[:1500] + "\n... [Truncated for Context Limit]"
        else:
            context += content
        return context
    except Exception as e:
        from utim_cli.logger import log_error
        log_error("bootstrap", f"Failed to load subagent markdown context for {subagent_name}", e)
        return ""

def get_time_rag_context(user_prompt: str) -> str:
    """Gets relevant past task execution time experiences (mock/empty as databases are simplified)."""
    return ""

if __name__ == '__main__':
    print(f"Initializing UTIM... Database: {initialize_utim()}")