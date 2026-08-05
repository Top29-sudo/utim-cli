"""
Diagnostic: how prompt_toolkit parses 'dim' in a style string.

Demonstrates the fix. Run this to confirm the corrected pattern works.
"""
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit import print_formatted_text

# WRONG — 'dim' is not a color name; prompt_toolkit will raise:
#   ValueError: Wrong color format 'dim'
try:
    print_formatted_text(HTML('<style fg="dim">wrong: dim as color</style>'))
except ValueError as e:
    print(f"Caught expected error: {e}")

# CORRECT — use 'dim' as a separate class token, OR use a real color.
# Option 1: a real color
print_formatted_text(HTML('<style fg="gray">correct: gray color</style>'))

# Option 2: 'dim' as a class attribute (comma-separated style tokens)
print_formatted_text(HTML('<style class="dim">correct: dim as a class</style>'))

# Option 3: combine color and the dim modifier
print_formatted_text(HTML('<style fg="gray" class="dim">correct: gray + dim</style>'))
