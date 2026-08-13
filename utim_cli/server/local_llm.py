import os
import sys
import json
import logging
import threading
import requests
import asyncio
import subprocess
import time
import socket
from typing import AsyncGenerator, Dict, List, Any, Optional

logger = logging.getLogger("utim.server.local_llm")

MODEL_DRIVE_ID   = "194wS1PRYySnlpD8G6zYEyojHEMU4ksm_"
MODEL_PATH       = "/tmp/qwen2.5-1.5b-instruct-q4_k_m.gguf"
SERVER_PORT      = 8001
N_PARALLEL_SLOTS = 4   # must match --n-parallel passed to llama_cpp.server

# If we are on Windows (local dev), fall back to a local temp folder or project root
if os.name == "nt":
    from utim_cli.config import get_utim_dir
    MODEL_PATH = str(get_utim_dir() / "qwen2.5-1.5b-instruct-q4_k_m.gguf")

_download_lock = threading.Lock()
_model_instance = None
_model_lock = threading.Lock()
_server_process = None
_server_lock = threading.Lock()

def _is_port_in_use(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(('127.0.0.1', port)) == 0

def download_model_if_missing():
    """Download Qwen 2.5 1.5B Instruct GGUF model from Hugging Face (primary) or Google Drive (fallback) if it doesn't exist."""
    if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100 * 1024 * 1024:
        logger.info(f"Local model already exists at: {MODEL_PATH}")
        return

    with _download_lock:
        if os.path.exists(MODEL_PATH) and os.path.getsize(MODEL_PATH) > 100 * 1024 * 1024:
            return

        # Guard: makedirs crashes if dirname is empty string (e.g. bare filename)
        model_dir = os.path.dirname(MODEL_PATH)
        if model_dir:
            os.makedirs(model_dir, exist_ok=True)

        tmp_path = MODEL_PATH + ".tmp"
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0"})

        # --- Source 1: Hugging Face (Primary) ---
        HF_URL = "https://huggingface.co/Qwen/Qwen2.5-1.5B-Instruct-GGUF/resolve/main/qwen2.5-1.5b-instruct-q4_k_m.gguf"
        logger.info(f"Attempting to download model from Hugging Face: {HF_URL}...")
        try:
            response = session.get(HF_URL, stream=True, timeout=30)
            if response.status_code == 200:
                CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
                downloaded = 0
                with open(tmp_path, "wb") as f:
                    for chunk in response.iter_content(CHUNK_SIZE):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            if downloaded % (50 * 1024 * 1024) == 0:
                                logger.info(f"Downloaded {downloaded // (1024 * 1024)} MB from Hugging Face...")

                # Validate size
                if os.path.getsize(tmp_path) > 100 * 1024 * 1024:
                    os.replace(tmp_path, MODEL_PATH)
                    logger.info("Local model download from Hugging Face complete!")
                    return
                else:
                    logger.warning("Downloaded Hugging Face file is too small. Falling back to Google Drive...")
            else:
                logger.warning(f"Hugging Face download failed with status code {response.status_code}. Falling back to Google Drive...")
        except Exception as e:
            logger.warning(f"Hugging Face download failed: {e}. Falling back to Google Drive...")

        # Clear tmp file if any partial/broken download remains
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

        # --- Source 2: Google Drive (Fallback) ---
        logger.info(f"Downloading model {MODEL_DRIVE_ID} from Google Drive to {MODEL_PATH}...")
        try:
            # Step 1: hit the export URL; Drive may return a virus-warning HTML page
            # for files > ~40 MB instead of redirecting directly.
            URL = "https://docs.google.com/uc?export=download"
            response = session.get(URL, params={"id": MODEL_DRIVE_ID}, stream=True, timeout=30)

            # Step 2: Check if we got an HTML warning page (not the actual file).
            # Drive embeds a confirmation form with 'confirm' and 'uuid' tokens we must extract.
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                import re as _re
                html = response.content.decode("utf-8", errors="ignore")

                confirm_token = None
                uuid_token = None

                # Extract 'confirm' token from form hidden input or query param
                m_confirm = _re.search(r'name="confirm"\s+value="([^"]+)"', html)
                if m_confirm:
                    confirm_token = m_confirm.group(1)
                else:
                    m_confirm_qp = _re.search(r'confirm=([0-9A-Za-z_\-]+)', html)
                    if m_confirm_qp:
                        confirm_token = m_confirm_qp.group(1)

                # Extract 'uuid' token from form hidden input
                m_uuid = _re.search(r'name="uuid"\s+value="([^"]+)"', html)
                if m_uuid:
                    uuid_token = m_uuid.group(1)

                if confirm_token:
                    params = {
                        "id": MODEL_DRIVE_ID,
                        "export": "download",
                        "confirm": confirm_token
                    }
                    if uuid_token:
                        params["uuid"] = uuid_token
                    
                    response = session.get(
                        "https://drive.usercontent.google.com/download",
                        params=params,
                        stream=True,
                        timeout=30,
                    )
                else:
                    # Legacy fallback
                    response = session.get(
                        f"https://drive.google.com/uc?id={MODEL_DRIVE_ID}&export=download&confirm=t",
                        stream=True,
                        timeout=30,
                    )

            CHUNK_SIZE = 1024 * 1024  # 1 MB chunks
            downloaded = 0
            with open(tmp_path, "wb") as f:
                for chunk in response.iter_content(CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if downloaded % (50 * 1024 * 1024) == 0:
                            logger.info(f"Downloaded {downloaded // (1024 * 1024)} MB from Google Drive...")

            # Validate the downloaded file is at least 100 MB
            if os.path.getsize(tmp_path) < 100 * 1024 * 1024:
                logger.error(
                    f"Downloaded file is too small ({os.path.getsize(tmp_path)} bytes). "
                    "Likely got an HTML error page from Google Drive instead of the model. "
                    "Check that the Drive file is publicly shared."
                )
                os.remove(tmp_path)
                return

            os.replace(tmp_path, MODEL_PATH)
            logger.info("Local model download from Google Drive complete!")
        except Exception as e:
            logger.error(f"Failed downloading model: {e}")
            if os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception:
                    pass

def start_local_llm_server() -> bool:
    """No-op: local LLM background server is disabled in favor of fast remote models."""
    return True

def get_model_instance():
    """Fallback: Lazily load the Llama model directly into memory (single-threaded)."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance
        
    download_model_if_missing()
    
    with _model_lock:
        if _model_instance is not None:
            return _model_instance
            
        try:
            from llama_cpp import Llama
            logger.info(f"Loading GGUF model from {MODEL_PATH} into memory...")
            _model_instance = Llama(
                model_path=MODEL_PATH,
                n_ctx=32768,
                n_threads=int(os.environ.get("LOCAL_LLM_THREADS", "4")),
                verbose=False
            )
            logger.info("GGUF model loaded successfully!")
            return _model_instance
        except ImportError:
            logger.error("llama-cpp-python is not installed. Please install it on the server.")
            return None
        except Exception as e:
            logger.error(f"Failed to load GGUF model: {e}")
            return None

# ── Asyncio semaphore for concurrency control ─────────────────────────────────
# One slot per llama_cpp parallel slot. Prevents more than N_PARALLEL_SLOTS
# coroutines from hitting the subprocess simultaneously, keeping memory stable.
_llm_semaphore: Optional[asyncio.Semaphore] = None

def _get_semaphore() -> asyncio.Semaphore:
    """Lazily create the per-event-loop semaphore."""
    global _llm_semaphore
    if _llm_semaphore is None:
        _llm_semaphore = asyncio.Semaphore(N_PARALLEL_SLOTS)
    return _llm_semaphore


async def call_local_completion(
    messages: List[Dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> str:
    """
    Non-streaming single completion against the local GGUF model.
    Semaphore-gated: at most N_PARALLEL_SLOTS requests run concurrently.
    Returns the full generated text string. Used by LocalLLMBatchQueue.
    """
    sem = _get_semaphore()
    async with sem:
        # ── Primary: hit the llama_cpp.server subprocess (non-streaming) ──
        if _is_port_in_use(SERVER_PORT) or start_local_llm_server():
            try:
                import aiohttp
                payload = {
                    "messages":   messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "stream":     False,
                }
                timeout = aiohttp.ClientTimeout(total=120)
                async with aiohttp.ClientSession(timeout=timeout) as session:
                    async with session.post(
                        f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions",
                        json=payload,
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            return data["choices"][0]["message"].get("content") or ""
            except Exception as e:
                logger.warning(f"[LOCAL-LLM] Non-streaming server call failed: {e}. Trying in-process fallback.")

        # ── Fallback: direct in-process Llama() ───────────────────────────
        llm = get_model_instance()
        if not llm:
            logger.error("[LOCAL-LLM] No model available (server down + in-process load failed).")
            return ""
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                None,
                lambda: llm.create_chat_completion(
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    stream=False,
                ),
            )
            return result["choices"][0]["message"].get("content") or ""
        except Exception as e:
            logger.error(f"[LOCAL-LLM] In-process fallback failed: {e}")
            return ""


async def call_local_completion_batch(
    requests: List[Dict[str, Any]],
) -> List[str]:
    """
    Fire a list of non-streaming completion requests concurrently.
    Each request dict: {"messages": [...], "max_tokens": int, "temperature": float}.
    Semaphore inside call_local_completion() limits actual concurrency to
    N_PARALLEL_SLOTS regardless of batch size, so llama_cpp isn't overloaded.
    Returns responses in input order.
    """
    tasks = [
        call_local_completion(
            messages=r["messages"],
            max_tokens=r.get("max_tokens", 2048),
            temperature=r.get("temperature", 0.7),
        )
        for r in requests
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Replace exceptions with empty strings so one failure doesn't kill the batch
    return [
        r if isinstance(r, str) else ""
        for r in results
    ]

async def generate_local_completions(
    messages: List[Dict[str, Any]],
    max_tokens: int = 2048,
    temperature: float = 0.7,
) -> AsyncGenerator[str, None]:
    """Generate streaming completion chunks from the local Qwen GGUF model.
    For streaming user-facing calls only. Reflection/brain calls use
    call_local_completion() + LocalLLMBatchQueue instead.
    """
    # Try calling the parallelized local LLM server first (unblocks parallel requests)
    if _is_port_in_use(SERVER_PORT) or start_local_llm_server():
        try:
            import aiohttp
            payload = {
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "stream": True
            }
            async with aiohttp.ClientSession() as session:
                async with session.post(f"http://127.0.0.1:{SERVER_PORT}/v1/chat/completions", json=payload) as resp:
                    if resp.status == 200:
                        async for line in resp.content:
                            if not line:
                                continue
                            line_str = line.decode("utf-8").strip()
                            if line_str.startswith("data: "):
                                data_content = line_str[6:]
                                if data_content == "[DONE]":
                                    break
                                try:
                                    chunk_data = json.loads(data_content)
                                    delta = chunk_data["choices"][0].get("delta", {})
                                    content = delta.get("content")
                                    if content:
                                        yield content
                                except Exception:
                                    pass
                        return
        except Exception as e:
            logger.warning(f"Failed calling local LLM server: {e}. Falling back to in-process single-turn inference.")

    # Fallback to direct single-threaded execution inside uvicorn executor thread
    llm = get_model_instance()
    if not llm:
        logger.error("Local model fallback not available.")
        return

    try:
        loop = asyncio.get_running_loop()
        
        def run_sync_completion():
            return llm.create_chat_completion(
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                stream=True
            )
            
        stream = await loop.run_in_executor(None, run_sync_completion)
        
        for chunk in stream:
            if not chunk or "choices" not in chunk or not chunk["choices"]:
                continue
            delta = chunk["choices"][0].get("delta", {})
            content = delta.get("content")
            if content:
                yield content

    except Exception as e:
        logger.error(f"Error during local model inference: {e}")
        return
