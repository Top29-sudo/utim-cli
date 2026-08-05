import os

DEFAULT_MODEL = "cohere/north-mini-code:free"
SERVER_URL = os.getenv("UTIM_SERVER_URL", "https://api.utim.dev")
OPENROUTER_BASE_URL = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")

SUBAGENT_DEFAULTS = {
    "web_search": DEFAULT_MODEL,
    "plan_project": DEFAULT_MODEL,
    "generate_image": "nvidia/nemotron-3-nano-30b-a3b:free",
}

import sys
_IS_LEGACY_WIN = (sys.platform == "win32" and "WT_SESSION" not in os.environ)
PROMPT_SYMBOL = ">" if _IS_LEGACY_WIN else "❯"
ARROW_SYMBOL = "->" if _IS_LEGACY_WIN else "➔"

