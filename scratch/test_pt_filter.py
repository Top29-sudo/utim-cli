from prompt_toolkit.widgets import TextArea
from prompt_toolkit.filters import Condition

input_field = None

try:
    input_field = TextArea(
        complete_while_typing=Condition(lambda: input_field.text.startswith('/'))
    )
    print("Success! Created TextArea with Condition filter for complete_while_typing")
except Exception as e:
    print("Error:", e)
