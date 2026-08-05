---
name: mcp_server_development
description: Automatically learned guidelines for Mcp_Server_Development.
---

# Mcp_Server_Development Guidelines

## Learnt Guidelines
- Buffer streamed token output before rendering to preserve markdown/table formatting
- Verify checklist removals are actually reflected in code before proceeding

- Prefer non-streaming API calls for better display compatibility
- Test streaming vs non-streaming behavior in terminal environments

- Stream markdown output using console.print instead of raw stdout
- Implement lazy stop detection with tail-aware phrase scanning
- Add graceful error handling for missing function arguments

