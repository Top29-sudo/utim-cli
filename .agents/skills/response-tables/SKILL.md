---
name: response-tables
description: Guidelines for preserving markdown formatting during token-by-token streaming display of response tables and other content.
---

# Response Tables Guidelines

Guidelines for preserving markdown formatting during token-by-token streaming display of response tables and other content.

## Core Guidelines
- Buffer response chunks before applying markdown formatting to ensure table structures remain intact during token-by-token display. When streaming responses containing markdown tables, process the raw content through a markdown parser before outputting tokens to prevent premature rendering of table syntax.
- Implement a markdown formatter that handles table-specific syntax (pipes, dashes, alignment) separately from regular text processing. This ensures that table headers, separators, and rows are preserved exactly as written, maintaining proper column alignment and preventing broken table displays in the final output.

- Always buffer incoming response chunks before applying markdown formatting to ensure proper table alignment and header rendering. Token-by-token streaming can break markdown syntax if processed immediately, so accumulate content in a structured buffer that tracks table boundaries and formatting context.
- Implement a markdown formatter that processes the complete response before token streaming begins, using the formatted output as the source for chunk-by-chunk display. This ensures that table headers, pipes, and spacing remain intact while still providing the interactive typing effect to the user.

## Implementation Patterns

- Use a two-phase approach: first render the full response with proper markdown formatting, then stream the formatted result token-by-token using a response_chunks or content_buffer mechanism. This pattern appears consistently across implementations and prevents markdown corruption during streaming.
- Integrate a token_streamer with a markdown parser/formatter pipeline that can handle both plain text and complex table structures. The formatter should be applied before the token stream is initiated, ensuring that display_renderer or output_printer receives properly structured markdown.

## Examples
```
// Before: Broken table output during streaming
response_chunks = ['| Header1 | Header2 |\n', '| --- | --- |\n', '| Cell1 | Cell2 |']
// Streaming each chunk directly produces malformed tables

// After: Buffered processing with markdown preservation
chunk_buffer = []
for chunk in token_stream:
    chunk_buffer.append(chunk)
    if '\n' in chunk and is_table_complete(chunk_buffer):
        formatted = markdown_formatter.format_table(chunk_buffer)
        output_printer.stream_tokens(formatted)
```

```
// Phase 1: Format complete response
const formattedResponse = markdown_formatter.format(rawResponse);

// Phase 2: Stream formatted content
const chunks = response_chunks.create(formattedResponse);
while(chunks.hasMore()) {
  token_streamer.display(chunks.next());
}
```

## Error Handling & Edge Cases

- Handle incomplete table structures gracefully by deferring markdown rendering until table completion is detected through proper row termination. When a table is interrupted or malformed, fall back to displaying raw markdown syntax rather than attempting partial rendering that could produce garbled output.
- Validate table consistency by checking for matching column counts across rows and proper separator line formatting before applying markdown transformations. Edge cases like single-row tables, missing alignment indicators, or inconsistent pipe placement should trigger warning logs while still attempting to preserve the original table structure.
