import os
import re
import time
import traceback
from typing import Any

from utim_cli.config import get_utim_dir

# Global logging path
LOG_FILE = os.path.join(get_utim_dir(), "utim_debug.log")

# Sensitive word list for log redaction
SENSITIVE_KEYWORDS = {
    "girlfriend", "gf", "wife", "spouse", "partner", "relationship",
    "secret", "password", "code", "private", "personal", "anushka", "puchkuli"
}

# Compile regex to match sensitive words case-insensitively
_REDACT_RE = re.compile(
    r"\b(" + "|".join(re.escape(w) for w in SENSITIVE_KEYWORDS) + r")\b",
    re.IGNORECASE
)

# API key patterns (OpenAI, Anthropic, OpenRouter, etc.)
_API_KEY_RE = re.compile(
    r"\b(?:sk-|sk-or-v1-|xai-|ai-)[a-zA-Z0-9\-]{20,}\b",
    re.IGNORECASE
)

# Bearer token patterns
_BEARER_TOKEN_RE = re.compile(
    r"\bbearer\s+[a-zA-Z0-9\-._~+/]+=*\b",
    re.IGNORECASE
)

# Email address patterns
_EMAIL_RE = re.compile(
    r"\b[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+\b",
    re.IGNORECASE
)

def redact_text(text: str) -> str:
    """Redact sensitive keywords, API keys, tokens, emails, working directories, and usernames."""
    if not text:
        return text
    
    # 1. Redact API keys and bearer tokens
    text = _API_KEY_RE.sub("[REDACTED_API_KEY]", text)
    text = _BEARER_TOKEN_RE.sub("[REDACTED_TOKEN]", text)
    
    # 2. Redact emails
    text = _EMAIL_RE.sub("[REDACTED_EMAIL]", text)
    
    # 3. Redact current working directory
    try:
        cwd = os.getcwd()
        if cwd and len(cwd) > 3:
            text = text.replace(cwd, "[WORKSPACE_DIR]")
            # Also redact with forward slashes if paths are converted
            cwd_f = cwd.replace('\\', '/')
            text = text.replace(cwd_f, "[WORKSPACE_DIR]")
    except Exception:
        pass
        
    # 4. Redact system username dynamically
    try:
        import getpass
        user = getpass.getuser()
        if user and len(user) > 2:
            user_re = re.compile(re.escape(user), re.IGNORECASE)
            text = user_re.sub("[USER]", text)
    except Exception:
        pass
        
    # 5. Redact general sensitive keywords
    text = _REDACT_RE.sub("[REDACTED]", text)
    
    # 6. Redact sensitive values from environment variables
    for k, v in os.environ.items():
        if any(sec in k.upper() for sec in ["KEY", "SECRET", "PASSWORD", "TOKEN", "AUTH"]):
            if v and len(v) > 4:
                text = text.replace(v, f"[REDACTED_{k}]")
                
    return text

def log_event(level: str, module: str, message: str, error: Exception = None):
    """Log structured events to .utim/utim_debug.log.
    
    Levels: INFO, WARNING, ERROR, DEBUG
    """
    try:
        os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%S")
        
        # Redact secrets
        safe_msg = redact_text(message)
        
        log_line = f"[{timestamp}] [{level}] [{module}] {safe_msg}"
        if error:
            tb = redact_text(traceback.format_exc())
            log_line += f"\nTraceback:\n{tb}"
            
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(log_line + "\n")
            
        # If debug mode is active in the environment, we print it to console/debug stream
        from utim_cli.config import config
        if config.debug_mode:
            print(f"[DEBUG-LOG] {log_line}")
    except Exception:
        pass # Logging failures should never crash the main application

def log_info(module: str, message: str):
    log_event("INFO", module, message)

def log_warning(module: str, message: str, error: Exception = None):
    log_event("WARNING", module, message, error)

def log_error(module: str, message: str, error: Exception = None):
    log_event("ERROR", module, message, error)

def log_debug(module: str, message: str):
    log_event("DEBUG", module, message)
