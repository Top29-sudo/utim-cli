---
name: response-token-by-tokenprinting
description: Comprehensive guidelines for response token-by-token printing with preserved markdown formatting and table structure.
---

# Response Token By Tokenprinting Guidelines

Comprehensive guidelines for response token-by-token printing with preserved markdown formatting and table structure.

## Core Guidelines
- Process response chunks into structured segments before token-by-token output to preserve markdown formatting integrity. This prevents raw token output from breaking multi-line elements like tables or headers, ensuring visual coherence in CLI displays. Implement a pre-processing step that identifies and groups logical content blocks (e.g., tables, lists) before streaming tokens.
- Prioritize token boundaries at natural markdown breakpoints (e.g., after table rows, before headers, or after code blocks) to maintain formatting during incremental display. Use delimiter-aware token splitting to avoid mid-element truncation, which can corrupt table columns or paragraph structure during partial output rendering.
- Process response chunks into structured segments before token-by-token printing to preserve markdown formatting, table structures, and visual hierarchy. Raw token-by-token printing of markdown content results in broken tables, lost headers, and degraded user experience.
- Implement chunk-based processing that identifies and preserves structural elements like headers, tables, code blocks, and list items before initiating token-by-token display. This ensures that complex formatted content maintains its intended appearance during streaming output.

- Always process response chunks into structured segments before token-by-token printing to preserve markdown headers, lists, and table formatting. This prevents visual corruption that occurs when raw tokens are printed sequentially without contextual awareness of markdown syntax boundaries.
- Implement chunk-aware token streaming by first parsing response content into semantic blocks (headers, paragraphs, tables) using markdown-aware segmentation. This ensures that visual indicators like emojis and decorative formatting remain aligned with their intended content structure during progressive display.

## Error Handling & Edge Cases
- Implement fallback rendering for malformed or incomplete markdown elements that may occur during partial token streaming. If a table's closing delimiter is missing in displayed tokens, append visual indicators (e.g., '...' or row continuation markers) to signal incomplete structure and prevent user confusion from truncated content.
- Handle ANSI escape sequences and whitespace normalization carefully during token processing to avoid terminal display artifacts. Pre-validate token streams for control characters that might interfere with markdown rendering, and buffer tokens until complete formatting units (e.g., full table rows) are assembled.
- Handle incomplete markdown structures gracefully by buffering partial content until structural completeness is achieved or a timeout occurs. This prevents malformed output when streaming terminates prematurely or network interruptions occur.
- Preserve visual indicators and decorative formatting elements (emojis, dividers, headers) by prioritizing them in chunk processing and ensuring they are not fragmented during token-by-token display. Users rely on consistent visual cues for comprehension and engagement.

- Handle incomplete markdown structures during streaming by implementing buffer recovery for unclosed code blocks, tables, or list items that span chunk boundaries. Use lookahead token analysis to detect and repair structural interruptions before displaying partial content to the user.
- Gracefully degrade formatting when markdown parsing fails by reverting to plain text token printing with optional visual separators. Maintain user experience continuity by preserving line breaks and spacing even when advanced markdown rendering cannot be applied mid-stream.

## Examples
```
// BEFORE (broken structure):
streamTokens('### Header\n| Col1 | Col2 |\n| A | B |'); // Output shows fragmented rows

// AFTER (chunk-processed):
const chunks = processMarkdownChunks(response);
for (const chunk of chunks) {
  for (const token of tokenize(chunk)) processTokenWithStructure(token);
}
```
```
const renderTokenStream = (rawResponse) => {
  const structuredChunks = groupByMarkdownElement(rawResponse);
  return structuredChunks.flatMap(chunk => 
    tokenize(chunk).map(token => 
      preserveWhitespace(token)
    )
  );
};
```
```
// Before: Raw token-by-token printing breaks markdown
const badPrint = (text) => {
  for(let char of text) process.stdout.write(char);
};

// After: Chunk processing preserves structure
const goodPrint = (chunks) => {
  const processed = processChunks(chunks);
  for(let chunk of processed) {
    displayTokens(chunk.content);
  }
};
```

```
// BEFORE (token-by-token without chunk processing):
// Output: | Col1 | Col2 |\n|------|------|
//         | Val1 | Val2 | (table structure lost)

// AFTER (chunk-processed token streaming):
const response = "## Header\n| Col1 | Col2 |\n|------|------|
| Val1 | Val2 |";
const chunks = parseMarkdownChunks(response);
for (const chunk of chunks) {
  for (const token of chunk.tokens) {
    process.stdout.write(token.content);
  }
}
// Output: Properly formatted markdown with visible table boundaries
```

```
if (detectMarkdownTable(tokens)) {
  const tableChunks = segmentTableStructure(tokens);
  for (const rowChunk of tableChunks) {
    renderRowWithAlignment(rowChunk);
  }
} else {
  fallbackToLinearPrinting(tokens);
}
```
