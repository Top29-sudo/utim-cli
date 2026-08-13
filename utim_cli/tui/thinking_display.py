'''
utim_cli/tui/thinking_display.py

Antigravity-style Thinking Stream display engine for UTIM CLI.
Supports multiple thinking blocks within a single response.
Each block renders as:
  ▸ Thought for 10s  (Ctrl+O to expand)
    The user is sharing an evaluation of UTIM CLI...

Pressing Ctrl+O expands/collapses all thought blocks.
'''
import time
from typing import Optional, List


class ThinkingBlock:
    """A single completed or in-progress reasoning block."""

    def __init__(self):
        self.start_time: float = time.time()
        self.end_time: Optional[float] = None
        self.thought_buffer: str = ""
        self.topic: str = ""

    def append(self, text: str):
        """Append chunk to thought buffer and update topic preview."""
        self.thought_buffer += text
        lines = [l.strip() for l in self.thought_buffer.splitlines() if l.strip()]
        if lines:
            top = lines[-1]
            if len(top) > 75:
                top = top[:72] + "..."
            self.topic = top

    def finish(self):
        """Mark this block as complete."""
        if not self.end_time:
            self.end_time = time.time()

    def duration_sec(self) -> int:
        end = self.end_time or time.time()
        return max(1, int(end - self.start_time))

    def render(self, expanded: bool = False) -> str:
        """Return Rich-formatted string for this block."""
        if not self.thought_buffer:
            return ""
        dur = self.duration_sec()
        arrow = "▾" if expanded else "▸"
        ctrl_hint = " [dim](Ctrl+O to collapse)[/dim]" if expanded else " [dim](Ctrl+O to expand)[/dim]"
        header = f"[cyan]{arrow} Thought for {dur}s[/cyan]{ctrl_hint}"

        if expanded:
            lines = self.thought_buffer.strip().splitlines()
            body_lines = [f"  [dim cyan]│ {l}[/dim cyan]" for l in lines]
            return f"{header}\n" + "\n".join(body_lines) + "\n"
        else:
            preview = self.topic or "Analyzing context and prompt..."
            return f"{header}\n  [dim]{preview}[/dim]\n"


class ThinkingStreamManager:
    """
    Manages state and rendering for all reasoning blocks in a single LLM turn.
    Supports multiple interleaved thinking → content → thinking cycles.
    """

    def __init__(self):
        self.blocks: List[ThinkingBlock] = []
        self.current_block: Optional[ThinkingBlock] = None
        self.expanded: bool = False

    def reset(self):
        """Reset for a new LLM call. Preserves expanded preference."""
        self.blocks = []
        self.current_block = None

    def start(self):
        """Start a new thinking block."""
        # Finish any currently open block first (safety)
        if self.current_block and not self.current_block.end_time:
            self.current_block.finish()
        block = ThinkingBlock()
        self.current_block = block
        self.blocks.append(block)

    def append(self, text: str):
        """Append chunk to current active block."""
        if self.current_block is None:
            self.start()
        self.current_block.append(text)

    def finish(self) -> Optional[ThinkingBlock]:
        """Finish current block. Returns the finished block."""
        if self.current_block and not self.current_block.end_time:
            self.current_block.finish()
        finished = self.current_block
        self.current_block = None
        return finished

    def toggle_expand(self) -> bool:
        """Toggle expanded state with Ctrl+O."""
        self.expanded = not self.expanded
        return self.expanded

    def render_block(self, block: ThinkingBlock) -> str:
        """Render a single block with current expand state."""
        return block.render(expanded=self.expanded)

    def render_all(self, console=None) -> str:
        """
        Render all completed blocks concatenated.
        Used for history re-render (Ctrl+O).
        """
        parts = []
        for block in self.blocks:
            rendered = block.render(expanded=self.expanded)
            if rendered:
                parts.append(rendered)
        return "\n".join(parts)

    # Legacy compat: render() used by _print_session_history
    def render(self, console=None) -> str:
        return self.render_all(console)

    @property
    def thought_buffer(self) -> str:
        """Legacy compat: combined buffer of all blocks."""
        return "\n".join(b.thought_buffer for b in self.blocks)

    @property
    def is_active(self) -> bool:
        return self.current_block is not None and not self.current_block.end_time


# Global singleton instance for the live prompt_toolkit session
global_thinking_manager = ThinkingStreamManager()
