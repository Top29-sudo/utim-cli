---
name: tool_call_parsing
description: Automatically learned guidelines for Tool_Call_Parsing.
---

# Tool_Call_Parsing Guidelines

## Learnt Guidelines
- Validate JSON arguments structure before tool invocation
- Implement fallback parsing for incomplete tool calls
- Detect and handle empty argument objects

- Always validate required positional arguments exist before function invocation
- Parse tool call arguments with strict key-value extraction to prevent missing parameters
- Verify argument names match function signatures exactly

