import sys
import os
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.layout.menus import CompletionsMenu
from prompt_toolkit.filters import Condition
from prompt_toolkit.output import DummyOutput

import asyncio

async def test_render(with_conditional_float):
    input_field = TextArea(
        prompt=' ▶  ',
        multiline=True,
        dont_extend_height=True,
    )
    
    float_content = CompletionsMenu(max_height=8, scroll_offset=2)
    if with_conditional_float:
        float_content = ConditionalContainer(
            content=float_content,
            filter=Condition(lambda: input_field.buffer.complete_state is not None)
        )
        
    layout = Layout(
        FloatContainer(
            content=HSplit([
                input_field,
                Window(content=FormattedTextControl("Footer line 1\nFooter line 2"), height=2),
            ]),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=float_content,
                )
            ]
        ),
        focused_element=input_field
    )
    
    # We use DummyOutput so we can run it programmatically without terminal issues
    app = Application(
        layout=layout,
        output=DummyOutput(),
        full_screen=False,
    )
    
    # Fake terminal size: 80 columns, 10 lines
    class Size:
        def __init__(self, cols, rows):
            self.columns = cols
            self.rows = rows
    app.renderer.output.get_size = lambda: Size(80, 10)
    
    # Setup rendering
    app._app_loop = asyncio.get_running_loop()
    app.renderer.request_absolute_cursor_position = lambda: None
    
    # Render once
    app.renderer.render(app, layout)
    
    pref_h = layout.container.preferred_height(80, 10)
    print(f"with_conditional_float={with_conditional_float}")
    print(f"Preferred height: {pref_h.preferred}")
    print(f"Min height: {pref_h.min}")
    print(f"Max height: {pref_h.max}")

async def main_async():
    await test_render(False)
    await test_render(True)

if __name__ == "__main__":
    asyncio.run(main_async())
