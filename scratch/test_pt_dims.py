from prompt_toolkit import Application
from prompt_toolkit.layout import Layout, HSplit, VSplit, Window, FloatContainer, Float, ConditionalContainer
from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.widgets import TextArea
from prompt_toolkit.filters import Condition
from prompt_toolkit.widgets import CompletionsMenu

def main():
    input_field = TextArea(
        prompt=' ▶  ',
        multiline=True,
        completer=None,
        dont_extend_height=True,
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
    
    # Let's inspect the layout dimensions computed by prompt_toolkit
    from prompt_toolkit.layout.dimensions import LayoutDimension
    
    # We can fake a renderer or inspect size requirements
    # Let's write a simple script to check if the completion menu float is causing a large height reservation.
    # We can check floats:
    print("Floats defined:", len(layout.container.floats))
    
if __name__ == "__main__":
    main()
