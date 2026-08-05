---
name: llm-orchestration
description: Guidelines and patterns for LLM agent loops, tool-calling, context management, semantic token pruning, and reflection strategies inside the UTIM CLI framework. Activate this skill when coding AI orchestration logic, system prompt adjustments, tool dispatch, or memory-retrieval mechanisms.
---

# LLM Orchestration & Agent Loop Design

Agentic software relies on loops of text generation, parsing, tool calling, execution feedback, and self-correction. Keep prompt length optimized, tool payloads safe, and models resilient to execution failures.

---

## 1. The Core Agent Cycle (Think-Act-Observe)

Design agent loops as a robust machine. Avoid infinite loops by applying strict iteration limits and tracking repeated outputs:

```python
import time

def agent_loop(user_prompt: str, max_iterations: int = 10):
    conversation_history = [{"role": "system", "content": "..."}]
    conversation_history.append({"role": "user", "content": user_prompt})
    
    for i in range(max_iterations):
        # 1. Ask the model for next actions (thoughts & tool calls)
        response = call_llm(conversation_history)
        conversation_history.append({"role": "assistant", "content": response})
        
        # 2. Check if the model is done
        if "final_answer" in response:
            return extract_final_answer(response)
            
        # 3. Parse tool calls
        tool_calls = parse_tool_calls(response)
        if not tool_calls:
            # Fallback or prompt for clarification
            break
            
        # 4. Execute tool calls and feed results back to context
        observations = []
        for call in tool_calls:
            result = execute_tool(call.name, call.args)
            observations.append(result)
            
        conversation_history.append({
            "role": "tool_observation",
            "content": "\n".join(observations)
        })
        
        # Add a minor delay to prevent API rate limiting
        time.sleep(0.5)
        
    raise TimeoutError("Agent exceeded max iterations without returning final answer.")
```

---

## 2. Context Pruning & Token Budgeting

LLM context windows are finite. Massive prompt histories lead to high costs and slow response times. Implement smart context pruners:

1. **Keep System Message Fixed**: Never drop or modify the initial system identity prompt.
2. **Recent Turns Priority**: Always preserve the last $N$ turns (typically 4–6 messages) in full.
3. **Semantic Memory Compression (RAG)**: For older turns, extract structural summaries or index them into a local vector DB (like ChromaDB or SQLite-backed embeddings). Dynamically inject only highly-scored memories based on current query similarity.
4. **Buffer Pruning Strategy**: If the prompt length reaches 80% of the token limit, drop the middle section of the conversation history or replace long tool output text blocks with short summaries.

---

## 3. Tool Execution & Error Isolation

1. **Strict Type Coercion**: Ensure input arguments from the LLM match target type annotations. Coerce string outputs into integers/booleans where required.
2. **AST Linting/Syntax Checks**: For tools that write code, compile the code locally using Python's `ast.parse()` or lint checks *before* saving to disk to prevent syntax errors.
3. **No Raw Crashes**: Catch all exceptions inside tool definitions. Instead of letting a tool raise an uncaught exception (which halts the orchestrator process), return the error string back to the model:
   `"Tool failed with error: FileNotFoundError. Please verify path exist."`
4. **Self-Healing Loop**: If the tool observation indicates a test suite failure (`pytest` or `npm test`), prompt the LLM with the error output to trigger self-healing.

---

## 4. Reflexive Evaluation & Scoring

For complex or creative prompts:
- **Reflection Stage**: Request a brief evaluation turn where the LLM critiques its own plan before initiating file writes.
- **Situational Scoring**: Use smaller, fast models to categorize task complexity. Scale orchestrator logic dynamically: simple tasks use direct fast-paths; complex tasks use full multi-agent reflection loops.
- **Safety Gate**: Scan proposed commands against a database of destructive patterns (e.g. `rm -rf`, `format`, `del /q`). Prompt the user for manual confirmation if matches are found.
