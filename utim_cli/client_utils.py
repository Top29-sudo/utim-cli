import os
import json
import math
import requests
from utim_cli.config import config

class WrappedResponse:
    """A compatibility wrapper that mimics requests.Response for client callers."""
    def __init__(self, content_str=None, generator=None, status_code=200):
        self.content_str = content_str
        self.generator = generator
        self.status_code = status_code
        self.encoding = "utf-8"

    def raise_for_status(self):
        if self.status_code != 200:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self.content_str:
            return json.loads(self.content_str)
        raise ValueError("No JSON content available")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass

    def iter_lines(self, decode_unicode=False):
        if self.generator:
            return self.generator
        if self.content_str:
            return [self.content_str]
        return []

def get_server_url() -> str:
    return "https://api.utim.dev"


def _sanitize_json(obj):
    """Recursively scrub a payload for values that break strict JSON parsers.

    Python's json.dumps emits NaN/Infinity as literal `NaN` / `Infinity`,
    which is NOT valid JSON — strict providers (e.g. Parasail) reject the
    whole request with 'Expecting value' at the exact offending character.
    This replaces non-finite floats with None (safe in API payloads) and
    drops anything that cannot round-trip through JSON.
    """
    if isinstance(obj, dict):
        return {k: _sanitize_json(v) for k, v in obj.items()
                if isinstance(k, (str, int, float, bool)) or k is None}
    if isinstance(obj, (list, tuple)):
        return [_sanitize_json(v) for v in obj]
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else None
    if isinstance(obj, (str, int, bool)) or obj is None:
        return obj
    # Anything else (bytes, objects, sets…) can't survive JSON serialisation.
    try:
        json.dumps(obj)
        return obj
    except (TypeError, ValueError):
        return None


# ─── Model catalog cache ──────────────────────────────────────────────────────
_catalog_cache: dict | None = None
_catalog_cache_ts: float = 0.0
_CATALOG_TTL = 3600.0  # 1 hour cache


def get_server_model_catalog(timeout: float = 5.0) -> dict | None:
    """Fetch the model catalog from the UTIM server /models/catalog endpoint.

    Returns a dict keyed by tool target:
        "main_agent", "plan_project", "analyze_image", "image_gen", "all_text"
    Each value is a list of model dicts with fields:
        model_id, name, provider, description, context_window, max_output_tokens,
        cost_input_per_1k, cost_output_per_1k, capabilities, tags,
        is_free, is_vision, is_image_gen, is_reasoning

    Returns None on network failure (caller should fall back to local data).
    Responses are cached for 1 hour to avoid repeated requests.
    """
    global _catalog_cache, _catalog_cache_ts
    import time

    now = time.monotonic()
    if _catalog_cache is not None and (now - _catalog_cache_ts) < _CATALOG_TTL:
        return _catalog_cache

    server_url = get_server_url()
    try:
        resp = requests.get(
            f"{server_url.rstrip('/')}/models/catalog",
            timeout=timeout,
        )
        if resp.status_code == 200:
            data = resp.json()
            if isinstance(data, dict) and data:
                _catalog_cache = data
                _catalog_cache_ts = now
                return _catalog_cache
    except Exception:
        pass
    return None


def proxy_openrouter_request(json_data: dict, stream: bool = False, timeout=None, is_reflection: bool = False) -> WrappedResponse:
    """Routes LLM request to UTIM server /completions, or falls back to direct OpenRouter."""
    if timeout is None:
        timeout = (15, 900)
    # Scrub payload for NaN/Infinity/non-JSON types BEFORE it leaves the
    # machine. Providers like Parasail do a strict parse and reject the whole
    # request (400 'Expecting value') if even one value is malformed.
    json_data = _sanitize_json(json_data)
    # Ensure environment variables are loaded (orchestrator handles this, but tools.py is independent)
    _cwd_env = os.path.join(os.getcwd(), ".env")
    if os.path.isfile(_cwd_env):
        try:
            from dotenv import load_dotenv
            load_dotenv(_cwd_env, override=True)
        except Exception:
            pass

    api_key = config.get("api_key")
    server_url = get_server_url()
    llm_key = os.getenv("OPENROUTER_API_KEY")

    if llm_key:
        # Direct path to OpenRouter — must always carry canonical attribution
        # headers so OpenRouter shows "UTIM CLI Agent" (NOT "unknown") in its
        # analytics. The user-agent and install-id are added by the global
        # session patcher in config.py.
        headers = {
            "Authorization": f"Bearer {llm_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://utim.dev",
            "X-Title": "UTIM CLI Agent",
            "User-Agent": "UTIM-CLI/2.0 (+https://utim.dev)",
        }
        return requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            json=json_data,
            headers=headers,
            stream=stream or json_data.get("stream"),
            timeout=timeout,
            verify=config.verify_ssl,
        )

    if api_key:
        # Path via UTIM server. We attach CLI identity headers (version,
        # install-id) so the server can correlate calls and (when enforcement
        # is on) verify the request signature. The session-level UA patch in
        # config.py adds the User-Agent too.
        try:
            from utim_cli._version import VERSION as _CLI_VERSION
        except Exception:
            _CLI_VERSION = "unknown"

        try:
            from utim_cli.config import get_install_id
            _INSTALL_ID = get_install_id()
        except Exception:
            _INSTALL_ID = ""

        headers = {
            "X-API-Key": api_key,
            "Content-Type": "application/json",
            "X-UTIM-CLI-Version": _CLI_VERSION,
            "X-UTIM-Install-ID": _INSTALL_ID,
            "User-Agent": f"UTIM-CLI/{_CLI_VERSION} (+https://utim.dev)",
        }

        # Optional: attach CLI signature if the server is enforcing
        # signatures. The signing flow (challenge → sign) is implemented in
        # config.py's global session patcher so it works for every request,
        # not just this one. If unavailable, we still send the headers above
        # so the server can at least identify the caller.
        try:
            from utim_cli.config import sign_request_for_server
            signed = sign_request_for_server(method="POST", path="/completions", body=json_data)
            if signed:
                headers.update(signed)
        except Exception:
            pass

        payload = {
            "messages": json_data.get("messages"),
            "model_id": json_data.get("model"),
            "tools": json_data.get("tools"),
            "is_reflection": is_reflection or json_data.get("is_reflection", False)
        }
        if "temperature" in json_data:
            payload["temperature"] = json_data["temperature"]
        if "max_tokens" in json_data:
            payload["max_tokens"] = json_data["max_tokens"]
        if "reasoning" in json_data:
            payload["reasoning"] = json_data["reasoning"]
        
        # UTIM server completions is a streaming endpoint
        resp = requests.post(f"{server_url}/completions", json=payload, headers=headers, stream=True, timeout=timeout, verify=config.verify_ssl)
        resp.raise_for_status()

        if stream or json_data.get("stream"):
            def line_generator():
                for line in resp.iter_lines(decode_unicode=True):
                    if line:
                        try:
                            data = json.loads(line)
                            if data.get("type") == "content_delta" and data.get("text"):
                                chunk = {
                                    "choices": [{
                                        "delta": {"content": data["text"]}
                                    }]
                                }
                                yield "data: " + json.dumps(chunk)
                            elif data.get("type") == "done":
                                if data.get("error"):
                                    yield "data: " + json.dumps({"error": {"message": data["error"]}})
                                    break
                                usage = data.get("usage")
                                if usage:
                                    in_tokens = usage.get("input_tokens", 0)
                                    out_tokens = usage.get("output_tokens", 0)
                                    model_id = json_data.get("model") or "cohere/north-mini-code:free"
                                    from utim_cli.server.models import estimate_cost
                                    cost = estimate_cost(model_id, in_tokens, out_tokens)
                                    update_session_usage("tools", in_tokens, out_tokens, cost)
                                tcs = data.get("tool_calls")
                                if tcs:
                                    chunk = {
                                        "choices": [{
                                            "delta": {"tool_calls": tcs}
                                        }]
                                    }
                                    yield "data: " + json.dumps(chunk)
                                break
                        except Exception:
                            pass
                yield "data: [DONE]"
            return WrappedResponse(generator=line_generator())
        else:
            # Consume stream to construct final non-streaming response dict
            content = ""
            tool_calls = None
            in_tokens = 0
            out_tokens = 0
            server_error = None
            for line in resp.iter_lines(decode_unicode=True):
                if line:
                    try:
                        data = json.loads(line)
                        if data.get("type") == "content_delta" and data.get("text"):
                            content += data["text"]
                        elif data.get("type") == "done":
                            if data.get("error"):
                                server_error = data["error"]
                                break
                            content = data.get("content") or content
                            tool_calls = data.get("tool_calls")
                            usage = data.get("usage")
                            if usage:
                                in_tokens = usage.get("input_tokens", 0)
                                out_tokens = usage.get("output_tokens", 0)
                    except Exception:
                        pass
            if server_error:
                raise RuntimeError(server_error)
            if in_tokens > 0 or out_tokens > 0:
                model_id = json_data.get("model") or "cohere/north-mini-code:free"
                from utim_cli.server.models import estimate_cost
                cost = estimate_cost(model_id, in_tokens, out_tokens)
                update_session_usage("tools", in_tokens, out_tokens, cost)
            res_dict = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": content,
                        "tool_calls": tool_calls
                    }
                }]
            }
            return WrappedResponse(content_str=json.dumps(res_dict))
    else:
        llm_key = os.getenv("OPENROUTER_API_KEY")
        if not llm_key:
            raise RuntimeError("Neither UTIM API key nor local OPENROUTER_API_KEY is configured.")
        
        headers = {
            "Authorization": f"Bearer {llm_key}",
            "Content-Type": "application/json"
        }
        return requests.post("https://openrouter.ai/api/v1/chat/completions", json=json_data, headers=headers, stream=stream or json_data.get("stream"), timeout=timeout, verify=config.verify_ssl)


def parse_xml_tool_calls(content: str) -> tuple[str | None, list[dict]]:
    """
    Parses XML-style tool calls like:
    <tool_call>
    tool_name
    <arg_key>key</arg_key>
    <arg_value>value</arg_value>
    </tool_call>
    
    Returns (cleaned_content, list_of_parsed_tool_calls)
    """
    if not content:
        return content, []
        
    import re
    import uuid
    tool_calls = []
    # Match BOTH <tool_call> and the pipe-delimited <|tool_call|> variant.
    # Some models emit <|tool_call|> (Claude/Ollama style); the old regex only
    # matched <tool_call>, so those calls leaked raw into chat as text.
    tool_call_pattern = re.compile(r'<\|?tool_call\|?>([\s\S]*?)<\|?/tool_call\|?>')
    
    matches = list(tool_call_pattern.finditer(content))
    if not matches:
        return content, []
        
    parts = []
    last_idx = 0
    for match in matches:
        parts.append(content[last_idx:match.start()])
        last_idx = match.end()
        
        block = match.group(1).strip()
        lines = block.split('\n')
        if not lines:
            continue
        tool_name = lines[0].strip()
        
        # Handle hint messages - if the tool_name starts with /hint, treat it as a hint command
        if tool_name.startswith('/hint'):
            # For hint commands, extract the actual hint and handle it
            hint_message = tool_name[5:]  # Remove the leading '/hint '
            # Add hint to messages state so orchestrator can process it
            from utim_cli.state import STATE
            if "hint_messages" not in STATE:
                STATE["hint_messages"] = []
            STATE["hint_messages"].append(hint_message)
            # Don't add a tool call, just treat as empty content
            parts.append("")
            continue
        # For command tools that start with /hint, treat them as hint messages
        elif tool_name.startswith('/hint '):
            # This handles the case where /hint is passed as a tool name with the actual hint
            hint_message = tool_name[5:]  # Remove the leading '/hint '
            # Add hint to messages state so orchestrator can process it
            from utim_cli.state import STATE
            if "hint_messages" not in STATE:
                STATE["hint_messages"] = []
            STATE["hint_messages"].append(hint_message)
            # Don't add a tool call, just treat as empty content
            parts.append("")
            continue
        
        # Also handle direct user messages with /hint prefix
        if content and content.startswith('/hint'):
            # This handles the case where the user message itself starts with /hint
            # This should not happen in normal operation but handles edge cases
            hint_message = content[5:]  # Remove the leading '/hint '
            from utim_cli.state import STATE
            if "hint_messages" not in STATE:
                STATE["hint_messages"] = []
            STATE["hint_messages"].append(hint_message)
            # Don't add a tool call, just treat as empty content
            parts.append("")
            continue
            
        # Map common alias tool names to actual UTIM CLI tool names
        _TOOL_NAME_ALIASES = {
            "shell": "run_command",
            "bash": "run_command",
            "cmd": "run_command",
            "execute_command": "run_command",
            "view_file": "read_file",
            "search": "grep_search",
            "search_codebase": "grep_search",
        }
        if tool_name in _TOOL_NAME_ALIASES:
            tool_name = _TOOL_NAME_ALIASES[tool_name]
            
        args = {}
        # Pattern 1: <arg_key>key</arg_key>\s*<arg_value>value</arg_value>
        arg_pattern = re.compile(r'<arg_key>([^<]+)</arg_key>\s*<arg_value>([\s\S]*?)</arg_value>')
        for arg_match in arg_pattern.finditer(block):
            args[arg_match.group(1).strip()] = arg_match.group(2).strip()
            
        # Pattern 2: <parameter=name>value</parameter>
        param_pattern = re.compile(r'<parameter=([^>]+)>([\s\S]*?)</parameter>')
        for param_match in param_pattern.finditer(block):
            args[param_match.group(1).strip()] = param_match.group(2).strip()
            
        # Standardize argument name for run_command
        if tool_name == "run_command":
            for wrong_key in ["CommandLine", "commandLine", "command_line", "cmd_line", "cmd", "shell", "script"]:
                if wrong_key in args and "command" not in args:
                    args["command"] = args.pop(wrong_key)
            for path_key in ["cwd", "directory", "folder", "path"]:
                if path_key in args and "dir_path" not in args:
                    args["dir_path"] = args.pop(path_key)
            for bg_key in ["background", "is_background", "bg"]:
                if bg_key in args:
                    val = args.pop(bg_key)
                    args["is_background"] = str(val).lower() in ("true", "1", "yes") if isinstance(val, (str, bool, int)) else bool(val)
            for wait_key in ["wait", "wait_seconds", "wait_time"]:
                if wait_key in args and "wait_seconds" not in args:
                    try:
                        args["wait_seconds"] = int(args.pop(wait_key))
                    except Exception:
                        pass
                    
        # Standardize argument name for background tools
        if tool_name in ("get_background_output", "send_background_input", "stop_background_process"):
            for wrong_key in ["id", "proc_id", "pid"]:
                if wrong_key in args and "process_id" not in args:
                    args["process_id"] = args.pop(wrong_key)
            if "input" in args and "text" not in args:
                args["text"] = args.pop("input")
                    
        # Standardize argument name for read_file
        if tool_name == "read_file":
            for wrong_key in ["path", "file", "filename"]:
                if wrong_key in args and "filepath" not in args:
                    args["filepath"] = args.pop(wrong_key)
            
        tool_calls.append({
            "id": f"call_{uuid.uuid4().hex[:12]}",
            "type": "function",
            "function": {
                "name": tool_name,
                "arguments": json.dumps(args)
            }
        })
        
    parts.append(content[last_idx:])
    cleaned_content = "".join(parts).strip()
    if not cleaned_content:
        cleaned_content = None
        
    return cleaned_content, tool_calls


# ── Process-level session-usage runtime sentinel ────────────────────────────
_RUNTIME_SESSION_KEY: str = ""

def _get_runtime_session_key() -> str:
    """Return a stable per-process key, created lazily on first call."""
    global _RUNTIME_SESSION_KEY
    if not _RUNTIME_SESSION_KEY:
        import uuid
        _RUNTIME_SESSION_KEY = str(uuid.uuid4())
    return _RUNTIME_SESSION_KEY


def _get_usage_file():
    from utim_cli.config import get_utim_dir
    return get_utim_dir() / "session_usage.json"


def _resolve_session_id(session_id: str = "") -> str:
    """Resolve the effective session ID: caller-supplied > session_state.json > runtime sentinel."""
    import json, os
    from utim_cli.config import get_utim_dir
    if session_id:
        return session_id
    state_file = get_utim_dir() / "session_state.json"
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as sf:
                return json.load(sf).get("session_id", "") or ""
        except Exception:
            pass
    return _get_runtime_session_key()


def _read_all_usage() -> dict:
    """Read the full per-session usage file, migrating legacy flat format."""
    import json
    usage_file = _get_usage_file()
    if not usage_file.exists():
        return {}
    try:
        raw = json.loads(usage_file.read_text(encoding="utf-8"))
        if isinstance(raw, dict) and "sessions" in raw:
            return raw["sessions"]
        # Legacy flat format: {"session_id": "...", "main_agent_credits": ...}
        if isinstance(raw, dict) and raw.get("session_id"):
            sid = raw["session_id"]
            return {
                sid: {
                    "main_agent_input_tokens":  raw.get("main_agent_input_tokens", 0),
                    "main_agent_output_tokens": raw.get("main_agent_output_tokens", 0),
                    "main_agent_credits":       raw.get("main_agent_credits", 0.0),
                    "tools_input_tokens":       raw.get("tools_input_tokens", 0),
                    "tools_output_tokens":      raw.get("tools_output_tokens", 0),
                    "tools_credits":            raw.get("tools_credits", 0.0),
                }
            }
    except Exception:
        pass
    return {}


def _write_all_usage(all_sessions: dict) -> None:
    """Persist the full per-session usage dict."""
    import json
    try:
        usage_file = _get_usage_file()
        usage_file.write_text(
            json.dumps({"sessions": all_sessions}, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def get_session_usage(session_id: str = "") -> dict:
    """
    Return accumulated usage for the given session (or current session if
    session_id is empty).  Keys: main_agent_input_tokens, main_agent_output_tokens,
    main_agent_credits, tools_input_tokens, tools_output_tokens, tools_credits.
    """
    eff_id = _resolve_session_id(session_id)
    empty = {
        "main_agent_input_tokens":  0,
        "main_agent_output_tokens": 0,
        "main_agent_credits":       0.0,
        "tools_input_tokens":       0,
        "tools_output_tokens":      0,
        "tools_credits":            0.0,
    }
    if not eff_id:
        return empty
    return _read_all_usage().get(eff_id, empty)


def update_session_usage(
    usage_type: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
    credits_used: float = 0.0,
    session_id: str = "",
) -> None:
    """
    Accumulate session usage stats in `.utim/session_usage.json`.

    The file is stored as {"sessions": {<session_id>: {...}}} so multiple
    sessions (including resumed ones) accumulate independently and are never
    wiped when switching between them.

    Args:
        usage_type:    'main_agent' or 'tools'
        input_tokens:  input tokens consumed by this call
        output_tokens: output tokens produced by this call
        credits_used:  estimated credit cost of this call
        session_id:    the session UUID (optional; resolved automatically)
    """
    eff_id = _resolve_session_id(session_id)
    if not eff_id:
        return  # no session yet — skip silently

    all_sessions = _read_all_usage()
    entry = all_sessions.get(eff_id) or {
        "main_agent_input_tokens":  0,
        "main_agent_output_tokens": 0,
        "main_agent_credits":       0.0,
        "tools_input_tokens":       0,
        "tools_output_tokens":      0,
        "tools_credits":            0.0,
    }

    if usage_type == "main_agent":
        entry["main_agent_input_tokens"]  = entry.get("main_agent_input_tokens",  0)   + input_tokens
        entry["main_agent_output_tokens"] = entry.get("main_agent_output_tokens", 0)   + output_tokens
        entry["main_agent_credits"]       = entry.get("main_agent_credits",       0.0) + credits_used
    elif usage_type == "tools":
        entry["tools_input_tokens"]  = entry.get("tools_input_tokens",  0)   + input_tokens
        entry["tools_output_tokens"] = entry.get("tools_output_tokens", 0)   + output_tokens
        entry["tools_credits"]       = entry.get("tools_credits",       0.0) + credits_used

    all_sessions[eff_id] = entry
    _write_all_usage(all_sessions)
