---
name: streaming-markdown-rendering-fix
description: A comprehensive skill for fixing broken Markdown rendering in streaming code paths, particularly when multi-line structures like tables and raw path strings leak into terminal output.
---

# Streaming Markdown Rendering Fix Guidelines

A comprehensive skill for fixing broken Markdown rendering in streaming code paths, particularly when multi-line structures like tables and raw path strings leak into terminal output.

## Core Guidelines

- Always ensure Markdown rendering is applied consistently across both main execution paths and streaming paths. When implementing streaming functionality, identify all code branches where output is generated and verify that each branch applies the appropriate Markdown renderer before displaying content to the user.
- Avoid calling Markdown rendering functions on a per-line basis during streaming, as this fragments multi-line structures like tables into broken output. Instead, buffer streaming content until complete structures are received, then render the entire block as a single Markdown unit to preserve formatting integrity.

## File Operations & Parameter Consistency

- Maintain consistent parameter naming across related functions, especially when extracting file paths from tool calls. When refactoring functions like _extract_write_file_calls, update all dependent functions to use the same parameter names to prevent broken file reading operations and ensure proper key access for file path extraction.
- Implement robust error handling and recovery paths for file operations, including proper trace analysis when write_file operations fail. When debugging file reading functions, verify that the filepath parameter is correctly passed and that all access paths use direct key access rather than aliased or remapped keys that could lead to data loss.

## Debugging & Verification

- When encountering broken output in streaming paths, trace the exact transformation path from data reception to display. Use systematic path tracing to identify where Markdown rendering is skipped or where raw path strings leak into terminal output, and verify the fix by checking both primary and streaming code paths.
- Verify logic soundness through comprehensive path tracing and cross-reference fixes across related systems like OpenAI and OpenRouter APIs. After implementing a fix, ensure that all related streaming paths, including those in different API implementations, are updated consistently to prevent similar issues from appearing in other contexts.

## Examples

```
// BEFORE: Per-line Markdown calls fragment multi-line tables
for line in streaming_data:
    print(Markdown(line))  # Breaks table formatting

// AFTER: Buffer and render complete structures
buffered_content = []
for line in streaming_data:
    buffered_content.append(line)
if is_complete_structure(buffered_content):
    print(Markdown('\n'.join(buffered_content)))
```

```
// BEFORE: Inconsistent parameter naming breaks file operations
result = _extract_write_file_calls(aliases=call_args)
file_data = read_file(filepath=result['file_path'])  # May fail

// AFTER: Consistent key access prevents errors
result = _extract_write_file_calls(call_args)
file_data = read_file(filepath=result['filepath'])  # Reliable access
```
