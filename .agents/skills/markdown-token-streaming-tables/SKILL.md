---
name: markdown-token-streaming-tables
description: Guidelines for preserving markdown formatting (especially tables) during token-by-token streaming responses in CLI chat displays.
---

# Markdown Token Streaming Tables Guidelines

Guidelines for preserving markdown formatting (especially tables) during token-by-token streaming responses in CLI chat displays.

## Core Guidelines

- Always buffer response chunks before applying markdown formatting to ensure tables and other markdown structures are properly rendered. Token-by-token display without buffering will break markdown table alignment and formatting, leading to corrupted output.
- Use a dedicated markdown formatter/parser in conjunction with a token streamer to separate content generation from display formatting. This pipeline approach ensures that markdown syntax is correctly interpreted before being sent to the output printer for display.

## Error Handling & Edge Cases

- When streaming responses containing incomplete markdown structures (e.g., a table header without rows), hold rendering until the full structure is received or implement a timeout-based flush mechanism to prevent indefinite buffering.
- Handle malformed or broken markdown in streamed responses by implementing a fallback plain-text rendering path that preserves readability even when table formatting fails.

## Examples

```
Correct pattern: TokenStreamer -> ContentBuffer -> MarkdownParser -> MarkdownFormatter -> DisplayRenderer -> OutputPrinter (ensures tables remain aligned during streaming)
```

```
Before (broken): Direct token streaming without buffering -> Markdown output shows misaligned tables
After (fixed): Buffered chunk processing with markdown pipeline -> Tables display correctly formatted
```
