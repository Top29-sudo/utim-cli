"""
Importance-Weighted Context Pruning — LLM-driven scoring for intelligent context summarization.

This module implements a scoring pass that distinguishes between high-signal technical content
and low-signal conversational filler before summarization.
"""

import os
import re
from typing import List, Dict, Tuple, Optional, Set
import requests
import json
import hashlib
from utim_cli.constants import DEFAULT_MODEL

# Fallback models for compression operations - ordered by reliability and quality.
# "openrouter/free" is the first fallback tried after the primary model.
COMPRESSION_FALLBACK_MODELS = [
    "openrouter/free",
    "poolside/laguna-xs-2.1:free",
    "cohere/north-mini-code:free",
]

# Track what content has already been summarized to prevent duplicate summarization
_summarized_content_hashes: Set[str] = set()

def _compute_content_hash(content: str) -> str:
    """Compute a hash of content to detect duplicates."""
    return hashlib.md5(content[:500].encode()).hexdigest()[:16]


# Patterns that indicate high-importance content
HIGH_SIGNAL_PATTERNS = [
    r"(?i)(must|should|requirement|constraint|rule)",
    r"(?i)(architecture|design|pattern|structure)",
    r"(?i)(file|path|module|class|function|method)",
    r"(?i)(import|export|dependency|reference)",
    r"(?i)(config|setting|environment|variable)",
    r"(?i)(api|endpoint|route|handler)",
    r"(?i)(test|spec|verify|assert)",
    r"(?i)(error|exception|failure|bug)",
    r"(?i)(security|auth|permission|access)",
    r"(?i)(performance|optimization|scale)",
    r"(?i)(convention|standard|style|format)",
    r"(?i)(preference|always|prefer|use)",
    r"(?i)(plan|implement|create|build|modify)",
    r"(?i)(important|critical|vital|essential)",
]

# Patterns that indicate low-importance content
LOW_SIGNAL_PATTERNS = [
    r"(?i)^(ok|okay|yes|no|got it|understood|thanks)$",
    r"(?i)^(i see|i understand|right|correct)$",
    r"(?i)^(here's|here is|this is|that's|that is)",
    r"(?i)^(you're welcome|no problem|np)$",
    r"^[^a-zA-Z0-9]*$",  # Pure whitespace/punctuation
]

# Continuity markers that should be preserved to avoid task-looping after compression
CONTINUITY_PATTERNS = [
    r"(?i)(next step|next action|in progress|pending|remaining|blocker)",
    r"(?i)(todo|to-do|plan|objective|goal|continue|resume|finish)",
    r"(?i)(tried|attempted|worked|failed|error|fix|patch)",
]

# Regex to strip <think>...</think> and <thinking>...</thinking> reasoning blocks
_THINK_RE = re.compile(r"<think(?:ing)?>.*?</think(?:ing)?>", re.DOTALL | re.IGNORECASE)


def _strip_thinking_blocks(messages: List[Dict], keep_last: int = 1) -> List[Dict]:
    """Remove <think>...</think> blocks from all but the last `keep_last` assistant messages.

    Reasoning traces are only useful in the *current* step; older ones waste tokens
    without adding signal. We keep the most recent one intact so the model can see
    its own chain-of-thought for the ongoing action.
    """
    result = []
    # Collect indices of assistant text messages (no tool_calls) in reverse order
    assistant_text_indices = [
        i for i, m in enumerate(messages)
        if m.get("role") == "assistant" and not m.get("tool_calls") and m.get("content")
    ]
    # The last `keep_last` indices are kept intact
    keep_intact = set(assistant_text_indices[-keep_last:]) if assistant_text_indices else set()

    for i, msg in enumerate(messages):
        if (
            msg.get("role") == "assistant"
            and not msg.get("tool_calls")
            and i not in keep_intact
        ):
            content = msg.get("content") or ""
            stripped = _THINK_RE.sub("", content).strip()
            if stripped != content:
                msg = dict(msg)
                msg["content"] = stripped if stripped else "[thinking block removed]"
        result.append(msg)
    return result


def _deduplicate_tool_outputs(messages: List[Dict]) -> List[Dict]:
    """Compress repeated identical tool responses to a one-liner stub.

    When the agent calls the same tool with the same arguments repeatedly and gets
    the same output (e.g. re-reading an unchanged file multiple times), only the
    first occurrence is kept verbatim. Subsequent duplicates are replaced with:
      [Duplicate tool output — identical to earlier result, omitted to save tokens]
    """
    # Map: (tool_call_id_of_preceding_assistant_call -> output_hash)
    # We key on (tool_name, args_hash) -> first_output_hash seen
    seen: dict = {}  # (tool_name_or_id, content_hash) -> True
    result = []

    for msg in messages:
        if msg.get("role") == "tool":
            content = msg.get("content") or ""
            tool_name = msg.get("name", "")
            # Use first 300 chars of content for the hash to avoid hashing huge outputs
            content_key = (tool_name, hashlib.md5(content[:300].encode(errors="replace")).hexdigest())
            if content_key in seen and len(content) > 200:
                # Replace with stub
                msg = dict(msg)
                msg["content"] = (
                    f"[Duplicate {tool_name!r} output — identical to earlier result, "
                    f"omitted to save tokens. Original length: {len(content)} chars]"
                )
            else:
                seen[content_key] = True
        result.append(msg)
    return result


def estimate_context_tokens(messages: List[Dict]) -> int:
    """Rough token estimate for a message list (4 chars ≈ 1 token heuristic)."""
    try:
        total_chars = sum(
            len(str(m.get("content") or "")) +
            len(json.dumps(m.get("tool_calls") or []))
            for m in messages
        )
        return total_chars // 4
    except Exception:
        return 0


def sanitize_message_sequence(messages: List[Dict]) -> List[Dict]:
    """
    Ensure the messages list is valid for LLM API calls.
    - Each tool message must have a preceding assistant message with the matching tool_call_id.
    - Each assistant message with tool_calls must have corresponding tool messages.
    - Strips <think> blocks from non-current assistant messages to save tokens.
    - Deduplicates repeated identical tool outputs.
    """
    if not messages:
        return messages

    # Strip thinking blocks from older assistant messages
    messages = _strip_thinking_blocks(messages)

    # Compress duplicate tool outputs
    messages = _deduplicate_tool_outputs(messages)
        
    # Step 1: Identify all tool call IDs present in tool messages
    present_tool_ids = {
        m.get("tool_call_id") for m in messages 
        if m.get("role") == "tool" and m.get("tool_call_id")
    }
    
    # Step 2: Filter assistant messages' tool_calls to only include those present
    temp_messages = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            valid_tcs = [tc for tc in m.get("tool_calls", []) if tc.get("id") in present_tool_ids]
            if valid_tcs:
                new_m = dict(m)
                new_m["tool_calls"] = valid_tcs
                temp_messages.append(new_m)
            else:
                # If no tool calls are valid, keep only if it has text content
                if m.get("content"):
                    new_m = dict(m)
                    new_m.pop("tool_calls", None)
                    temp_messages.append(new_m)
                # otherwise drop it (do not append)
        else:
            temp_messages.append(m)
            
    # Step 3: Now identify all tool call IDs that are actually in the kept assistant messages
    active_tool_ids = set()
    for m in temp_messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            for tc in m.get("tool_calls", []):
                if tc.get("id"):
                    active_tool_ids.add(tc.get("id"))
                    
    # Step 4: Keep only tool messages whose tool_call_id is in active_tool_ids
    final_messages = []
    for m in temp_messages:
        if m.get("role") == "tool":
            tc_id = m.get("tool_call_id")
            if tc_id in active_tool_ids:
                final_messages.append(m)
            # If no matching assistant tool call, drop the orphan tool message
        else:
            final_messages.append(m)
            
    return final_messages


def score_message_importance(message: Dict, llm_key: str = None) -> float:
    """
    Score a message's importance for context preservation.
    
    Returns a score between 0.0 (discard) and 1.0 (must preserve).
    """
    role = message.get("role", "")
    content = message.get("content", "") or ""
    if not isinstance(content, str):
        content = str(content)
        
    # Start with base score depending on role
    if role == "user":
        score = 0.85
    elif role == "assistant":
        if message.get("tool_calls"):
            score = 0.85
        else:
            score = 0.6  # Base assistant score
    elif role == "tool":
        score = 0.65  # Base tool score
    else:
        score = 0.5

    # If it is a tool message, analyze its significance in-depth (no early return)
    if role == "tool":
        content_lower = content.lower()
        tool_name = message.get("name", "")
        
        # Critical fix: Short but critical content gets high priority
        # Tool messages with error/failure indicators are always high priority
        critical_keywords = ["error", "exception", "failed", "failure", "traceback", 
                            "conflict", "permission denied", "not found", "undefined"]
        if any(kw in content_lower for kw in critical_keywords):
            score = max(score, 0.9)  # Boost critical errors
            
        # Code reading/inspections are highly valued to prevent checking the same files in a loop
        if tool_name in ["read_file", "view_file", "grep_search", "view_file_outline"]:
            score += 0.2
            
        # File edits or changes are high priority
        if any(kw in content_lower for kw in ["success", "created", "modified", "deleted", "replaced", "written"]):
            score += 0.2
            
        # Errors or warnings are high priority for debugging loops
        if any(kw in content_lower for kw in ["error", "exception", "failed", "failure", "traceback", "warning", "conflict"]):
            score += 0.2
            
        # Code reading (grep search or file view output) is extremely high priority to prevent loops!
        if "def " in content or "class " in content or "import " in content or "function " in content:
            score += 0.25
        if "```" in content or "LineNumber" in content or "LineContent" in content:
            score += 0.2
            
        # FIX: Even short tool outputs with technical content should score higher
        # This addresses the issue where short file reads get scored low
        if len(content) > 0 and len(content) < 200:
            # Short content that has code indicators is very valuable
            if re.search(r"[{};()=\[\]]", content) or "\n" in content:
                score = max(score, 0.8)
            elif re.search(r":[a-zA-Z_]\w*\s*=", content):  # Key-value pairs
                score = max(score, 0.75)
            
        # If the content is from a file read (e.g. a long source code snippet), keep it
        if len(content) > 100 and (re.search(r"[{};()=+\-\[\]]", content) or "\n" in content):
            score += 0.15
            
    elif role == "assistant":
        # Assistant responses that contain code or architecture details are important
        if "def " in content or "class " in content or "import " in content or "```" in content:
            score += 0.2
            
    # Adjust score based on patterns for all message types
    for pattern in HIGH_SIGNAL_PATTERNS:
        if re.search(pattern, content):
            score += 0.1
            
    for pattern in LOW_SIGNAL_PATTERNS:
        if re.search(pattern, content.strip()):
            score -= 0.15

    # Preserve execution continuity details aggressively (e.g., plans, next steps, todos)
    for pattern in CONTINUITY_PATTERNS:
        if re.search(pattern, content):
            score += 0.25
            
    # General code snippets check
    if "```" in content or re.search(r"\w+\s*\(\s*\w*", content):
        score += 0.15
        
    # File paths are high signal
    if re.search(r"[\w/\\-]+\.\w+", content):
        score += 0.15

    # FIXED: Better normalization - critical short content should not be penalized
    min_floor = 0.2
    if role == "user":
        # BUG 5 FIX: User instructions must NEVER be below the compression
        # threshold (0.75).  Previously the floor was 0.8, but LOW_SIGNAL_PATTERNS
        # could subtract 0.15 and push a genuine instruction (e.g. "here is the
        # constraint: use Redis") down to 0.70 — below the 0.75 cut-off used in
        # _compress_intra_turn — causing it to be classified as compressible.
        # Setting the floor to 1.0 means user messages always survive verbatim.
        min_floor = 1.0  # Never compress user instructions
    elif role == "assistant":
        if message.get("tool_calls"):
            min_floor = 0.75  # Keep tool calls so we don't break message schema
        else:
            min_floor = 0.45
    elif role == "tool":
        # Keep tool outputs that contain critical technical details
        # Especially grep search or view file results
        if "def " in content or "class " in content or "import " in content or "LineNumber" in content:
            min_floor = 0.8  # Critical files/code should not be pruned
        # FIX: Short but technical content should also have higher floor
        elif len(content) > 0 and len(content) < 300 and (re.search(r"[{}();\[\]]", content) or "\n" in content):
            min_floor = 0.7  # Short technical content preserved
        else:
            min_floor = 0.5
            
    return max(min_floor, min(1.0, score))


def _call_compression_model_with_fallback(messages: List[Dict], llm_key: str, max_tokens: int = 1500, content_hint: str = None, primary_model: str = None) -> str:
    """Call compression model with fallback support."""
    global _summarized_content_hashes
    
    # FIX #4: Deduplication - check if this content was already summarized
    if content_hint:
        content_hash = _compute_content_hash(content_hint)
        if content_hash in _summarized_content_hashes:
            return "[Content previously summarized - skipped]"
        _summarized_content_hashes.add(content_hash)
    
    # Prioritize primary model if provided, followed by fallback models
    models_to_try = list(COMPRESSION_FALLBACK_MODELS)
    if primary_model:
        if primary_model in models_to_try:
            models_to_try.remove(primary_model)
        models_to_try.insert(0, primary_model)
    
    last_error = None
    for i, model in enumerate(models_to_try):
        model_retries = 2
        for attempt in range(model_retries + 1):
            try:
                from utim_cli.client_utils import proxy_openrouter_request
                resp = proxy_openrouter_request(
                    json_data={
                        "model": model,
                        "messages": messages,
                        "max_tokens": max_tokens
                    },
                    stream=False,
                    timeout=30,
                    is_reflection=True
                )
                if resp.status_code == 429 and attempt < model_retries:
                    import time
                    time.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                
                if resp.status_code == 200:
                    result = resp.json()["choices"][0]["message"]["content"]
                    # Strip thinking tags
                    result = re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", result, flags=re.DOTALL)
                    result = result.strip()
                    
                    # FIX #1: Hallucination detection - reject summaries with suspicious patterns
                    hallucination_patterns = [
                        r"\[.*added.*\]",  # Made-up additions like "[feature added]"
                        r"\[.*created.*\]",  # Made-up creations
                        r"I have (?:created|modified|deleted|implemented)",  # False claims of action
                        r"Successfully (?:added|removed|integrated)",  # False success claims
                    ]
                    
                    # Check if summary makes claims not in source
                    for pattern in hallucination_patterns:
                        if re.search(pattern, result, re.I) and content_hint:
                            # Check if the claim is actually in the original content
                            if not re.search(pattern.replace(r"\[", r"[^[]*").replace(r"\]", r"[^]]*"), content_hint, re.I):
                                print(f"[HALLUCINATION PREVENTED] Pattern '{pattern}' detected in summary but not in source", file=__import__('sys'))
                                # Try next model instead of returning bad summary
                                continue
                    
                    return result
                
                last_error = f"Model {model} returned status {resp.status_code}"
                break # Not 200 and not 429, break attempt loop and try next model

            except requests.exceptions.HTTPError as e:
                code = e.response.status_code if e.response is not None else 0
                if code == 429 and attempt < model_retries:
                    import time
                    time.sleep(5 * (attempt + 1))
                    continue
                last_error = e
                break
            except Exception as e:
                last_error = e
                break
    
    # Log the failure for debugging
    import sys
    print(f"[COMPRESSION FALLBACK FAILURE] All models failed. Last error: {last_error}", file=sys.stderr)
    return None


def llm_score_messages(messages: List[Dict], llm_key: str, primary_model: str = None) -> List[Tuple[int, float]]:
    """
    Use LLM to score message importance for more nuanced evaluation.
    
    Returns list of (index, score) tuples.
    """
    if not llm_key:
        return [(i, score_message_importance(m)) for i, m in enumerate(messages)]
    
    # Prepare messages for scoring
    msg_texts = []
    for i, m in enumerate(messages):
        role = m.get("role", "")
        content = m.get("content", "") or ""
        if len(content) > 200:
            content = content[:200] + "..."
        msg_texts.append(f"[{i}] {role}: {content}")
    
    prompt = f"""Score each message for importance on a scale of 0-100 based on technical value:
- High scores for: code snippets, file paths, architectural decisions, user constraints, errors, implementations
- Low scores for: acknowledgments, small talk, filler phrases, generic confirmations

Messages to score:
{chr(10).join(msg_texts[:20])}  # Limit to 20 for cost

Return only JSON array like: [{{"idx": 0, "score": 85}}, {{"idx": 1, "score": 30}}]"""
    
    llm_messages = [
        {"role": "system", "content": "You are a context analyzer. Score messages for technical importance."},
        {"role": "user", "content": prompt}
    ]
    
    result = _call_compression_model_with_fallback(llm_messages, llm_key, primary_model=primary_model)
    if result:
        try:
            data = json.loads(result)
            return [(int(d["idx"]), d["score"] / 100.0) for d in data]
        except Exception:
            pass
    
    return [(i, score_message_importance(m)) for i, m in enumerate(messages)]


def prune_context(messages: List[Dict], keep_threshold: float = 0.6, 
                  llm_key: str = None, primary_model: str = None) -> List[Dict]:
    """
    Prune messages based on importance scores.
    
    Messages below the threshold are either summarized or dropped.
    """
    if not messages:
        return messages
    
    # Get scores
    if llm_key and len(messages) > 5:
        scores = dict(llm_score_messages(messages, llm_key, primary_model=primary_model))
    else:
        scores = {i: score_message_importance(m) for i, m in enumerate(messages)}
    
    # Split into keep and summarize groups
    to_keep = []
    to_summarize = []
    
    for i, msg in enumerate(messages):
        # Never prune first/last anchors; they often carry objective and latest state.
        if i == 0 or i == len(messages) - 1:
            to_keep.append(msg)
            continue
        score = scores.get(i, 0.5)
        if score >= keep_threshold:
            to_keep.append(msg)
        else:
            to_summarize.append(msg)
    
    # BUG 4 FIX: When more messages need pruning than are being kept, generate a
    # real LLM summary instead of a useless placeholder string.  The old code wrote
    # "[Context pruned: N messages removed]" which gives the model zero information
    # about what was dropped, making it unable to continue the task coherently.
    if len(to_summarize) > len(to_keep):
        if llm_key and to_summarize:
            # Build a text digest of the low-importance messages
            text_parts = []
            for m in to_summarize:
                role = m.get("role", "")
                content = (m.get("content") or "")[:800]
                if role == "assistant" and m.get("tool_calls"):
                    tc_names = ", ".join(
                        tc.get("function", {}).get("name", "") for tc in m.get("tool_calls", [])
                    )
                    text_parts.append(f"assistant (tools: {tc_names}): {content}")
                else:
                    text_parts.append(f"{role}: {content}")
            raw = "\n---\n".join(text_parts)
            llm_msgs = [
                {
                    "role": "system",
                    "content": (
                        "You are a context compressor for an AI agent. "
                        "Summarise the following conversation excerpts into a dense, "
                        "technically precise paragraph. Preserve all file paths, error "
                        "messages, variable names, and decisions. No filler."
                    ),
                },
                {"role": "user", "content": f"Excerpts to compress:\n{raw}"},
            ]
            summary_text = _call_compression_model_with_fallback(
                llm_msgs, llm_key, max_tokens=800, primary_model=primary_model
            )
            if summary_text:
                summary_content = (
                    "[CONTEXT SUMMARY — earlier pruned messages]\n" + summary_text
                )
            else:
                # Compression call failed; fall back to a richer placeholder
                roles = ", ".join({m.get("role", "?") for m in to_summarize})
                summary_content = (
                    f"[Context pruned: {len(to_summarize)} messages ({roles}) removed "
                    "— compression model unavailable. Some context may be missing.]"
                )
        else:
            roles = ", ".join({m.get("role", "?") for m in to_summarize})
            summary_content = (
                f"[Context pruned: {len(to_summarize)} messages ({roles}) removed.]"
            )
        return sanitize_message_sequence(
            to_keep + [{"role": "user", "content": summary_content}]
        )
    
    return sanitize_message_sequence(to_keep + to_summarize)


def adaptive_compression(messages: List[Dict], target_tokens: int = 50000, primary_model: str = None) -> List[Dict]:
    """
    Intelligently compress messages to stay under token budget.
    
    Uses importance scoring to decide what to keep verbatim vs summarize.
    """
    def estimate_tokens(msgs):
        try:
            return len(json.dumps([{"role": m.get("role"), "content": str(m.get("content", ""))[:500]} for m in msgs])) // 4
        except:
            return len(str(msgs)) // 4
    
    current_tokens = estimate_tokens(messages)
    if current_tokens <= target_tokens:
        return messages
    
    # Load .env from the current working directory explicitly so adaptive_compression
    # uses the same folder-local key that Orchestrator resolved, not a stale key
    # inherited from a different utim installation elsewhere on the PATH.
    _cwd_env = os.path.join(os.getcwd(), ".env")
    try:
        from dotenv import load_dotenv as _load_dotenv
        if os.path.isfile(_cwd_env):
            _load_dotenv(_cwd_env, override=True)
    except Exception:
        pass
    from utim_cli.config import config
    llm_key = os.getenv("OPENROUTER_API_KEY") or config.get("api_key")
    
    # Iteratively remove lowest importance until under budget
    pruned = list(messages)
    while estimate_tokens(pruned) > target_tokens and len(pruned) > 2:
        # Re-score current list each iteration to avoid stale index mappings after pops.
        scores = llm_score_messages(pruned, llm_key, primary_model=primary_model) if llm_key else \
                 [(i, score_message_importance(m)) for i, m in enumerate(pruned)]
        score_dict = dict(scores)
        # Protect boundaries to preserve task continuity.
        candidates = [i for i in range(1, len(pruned) - 1)]
        if not candidates:
            break
        worst_idx = min(candidates, key=lambda i: score_dict.get(i, 0.5))
        pruned.pop(worst_idx)
    
    return sanitize_message_sequence(pruned)
