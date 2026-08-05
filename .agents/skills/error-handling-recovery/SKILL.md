---
name: error-handling-recovery
description: Comprehensive guidelines for error handling recovery in AI coding agents, focusing on tool execution failures, argument validation, and control flow corrections.
---

# Error Handling Recovery Guidelines

Comprehensive guidelines for error handling recovery in AI coding agents, focusing on tool execution failures, argument validation, and control flow corrections.

## Core Guidelines
- Always validate tool call arguments before execution to ensure all required parameters are present and correctly formatted. When parsing tool calls fails due to missing or incorrect keys (e.g., TypeError in write_file), implement strict argument validation in the orchestrator to catch issues before they propagate to runtime errors.
- Maintain strict focus on the primary error reported by the user; avoid pivoting to unrelated topics until the current issue is acknowledged and addressed. If a user repeatedly reports the same error, treat it as a signal requiring urgent resolution rather than abandoning it for secondary concerns like encoding issues.

- Always validate tool call arguments before execution by checking for required positional and keyword arguments. Missing arguments like 'path' in file operations cause TypeErrors that terminate workflows, so implement pre-execution checks using isinstance() and required parameter lists.
- Implement systematic recovery mechanisms for failed tool executions by capturing exceptions, logging detailed error context, and providing actionable hints to users. For example, when write_file fails due to argument parsing errors, return both the error message and reconstructed tool call syntax to enable user correction.

## Error Handling & Edge Cases
- Diagnose encoding errors by switching from CP1252 to Latin-1 (ISO-8859-1) when terminal operations fail on byte values in the 0x80-0x9F range. Use binary inspection tools like xxd or Python's enumerate in binary mode to identify non-UTF-8 characters causing persistent encoding crashes in text files.
- Trace dependency failures at runtime by examining pip's dependency resolver output or setup.py/pyproject.toml entry points, as static analysis of requirements.txt may miss runtime-triggered installations (e.g., pydantic being installed despite no direct pydantic code).

- Address control flow errors by auditing return statements in multi-step operations to prevent premature termination. Misplaced return statements in file read/write sequences cause logic failures that halt task completion, so use explicit error propagation with try/finally blocks.
- Establish comprehensive test coverage for edge cases in tool execution by simulating argument parsing failures, missing parameters, and invalid file paths. Test functions should verify both success paths and recovery scenarios, ensuring assertion patterns cover 100% of exception handling branches.

## Examples
```
Tool Call Argument Fix:

Before (TypeError):
```
write_file()
TypeError: write_file() missing required positional arguments
```

After (corrected):
```
write_file(path='output.html', content=generated_content)
```

Ensure all tool arguments are explicitly captured during parsing to prevent positional argument mismatches.
```
```
Encoding Resolution Example:

For CP1252 to Latin-1 conversion in Python:
```
import codecs

# Convert problematic file to Latin-1
with open('corrupted_file.txt', 'rb') as f:
    raw_bytes = f.read()

# Force Latin-1 encoding to handle 0x80-0x9F bytes
decoded_text = raw_bytes.decode('latin-1')

with open('fixed_file.txt', 'w', encoding='latin-1') as f:
    f.write(decoded_text)
```
```
```
Dependency Chain Investigation:

When encountering unexpected dependency installation (e.g., pydantic):
```
pip install --dry-run your_package  # Shows full dependency resolution
```

Check entry points in setup.py/pyproject.toml for hidden dependencies:
```python
# Check for post-install hooks or scripts
entry_points={...}
```
Static analysis of requirements.txt alone may miss runtime-triggered installations.
```
```
// Before: Missing argument validation causing TypeError
parser_tool → write_file (missing required 'content' key)

// After: Systematic verification approach
1. Parse user request into tool call arguments
2. Validate all required arguments are present and correctly formatted
3. Execute tool with verified arguments
4. Confirm execution succeeded before proceeding
5. Handle exceptions and provide recovery options

// Dependency resolution example:
# Static analysis: requirements.txt shows only 'requests'
# Runtime failure: pydantic unexpectedly installed
# Diagnostic: Check pip install --verbose output and examine setup.py entry_points
```
```
// Control flow error example:
# BEFORE: Misplaced return statement causing premature exit
if condition:
    return result
    edit_file()  # Never reached

# AFTER: Correct control flow with proper error handling
try:
    result = process_data()
    if not result:
        return None
    edit_file(result)
    return result
except Exception as e:
    handle_error(e)
    return None
```
```
Tool Call Parsing Fix:

# Before: Missing argument preservation
parsed_args = {"path": "/tmp/file.txt"}
# Missing 'content' key causes TypeError

tool_call(path="/tmp/file.txt")  # TypeError: missing required argument

# After: Complete argument validation
parsed_args = {"path": "/tmp/file.txt", "content": "data"}
validated_args = validate_required_keys(parsed_args, ["path", "content"])
if validated_args:
    write_file(**validated_args)
```
```
Dependency Resolution Debug:

# Before: Static analysis only
requires = ["requests", "flask"]  # Missing pydantic

# After: Trace actual installation
$ pip install mypackage --verbose
# Reveals: pydantic pulled in by package metadata
# Fix: Add pydantic to explicit requirements or handle transitive dependency
```

```
# Before: Missing required argument causes TypeError
write_file(path="output.txt", content="data")  # Missing 'content' key

# After: Pre-validation with recovery hint
def safe_write_file(path, content):
    if not path or not isinstance(content, str):
        return {"error": "Invalid arguments", "hint": "Provide 'path' (str) and 'content' (str)"}
    return write_file(path=path, content=content)

# Usage with error recovery
error_result = safe_write_file("", "test")
if "error" in error_result:
    print(f"Recovery hint: {error_result['hint']}")
```

```
# Before: Premature return in control flow
def process_files(file_list):
    for f in file_list:
        read_file(f)
        return True  # Exits after first file

# After: Proper control flow with error propagation

def process_files(file_list):
    results = []
    for f in file_list:
        try:
            content = read_file(f)
            results.append(content)
        except FileNotFoundError:
            return {"error": f"Missing file: {f}", "hint": "Verify file exists"}
    return {"success": True, "results": results}
```

## Tool Call Parsing and Validation

- Always validate that tool call arguments contain all required keys before execution. When parsing tool calls from text, ensure that argument keys are preserved and none are dropped during the transformation process. Missing required positional arguments will cause TypeError exceptions that halt task completion.
- Implement explicit argument validation in the orchestrator tool parser to catch missing or malformed arguments before they reach the tool execution layer. This includes checking for required function parameters and ensuring type consistency between parsed arguments and function signatures.


## Dependency Resolution and Installation

- When encountering runtime dependency failures (such as pydantic installation issues), trace the actual installation chain rather than relying solely on static analysis of requirements.txt. Static code analysis may miss runtime-triggered installations from package metadata, entry points, or installation scripts in setup.py/pyproject.toml.
- Always verify dependency resolution by examining pip's resolver output and checking for indirect dependencies that may be pulled in during package installation. Create virtual environments to isolate and reproduce dependency issues before implementing fixes.


## Control Flow and Return Statement Management

- Carefully manage return statements in file operations and tool execution functions to ensure proper control flow continuation. Misplaced return statements can cause premature function termination, preventing subsequent operations like file writes or additional processing steps from completing.
- Structure file system operations with explicit error handling and recovery mechanisms that allow for graceful degradation. Ensure that return statements only occur after all necessary operations have been completed successfully or after implementing proper rollback procedures.


## Exception Handling and Recovery Mechanisms

- Implement comprehensive exception handling around all tool executions and file system operations with specific catch blocks for expected error types. Provide meaningful error messages and recovery suggestions rather than simply propagating raw exceptions that may leave the system in an inconsistent state.
- Design recovery mechanisms that can restore system state or provide alternative execution paths when operations fail. This includes implementing assertion patterns to catch edge cases and ensuring test coverage for both success and failure scenarios.

## Root Cause Analysis & Diagnostic Approach

- When encountering TypeError or missing argument errors, trace the failure through the complete chain: user request → orchestrator → parser_tool → function arguments → tool execution. Examine the parser logic to identify where required argument keys are being dropped or transformed incorrectly during text-to-tool-call conversion. Verify that the parsed arguments match the actual function signature requirements before any tool execution attempt.
- For dependency-related runtime failures (like unexpected pydantic installations), trace the actual installation chain using pip's verbose dependency resolver output rather than relying solely on static requirements.txt analysis. Check entry points, hooks, and installation scripts in setup.py/pyproject.toml as these may trigger runtime dependencies not visible in static analysis. Document the gap between source code analysis and actual dependency resolution for future reference.


## Error Prevention & Validation

- Implement systematic verification before responding: verify file operations completed successfully, tool calls executed without errors, and all required arguments were preserved through the parsing chain. Use assertion patterns and exception handling to catch edge cases during development, and ensure test functions cover recovery mechanisms for failed tool executions. Never assume tool execution succeeded without explicit confirmation or error handling.
- Always validate control flow logic by checking return statement placement and ensuring edit_file and read_file operations don't introduce logic errors. Implement crash prevention requirements for file system operations by verifying write operations completed successfully and handling potential I/O exceptions. Structure code to fail gracefully and provide meaningful error messages when operations fail.


## Recovery Mechanisms & Workarounds

- When automated fixes fail or tool calls are rejected, acknowledge the failure explicitly and pivot to diagnostic questioning rather than repeating the same failed approach. Propose alternative solutions or workarounds when encountering parsing errors, such as manually constructing valid tool call arguments or using different tool invocation patterns. Document recovery paths for common failure modes to enable faster future resolution.
- Implement comprehensive exception handling around tool executions and file system operations to prevent crashes and enable graceful degradation. Create recovery mechanisms that can restore system state or provide fallback options when primary operations fail. Test recovery mechanisms specifically for edge cases that may not be covered by normal execution paths.
