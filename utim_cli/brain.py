"""
UTIM Brain — Hierarchical Memory System
========================================

Humans don't store facts in a flat list. The brain organises memory into
folders (episodic, semantic, procedural) and retrieves by PATTERN, not keyword.
This module mirrors that structure for UTIM.

Folder layout  (~/.utim/brain/):
──────────────────────────────────────────────────────────────────────────────
  brain/
    index.json                  ← registry of all memory folders / projects
    embeddings.db               ← SQLite: all MiniLM vector embeddings
    global/                     ← cross-project persistent memories
      memories/
        <id>.json
    projects/
      <project_id>/             ← per-project (keyed by cwd hash)
        meta.json               ← project name, path, last indexed
        architecture.md         ← auto-generated project file tree snapshot
        conventions.md          ← learned conventions for this project
        memories/
          <id>.json

Memory entry schema (each <id>.json):
──────────────────────────────────────────────────────────────────────────────
  {
    "id":           "mem_a1b2c3",
    "type":         "episodic|semantic|procedural|correction|architecture",
    "title":        "Short headline",
    "content":      "Full text of the memory",
    "tags":         ["list", "of", "concept", "keywords"],
    "project_id":   "proj_xxxx"  or null for global,
    "created_at":   "ISO timestamp",
    "last_accessed":"ISO timestamp",
    "access_count": 0,
    "source":       "user_correction|reflection|architecture_scan|manual"
  }

Retrieval pipeline (two-stage RAG):
──────────────────────────────────────────────────────────────────────────────
  Stage 1 — Forward pass (MiniLM cosine search):
    user_prompt → all-MiniLM-L6-v2 → top_k candidate memories

  Stage 2 — Reverse loop (Qwen3-0.6B query expansion):
    context → Qwen3 → ["refined sub-query 1", "refined sub-query 2", ...]
    Each sub-query → MiniLM → additional candidates
    All candidates merged + deduplicated + re-ranked by score

The reverse loop prevents semantic drift: Qwen decomposes the active context
into precise factual sub-questions, then MiniLM fetches the exact memories
those sub-questions point to.

Background watcher:
──────────────────────────────────────────────────────────────────────────────
  A daemon thread runs every BRAIN_SCAN_INTERVAL seconds. It:
    1. Checks if the project architecture has changed (file tree diff)
    2. If changed → stores new architecture memory + re-embeds
    3. Checks current conversation context against brain entries
    4. Injects any high-relevance matches into STATE["brain_context"]
       so get_system_prompt() can include them
"""

import os
import re
import json
import uuid
import math
import hashlib
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Optional, Tuple

# ── Constants ──────────────────────────────────────────────────────────────────

BRAIN_SCAN_INTERVAL   = 45     # seconds between background scans
BRAIN_TOP_K_FORWARD   = 12     # MiniLM candidates from forward pass
BRAIN_TOP_K_REVERSE   = 6      # MiniLM candidates per Qwen sub-query
BRAIN_FINAL_LIMIT     = 6      # max memories injected into system prompt
BRAIN_RELEVANCE_FLOOR = 0.30   # cosine similarity floor for injection
QWEN_BRAIN_MODEL      = "qwen/qwen2.5-1.5b-instruct"   # fast reasoning model on server

# Reuse the reflection model list so brain calls use the same fallback chain
try:
    from utim_cli.reflection import REFLECTION_MODELS
except Exception:
    REFLECTION_MODELS = ["openrouter/free", QWEN_BRAIN_MODEL]

# ── Paths ──────────────────────────────────────────────────────────────────────

def _brain_root() -> Path:
    from utim_cli.config import get_utim_dir
    root = get_utim_dir() / "brain"
    root.mkdir(parents=True, exist_ok=True)
    return root

def _brain_db_path() -> str:
    return str(_brain_root() / "embeddings.db")

def _project_id(workspace_path: Optional[str] = None) -> str:
    """Stable short hex ID for the current workspace directory."""
    cwd = workspace_path or os.getcwd()
    return "proj_" + hashlib.sha1(cwd.encode()).hexdigest()[:10]

def _project_dir(project_id: str) -> Path:
    d = _brain_root() / "projects" / project_id
    (d / "memories").mkdir(parents=True, exist_ok=True)
    return d

def _global_dir() -> Path:
    d = _brain_root() / "global" / "memories"
    d.mkdir(parents=True, exist_ok=True)
    return d.parent   # return global/ not global/memories/

# ── SQLite Embeddings Store ────────────────────────────────────────────────────

def _get_db() -> sqlite3.Connection:
    conn = sqlite3.connect(_brain_db_path(), check_same_thread=False)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS brain_embeddings (
            memory_id   TEXT PRIMARY KEY,
            project_id  TEXT,
            embedding   TEXT,          -- JSON float array
            content     TEXT,
            created_at  TEXT
        )
    """)
    conn.commit()
    return conn

# ── MiniLM Embedding Function ──────────────────────────────────────────────────

_minilm_fn = None
_minilm_lock = threading.Lock()

def _get_minilm():
    """Lazily load all-MiniLM-L6-v2 via ChromaDB or sentence-transformers."""
    global _minilm_fn
    if _minilm_fn is not None:
        return _minilm_fn
    with _minilm_lock:
        if _minilm_fn is not None:
            return _minilm_fn
        try:
            import chromadb.utils.embedding_functions as ef
            fn = ef.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            _minilm_fn = fn
            return fn
        except Exception:
            pass
        try:
            from sentence_transformers import SentenceTransformer
            _model = SentenceTransformer("all-MiniLM-L6-v2")
            class _STWrapper:
                def __call__(self, texts):
                    return _model.encode(texts, show_progress_bar=False).tolist()
            _minilm_fn = _STWrapper()
            return _minilm_fn
        except Exception:
            return None

def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    fn = _get_minilm()
    if not fn:
        return None
    try:
        return fn(texts)
    except Exception:
        return None

def _cosine(v1: List[float], v2: List[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2))
    n1  = math.sqrt(sum(a * a for a in v1))
    n2  = math.sqrt(sum(b * b for b in v2))
    if n1 == 0 or n2 == 0:
        return 0.0
    return dot / (n1 * n2)

# ── Qwen3-0.6B Brain Reasoning ─────────────────────────────────────────────────

def _call_qwen_brain(prompt: str, system: str = "", max_tokens: int = 400) -> str:
    """
    Call a lightweight free model on OpenRouter for internal reasoning tasks.
    Returns the raw text response, or "" on failure.
    """
    import re as _re
    try:
        from utim_cli.config import config as _cfg
        _key = _cfg.get("api_key") or os.getenv("OPENROUTER_API_KEY") or os.getenv("UTIM_API_KEY") or ""
    except Exception:
        _key = os.getenv("OPENROUTER_API_KEY") or os.getenv("UTIM_API_KEY") or ""

    if not _key:
        return ""

    import requests as _req
    _system = system or "You are a precise AI assistant. Be concise and accurate."

    for model in REFLECTION_MODELS:
        try:
            resp = _req.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://utim.dev",
                    "X-Title": "UTIM Brain",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _system},
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": max_tokens,
                    "temperature": 0.1,
                },
                timeout=20,
            )
            if resp.status_code != 200:
                continue
            raw = resp.json().get("choices", [{}])[0].get("message", {}).get("content", "")
            raw = _re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", raw, flags=_re.DOTALL).strip()
            return raw
        except Exception:
            continue
    return ""

def _strip_think_tags(text: str) -> str:
    import re as _re
    return _re.sub(r"<think(?:ing)?>.*?</think(?:ing)?>", "", text, flags=_re.DOTALL).strip()

# ── Memory CRUD ────────────────────────────────────────────────────────────────

def store_brain_memory(
    content: str,
    title: str = "",
    memory_type: str = "semantic",
    tags: Optional[List[str]] = None,
    project_id: Optional[str] = None,
    source: str = "manual",
) -> str:
    """
    Store a new memory in the brain.
    Returns the memory_id of the created entry.
    """
    if not content or not content.strip():
        return ""

    mem_id = "mem_" + uuid.uuid4().hex[:8]
    pid    = project_id or _project_id()
    now    = datetime.now().isoformat()

    entry = {
        "id":           mem_id,
        "type":         memory_type,
        "title":        title or content[:60].replace("\n", " "),
        "content":      content,
        "tags":         tags or [],
        "project_id":   pid,
        "created_at":   now,
        "last_accessed": now,
        "access_count": 0,
        "source":       source,
    }

    # Write JSON file
    try:
        if memory_type == "architecture" or project_id:
            mem_dir = _project_dir(pid) / "memories"
        else:
            mem_dir = _global_dir() / "memories"
        mem_dir.mkdir(parents=True, exist_ok=True)
        with open(mem_dir / f"{mem_id}.json", "w", encoding="utf-8") as f:
            json.dump(entry, f, indent=2)
    except Exception:
        pass

    # Embed and store
    try:
        vecs = _embed([content])
        if vecs:
            conn = _get_db()
            conn.execute(
                "INSERT OR REPLACE INTO brain_embeddings VALUES (?, ?, ?, ?, ?)",
                (mem_id, pid, json.dumps(vecs[0]), content[:2000], now)
            )
            conn.commit()
            conn.close()
    except Exception:
        pass

    _update_brain_index()
    return mem_id


def retrieve_brain_memories(
    query: str,
    top_k: int = BRAIN_FINAL_LIMIT,
    project_id: Optional[str] = None,
    use_reverse_loop: bool = True,
) -> List[Dict]:
    """
    Two-stage brain retrieval:
      Stage 1 — Forward: MiniLM cosine search
      Stage 2 — Reverse loop: Qwen generates sub-queries → MiniLM refines

    Returns list of memory dicts with added 'score' field.
    """
    if not query:
        return []

    pid = project_id or _project_id()

    # ── Stage 1: Forward pass ─────────────────────────────────────────────
    candidates = _forward_search(query, pid, top_k=BRAIN_TOP_K_FORWARD)

    # ── Stage 2: Reverse loop ─────────────────────────────────────────────
    if use_reverse_loop and candidates:
        sub_queries = _qwen_generate_sub_queries(query, candidates)
        for sq in sub_queries:
            extra = _forward_search(sq, pid, top_k=BRAIN_TOP_K_REVERSE)
            for item in extra:
                if not any(c["id"] == item["id"] for c in candidates):
                    candidates.append(item)

    # Re-rank all candidates against the original query
    if candidates:
        q_vecs = _embed([query])
        if q_vecs:
            q_vec = q_vecs[0]
            for c in candidates:
                raw_vec = c.get("_vec")
                if raw_vec:
                    c["score"] = _cosine(q_vec, raw_vec)
                # Boost corrections / verified memories
                if c.get("source") in ("user_correction", "reflection"):
                    c["score"] = c.get("score", 0.0) + 0.15

    candidates.sort(key=lambda x: x.get("score", 0.0), reverse=True)

    # Filter below floor and deduplicate
    seen_ids = set()
    results = []
    for c in candidates:
        if c.get("score", 0.0) < BRAIN_RELEVANCE_FLOOR:
            continue
        if c["id"] in seen_ids:
            continue
        seen_ids.add(c["id"])
        # Update last_accessed
        _touch_memory(c["id"], c.get("_project_id", pid))
        c.pop("_vec", None)
        c.pop("_project_id", None)
        results.append(c)
        if len(results) >= top_k:
            break

    return results


def _forward_search(query: str, project_id: str, top_k: int = 10) -> List[Dict]:
    """MiniLM cosine similarity search against embeddings.db."""
    q_vecs = _embed([query])
    if not q_vecs:
        return []
    q_vec = q_vecs[0]

    try:
        conn = _get_db()
        rows = conn.execute(
            "SELECT memory_id, project_id, embedding, content FROM brain_embeddings"
        ).fetchall()
        conn.close()
    except Exception:
        return []

    scored = []
    for row in rows:
        mem_id, pid, emb_json, content = row
        try:
            vec  = json.loads(emb_json)
            sim  = _cosine(q_vec, vec)
            data = {"id": mem_id, "content": content, "score": sim,
                    "_vec": vec, "_project_id": pid}
            scored.append(data)
        except Exception:
            continue

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored[:top_k]


def _qwen_generate_sub_queries(original_query: str, candidates: List[Dict]) -> List[str]:
    """
    Ask Qwen3-0.6B: given the user's query and top retrieved memories,
    what more specific sub-questions would retrieve even better memories?
    Returns a list of refined query strings (max 3).
    """
    preview = "\n".join(f"- {c.get('content','')[:120]}" for c in candidates[:4])
    prompt = (
        f"User query: \"{original_query}\"\n\n"
        f"Top retrieved memories so far:\n{preview}\n\n"
        "Generate 2-3 specific sub-queries (as a JSON array of strings) that would "
        "retrieve more precise, relevant memories from the knowledge base to answer "
        "the user's query. Focus on concrete facts, not generic terms.\n"
        "Return ONLY a JSON array like: [\"sub-query 1\", \"sub-query 2\"]"
    )
    resp = _call_qwen_brain(prompt, system="You are a memory retrieval optimizer. Return ONLY a JSON array.", max_tokens=200)
    if not resp:
        return []
    try:
        # Extract JSON array from response
        match = re.search(r'\[.*?\]', resp, re.DOTALL)
        if match:
            return json.loads(match.group())[:3]
    except Exception:
        pass
    return []


def _touch_memory(mem_id: str, project_id: str):
    """Update last_accessed and increment access_count for a memory."""
    try:
        # Try to find and update the JSON file
        pid = project_id
        for search_dir in [_project_dir(pid) / "memories", _global_dir() / "memories"]:
            fp = search_dir / f"{mem_id}.json"
            if fp.exists():
                with open(fp, "r", encoding="utf-8") as f:
                    data = json.load(f)
                data["last_accessed"] = datetime.now().isoformat()
                data["access_count"]  = data.get("access_count", 0) + 1
                with open(fp, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                break
    except Exception:
        pass

# ── Brain Index ────────────────────────────────────────────────────────────────

def _update_brain_index():
    """Maintain the brain/index.json registry."""
    try:
        root  = _brain_root()
        idx_f = root / "index.json"
        idx   = {}
        if idx_f.exists():
            with open(idx_f, "r", encoding="utf-8") as f:
                idx = json.load(f)

        # Count memories
        total = 0
        projects = {}
        proj_root = root / "projects"
        if proj_root.exists():
            for pdir in proj_root.iterdir():
                if pdir.is_dir():
                    mem_dir = pdir / "memories"
                    count = len(list(mem_dir.glob("*.json"))) if mem_dir.exists() else 0
                    total += count
                    meta_f = pdir / "meta.json"
                    meta = {}
                    if meta_f.exists():
                        with open(meta_f, "r", encoding="utf-8") as f:
                            meta = json.load(f)
                    projects[pdir.name] = {"count": count, "name": meta.get("name", pdir.name)}

        glob_dir = root / "global" / "memories"
        glob_count = len(list(glob_dir.glob("*.json"))) if glob_dir.exists() else 0
        total += glob_count

        idx.update({
            "total_memories": total,
            "global_memories": glob_count,
            "projects": projects,
            "last_updated": datetime.now().isoformat(),
        })

        with open(idx_f, "w", encoding="utf-8") as f:
            json.dump(idx, f, indent=2)
    except Exception:
        pass

# ── Project Architecture Indexing ──────────────────────────────────────────────

_last_arch_hash: Dict[str, str] = {}

def _snapshot_project_architecture(workspace: str = ".") -> str:
    """Walk the workspace and return a compact file-tree string."""
    lines = []
    skip_dirs = {".git", "__pycache__", "node_modules", ".venv", "venv",
                 "dist", "build", ".utim_tmp", "brain", ".brain"}
    skip_exts = {".pyc", ".pyo", ".class", ".o", ".so", ".dll",
                 ".db", ".sqlite", ".bin", ".pkl"}
    try:
        for root, dirs, files in os.walk(workspace):
            dirs[:] = [d for d in sorted(dirs) if d not in skip_dirs and not d.startswith(".")]
            depth = root.replace(workspace, "").count(os.sep)
            if depth > 5:
                dirs.clear()
                continue
            indent = "  " * depth
            rel = os.path.relpath(root, workspace)
            lines.append(f"{indent}{rel}/")
            for fname in sorted(files)[:30]:
                ext = os.path.splitext(fname)[1].lower()
                if ext in skip_exts:
                    continue
                lines.append(f"{indent}  {fname}")
    except Exception:
        pass
    return "\n".join(lines[:200])


def index_project_architecture(workspace: str = "."):
    """
    Check if the project architecture has changed since last scan.
    If yes, store an updated architecture memory in the brain.
    """
    pid  = _project_id(workspace)
    snap = _snapshot_project_architecture(workspace)
    snap_hash = hashlib.sha1(snap.encode()).hexdigest()

    if _last_arch_hash.get(pid) == snap_hash:
        return   # unchanged

    _last_arch_hash[pid] = snap_hash

    # Write architecture.md
    try:
        arch_f = _project_dir(pid) / "architecture.md"
        with open(arch_f, "w", encoding="utf-8") as f:
            f.write(f"# Project Architecture\nLast scanned: {datetime.now().isoformat()}\n\n```\n{snap}\n```\n")
    except Exception:
        pass

    # Write project meta.json
    try:
        meta_f = _project_dir(pid) / "meta.json"
        meta = {}
        if meta_f.exists():
            with open(meta_f, "r", encoding="utf-8") as f:
                meta = json.load(f)
        meta.update({
            "project_id":    pid,
            "workspace":     os.path.abspath(workspace),
            "name":          os.path.basename(os.path.abspath(workspace)),
            "last_indexed":  datetime.now().isoformat(),
        })
        with open(meta_f, "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=2)
    except Exception:
        pass

    # Store as an architecture memory entry
    store_brain_memory(
        content=f"Project file tree for '{os.path.basename(os.path.abspath(workspace))}':\n\n{snap}",
        title=f"Architecture — {os.path.basename(os.path.abspath(workspace))}",
        memory_type="architecture",
        tags=["architecture", "file_tree", "project_structure"],
        project_id=pid,
        source="architecture_scan",
    )

# ── Background Watcher ─────────────────────────────────────────────────────────

_watcher_started = False
_watcher_lock    = threading.Lock()

def start_brain_watcher():
    """
    Start the background brain watcher daemon thread.
    Safe to call multiple times — only one thread is ever started.
    """
    global _watcher_started
    with _watcher_lock:
        if _watcher_started:
            return
        _watcher_started = True

    def _watcher_loop():
        while True:
            try:
                _brain_tick()
            except Exception:
                pass
            time.sleep(BRAIN_SCAN_INTERVAL)

    t = threading.Thread(target=_watcher_loop, daemon=True, name="utim-brain-watcher")
    t.start()


def _brain_tick():
    """
    Single tick of the brain watcher:
      1. Re-index project architecture if it changed
      2. Check current conversation context against brain
      3. Surface highly relevant memories into STATE["brain_context"]
    """
    try:
        # 1. Architecture re-scan
        index_project_architecture(os.getcwd())
    except Exception:
        pass

    try:
        # 2. Read the latest user prompt from STATE
        from utim_cli.state import STATE
        active_prompt = STATE.get("last_user_prompt", "") or ""
        if not active_prompt or len(active_prompt.strip()) < 10:
            return

        # 3. Retrieve relevant brain memories
        memories = retrieve_brain_memories(active_prompt, top_k=BRAIN_FINAL_LIMIT)
        if memories:
            STATE["brain_context"] = memories
        else:
            STATE.pop("brain_context", None)
    except Exception:
        pass

# ── Qwen Reasoning over Retrieved Memories ─────────────────────────────────────

def reason_over_memories(user_prompt: str, memories: List[Dict]) -> str:
    """
    Ask Qwen3-0.6B to synthesize retrieved brain memories into a concise
    context summary relevant to the user's current task.
    Returns a 2-5 sentence insight string, or "" if nothing useful.
    """
    if not memories or not user_prompt:
        return ""

    mem_text = "\n".join(
        f"[{i+1}] ({m.get('type','?')}) {m.get('title','')}: {m.get('content','')[:200]}"
        for i, m in enumerate(memories)
    )

    prompt = (
        f"User's current task: \"{user_prompt}\"\n\n"
        f"Retrieved brain memories:\n{mem_text}\n\n"
        "Based ONLY on the retrieved memories above, write a 1-3 sentence insight "
        "that directly helps with the user's task. If the memories are not relevant, "
        "respond with exactly: NONE"
    )
    resp = _call_qwen_brain(
        prompt,
        system="You are a concise memory synthesizer. Be direct and factual. Max 3 sentences.",
        max_tokens=250,
    )
    if resp.strip().upper() == "NONE" or not resp.strip():
        return ""
    return resp.strip()


# ── Context Injection Helper (called by orchestrator) ─────────────────────────

def get_brain_context_prompt(user_prompt: str = "") -> str:
    """
    Build the brain context block for injection into the system prompt.
    Called by orchestrator.get_system_prompt().
    Attempts fast retrieval first; if memories exist, runs Qwen synthesis.
    """
    try:
        from utim_cli.state import STATE

        # Prefer pre-computed brain_context from background watcher
        cached = STATE.get("brain_context")
        if not cached and user_prompt:
            cached = retrieve_brain_memories(user_prompt, top_k=BRAIN_FINAL_LIMIT)
            if cached:
                STATE["brain_context"] = cached

        if not cached:
            return ""

        # Build raw memory bullets
        bullets = []
        for m in cached:
            title   = m.get("title", "")
            content = m.get("content", "")[:300]
            mtype   = m.get("type", "")
            score   = m.get("score", 0.0)
            bullets.append(f"  [{mtype.upper()}] {title}\n    {content}")

        raw_block = "\n".join(bullets)

        # Optionally synthesize with Qwen (only if we have an active prompt)
        synthesis = ""
        if user_prompt and len(user_prompt.strip()) > 15:
            synthesis = reason_over_memories(user_prompt, cached)

        out = "\n\n### BRAIN MEMORY CONTEXT ###\n"
        if synthesis:
            out += f"[Synthesized Insight]: {synthesis}\n\n"
        out += f"[Raw Memories]:\n{raw_block}\n"
        return out

    except Exception:
        return ""


# ── Public convenience wrappers ────────────────────────────────────────────────

def store_memory_from_experience(content: str, category: str, project_id: str = None):
    """
    Called by the reflection engine after storing a new experience.
    Mirrors the experience into the brain's memory system so it's also
    retrievable by MiniLM + Qwen during brain retrieval.
    """
    mtype = "correction" if "correction" in category else "semantic"
    source = "user_correction" if category == "knowledge_correction" else "reflection"
    store_brain_memory(
        content=content,
        memory_type=mtype,
        tags=[category],
        project_id=project_id or _project_id(),
        source=source,
    )


def get_brain_stats() -> Dict:
    """Return brain statistics for display in /brain command."""
    try:
        idx_f = _brain_root() / "index.json"
        if idx_f.exists():
            with open(idx_f, "r", encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {}
