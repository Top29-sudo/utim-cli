"""
Semantic Vector Memory — Enhanced RAG using ChromaDB with all-MiniLM-L6-v2 embeddings.

This module provides semantic search capabilities that understand meaning and context,
going beyond exact keyword matching to find conceptually related code.
"""

import os
import warnings

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Suppress HuggingFace and SentenceTransformers warnings and progress bars
os.environ["HF_HUB_DISABLE_PROGRESS_BARS"] = "1"
os.environ["TRANSFORMERS_VERBOSITY"] = "error"
os.environ["TOKENIZERS_PARALLELISM"] = "false"

import logging
logging.getLogger("huggingface_hub").setLevel(logging.ERROR)
logging.getLogger("httpx").setLevel(logging.ERROR)
logging.getLogger("httpcore").setLevel(logging.ERROR)
logging.getLogger("sentence_transformers").setLevel(logging.ERROR)
logging.getLogger("chromadb").setLevel(logging.ERROR)
warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")
warnings.filterwarnings("ignore", module="huggingface_hub.*")

import json
import hashlib
from typing import List, Dict, Optional, Tuple

# Enable ChromaDB and Hugging Face vector memory embeddings
try:
    import chromadb
    import chromadb.utils.embedding_functions as embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False

import os as _os

def is_lite_mode() -> bool:
    """Dynamic check for lite mode status."""
    return _os.environ.get("UTIM_LITE_MODE", "0").lower() in ("1", "true", "yes")

# LITE MODE: when enabled, NEVER load ChromaDB / sentence-transformers /
# the MiniLM model (which is ~90MB and eats RAM on load). Vector memory
# degrades to the deterministic mock so the CLI stays light on low-spec PCs.
LITE_MODE = is_lite_mode()
if LITE_MODE:
    CHROMA_AVAILABLE = False


from utim_cli.config import get_utim_dir

# Vector DB path
VECTOR_DB_PATH = str(get_utim_dir() / "vector_db")
METADATA_FILE = str(get_utim_dir() / "vector_meta.json")


class DeterministicMockEmbeddingFunction:
    """Fallback 100% offline mock embedding function."""
    def __init__(self):
        pass

    @classmethod
    def name(cls) -> str:
        return "DeterministicMockEmbeddingFunction"

    def get_config(self) -> dict:
        return {}

    @staticmethod
    def build_from_config(config: dict) -> 'DeterministicMockEmbeddingFunction':
        return DeterministicMockEmbeddingFunction()

    def __call__(self, input: List[str]) -> List[List[float]]:
        import hashlib
        embeddings = []
        for text in input:
            words = text.lower().split()
            vec = [0.0] * 384
            if words:
                for w in words:
                    h = int(hashlib.md5(w.encode('utf-8')).hexdigest(), 16)
                    for i in range(4):
                        idx = (h >> (i * 8)) % 384
                        vec[idx] += 1.0
                norm = sum(x*x for x in vec) ** 0.5
                if norm > 0:
                    vec = [x / norm for x in vec]
            embeddings.append(vec)
        return embeddings


class VectorMemory:
    """
    Semantic vector memory using ChromaDB with Hugging Face embeddings (all-MiniLM-L6-v2).
    Provides meaning-based search over codebase content, task reflections, and experiences.
    """
    
    def __init__(self, collection_name: str = "codebase"):
        self.client = None
        self.collection = None
        self.embedding_func = None
        self.file_metadata: Dict[str, Dict] = {}
        self.collection_name = collection_name
        self.metadata_file = f".utim_tmp/vector_meta_{collection_name}.json"
        
        if not CHROMA_AVAILABLE:
            raise ImportError("chromadb is required for vector memory")
        
        self._initialize()
    
    def _initialize(self):
        """Initialize ChromaDB client and collection with Hugging Face embedding model."""
        os.makedirs(VECTOR_DB_PATH, exist_ok=True)
        
        # Create persistent client
        self.client = chromadb.PersistentClient(path=VECTOR_DB_PATH)
        
        # Initialize Hugging Face embeddings
        try:
            self.embedding_func = embedding_functions.DefaultEmbeddingFunction()
        except Exception:
            try:
                self.embedding_func = embedding_functions.SentenceTransformerEmbeddingFunction(model_name="all-MiniLM-L6-v2")
            except Exception:
                self.embedding_func = DeterministicMockEmbeddingFunction()
        
        # Get or create collection
        try:
            self.collection = self.client.get_collection(
                name=self.collection_name,
                embedding_function=self.embedding_func
            )
        except Exception:
            self.collection = self.client.create_collection(
                name=self.collection_name,
                embedding_function=self.embedding_func
            )
        
        # Load metadata
        self._load_metadata()
    
    def _load_metadata(self):
        """Load file metadata from disk."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file, "r", encoding="utf-8") as f:
                    self.file_metadata = json.load(f)
            except Exception as e:
                from utim_cli.logger import log_error
                log_error("vector_memory", f"Failed to load vector metadata from {self.metadata_file}. Resetting metadata.", e)
                self.file_metadata = {}
    
    def _save_metadata(self):
        """Save file metadata to disk."""
        os.makedirs(".utim_tmp", exist_ok=True)
        with open(self.metadata_file, "w", encoding="utf-8") as f:
            json.dump(self.file_metadata, f, indent=2)
    
    def _get_file_hash(self, filepath: str) -> str:
        """Get MD5 hash of file for change detection."""
        try:
            with open(filepath, "rb") as f:
                return hashlib.md5(f.read()).hexdigest()
        except Exception as e:
            from utim_cli.logger import log_warning
            log_warning("vector_memory", f"Failed to get file hash for {filepath}", e)
            return ""
    
    def sync_files(self, paths: List[str] = None, exclude_dirs: List[str] = None) -> int:
        """
        Sync files to vector database.
        
        Args:
            paths: List of file paths to sync. If None, walks current directory.
            exclude_dirs: Directories to exclude from sync.
        
        Returns:
            Number of files indexed/updated.
        """
        if exclude_dirs is None:
            exclude_dirs = {".git", "node_modules", "dist", "build", "__pycache__", ".venv", "venv", ".utim_tmp"}
        else:
            exclude_dirs = set(exclude_dirs)
        
        files_to_sync = []
        
        if paths:
            files_to_sync = [(p, os.path.getmtime(p)) for p in paths if os.path.exists(p)]
        else:
            for root, dirs, files in os.walk("."):
                dirs[:] = [d for d in dirs if d not in exclude_dirs]
                for f in files:
                    ext = os.path.splitext(f)[1].lower()
                    if ext in ['.png', '.jpg', '.jpeg', '.gif', '.mp4', '.pdf', '.zip', '.exe', '.dll', '.pyc']:
                        continue
                    p = os.path.join(root, f)
                    try:
                        files_to_sync.append((p, os.path.getmtime(p)))
                    except Exception as e:
                        from utim_cli.logger import log_warning
                        log_warning("vector_memory", f"Failed to get modification time for {p}", e)
        
        # Determine which files need updating
        to_index = []
        to_delete_ids = []
        
        current_hashes = {}
        for filepath, mtime in files_to_sync:
            file_hash = self._get_file_hash(filepath)
            current_hashes[filepath] = file_hash
            
            existing = self.file_metadata.get(filepath, {})
            if (filepath not in self.file_metadata or 
                existing.get("hash") != file_hash):
                to_index.append(filepath)
        
        # Check for deleted files
        for filepath in list(self.file_metadata.keys()):
            if filepath not in current_hashes:
                to_delete_ids.append(self.file_metadata[filepath].get("chunk_ids", []))
                del self.file_metadata[filepath]
        
        # Delete removed chunks
        if to_delete_ids:
            flat_ids = [id for ids in to_delete_ids for id in ids]
            if flat_ids:
                try:
                    self.collection.delete(ids=flat_ids)
                except Exception as e:
                    from utim_cli.logger import log_error
                    log_error("vector_memory", f"Failed to delete chunks from collection {self.collection_name}", e)
        
        # Index new/updated files
        indexed_count = 0
        new_metadata = {}
        
        for filepath in to_index:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()
                
                file_hash = self._get_file_hash(filepath)
                
                # Chunk content for better retrieval
                chunks = self._chunk_content(content, filepath)
                
                if chunks:
                    ids = []
                    documents = []
                    metadatas = []
                    
                    for i, (chunk_text, line_start, line_end) in enumerate(chunks):
                        chunk_id = f"{filepath}:{line_start}-{line_end}"
                        ids.append(chunk_id)
                        documents.append(chunk_text)
                        metadatas.append({
                            "filepath": filepath,
                            "line_start": line_start,
                            "line_end": line_end,
                            "chunk_index": i
                        })
                    
                    self.collection.add(
                        ids=ids,
                        documents=documents,
                        metadatas=metadatas
                    )
                    
                    new_metadata[filepath] = {
                        "hash": file_hash,
                        "mtime": os.path.getmtime(filepath),
                        "chunk_ids": ids
                    }
                    indexed_count += 1
                    
            except Exception as e:
                continue
        
        self.file_metadata.update(new_metadata)
        self._save_metadata()
        
        return indexed_count
    
    def _chunk_content(self, content: str, filepath: str, chunk_size: int = 1000, overlap: int = 100) -> List[Tuple[str, int, int]]:
        """
        Chunk content into overlapping segments with line number tracking.
        
        Returns list of (chunk_text, start_line, end_line) tuples.
        """
        lines = content.split('\n')
        chunks = []
        
        if len(lines) <= chunk_size:
            return [(content, 1, len(lines))]
        
        for i in range(0, len(lines), chunk_size - overlap):
            end = min(i + chunk_size, len(lines))
            chunk_text = '\n'.join(lines[i:end])
            chunks.append((chunk_text, i + 1, end))
        
        return chunks
    
    def query(self, query_text: str, n_results: int = 5, where: Dict = None) -> List[Dict]:
        """
        Query the vector database for semantically similar content.
        
        Args:
            query_text: Natural language query
            n_results: Number of results to return
            where: Optional metadata filter
        
        Returns:
            List of result dictionaries with content, filepath, and similarity info.
        """
        if not self.collection:
            return []
        
        try:
            results = self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
                where=where
            )
            
            formatted_results = []
            if results["documents"] and results["documents"][0]:
                for i, doc in enumerate(results["documents"][0]):
                    formatted_results.append({
                        "id": results["ids"][0][i] if results["ids"] else None,
                        "content": doc,
                        "filepath": results["metadatas"][0][i].get("filepath", ""),
                        "line_start": results["metadatas"][0][i].get("line_start", 0),
                        "line_end": results["metadatas"][0][i].get("line_end", 0),
                        "metadata": results["metadatas"][0][i],
                        "distance": results["distances"][0][i] if results["distances"] else None
                    })
            
            return formatted_results
            
        except Exception as e:
            return []
            
    def add_text(self, text_id: str, content: str, metadata: Dict = None) -> bool:
        """Add a single piece of text directly to the vector database."""
        if not self.collection:
            return False
            
        try:
            # Try to update if it exists
            existing = self.collection.get(ids=[text_id])
            if existing and existing["ids"]:
                self.collection.update(
                    ids=[text_id],
                    documents=[content],
                    metadatas=[metadata or {}]
                )
            else:
                self.collection.add(
                    ids=[text_id],
                    documents=[content],
                    metadatas=[metadata or {}]
                )
            return True
        except Exception as e:
            return False
    
    def get_stats(self) -> Dict:
        """Get statistics about the vector database."""
        if not self.collection:
            return {"total_files": 0, "total_chunks": 0}
        
        try:
            count = self.collection.count()
            return {
                "total_files": len(self.file_metadata),
                "total_chunks": count,
                "db_path": VECTOR_DB_PATH
            }
        except Exception as e:
            from utim_cli.logger import log_error
            log_error("vector_memory", f"Failed to get stats for collection {self.collection_name}", e)
            return {"total_files": 0, "total_chunks": 0}


# Global instance
_vector_memory: Optional[VectorMemory] = None
_experiences_memory: Optional[VectorMemory] = None
_skills_memory: Optional[VectorMemory] = None

# Sub-agent global instances
_project_res_experiences: Optional[VectorMemory] = None
_project_res_skills: Optional[VectorMemory] = None
_plan_project_experiences: Optional[VectorMemory] = None
_plan_project_skills: Optional[VectorMemory] = None
_web_search_experiences: Optional[VectorMemory] = None
_web_search_skills: Optional[VectorMemory] = None
_generate_image_experiences: Optional[VectorMemory] = None
_generate_image_skills: Optional[VectorMemory] = None

# Time memory global instance
_time_memory: Optional[VectorMemory] = None
_user_memories: Optional[VectorMemory] = None

def get_vector_memory() -> VectorMemory:
    """Get or create the global vector memory instance for the codebase."""
    global _vector_memory
    if _vector_memory is None:
        try:
            _vector_memory = VectorMemory(collection_name="codebase")
        except ImportError:
            pass
    return _vector_memory

def get_experiences_memory() -> VectorMemory:
    """Get or create the global vector memory instance for the experiences."""
    global _experiences_memory
    if _experiences_memory is None:
        try:
            _experiences_memory = VectorMemory(collection_name="experiences")
        except ImportError:
            pass
    return _experiences_memory

def get_skills_memory() -> VectorMemory:
    """Get or create the global vector memory instance for skills/rules."""
    global _skills_memory
    if _skills_memory is None:
        try:
            _skills_memory = VectorMemory(collection_name="skills")
        except ImportError:
            pass
    return _skills_memory

# Sub-agent getters
def get_project_res_experiences_memory() -> VectorMemory:
    """Get or create the experiences vector memory instance for the project_res sub-agent."""
    global _project_res_experiences
    if _project_res_experiences is None:
        try:
            _project_res_experiences = VectorMemory(collection_name="project_res_experiences")
        except ImportError:
            pass
    return _project_res_experiences

def get_project_res_skills_memory() -> VectorMemory:
    """Get or create the skills vector memory instance for the project_res sub-agent."""
    global _project_res_skills
    if _project_res_skills is None:
        try:
            _project_res_skills = VectorMemory(collection_name="project_res_skills")
        except ImportError:
            pass
    return _project_res_skills

def get_plan_project_experiences_memory() -> VectorMemory:
    """Get or create the experiences vector memory instance for the plan_project sub-agent."""
    global _plan_project_experiences
    if _plan_project_experiences is None:
        try:
            _plan_project_experiences = VectorMemory(collection_name="plan_project_experiences")
        except ImportError:
            pass
    return _plan_project_experiences

def get_plan_project_skills_memory() -> VectorMemory:
    """Get or create the skills vector memory instance for the plan_project sub-agent."""
    global _plan_project_skills
    if _plan_project_skills is None:
        try:
            _plan_project_skills = VectorMemory(collection_name="plan_project_skills")
        except ImportError:
            pass
    return _plan_project_skills

def get_web_search_experiences_memory() -> VectorMemory:
    """Get or create the experiences vector memory instance for the web_search sub-agent."""
    global _web_search_experiences
    if _web_search_experiences is None:
        try:
            _web_search_experiences = VectorMemory(collection_name="web_search_experiences")
        except ImportError:
            pass
    return _web_search_experiences

def get_web_search_skills_memory() -> VectorMemory:
    """Get or create the skills vector memory instance for the web_search sub-agent."""
    global _web_search_skills
    if _web_search_skills is None:
        try:
            _web_search_skills = VectorMemory(collection_name="web_search_skills")
        except ImportError:
            pass
    return _web_search_skills

def get_generate_image_experiences_memory() -> VectorMemory:
    """Get or create the experiences vector memory instance for the generate_image sub-agent."""
    global _generate_image_experiences
    if _generate_image_experiences is None:
        try:
            _generate_image_experiences = VectorMemory(collection_name="generate_image_experiences")
        except ImportError:
            pass
    return _generate_image_experiences

def get_generate_image_skills_memory() -> VectorMemory:
    """Get or create the skills vector memory instance for the generate_image sub-agent."""
    global _generate_image_skills
    if _generate_image_skills is None:
        try:
            _generate_image_skills = VectorMemory(collection_name="generate_image_skills")
        except ImportError:
            pass
    return _generate_image_skills

def get_time_memory() -> VectorMemory:
    """Get or create the vector memory instance for time tracking and performance history."""
    global _time_memory
    if _time_memory is None:
        try:
            _time_memory = VectorMemory(collection_name="time_memory")
        except ImportError:
            pass
    return _time_memory

# Global reflection memory instance
_reflections_memory: Optional[VectorMemory] = None

def get_reflections_memory() -> VectorMemory:
    """Get or create the global vector memory instance for task reflections."""
    global _reflections_memory
    if _reflections_memory is None:
        try:
            _reflections_memory = VectorMemory(collection_name="reflections")
        except Exception:
            pass
    return _reflections_memory

def warmup_embedding_model() -> bool:
    """
    Eagerly load the Hugging Face all-MiniLM-L6-v2 embedding model into memory.
    Call this at startup in a background thread so the first real encode is instant.
    Returns True if model was successfully loaded, False otherwise.
    """
    if is_lite_mode():
        return False
    try:
        vm = get_reflections_memory()

        if vm and vm.embedding_func:
            # Encode a dummy string — this forces the ONNX/SentenceTransformer
            # model weights to be downloaded (if not cached) and loaded into RAM.
            _ = vm.embedding_func(["utim warmup ping"])
            return True
    except Exception:
        pass
    # Also try to pre-warm situational scoring's shared embedding function
    try:
        from utim_cli.situational_scoring import get_embedding_fn
        fn = get_embedding_fn()
        if fn:
            _ = fn(["utim warmup ping"])
    except Exception:
        pass
    return False

def store_reflection(content: str, category: str = "general_reflection", task_prompt: str = "") -> bool:
    """Store a reflection or learned insight into the Hugging Face Reflection Vector DB."""
    vm = get_reflections_memory()
    if not vm:
        return False
    import uuid
    from datetime import datetime
    text_id = f"refl_{uuid.uuid4().hex[:12]}"
    return vm.add_text(
        text_id=text_id,
        content=content,
        metadata={
            "category": category,
            "timestamp": datetime.now().isoformat(),
            "task_prompt": task_prompt[:150]
        }
    )

def fetch_relevant_experiences(query_text: str, top_k: int = 2) -> List[Dict]:
    """
    Fetch semantically relevant reflections and learned rules using Hugging Face embeddings.
    Applies situational parameter scoring to prioritize operational rules (e.g. command operators) matching the task.
    """
    results = []
    # 1. Query reflections vector collection
    vm_ref = get_reflections_memory()
    if vm_ref:
        res = vm_ref.query(query_text=query_text, n_results=5)
        results.extend([r for r in res if r.get("distance") is None or r.get("distance") < 1.2])
        
    # 2. Query general experiences vector collection
    vm_exp = get_experiences_memory()
    if vm_exp:
        res = vm_exp.query(query_text=query_text, n_results=5)
        results.extend([r for r in res if r.get("distance") is None or r.get("distance") < 1.2])
        
    # Deduplicate by content
    seen = set()
    unique_results = []
    for item in results:
        text = item.get("content", "").strip()
        if text and text not in seen:
            seen.add(text)
            # Invert distance into base_score (closer distance = higher score)
            dist = item.get("distance")
            item["base_score"] = 1.0 / (1.0 + dist) if dist is not None else 1.0
            unique_results.append(item)
            
    # Apply situational scoring and filtering
    try:
        from utim_cli.situational_scoring import score_and_filter_context
        scored_results = score_and_filter_context(unique_results, query_text, limit=top_k)
        return scored_results
    except Exception:
        return unique_results[:top_k]

def reset_vector_memory():
    """Reset the global vector memory instances."""
    global _vector_memory, _experiences_memory, _skills_memory, _reflections_memory
    global _project_res_experiences, _project_res_skills, _plan_project_experiences, _plan_project_skills, _web_search_experiences, _web_search_skills, _generate_image_experiences, _generate_image_skills
    global _time_memory, _user_memories
    _vector_memory = None
    _experiences_memory = None
    _skills_memory = None
    _reflections_memory = None
    _project_res_experiences = None
    _project_res_skills = None
    _plan_project_experiences = None
    _plan_project_skills = None
    _web_search_experiences = None
    _web_search_skills = None
    _generate_image_experiences = None
    _generate_image_skills = None
    _time_memory = None
    _user_memories = None