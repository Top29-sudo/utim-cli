---
name: async-python-execution
description: Comprehensive guidelines for async python execution in CLI agents, covering stream handling, encoding, and process monitoring.
---

# Async Python Execution Guidelines

Comprehensive guidelines for async python execution in CLI agents, covering stream handling, encoding, and process monitoring.

## Process Monitoring and Health Checks
- Always implement active health checks and process monitoring when spawning subprocesses in async contexts, particularly when integrating with MCP servers or other external services. Without continuous monitoring, background processes can silently fail or hang, leaving the CLI in an inconsistent state where user requests appear to be processed but never complete. Use async polling loops with timeout mechanisms to check process status and implement graceful degradation when health checks fail.
- Implement explicit process state tracking using asyncio.Event or similar synchronization primitives to maintain visibility into subprocess lifecycle events. Track process startup, running, completion, and failure states separately to enable accurate busy status indicators in the terminal UI and prevent race conditions between concurrent async operations.

- Always implement health checks and monitoring for background processes spawned during async execution. Background processes can become zombie processes or hang indefinitely if not properly monitored, leading to resource leaks and unresponsive CLI agents.
- Use asyncio.create_subprocess_exec with proper process group management and implement timeout mechanisms for all subprocess operations. This ensures that long-running or stuck processes can be terminated cleanly without leaving orphan processes consuming system resources.

## File Encoding and Stream Handling

- Always explicitly specify encoding='utf-8' when performing file write operations in async contexts to prevent UnicodeDecodeError crashes across different platforms. Different operating systems have varying default encodings which can cause file operations to fail when the subprocess output contains Unicode characters.
- Handle subprocess output streams with proper encoding detection and error handling, using errors='replace' or errors='ignore' parameters when writing to files to gracefully handle encoding mismatches. This prevents crashes when processing output from external commands that may use different character encodings than the system default.

## Terminal Output and User Interface

- Ensure proper cursor positioning and visual gap management between user input and AI response in terminal output by adjusting display buffer and cursor positioning logic. Missing visual gaps due to improper cursor handling can make the CLI experience feel cramped and reduce readability of the interaction flow.
- Implement busy status indicators and footer content management when orchestrating request-response cycles in async contexts to provide visual feedback to users during background processing. This improves perceived performance and prevents users from interacting with an unresponsive interface while operations are in progress.

## Examples
```
# Process monitoring with health checks in async context
import asyncio
import aiofiles

async def safe_subprocess_write(filepath: str, content: str):
    """Write file with explicit encoding and health monitoring."""
    try:
        async with aiofiles.open(filepath, 'w', encoding='utf-8') as f:
            await f.write(content)
        return True
    except UnicodeDecodeError as e:
        print(f"Encoding error writing {filepath}: {e}")
        return False
    except Exception as e:
        print(f"Unexpected error: {e}")
        return False

# Monitor subprocess health with timeout
async def monitor_process(proc: asyncio.subprocess.Process, timeout: int = 30):
    """Monitor subprocess with active health checks."""
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        return proc.returncode == 0, stdout, stderr
    except asyncio.TimeoutError:
        proc.terminate()
        return False, None, b"Process timed out"
```
```
# Proper Live context with visual gap management
from rich.live import Live
from rich.console import Console
from rich.table import Table

console = Console()

with Live(console=console) as live:
    # User input section
    input_table = Table(title="User Input")
    input_table.add_column("Command", style="cyan")
    input_table.add_row("/analyze data.json")
    
    # Add visual gap
    console.print("\n")  # Explicit newline for visual separation
    
    # Processing indicator
    status_table = Table(title="Status")
    status_table.add_column("State", style="yellow")
    status_table.add_row("Processing...")
    
    live.update(input_table)
    await asyncio.sleep(0.5)  # Simulate processing
    live.update(status_table)
```
```
# BEFORE - Crash-prone implementation without encoding specification
import asyncio
import aiofiles

async def unsafe_write(task_id, content):
    async with aiofiles.open(f'task_{task_id}.md', 'w') as f:
        await f.write(content)  # UnicodeDecodeError risk on cross-platform

# AFTER - Safe implementation with explicit encoding
import asyncio
import aiofiles

async def safe_write(task_id, content):
    async with aiofiles.open(f'task_{task_id}.md', 'w', encoding='utf-8') as f:
        await f.write(content)
    # Handle encoding errors gracefully
    try:
        async with aiofiles.open(f'task_{task_id}.md', 'w', encoding='utf-8') as f:
            await f.write(content)
    except UnicodeDecodeError as e:
        # Log error and implement fallback encoding
        print(f"Encoding error: {e}. Using fallback encoding.")
        async with aiofiles.open(f'task_{task_id}.md', 'w', encoding='utf-8', errors='replace') as f:
            await f.write(content)
```
```
# BEFORE - No process monitoring
import asyncio

async def run_background_task(cmd):
    proc = await asyncio.create_subprocess_exec(*cmd)
    await proc.wait()  # No health check, can hang indefinitely

# AFTER - With process monitoring and health checks
import asyncio

async def run_monitored_task(cmd, timeout=30):
    try:
        proc = await asyncio.create_subprocess_exec(*cmd)
        try:
            await asyncio.wait_for(proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.terminate()
            await proc.wait()
            raise TimeoutError(f"Process {cmd} timed out after {timeout}s")
    except Exception as e:
        # Health check: verify process actually completed
        if proc.returncode is None:
            proc.kill()
            await proc.wait()
        raise e
```

```
# Correct subprocess execution with monitoring and encoding
import asyncio
import sys

async def safe_subprocess_run(command):
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(
            process.communicate(), timeout=30.0
        )
        return stdout.decode('utf-8', errors='replace'), process.returncode
    except asyncio.TimeoutError:
        process.kill()
        raise
    except UnicodeDecodeError as e:
        print(f"Encoding error: {e}", file=sys.stderr)
        return None, 1

# Usage in async loop
async def main():
    output, code = await safe_subprocess_run(['python', '--version'])
    print(output)
```

```
# Terminal cursor and gap management example
from rich.live import Live
from rich.console import Console
from rich.text import Text

console = Console()

with Live(console=console) as live:
    # Simulate processing with visible gap
    live.update(Text("Processing..."))
    await asyncio.sleep(1)
    # Clear busy status and show response with proper spacing
    live.update(Text(""))  # Clear busy indicator
    console.print("\n")  # Add visual gap
    console.print("[bold green]Response:[/] Here is your processed output")
```

## Core Guidelines

- Always specify explicit encoding (typically 'utf-8') when performing file write operations with subprocess or streaming contexts to prevent UnicodeDecodeError crashes across different platform environments. This prevents cross-platform failures that occur when default system encodings differ from the expected file content encoding.
- Implement process monitoring and health checks for all async subprocess operations to detect and handle hung or crashed processes before they block the entire async loop. Regular health checks ensure system stability when executing long-running or background processes.
- Maintain clear visual separation between user input and AI response by managing cursor positioning and busy status indicators in Live terminal contexts. This prevents visual confusion where the cursor appears to be still in a 'live' state when the system is actually processing or has already completed output.


## Error Handling & Edge Cases

- Handle UnicodeDecodeError exceptions proactively by catching encoding-related errors during file write operations and implementing fallback encoding strategies or error handling callbacks. When writing files from subprocess output, always wrap write operations in try-except blocks that can gracefully handle encoding mismatches.
- Implement proper async loop management with timeout mechanisms for subprocess operations to prevent indefinite blocking when processes hang or become unresponsive. Use asyncio.wait_for() with reasonable timeouts and implement cleanup handlers to terminate stuck processes.
- Ensure thread-safe operations between background threads and main terminal display by using proper synchronization primitives when updating display buffers or status indicators. The orchestrator must coordinate between live context background threads and terminal output to prevent race conditions in the busy status footer and cursor display.

## Encoding and Cross-Platform File Operations

- Always specify explicit encoding parameters (typically 'utf-8') when performing file write operations in subprocess contexts, especially when handling Markdown content or user-generated text that may contain non-ASCII characters. Failure to specify encoding leads to UnicodeDecodeError crashes on different platforms where the default encoding varies, particularly between development environments and production systems. Use the 'encoding' parameter in write_file operations and ensure subprocess environments inherit the correct locale settings.
- Handle encoding errors gracefully by implementing fallback mechanisms and explicit error handling around file operations in streaming contexts. When writing files during MCP server interactions or other subprocess communications, wrap file operations in try-except blocks that catch UnicodeDecodeError and provide meaningful error messages to the user rather than allowing silent failures or crashes.


## Visual Output and User Experience Management

- Maintain clear visual separation between user input and AI response in terminal output by managing cursor positioning and implementing appropriate visual gaps in Live context displays. Without proper spacing, the terminal can appear cluttered with the busy status footer overlapping with user content, making it difficult to distinguish between input prompts and generated responses. Use display_buf management techniques to ensure content is properly formatted and separated during markdown rendering operations.
- Coordinate background thread operations with foreground terminal updates to prevent race conditions in output display. When using Live context for real-time terminal output, ensure that cursor positioning, status footer updates, and content rendering are synchronized to avoid visual artifacts and maintain a clean user experience during request-response cycles.
