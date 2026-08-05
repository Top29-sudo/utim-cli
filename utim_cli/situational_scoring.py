"""
Situational Scoring & Context Experience Feedback System.

Calculates situational scores for RAG context items (rules, memories, experiences)
based on the active task type, workspace parameters, and past success/efficiency feedback.
"""

import os
import sqlite3
import hashlib
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from utim_cli.config import get_utim_dir
RAG_DB_PATH = os.path.join(get_utim_dir(), "rag_intelligence.db")


TASK_ANCHORS = {
    "testing": [
        "run pytest tests suite",
        "check the test coverage",
        "verify assertions and test cases",
        "debug failing test assertions"
    ],
    "ui_design": [
        "style landing page css html",
        "aesthetic design slides logo ui",
        "create slide layout visual colors",
        "presentation design slide styling"
    ],
    "setup": [
        "npm install tailwindcss packages",
        "pip install requirements setup",
        "build environment configurations dependency",
        "initialize workspace project structure setup"
    ],
    "refactoring": [
        "refactor helper method cleanly",
        "simplify codebase layout modular structure",
        "optimize functions and clean structure",
        "restructure code components cleanup"
    ],
    "file_edit": [
        "edit target file code write",
        "modify python file update replace",
        "write code block content edit",
        "create code file replace lines"
    ],
    "search": [
        "grep search codebase query find",
        "locate symbols functions search files",
        "find class usage search directory",
        "query codebase locate definition"
    ],
    "general": [
        "hello general chat prompt conversation",
        "explain conceptual question general help",
        "discuss ideas general answer"
    ]
}

_emb_fn = None
_anchor_embeddings = {}

# LITE MODE: skip loading sentence-transformers / MiniLM (heavy) and fall
# straight to heuristic classification. Set UTIM_LITE_MODE=1 on low-spec PCs.
import os as _os
_LITE = _os.environ.get("UTIM_LITE_MODE", "0") in ("1", "true", "TRUE", "yes")

def get_embedding_fn():
    global _emb_fn
    if _LITE:
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

def classify_task_type(user_prompt: str) -> str:
    """Classify the user's task prompt into a conceptual technical pattern using Hugging Face embeddings."""
    if not user_prompt:
        return "general"
        
    def fallback_heuristics(p: str) -> str:
        if any(k in p for k in ["test", "pytest", "unittest", "assert", "coverage", "check test"]):
            return "testing"
        elif any(k in p for k in ["install", "setup", "init", "npm", "pip", "build", "dependency", "package"]):
            return "setup"
        elif any(k in p for k in ["ui", "design", "aesthetic", "style", "css", "html", "color", "slide"]):
            return "ui_design"
        elif any(k in p for k in ["refactor", "clean", "simplify", "restructure"]):
            return "refactoring"
        elif any(k in p for k in ["edit", "modify", "update", "write", "replace", "create"]):
            return "file_edit"
        elif any(k in p for k in ["search", "find", "grep", "locate", "query"]):
            return "search"
        return "general"

    p_lower = user_prompt.lower()
    emb_fn = get_embedding_fn()
    if not emb_fn:
        return fallback_heuristics(p_lower)
        
    try:
        global _anchor_embeddings
        user_emb = emb_fn([user_prompt])[0]
        
        if not _anchor_embeddings:
            for task_type, anchors in TASK_ANCHORS.items():
                _anchor_embeddings[task_type] = emb_fn(anchors)
                
        best_type = "general"
        best_sim = -1.0
        
        for task_type, embs in _anchor_embeddings.items():
            for emb in embs:
                sim = cosine_similarity(user_emb, emb)
                if sim > best_sim:
                    best_sim = sim
                    best_type = task_type
                    
        if best_sim > 0.30:
            return best_type
        return fallback_heuristics(p_lower)
    except Exception:
        return fallback_heuristics(p_lower)


def get_situational_multiplier(content: str, task_type: str, user_prompt: str = "") -> float:
    """
    Calculate dynamic situational multiplier using neural conceptual pattern recognition.
    Measures abstract semantic pattern similarity between user prompt and experience rules.
    """
    if not content:
        return 1.0
        
    multiplier = 1.0
    c_lower = content.lower()
    emb_fn = get_embedding_fn()

    # 1. Neural Semantic Conceptual Pattern Matching (Dense Vector Cosine Distance)
    if emb_fn and user_prompt:
        try:
            vecs = emb_fn([user_prompt, content])
            sim = cosine_similarity(vecs[0], vecs[1])
            if sim > 0.35:
                # Dynamic neural pattern boost up to 2.5x based on conceptual similarity
                multiplier *= (1.0 + (sim * 1.6))
        except Exception:
            pass

    # 2. Command Chaining & Operator Pattern Boosting (e.g., && vs ; separation)
    is_command_prompt = any(w in user_prompt.lower() for w in ["run", "exec", "command", "shell", "powershell", "cmd", "terminal", "install", "test"])
    if any(k in c_lower for k in ["&&", "command", "shell", "powershell", "cmd", "operator", "separate"]):
        if task_type in ["setup", "testing"] or is_command_prompt:
            multiplier *= 2.2

    # 3. Operating System and Platform Pattern Boosting
    if os.name == "nt":  # Windows
        if any(w in c_lower for w in ["win32", "windows", "powershell", "cmd", "chcp", "nt"]):
            multiplier *= 1.25
        if any(w in c_lower for w in ["sudo apt", "brew install", "darwin", "termux"]):
            multiplier *= 0.5
    else:  # Linux / Unix / macOS
        if any(w in c_lower for w in ["linux", "unix", "bash", "darwin", "macos", "sudo", "apt", "brew"]):
            multiplier *= 1.25
        if any(w in c_lower for w in ["powershell", "winget", "chocolatey"]):
            multiplier *= 0.5

    # 4. Dynamic Success & Efficiency Feedback Experience Loop
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    if os.path.exists(RAG_DB_PATH):
        try:
            conn = sqlite3.connect(RAG_DB_PATH)
            c = conn.cursor()
            c.execute("""
                SELECT status, steps, duration 
                FROM context_item_feedback 
                WHERE content_hash = ? AND task_type = ?
            """, (content_hash, task_type))
            rows = c.fetchall()
            conn.close()
            
            if rows:
                total_runs = len(rows)
                successes = sum(1 for r in rows if r[0] == "success")
                success_ratio = successes / total_runs
                
                if success_ratio >= 0.8:
                    multiplier *= 1.25
                elif success_ratio <= 0.4:
                    multiplier *= 0.6
        except Exception:
            pass
            
    return multiplier


def score_and_filter_context(items: List[Dict], user_prompt: str, limit: int = 5) -> List[Dict]:
    """Scores a list of retrieved context items based on neural conceptual pattern matching."""
    if not items:
        return []
        
    task_type = classify_task_type(user_prompt)
    scored_items = []
    
    for item in items:
        content = item.get("content", "")
        base_score = item.get("base_score", 1.0)
        
        # Calculate neural pattern multiplier
        multiplier = get_situational_multiplier(content, task_type, user_prompt=user_prompt)
        situational_score = base_score * multiplier
        
        scored_item = item.copy()
        scored_item["situational_score"] = situational_score
        scored_item["task_type"] = task_type
        scored_items.append(scored_item)
        
    scored_items.sort(key=lambda x: x["situational_score"], reverse=True)
    return scored_items[:limit]


def record_context_feedback(injected_contents: List[str], user_prompt: str, status: str, steps: int, duration: int):
    """Save feedback experience for all context contents injected in the prompt."""
    parent_dir = os.path.dirname(RAG_DB_PATH)
    if not injected_contents or (parent_dir and not os.path.exists(parent_dir)):
        return
        
    task_type = classify_task_type(user_prompt)
    timestamp = datetime.now().isoformat()
    
    try:
        conn = sqlite3.connect(RAG_DB_PATH)
        c = conn.cursor()
        
        # Make sure feedback table exists
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
