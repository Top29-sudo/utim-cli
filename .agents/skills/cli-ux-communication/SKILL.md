---
name: cli-ux-communication
description: Guidelines for designing, implementing, and troubleshooting Terminal User Interface (TUI) interactions in AI agent CLI tools, focusing on streaming output, markdown formatting, style consistency, and user preference handling.
---

# Cli Ux Communication Guidelines

Guidelines for designing, implementing, and troubleshooting Terminal User Interface (TUI) interactions in AI agent CLI tools, focusing on streaming output, markdown formatting, style consistency, and user preference handling.

## Core Guidelines
- Always respect user language preferences by checking for language hints in user input and adjusting response language accordingly. When a user provides a language directive (e.g., 'prefer French'), the assistant must switch to that language for all responses, conversation context included, to avoid communication mismatches that degrade user experience and trust.
- Ensure consistent formatting between streaming and non-streaming code paths by using the same markdown renderer and output mechanisms. Raw text should never appear in place of formatted markdown; always route both paths through the same formatting pipeline (e.g., Rich console.print with Markdown renderer) to maintain visual consistency.
- Properly manage the lifecycle of live context objects (_live_ctx) when rendering streaming content with markdown tables or formatting. Always check for _live_ctx existence before use and provide silent mode fallbacks to prevent crashes when context is improperly initialized or garbage collected during streaming loops.
- Ensure consistent Markdown formatting between streaming and non-streaming output paths by using a unified formatter (e.g., Rich console.print with Markdown renderer) to prevent raw text display. Streaming token-by-token output must apply the same formatting logic as batch HTML output, using tools like _live_ctx lifecycle management to sync rendering context.
- Implement style dictionary validation with CLASS_NAMES_RE pattern matching before applying prompt_toolkit styles to prevent async exceptions. Incorrect class naming in style_dict can cause UI crashes, so rigorously test style class names against valid identifier patterns before defining PTStyle configurations in dialogs or TUI components.
- Always respect and parse user language preferences early in the interaction flow, ensuring assistant responses and hints align with the detected language to prevent communication breakdowns. When language preference is ambiguous, explicitly ask the user or default to a neutral acknowledgment in their primary interaction language.
- Maintain consistent text formatting between streaming and non-streaming code paths by using a unified markdown formatter for all output, whether tokens are rendered live or displayed after completion. Ensure Raw text is never shown to users without proper markdown processing, especially in single-file HTML or TUI contexts.
- Always validate and sanitize style class names (e.g., 'class_names_re' patterns) before passing to prompt_toolkit's style_dict to prevent asyncio exceptions. Incorrect class naming conventions directly cause UI crashes and silent failures when rendering themed interfaces.
- Respect user language preferences and hints explicitly by aligning assistant responses with the detected 'language_preference' or 'user_hint' metadata. Failing to do so causes communication breakdowns and forces redundant clarification cycles.
- Always synchronize LLM response streaming with shell output to prevent display gaps. When using prompt_toolkit or Rich for rendering, ensure the input handler and output reader are properly coordinated through the orchestrator to maintain seamless user-AI interaction with minimal delay.
- Implement consistent markdown formatting across both streaming and non-streaming code paths. The token-by-token output in streaming mode must use the same Markdown renderer as HTML output to avoid raw text display inconsistencies in single-file HTML mode.
- Always ensure consistent formatting between streaming and non-streaming code paths by using a unified Markdown renderer that handles both token-by-token output and full content rendering, preventing raw text display issues that degrade user experience.
- Implement proper lifecycle management for streaming contexts (_live_ctx) with fallback mechanisms to silent mode when async exceptions occur, ensuring the application remains stable and doesn't silently terminate unexpectedly during user interactions.

- Ensure consistent formatting between streaming and non-streaming code paths by using a unified Markdown renderer that integrates with Rich console.print and sys.stdout.write. When streaming token-by-token output, preserve markdown formatting by routing through a centralized formatter rather than relying on raw text printing logic which can cause display inconsistencies in single-file HTML mode.
- Implement robust style dictionary handling by validating prompt_toolkit style_dict keys against expected class names (e.g., using CLASS_NAMES_RE patterns) before applying to UI components. Incorrect style class naming or malformed style dictionaries will trigger asyncio exceptions and crash the CLI, so always sanitize user-defined themes before applying to dialogs, windows, and widgets.

## Streaming Output Management
- Ensure markdown formatting is consistently applied in both streaming and non-streaming code paths by integrating the Markdown renderer with the token-by-token output loop. Raw text display without formatting breaks user comprehension and defeats the purpose of visual hierarchy.
- Implement proper lifecycle management for '_live_ctx' contexts to gracefully handle silent mode fallbacks and prevent memory leaks during streaming operations. Unmanaged contexts cause resource exhaustion and incomplete output rendering.

- When implementing AI response streaming, synchronize LLM response streamer with shell output readers to prevent display gaps between user input and response rendering. Use orchestrator patterns that coordinate between prompt_toolkit input handlers, TUI renderers, and live print flags to maintain seamless user-AI interaction with minimal delay.
- Manage _live_ctx lifecycle explicitly in streaming loops to handle fallback scenarios for markdown tables and ensure silent mode compatibility. Token-by-token output in streaming loops requires careful context management to prevent memory leaks and ensure proper cleanup when switching between planning mode and normal operation.

## UI Component Integration

- Fix scroll and scrollbar functionality in dialogs by properly initializing Window components with event_loop integration and vertical_scroll parameters. The usage dialog scroll error was resolved by ensuring prompt_toolkit scroll, scrollbar, and asyncio event_loop configurations align with the application's state transitions and user input handling.
- Correct UI crashes caused by style class mismatches by cross-referencing user-provided UI_theme dictionaries with UTIM's expected prompt_toolkit style_dict format. Apply defensive programming techniques to validate style keys before runtime to prevent exception stacks from malformed user configurations.

## Examples
```
// Before: Inconsistent streaming output causing raw text display
result = stream_tokens(query)
for token in result:
    print(token)  // Raw print, no markdown

// After: Consistent markdown formatting
from rich.console import Console
from rich.markdown import Markdown
console = Console()
result = stream_tokens(query)
markdown_buffer = ""
for token in result:
    markdown_buffer += token
    console.clear()
    console.print(Markdown(markdown_buffer))

---

// Before: Style dictionary causing asyncio crash
styles = {'class': 'error'}  // Incorrect class naming

// After: Proper PTStyle usage
from prompt_toolkit.styles import Style
style = Style.from_dict({'error': '#ff0000'})
```
```
// Before: Ignored language preference
user_input = "Bonjour, please proceed"  // French but English instruction
response = "Sure, I'll start working"  // English response

// After: Language-aware response
response = "Bien sûr, je vais commencer"  // French matching user's primary language
```
```
Before (crash-prone):
style_dict = {'invalid-class': '#FF0000'}
# After (safe):
import re
CLASS_NAMES_RE = re.compile(r'^[a-zA-Z_][\w-]*$')
validated = {k: v for k, v in style_dict.items() if CLASS_NAMES_RE.match(k)}

# Handle streaming markdown alignment:
before:
# Token loop: f.write(token) with no formatting
after:
# Middleware: formatted = markdown_formatter.format(token)
# Then: console.print(formatted, end='', update=True)
```
```
# Before (inconsistent streaming vs. static output):
print(response_text)

# After (unified markdown formatting):
from rich.console import Console
from rich.markdown import Markdown

console = Console()
console.print(Markdown(chunked_response_text))

# Language preference alignment example:
if user_preferred_lang == 'fr':
    hint_message = "Veuillez vérifier les paramètres de style."
else:
    hint_message = "Please check the style settings."
print(hint_message)
```
```
# Correct style_dict initialization pattern preventing crashes:
from prompt_toolkit.formatted_text import HTML

def safe_style_dict(style_dict):
    # Validate class names against CLASS_NAMES_RE pattern
    for key in style_dict:
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', key):
            raise ValueError(f"Invalid style class name: {key}")
    return style_dict

# Fix for markdown streaming:
from markdown import Markdown
from rich.console import Live

def stream_with_markdown(tokens):
    md = Markdown()
    with Live(md.render(''), refresh_per_second=4) as live:
        for token in tokens:
            md.feed(token)
            live.update(md.render())
```
```
# Language preference handling example:
user_hint = {"langue": "francaise"}
response = {"text": "Bienvenue dans l'interface CLI", "language": "fr"}

if user_hint.get("langue") != response["language"]:
    # Trigger language alignment protocol
    response = translate_response(response, user_hint["langue"])
```
```
Before: Streaming output displayed raw text while non-streaming used markdown formatting.
After: Unified markdown formatter applied to both paths:
```python
from markdown_formatter import Markdown
md = Markdown()
formatted = md.render(token_stream)
```
```
```
Before: UI crashed with asyncio exception due to style_dict mismatch.
After: Corrected style class naming:
```python
style_dict = {'class': 'error', 'name': 'prompt' }
# Ensure keys match prompt_toolkit style expectations
```
```
```
# Before: Raw text output due to inconsistent streaming formatting
# After: Unified Markdown rendering for both streaming and static content
from rich.console import Console
from rich.markdown import Markdown
console = Console()
console.print(Markdown("".join(streaming_tokens)))
```
```
# Before: Silent termination due to planning mode blocker
# After: Proper condition logic allowing message handling
if not self._in_planning_mode or self._allow_interrupt:
    await self._handle_user_message()
else:
    self._pause_streaming_and_wait()
```

```
# Before: Raw text streaming without markdown formatting
import sys
from rich.console import Console

console = Console()
for token in stream_tokens():
    sys.stdout.write(token)  # Breaks markdown tables and formatting

# After: Unified markdown-aware streaming
from rich.markdown import Markdown
from rich.print import print as rprint

for token in stream_tokens():
    if is_markdown_content(token):
        rprint(Markdown(token))  # Preserves formatting in streaming path
    else:
        sys.stdout.write(token)
```

```
# Style dictionary validation pattern
import re
CLASS_NAMES_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

def validate_style_dict(style_dict):
    for key in style_dict.keys():
        if not CLASS_NAMES_RE.match(key):
            raise ValueError(f"Invalid style class name: {key}")
    return {k: v for k, v in style_dict.items() if k.startswith('ui-')}

# Usage in dialog initialization
try:
    validated_styles = validate_style_dict(user_theme)
    dialog = Dialog(style=validated_styles)
except ValueError as e:
    logger.error(f"Theme validation failed: {e}")
    dialog = Dialog()  # Fallback to default styles
```

## Error Handling & Edge Cases
- Add explicit error handling for asyncio event loops in UI components like scroll bars and usage dialogs to prevent silent terminations. When embedding prompt_toolkit widgets in Window objects, ensure proper async lifecycle management and use fallback mechanisms (e.g., sync mode fallback) when event loop conflicts occur.
- Design self-healing UX by isolating component failures: e.g., recover from markdown table rendering errors in streaming loops by gracefully degrading to plain text output while logging the issue for async repair. Always include 'live_printed' flag management in orchestrators to enable recovery from display gaps between LLM response streamers and shell output readers.
- Correct style dictionary naming conventions in prompt_toolkit to prevent asyncio exceptions. When defining PTStyle or style_dict, ensure all class names match expected patterns and use CLASS_NAMES_RE for validation to avoid UI crashes from incorrect styling.
- Manage _live_ctx lifecycle properly with silent mode fallback for markdown tables and streaming content. Implement proper context management to handle table rendering during token-by-token output and provide graceful degradation when live rendering is not available.

- Correct prompt_toolkit style dictionary class naming conventions to prevent asyncio exceptions that crash the CLI, ensuring all style classes follow the proper format expected by the rendering engine.
- Fix UI scroll and keyboard navigation issues in dialogs by properly implementing event_loop integration with Window, scroll, and scrollbar components, enabling smooth user interaction with usage dialogs and other interface elements.

## UI Component Safety

- Fix scroll and scrollbar issues in TUI dialogs by correctly initializing 'Window' components with proper 'event_loop' and 'asyncio_dialog' configurations. Misaligned scroll parameters lead to frozen interfaces and inaccessible content.
- Synchronize LLM response streaming with shell output readers to prevent display gaps by using orchestrator patterns that manage stdout writes and prompt_toolkit input handlers concurrently.


## State Transition Integrity

- Remove planning mode blockers from condition logic that interfere with message handling during state transitions. Silent terminations occur when state-based conditions incorrectly block message processing pathways.
- Validate 'live_printed' flag states in orchestrators to ensure Rich console.print and sys.stdout.write operations are properly coordinated during streaming text output.

## Streaming Output & Async Handling

- Synchronize LLM response streaming with shell output readers to prevent display gaps or missing output by using shared context managers (e.g., `_live_ctx`) that manage lifecycle events across streaming loops. Implement proper backpressure and fallback mechanisms when streaming encounters errors or early termination conditions.
- Ensure asyncio event loops, prompt_toolkit scroll behaviors, and TUI window rendering are tightly integrated, especially in dialogs with vertical scroll, usage panels, or footer widgets; always test keyboard navigation and scrollbar interactions during async operations.


## Error Prevention & Self-Healing

- Validate all prompt_toolkit style class names and style dictionaries against known CLASS_NAMES_RE patterns before applying custom UI themes to prevent crashes from malformed keys or unsupported style attributes. Apply defensive fallbacks when user-defined themes conflict with expected UI component structures.
- Remove blocking condition logic that can cause silent termination or state transition failures in planning modes; ensure message handling and orchestrator request-response cycles gracefully handle interruptions, cancellations, and unexpected exit signals from the TUI renderer or Live output panels.

## Communication Protocols

- Respect user language preferences by dynamically selecting response templates and UI messages, adjusting localization parameters based on explicit user hints or system locale. Miscommunication due to ignored language directives (e.g., French vs English) can be resolved by maintaining a language_preference context variable and routing UI strings through a localization adapter.
- Implement state transition guards in planning modes to prevent silent blockages that terminate user sessions without feedback. Condition logic for mode transitions (e.g., from input to execution) must explicitly check for valid state preconditions and surface errors when blockers like missing response handlers are detected.


## UI Component Management

- Synchronize prompt_toolkit input handlers with LLM response streamers using coordinated stdout/read buffer management to eliminate display gaps. The shell output reader must align with token-by-token output streams using sys.stdout.write hooks and orchestrator flags to maintain consistent visual feedback between user typing and AI response rendering.
- Validate all UI theme dictionaries against prompt_toolkit's style_dict schema before application, ensuring keys like 'vertical_scroll' or 'footer_widget' match expected class names. Use try/except blocks around style application to catch KeyError exceptions and provide fallback UI themes for production stability.

## UI Rendering & State Management

- When implementing prompt_toolkit-based UI components, ensure style dictionaries use correct class naming conventions that match prompt_toolkit's expectations. Incorrect style class names (e.g., using 'style_dict' instead of proper PTStyle classes) will cause asyncio exceptions and crash the terminal interface.
- Implement proper scrollbar and navigation support for all dialog windows, especially usage dialogs and help screens. Users must have keyboard navigation (arrow keys, page up/down) through long content, and scrollbars should function correctly with both mouse and keyboard input.
- Handle planning mode state transitions carefully by ensuring condition logic doesn't block message handling inappropriately. Silent termination bugs often occur when planning mode blockers incorrectly prevent critical event processing; always verify that state transitions allow essential message flow.


## Streaming Synchronization

- Synchronize LLM response streaming with shell output reading to prevent display gaps and ensure tokens appear continuously. The streaming loop must coordinate between the AI response streamer and the stdout reader, using flags like live_printed to track display state and prevent race conditions.
- Implement proper asyncio event loop handling when embedding TUI windows or dialogs within larger applications. Window scroll and vertical_scroll components must be compatible with the running event_loop, and prompt_toolkit applications should not block the main asyncio flow.
- Route all output (both streaming and static) through consistent mechanisms using sys.stdout.write or Rich console.print rather than mixing direct prints with toolkit output. Inconsistent output routing causes display gaps and mixed formatting in the terminal.
