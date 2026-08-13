# Tool Usage Guidelines: grep_search

When executing `grep_search` on any file or codebase directory:
1. **Multi-Keyword OR Searches**: If the `Query` contains pipe (`|`) symbols intended for alternation (e.g., `Laguna|Gemma|GPT`), you MUST explicitly set `"IsRegex": true`.
2. **Case Insensitivity**: Always set `"CaseInsensitive": true` unless exact case matching is explicitly required.
3. **Regex Escaping**: When searching for literal special characters (like `[`, `]`, `(`, `)`), set `"IsRegex": false` for exact literal matching or escape regex characters properly.
