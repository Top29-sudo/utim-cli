---
name: mcp-server-development
description: Guidelines for developing and integrating Model Context Protocol (MCP) servers, troubleshooting stdio stream corruption, and implementing robust tool/resource handlers. Activate this skill when building new MCP servers or debugging connection/communication errors with existing servers.
---

# MCP Server Development and Integration Guide

This guide details best practices for building Model Context Protocol (MCP) servers and integrating them into the UTIM CLI environment. It addresses transport-layer reliability, schema validation, and error management.

---

## 1. The Stdio Transport Protocol (Rules & Constraints)

The most common transport layer is `stdio` (stdin/stdout). To avoid connection dropouts and protocol corruption:

1. **NEVER print debugging info to stdout**: If the server prints raw text or logs to standard output, the client parser will fail with a `ValidationError` (EOF or invalid JSON-RPC message).
2. **Log to stderr only**: Always redirect debug prints, errors, and diagnostic outputs to `sys.stderr` or use a standard logger configured to write to stderr.
3. **Handle stdin EOF gracefully**: When the parent process closes stdin, the server must shut down cleanly, terminating all child threads/processes.

### Safe Server Shell Wrapper (Standard Stdio Clean Interface)
If an external tool or library generates garbage print outputs, wrap the server process to filter stdout, allowing only valid JSON lines through:

```python
import sys
import json

def clean_stdio_loop():
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            # Validate if it is a JSON-RPC message
            data = json.loads(line)
            if "jsonrpc" in data:
                # Forward to actual server stdin or process it
                pass
        except json.JSONDecodeError:
            # Log junk to stderr
            print(f"[Wrapper Debug] Filtered non-JSON output: {line}", file=sys.stderr)
```

---

## 2. Implementing Tools in Python (MCP SDK)

Utilize the official Python `mcp` SDK to write type-safe tools. Let the SDK handle JSON-RPC message serialization.

```python
from mcp.server.fastmcp import FastMCP

# Create server instance
mcp = FastMCP("FileSystem Helper")

@mcp.tool()
def read_workspace_file(path: str) -> str:
    """
    Reads the content of a file within the workspace.
    
    Args:
        path: Absolute path to the file.
    """
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"Error reading file: {str(e)}"

if __name__ == "__main__":
    mcp.run()
```

---

## 3. Server Configuration Schema (`mcp.json`)

MCP configurations are stored in JSON. Ensure strict paths and environment replication:

```json
{
  "mcpServers": {
    "my-custom-server": {
      "command": "python",
      "args": ["-u", "C:/absolute/path/to/server.py"],
      "env": {
        "PYTHONUNBUFFERED": "1",
        "MY_API_KEY": "value"
      }
    }
  }
}
```

*Note: Always use `-u` (unbuffered) mode for Python servers to avoid delayed message deliveries.*

---

## 4. Connection Health Check & Self-Healing

When connecting to MCP servers, implement a handshake timeout and validator:

1. **Verify Stdio Handshake**: Send an initialization request and await `initialize` result within a 5-second timeout window.
2. **Handle Broken Pipes**: If a write fails with a broken pipe (`BrokenPipeError`), cleanly close the connection state, notify the user, and schedule a retry backoff loop.
3. **Diagnostic Report**: When a server fails to connect, probe the command execution manually (e.g. `subprocess.run` with simple flags) to inspect if the interpreter path or npm executable exists.
