f = open('orchestrator.py', encoding='utf-8').read()
idx = f.find('class Orchestrator')
idx2 = f.find('def __init__', idx)
# Find mcp_tool_names references
import re
for m in re.finditer(r'mcp_tool_names', f):
    line = f[:m.start()].count('\n') + 1
    context = f[max(0,m.start()-80):m.end()+80]
    print(f"Line {line}: ...{repr(context)}...")