---
name: async-python
description: Guidelines and patterns for asynchronous Python programming using asyncio. Covers event loops, subprocess task execution, thread boundaries, synchronization primitives, and safe cleanup loops. Activate this skill when coding concurrent features, network requests, or long-running shell command executions.
---

# Asynchronous Programming in Python (asyncio)

UTIM CLI heavily relies on concurrent task handling (MCP clients, shell command execution, live terminal rendering). This guide lists core async design rules.

---

## 1. Subprocess Execution & Stream Reading

When spawning external processes, use `asyncio.create_subprocess_exec` or `asyncio.create_subprocess_shell` rather than synchronous `subprocess.Popen` to prevent blocking the main event loop.

### Safe Subprocess Stderr/Stdout Monitoring
Ensure you read stdout and stderr concurrently to prevent buffer deadlocks:

```python
import asyncio

async def run_command_async(command: list[str]) -> tuple[str, str, int]:
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    
    # Read both streams concurrently without blocking
    stdout, stderr = await process.communicate()
    
    return (
        stdout.decode('utf-8', errors='replace'),
        stderr.decode('utf-8', errors='replace'),
        process.returncode
    )
```

---

## 2. Bridging Synchronous and Asynchronous Code

Never block the async event loop with long-running synchronous code (e.g. file system indexing, heavy CPU computations). Instead, run them inside a thread pool executor.

### Running Sync Functions in Threads
```python
import asyncio
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

def heavy_calculation(data):
    # Synchronous CPU-bound calculation
    import time
    time.sleep(2)
    return sum(data)

async def main_async_loop():
    loop = asyncio.get_running_loop()
    data = list(range(1000000))
    
    # Offload sync function to executor to avoid blocking the event loop
    result = await loop.run_in_executor(executor, heavy_calculation, data)
    print(f"Result: {result}")
```

---

## 3. Event Loop Safety & Re-entrance

1. **Avoid `asyncio.run()` nested inside coroutines**: This will crash with: `RuntimeError: asyncio.run() cannot be called from a running event loop`.
2. **Execute Coroutines from Synchronous Contexts**: Use `asyncio.run_coroutine_threadsafe` if calling from a background thread to schedule work on the main loop thread.
3. **Loop Detection**: Check if an event loop is running before trying to start one:
```python
def execute_coro(coro):
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
        
    if loop and loop.is_running():
        # Scheduled task execution on existing loop
        return asyncio.run_coroutine_threadsafe(coro, loop).result()
    else:
        # Run on a new event loop
        return asyncio.run(coro)
```

---

## 4. Graceful Cleanup and Timeouts

Always protect network calls and IPC commands with timeouts to prevent the CLI from hanging indefinitely.

### Using `asyncio.timeout` or `asyncio.wait_for`
```python
async def fetch_mcp_response(client, query: str):
    try:
        # Limit tool execution window to 10 seconds
        async with asyncio.timeout(10.0):
            response = await client.request_tool("run_search", {"query": query})
            return response
    except TimeoutError:
        return {"error": "Request timed out after 10.0 seconds."}
```
Always use `try...finally` to clean up tasks, close transport pipes, and release locks when a task is canceled.
