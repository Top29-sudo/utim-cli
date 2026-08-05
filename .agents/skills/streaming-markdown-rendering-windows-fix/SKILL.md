---
name: streaming-markdown-rendering-windows-fix
description: Ensures proper Markdown rendering and display handling during streaming responses in Windows environments, preventing raw output leakage and fragmented multi-line structures.
---

# Streaming Markdown Rendering Windows Fix Guidelines

Ensures proper Markdown rendering and display handling during streaming responses in Windows environments, preventing raw output leakage and fragmented multi-line structures.

## Core Guidelines

- Always use a dedicated Markdown renderer (like Rich's Markdown class) for streaming content instead of direct console output. This prevents raw Markdown syntax from being displayed to users and ensures proper formatting of tables, code blocks, and other structured content.
- Batch multi-line Markdown structures before rendering to prevent fragmentation during per-line processing. When streaming responses contain tables or formatted blocks, accumulate the complete structure before sending it to the renderer to maintain integrity.

## Error Handling & Edge Cases

- Implement explicit flush paths for the Markdown renderer after streaming completes to ensure all buffered content is properly displayed. Missing flush operations can result in truncated or missing output in the terminal.
- Maintain consistent parameter naming across all file I/O extraction functions, particularly ensuring 'filepath' is used instead of inconsistent aliases. This prevents extraction failures when parsing tool calls for file operations.

## Examples

```
// BEFORE: Raw Markdown leaked to console output
streaming_path.process_line('# Header\n| Col1 | Col2 |\n|------|------|\n', sys.stdout)

// AFTER: Proper Markdown rendering with buffering
markdown = Markdown('# Header\n| Col1 | Col2 |\n|------|------|\n')
renderer.render(markdown)
renderer.flush()
```

```
// BEFORE: Inconsistent parameter naming in extraction
_extract_write_file_calls(aliases={'filename': 'filepath'}, call_args)

// AFTER: Direct key access with correct parameter name
_extract_write_file_calls(call_args, 'filepath')
```
