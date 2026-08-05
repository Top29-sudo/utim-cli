---
name: streaming-markdown-rendering
description: Ensure proper Markdown rendering and file generation during streaming responses in agent execution, especially when handling multi-line structures and file write operations.
---

# Streaming Markdown Rendering Guidelines

Ensure proper Markdown rendering and file generation during streaming responses in agent execution, especially when handling multi-line structures and file write operations.

## Core Guidelines

- Use batch Markdown rendering for multi-line structures to prevent fragmentation; avoid calling Markdown rendering functions per-line during streaming as this breaks tables and raw path strings in terminal output.
- Trace the complete streaming-to-display transformation path to ensure consistency between console output, file writes, and terminal presentation, particularly when dealing with Rich Markdown, sys.stdout, and live_printed flags.

## Error Handling & Edge Cases

- When agents stall during single HTML file generation, implement a multi-file approach with explicit recovery paths and verify both main and streaming code paths are synchronized across OpenAI and OpenRouter APIs.
- Fix parameter naming inconsistencies in functions like _extract_write_file_calls by using direct key access and ensuring filepath parameters match function signatures to prevent tool call parsing failures.

## Examples

```
// BEFORE: Fragmented multi-line Markdown during streaming
for line in response:
    self.console.print(Markdown(line))  # Breaks tables

// AFTER: Batch rendering preserves structure
full_response = ''.join(response)
self.console.print(Markdown(full_response))  # Renders tables correctly
```

```
// BEFORE: Inconsistent parameter access
file_path = call_args.get('filepath') or call_args.get('path')

// AFTER: Direct key access with fallback
self.file_path = call_args.get('file_path', call_args.get('filepath', ''))
```
