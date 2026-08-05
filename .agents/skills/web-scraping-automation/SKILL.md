---
name: web-scraping-automation
description: Comprehensive guidelines for web scraping automation, covering source selection, data extraction strategies, and handling of dynamic content and rate limits.
---

# Web Scraping Automation Guidelines

Comprehensive guidelines for web scraping automation, covering source selection, data extraction strategies, and handling of dynamic content and rate limits.

## Source Selection and Data Validation

- Always verify whether static data sources (like local files, environment variables, or cached responses) are sufficient before attempting live web scraping, as demonstrated when exchange rate data was expected from a live source but a static source was provided; this prevents unnecessary network calls and improves reliability.
- When users request current data, explicitly confirm whether they need live/web data or if historical/cached data is acceptable, and clarify the scope of investigation to prevent unwanted research or scope creep that could lead to irrelevant results.

## Semantic Search and Embedding Integration

- Leverage embedding models and semantic search capabilities within scraping workflows to improve the quality and relevance of extracted content, as shown in the successful technical analysis that used UTIM and experience_gathering_system with embedding_model for high-quality results.
- Structure scraping tasks to integrate with semantic understanding systems by first querying codebases or knowledge bases with precise terms, then falling back to web search only when local resources are insufficient.

## Error Handling and Fallback Strategies

- Implement explicit error handling and fallback mechanisms when expected data sources fail or return unexpected formats, ensuring graceful degradation rather than complete task failure; always log and report discrepancies between expected and actual data sources.
- Maintain clear boundaries between investigation phases and execution phases—clarify task focus before beginning data gathering to prevent scope creep and ensure that all retrieved information aligns with the actual user requirements.

## Examples

```
// Before: Attempting live web scraping for exchange rate without confirming requirements
// After: Check static sources first, then query with precise terms
const rate = await getFromCache('exchange_rate') || await webSearch('current USD to EUR rate');

// Before: Unclear investigation scope leading to over-research
// After: Explicit task clarification
const investigationReport = await clarifyScope(project_res, user_request) 
  .then(scope => gatherEvidence(scope.terms)) 
  .catch(err => handleScopeAmbiguity(err));
```
