"""
Micro-batchers for UTIM Server.

Two separate batching strategies:

1. ModelSpecificMicroBatcher (OpenRouter models)
   ─────────────────────────────────────────────
   Used as a concurrency gate for all OpenRouter-backed models.
   Groups requests by (model_id, is_reflection), flushes when:
     • Queue reaches max_batch_size
     • max_wait_seconds timeout expires
   The _batch_processor is a pass-through (actual inference happens
   in the OpenRouter streaming path after the gate releases).

2. LocalLLMBatchQueue (server-deployed Qwen GGUF only)
   ─────────────────────────────────────────────────────
   Proper batch inference queue for qwen/qwen2.5-1.5b-instruct running
   as a local llama_cpp.server subprocess.

   For is_reflection=True calls (brain sub-queries, summarisation):
     • Non-streaming — waits for full text response
     • Accumulates requests for max_wait_seconds (default 0.2s) or until
       n_slots requests are queued
     • On flush: fires ALL queued requests concurrently via
       call_local_completion_batch(), which is semaphore-gated to
       N_PARALLEL_SLOTS inside local_llm.py
     • Each caller's asyncio.Future is resolved with its own result

   For streaming calls (rare, non-reflection):
     • Goes through the semaphore-gated generate_local_completions()
       directly — no queuing needed since streaming can't be batched
       meaningfully without buffering the full response first.
"""

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger("utim.micro_batcher")


# ── 1. ModelSpecificMicroBatcher — OpenRouter concurrency gate ────────────────

class ModelSpecificMicroBatcher:
    """Concurrency gate grouped by (model_id, is_reflection).

    Flushes when:
      • Queue for a model reaches max_batch_size
      • max_wait_seconds timeout expires

    The processor_func is a pass-through; real inference happens in the
    OpenRouter streaming path after the gate releases the caller.
    """

    def __init__(self, max_batch_size: int = 4, max_wait_seconds: float = 0.2):
        self.max_batch_size  = max_batch_size
        self.max_wait_seconds = max_wait_seconds
        # Key: (model_id, is_reflection) → List[(payload, Future)]
        self.queues:      Dict[Tuple[str, bool], List[Tuple[Any, asyncio.Future]]] = {}
        self.flush_tasks: Dict[Tuple[str, bool], asyncio.Task] = {}
        self.lock = asyncio.Lock()

    async def submit(
        self,
        model_id: str,
        is_reflection: bool,
        payload: Any,
        processor_func: Callable,
    ) -> Any:
        loop      = asyncio.get_running_loop()
        future    = loop.create_future()
        queue_key = (model_id, is_reflection)

        async with self.lock:
            if queue_key not in self.queues:
                self.queues[queue_key] = []

            self.queues[queue_key].append((payload, future))
            current_size = len(self.queues[queue_key])

            logger.debug(
                f"[MICRO-BATCH] model='{model_id}' reflection={is_reflection} "
                f"queue={current_size}/{self.max_batch_size}"
            )

            if current_size >= self.max_batch_size:
                # Trigger A: batch full → flush immediately
                if queue_key in self.flush_tasks and not self.flush_tasks[queue_key].done():
                    self.flush_tasks[queue_key].cancel()
                self.flush_tasks[queue_key] = asyncio.create_task(
                    self._flush(queue_key, processor_func)
                )
            elif current_size == 1:
                # Trigger B: first item → start timeout timer
                self.flush_tasks[queue_key] = asyncio.create_task(
                    self._wait_and_flush(queue_key, processor_func)
                )

        return await future

    async def _wait_and_flush(self, queue_key: Tuple[str, bool], processor_func: Callable):
        try:
            await asyncio.sleep(self.max_wait_seconds)
            async with self.lock:
                if queue_key in self.queues and self.queues[queue_key]:
                    await self._flush(queue_key, processor_func)
        except asyncio.CancelledError:
            pass

    async def _flush(self, queue_key: Tuple[str, bool], processor_func: Callable):
        batch = self.queues.get(queue_key, [])[: self.max_batch_size]
        if queue_key in self.queues:
            self.queues[queue_key] = self.queues[queue_key][self.max_batch_size :]
            if not self.queues[queue_key]:
                del self.queues[queue_key]

        if not batch:
            return

        model_id = queue_key[0]
        payloads = [item[0] for item in batch]
        futures  = [item[1] for item in batch]

        logger.debug(f"[MICRO-BATCH] Flushing {len(payloads)} request(s) for '{model_id}'")

        try:
            results = await processor_func(model_id, payloads)
            for fut, res in zip(futures, results):
                if not fut.done():
                    fut.set_result(res)
        except Exception as exc:
            logger.error(f"[MICRO-BATCH] Flush failed for '{model_id}': {exc}")
            for fut in futures:
                if not fut.done():
                    fut.set_exception(exc)


# ── 2. LocalLLMBatchQueue — proper batch inference for Qwen GGUF ──────────────

class LocalLLMBatchQueue:
    """
    True batch inference queue for the server-deployed Qwen GGUF model.

    Only used for is_reflection=True (non-streaming) calls:
      brain sub-queries, experience summarisation, Qwen expansion tasks.

    Flow per flush cycle:
      1. Accumulate requests for up to max_wait_seconds (or until n_slots full)
      2. Pop up to n_slots requests from the front of the queue
      3. Call call_local_completion_batch() which fires them ALL concurrently
         (semaphore-gated inside local_llm.py to exactly N_PARALLEL_SLOTS)
      4. Resolve each caller's Future with its individual result
      5. If more items remain in the queue, immediately schedule another flush

    Streaming calls for qwen/qwen2.5-1.5b-instruct bypass this queue and go
    directly to generate_local_completions() which is semaphore-gated.
    """

    def __init__(self, n_slots: int = 4, max_wait_seconds: float = 0.2):
        self.n_slots          = n_slots
        self.max_wait_seconds = max_wait_seconds
        # List of (request_dict, asyncio.Future)
        self._queue:      List[Tuple[Dict, asyncio.Future]] = []
        self._flush_task: Optional[asyncio.Task]            = None
        self._lock = asyncio.Lock()

    async def submit(
        self,
        messages: List[Dict],
        max_tokens: int = 2048,
        temperature: float = 0.7,
    ) -> str:
        """
        Submit a non-streaming reflection request.
        Suspends the caller until the batch flushes and the result is ready.
        Returns the full generated text.
        """
        loop: asyncio.AbstractEventLoop = asyncio.get_running_loop()
        future: asyncio.Future = loop.create_future()
        request = {
            "messages":    messages,
            "max_tokens":  max_tokens,
            "temperature": temperature,
        }

        async with self._lock:
            self._queue.append((request, future))
            size = len(self._queue)
            logger.info(
                f"[LOCAL-LLM-BATCH] Queued request #{size} "
                f"(slots={self.n_slots}, wait={self.max_wait_seconds}s)"
            )

            if size >= self.n_slots:
                # Batch is full — flush immediately
                logger.info(f"[LOCAL-LLM-BATCH] Batch full ({size}), flushing now.")
                if self._flush_task and not self._flush_task.done():
                    self._flush_task.cancel()
                self._flush_task = asyncio.create_task(self._flush())
            elif size == 1:
                # First item — start the collection window timer
                logger.info(
                    f"[LOCAL-LLM-BATCH] First request, collecting for "
                    f"{self.max_wait_seconds}s."
                )
                self._flush_task = asyncio.create_task(self._wait_and_flush())

        return await future

    async def _wait_and_flush(self):
        try:
            await asyncio.sleep(self.max_wait_seconds)
            async with self._lock:
                if self._queue:
                    logger.info(
                        f"[LOCAL-LLM-BATCH] Timeout expired, flushing "
                        f"{len(self._queue)} request(s)."
                    )
                    await self._flush()
        except asyncio.CancelledError:
            pass

    async def _flush(self):
        """
        Pop one full batch, execute all requests concurrently via
        call_local_completion_batch(), resolve each Future individually.
        If more items remain after the flush, schedule the next flush immediately.
        """
        batch = self._queue[: self.n_slots]
        self._queue = self._queue[self.n_slots :]
        remaining   = len(self._queue)

        if not batch:
            return

        requests = [item[0] for item in batch]
        futures  = [item[1] for item in batch]

        logger.info(
            f"[LOCAL-LLM-BATCH] Executing {len(requests)} request(s) concurrently "
            f"on local GGUF model. ({remaining} remaining in queue)"
        )

        try:
            from .local_llm import call_local_completion_batch
            results: List[str] = await call_local_completion_batch(requests)

            for fut, text in zip(futures, results):
                if not fut.done():
                    fut.set_result(text)

        except Exception as exc:
            logger.error(f"[LOCAL-LLM-BATCH] Batch execution failed: {exc}")
            for fut in futures:
                if not fut.done():
                    # Don't crash callers — resolve with empty string
                    fut.set_result("")

        # If items accumulated while we were processing, flush them immediately
        if remaining > 0:
            logger.info(
                f"[LOCAL-LLM-BATCH] {remaining} item(s) still queued, "
                "scheduling next flush."
            )
            self._flush_task = asyncio.create_task(self._flush())


# ── Singletons ────────────────────────────────────────────────────────────────

# Gate for OpenRouter-backed models (pass-through processor)
global_micro_batcher = ModelSpecificMicroBatcher(
    max_batch_size=4,
    max_wait_seconds=0.2,
)

# True batch queue for the server-deployed Qwen GGUF model (reflection only)
local_llm_batch_queue = LocalLLMBatchQueue(
    n_slots=4,           # matches N_PARALLEL_SLOTS in local_llm.py
    max_wait_seconds=0.2,
)
