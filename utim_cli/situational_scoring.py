"""
Situational Scoring & Pattern Recognition Engine.

Philosophy: Experience is pattern recognition, not information storage.
A child who has seen many fish can recognize any new fish by its structural
pattern (fins, scales, shape) — without knowing its name. Similarly, this
engine matches experiences to the active task by detecting shared ABSTRACT
STRUCTURAL PATTERNS — objects, relationships, conceptual similarity — not
by keyword or task-category matching.

The core scoring pipeline:
  1. Dense semantic vector cosine similarity (embedding model, if available)
  2. Abstract object-concept graph overlap (extracted from user prompt vs experience)
  3. Relationship pattern matching (e.g. corrects / requires / implies)
  4. Source trust bonus (user_correction experiences always score highest)
  5. Historical success/failure feedback loop (optional, SQLite-backed)
"""

import os
import re
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from utim_cli.config import get_utim_dir
RAG_DB_PATH = os.path.join(get_utim_dir(), "rag_intelligence.db")

import os as _os

def _is_lite() -> bool:
    return _os.environ.get("UTIM_LITE_MODE", "0").lower() in ("1", "true", "yes")

_emb_fn = None

def get_embedding_fn():
    global _emb_fn
    if _is_lite():
        return None
    if _emb_fn is None:
        try:
            import chromadb.utils.embedding_functions as ef
            _emb_fn = ef.DefaultEmbeddingFunction()
        except Exception:
            try:
                import chromadb.utils.embedding_functions as ef
                _emb_fn = ef.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            except Exception:
                _emb_fn = None
    return _emb_fn

def cosine_similarity(v1, v2) -> float:
    import math
    dot = sum(a * b for a, b in zip(v1, v2))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(a * a for a in v2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot / (norm1 * norm2)


# ---------------------------------------------------------------------------
# Object-concept extraction — lightweight NLP, no model required
# ---------------------------------------------------------------------------

# Stopwords: words that carry no conceptual weight for pattern matching
_STOP = frozenset([
    "the", "a", "an", "is", "it", "its", "be", "are", "was", "were", "do",
    "does", "did", "have", "has", "had", "will", "would", "could", "should",
    "can", "may", "might", "shall", "to", "of", "in", "on", "at", "by",
    "for", "with", "about", "from", "into", "through", "and", "or", "but",
    "if", "then", "so", "that", "this", "these", "those", "i", "you", "we",
    "they", "he", "she", "my", "your", "our", "their", "me", "him", "her",
    "us", "them", "not", "no", "yes", "just", "also", "than", "more", "very",
    "up", "out", "as", "what", "how", "when", "where", "which", "who",
])

def extract_concepts(text: str) -> set:
    """
    Extract abstract concept tokens from text.
    Returns a set of lowercase non-stopword tokens (length >= 3).
    This is the 'pattern signature' of a piece of text — analogous to
    recognizing a fish by its abstract features, not its name.
    """
    if not text:
        return set()
    tokens = re.findall(r"[a-zA-Z_][a-zA-Z0-9_'-]{2,}", text.lower())
    return {t.strip("'-") for t in tokens if t.strip("'-") not in _STOP and len(t) >= 3}


def concept_overlap_score(prompt_concepts: set, content_concepts: set) -> float:
    """
    Jaccard-like overlap between two concept sets.
    Returns value in [0, 1]. The more shared abstract concepts, the higher the score.
    """
    if not prompt_concepts or not content_concepts:
        return 0.0
    intersection = prompt_concepts & content_concepts
    union = prompt_concepts | content_concepts
    return len(intersection) / len(union)


# ---------------------------------------------------------------------------
# Task type — kept lean, used only for shell/platform boosting heuristics
# ---------------------------------------------------------------------------

TASK_ANCHORS = {
    "testing":     ["run pytest tests suite", "check test coverage", "debug failing assertions"],
    "ui_design":   ["style css html aesthetic design", "create slide layout visual colors"],
    "setup":       ["npm install pip build environment dependency"],
    "refactoring": ["refactor clean simplify restructure modular"],
    "file_edit":   ["edit modify write replace create code file"],
    "search":      ["grep search find locate query codebase"],
    "general":     ["explain conceptual question general chat help discuss"],
}

_anchor_embeddings: Dict[str, list] = {}


def classify_task_type(user_prompt: str) -> str:
    """Lightweight task-type classifier — used only for platform/shell heuristics."""
    if not user_prompt:
        return "general"

    p = user_prompt.lower()

    def _heuristic(p: str) -> str:
        if any(k in p for k in ["test", "pytest", "unittest", "assert", "coverage"]):
            return "testing"
        if any(k in p for k in ["install", "setup", "init", "npm", "pip", "build", "dependency"]):
            return "setup"
        if any(k in p for k in ["ui", "design", "css", "html", "color", "style", "slide"]):
            return "ui_design"
        if any(k in p for k in ["refactor", "clean", "simplify", "restructure"]):
            return "refactoring"
        if any(k in p for k in ["edit", "modify", "update", "write", "replace", "create"]):
            return "file_edit"
        if any(k in p for k in ["search", "find", "grep", "locate", "query"]):
            return "search"
        return "general"

    emb_fn = get_embedding_fn()
    if not emb_fn:
        return _heuristic(p)

    try:
        global _anchor_embeddings
        user_emb = emb_fn([user_prompt])[0]
        if not _anchor_embeddings:
            for task_type, anchors in TASK_ANCHORS.items():
                _anchor_embeddings[task_type] = emb_fn(anchors)
        best_type, best_sim = "general", -1.0
        for task_type, embs in _anchor_embeddings.items():
            for emb in embs:
                sim = cosine_similarity(user_emb, emb)
                if sim > best_sim:
                    best_sim, best_type = sim, task_type
        return best_type if best_sim > 0.30 else _heuristic(p)
    except Exception:
        return _heuristic(p)


# ---------------------------------------------------------------------------
# Core pattern-recognition scorer
# ---------------------------------------------------------------------------

def _compute_pattern_score(user_prompt: str, content: str,
                           metadata: dict, task_type: str) -> float:
    """
    Compute a pattern-recognition similarity score in [0, ∞).
    Score > 1.0 means this experience is highly relevant.
    Score < 0.45 means it should be filtered out as noise.

    Three signal layers (fish analogy):
      Layer 1 — Silhouette (dense semantic embedding cosine)
      Layer 2 — Features (concept/object graph overlap)
      Layer 3 — Behaviour (relationship/source trust bonus)
    """
    if not content or not user_prompt:
        return 0.5  # neutral, don't drop but don't boost

    score = 0.0

    # ── Layer 1: Dense semantic embedding similarity ──────────────────────
    emb_fn = get_embedding_fn()
    if emb_fn:
        try:
            vecs = emb_fn([user_prompt, content])
            sem_sim = cosine_similarity(vecs[0], vecs[1])
            # Semantic similarity is the primary signal — weight it heavily
            score += sem_sim * 2.0
        except Exception:
            pass
    else:
        # No embedding model: fall back to concept overlap only
        pass

    # ── Layer 2: Abstract concept/object graph overlap ────────────────────
    prompt_concepts = extract_concepts(user_prompt)
    content_concepts = extract_concepts(content)
    overlap = concept_overlap_score(prompt_concepts, content_concepts)
    score += overlap * 1.5  # strong secondary signal

    # ── Layer 3: Relationship and source trust bonus ──────────────────────
    source = (metadata or {}).get("source", "")
    category = (metadata or {}).get("category", "") or ""

    # User corrections are highly relevant if they share domain concepts with the
    # current prompt. Instead of an unconditional +2.0 boost (which caused past
    # corrections from unrelated domains to always inject), we apply a
    # concept-gated boost: full +2.0 if there is concept overlap, reduced +0.5
    # if there is no overlap (still slightly preferring corrections over neutral
    # content, but not forcing cross-domain injection).
    if source == "user_correction" or category in ("knowledge_correction", "failure_correction"):
        overlap_check = concept_overlap_score(prompt_concepts, content_concepts)
        if overlap_check > 0.0:
            score += 2.0   # strong boost: correction is relevant to this domain
        else:
            score += 0.5   # mild boost: correction exists but domain is different

    # failure_correction category gets a moderate boost too
    if "correction" in category or "failure" in category:
        score += 0.3

    # ── Platform-specific boosting (shell convention heuristics) ──────────
    c_lower = content.lower()
    is_command_prompt = any(w in user_prompt.lower() for w in
                            ["run", "exec", "command", "shell", "powershell", "cmd",
                             "terminal", "install", "test"])
    if any(k in c_lower for k in ["&&", "command", "shell", "powershell", "cmd", "operator"]):
        if task_type in ["setup", "testing"] or is_command_prompt:
            score += 0.4

    if os.name == "nt":  # Windows
        if any(w in c_lower for w in ["windows", "powershell", "cmd", "winnt"]):
            score += 0.2
        if any(w in c_lower for w in ["sudo apt", "brew install", "darwin"]):
            score -= 0.3
    else:
        if any(w in c_lower for w in ["linux", "unix", "bash", "darwin", "sudo", "apt"]):
            score += 0.2
        if any(w in c_lower for w in ["powershell", "winget", "chocolatey"]):
            score -= 0.3

    # ── Historical feedback loop (SQLite) ─────────────────────────────────
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if os.path.exists(RAG_DB_PATH):
        try:
            conn = sqlite3.connect(RAG_DB_PATH)
            c = conn.cursor()
            c.execute("""
                SELECT status FROM context_item_feedback
                WHERE content_hash = ? AND task_type = ?
            """, (content_hash, task_type))
            rows = c.fetchall()
            conn.close()
            if rows:
                total = len(rows)
                successes = sum(1 for r in rows if r[0] == "success")
                ratio = successes / total
                if ratio >= 0.8:
                    score += 0.3
                elif ratio <= 0.4:
                    score -= 0.3
        except Exception:
            pass

    return max(score, 0.0)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_situational_multiplier(content: str, task_type: str, user_prompt: str = "") -> float:
    """
    Backward-compatible wrapper — returns a multiplier in [0, ~3].
    Kept so existing callers (orchestrator.py) don't break.
    """
    metadata = {}
    raw = _compute_pattern_score(user_prompt, content, metadata, task_type)
    # Normalize: raw score 0..4+ → multiplier where 1.0 = neutral
    return max(0.1, raw)


def score_and_filter_context(items: List[Dict], user_prompt: str, limit: int = 5) -> List[Dict]:
    """
    Score a list of retrieved context items using pattern-recognition.
    Items whose pattern score falls below 0.45 are treated as noise and dropped.
    Items from user_correction source are always kept regardless of score.
    """
    if not items:
        return []

    task_type = classify_task_type(user_prompt)
    scored_items = []

    for item in items:
        content = item.get("content", "")
        metadata = item.get("metadata") or {}
        base_score = item.get("base_score", 1.0)

        pattern_score = _compute_pattern_score(user_prompt, content, metadata, task_type)
        situational_score = base_score * pattern_score

        scored_item = item.copy()
        scored_item["situational_score"] = situational_score
        scored_item["task_type"] = task_type
        scored_items.append(scored_item)

    # Sort by pattern relevance
    scored_items.sort(key=lambda x: x["situational_score"], reverse=True)

    # Filter: keep items that meet the base quality floor.
    # The final 0.62 relevance cutoff is applied externally by the orchestrator.
    # Corrections get a reduced floor (0.30) since their concept-gated boost
    # already handles cross-domain filtering in _compute_pattern_score.
    def _should_keep(item: Dict) -> bool:
        score = item.get("situational_score", 0.0)
        meta  = item.get("metadata") or {}
        is_correction = (
            meta.get("source") == "user_correction"
            or meta.get("category") == "knowledge_correction"
        )
        floor = 0.30 if is_correction else 0.45
        return score >= floor

    filtered = [i for i in scored_items if _should_keep(i)]

    # Return top-limit results
    return filtered[:limit]


def record_context_feedback(injected_contents: List[str], user_prompt: str,
                            status: str, steps: int, duration: int):
    """Save feedback experience for all context contents injected in the prompt."""
    parent_dir = os.path.dirname(RAG_DB_PATH)
    if not injected_contents or (parent_dir and not os.path.exists(parent_dir)):
        return

    task_type = classify_task_type(user_prompt)
    timestamp = datetime.now().isoformat()

    try:
        conn = sqlite3.connect(RAG_DB_PATH)
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS context_item_feedback (
                id TEXT PRIMARY KEY DEFAULT (hex(randomblob(16))),
                content_hash TEXT,
                task_type TEXT,
                status TEXT,
                steps INTEGER,
                duration INTEGER,
                timestamp TEXT
            )
        ''')
        for content in injected_contents:
            if not content:
                continue
            content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            c.execute("""
                INSERT INTO context_item_feedback (content_hash, task_type, status, steps, duration, timestamp)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (content_hash, task_type, status, steps, duration, timestamp))
        conn.commit()
        conn.close()
    except Exception:
        pass
