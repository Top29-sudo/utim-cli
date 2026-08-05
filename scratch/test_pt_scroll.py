import time
import sys
from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.filters import Condition

def main():
    completer = WordCompleter(['/help', '/doctor', '/report'])
    
    input_field = TextArea(
        prompt=' ▶  ',
        multiline=True,
        completer=completer,
        complete_while_typing=Condition(lambda: input_field.text.startswith('/')),
        dont_extend_height=True,
    )
    
    # Simulate a completions menu like UTIM's
    from prompt_toolkit.widgets import CompletionsMenu
    
    layout = Layout(
        FloatContainer(
            content=HSplit([
                Window(content=FormattedTextControl("Header text line 1\nHeader text line 2")),
                input_field,
                Window(content=FormattedTextControl("Footer line 1\nFooter line 2"), height=2),
            ]),
            floats=[
                Float(
                    xcursor=True,
                    ycursor=True,
                    content=CompletionsMenu(max_height=8, scroll_offset=2),
                )
            ]
        ),
        focused_element=input_field
    )
    
    app = Application(
        layout=layout,
        full_screen=False,
    )
    
    print("Some printed lines 1")
    print("Some printed lines 2")
    print("Some printed lines 3")
    print("Some printed lines 4")
    print("Some printed lines 5")
    
    app.run()

if __name__ == "__main__":
    main()
