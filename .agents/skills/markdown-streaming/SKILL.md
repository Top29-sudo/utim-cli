---
name: markdown-streaming
description: Automatically learned guidelines for Markdown Streaming.
---

# Markdown Streaming Guidelines

## Learnt Guidelines
- Buffer incoming token streams before markdown processing
- Apply markdown formatting to complete content chunks
- Preserve token-by-token UX while ensuring formatted output
- Separate collection and presentation phases

- Buffer incoming tokens into complete chunks before applying markdown formatting
- Apply markdown transformations to assembled content, not individual tokens
- Stream formatted output token-by-token after processing complete chunks

