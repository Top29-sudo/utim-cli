---
name: software-architecture
description: Guidelines and design patterns for Python application architecture, focus on modularity, decoupling, state management, and reliable abstractions within the UTIM CLI system. Activate this skill when planning refactoring, adding major system modules, or designing component integrations.
---

# Software Architecture Guidelines

UTIM is a local-first development agent CLI consisting of complex, asynchronous modules (e.g. `blender_agent`, `orchestrator`, `vector_memory`, `mcp_client`). To prevent tight coupling and preserve stability, adhere to these structural conventions.

---

## 1. High-Level Core Design Principles

1. **Separation of Concerns**: Keep business logic out of presentation layers. UI prompts and formats go in TUI scripts; orchestration logic goes in `orchestrator.py`; persistence goes in `state.py` or `vector_memory.py`.
2. **Synchronous Core with Async I/O**: The terminal UI loop is typically synchronous/event-driven via `prompt_toolkit`, while background tasks, network queries, and MCP servers run asynchronously via `asyncio`. Use clear translation bridges (`asyncio.run_coroutine_threadsafe` or `asyncio.run`) where synchronous code triggers async workflows.
3. **Idempotence and Recovery**: Every state mutation (file changes, memory additions) should be rollbackable or self-healing. Maintain a stack/journal of modifications.

---

## 2. Dependency Injection and Registry Patterns

Avoid import loops by registering plugins, tools, or handlers dynamically rather than importing them directly in core loops.

### Registry Pattern Example
For dynamically loading and referencing tools:

```python
class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, name: str):
        def decorator(func):
            self._tools[name] = func
            return func
        return decorator

    def get_tool(self, name: str):
        if name not in self._tools:
            raise KeyError(f"Tool {name} is not registered.")
        return self._tools[name]

registry = ToolRegistry()

@registry.register("run_command")
def run_command(command: str):
    # command execution logic
    pass
```

---

## 3. Session State Management & Rollbacks

Session state must be serialized cleanly to JSON. Avoid referencing un-serializable objects (e.g., active sockets, file handles, coroutines) inside state models.

### State Snapshot Pattern
Use standard python `dataclasses` or `pydantic` models for structure, ensuring serialization capability:

```python
from dataclasses import dataclass, asdict, field
import json
from typing import List, Dict

@dataclass
class FileChangeSnapshot:
    filepath: str
    original_sha: str
    backup_path: str

@dataclass
class TurnState:
    turn_index: int
    user_prompt: str
    assistant_response: str
    file_changes: List[FileChangeSnapshot] = field(default_factory=list)

class SessionManager:
    def __init__(self, state_file: str):
        self.state_file = state_file
        self.turns: List[TurnState] = []

    def commit_turn(self, turn: TurnState):
        self.turns.append(turn)
        self.save_to_disk()

    def save_to_disk(self):
        serialized = [asdict(t) for t in self.turns]
        with open(self.state_file, "w") as f:
            json.dump(serialized, f, indent=2)
```

---

## 4. Asynchronous Boundary Rules

When interfacing sync code (like the standard user interaction loop) with async subprocesses (like MCP clients running JSON-RPC stdio transport):

1. **Avoid `asyncio.run()` in running event loops**: If a loop is already running, use `asyncio.create_task` or await directly.
2. **Graceful Subprocess Cleanup**: Always use `try...finally` blocks to terminate subprocesses, close stdio pipes, and release port bindings.
3. **Thread Safety**: Never write to shared memory across threads without a lock. Use `threading.Lock` or queue-based communication.

---

## 5. Single Source of Truth for Configuration

All configuration should load from a single central module (e.g. `config.py`).
- **Precedence Order**: Environment Variables > Local Config JSON (`.utim/config.json`) > Defaults.
- **Fail-Safe Initialisation**: If the configuration file is corrupted or missing, fall back to safe default parameters and trigger a non-blocking configuration repair wizard.
