import ast
import re

for p in ["utim_cli/orchestrator.py", "utim_cli/client_utils.py"]:
    ast.parse(open(p, encoding="utf-8").read())
print("PARSE OK")

# Test the ACTUAL regex from client_utils.py (both closing variants)
pat = re.compile(r"<\|?tool_call\|?>([\s\S]*?)<\|?/tool_call\|?>")

# pipe format: opening <|tool_call|>, closing <|/tool_call|>
content = 'Here is code <|tool_call|>{"name":"run_command","arguments":{"command":"ls"}}<|/tool_call|> done'
m = pat.search(content)
assert m, "pipe format not matched"
print("pipe match:", m.group(1)[:30])

# legacy format: <tool_call> ... </tool_call>
content2 = "plain <tool_call>{'name':'x'}</tool_call> end"
assert pat.search(content2), "legacy format not matched"
print("legacy match: OK")

# mixed weird format: <tool_call> ... <|/tool_call|>
content3 = "<tool_call>{'a':1}<|/tool_call|>"
assert pat.search(content3), "mixed format not matched"
print("mixed match: OK")

src = open("utim_cli/orchestrator.py", encoding="utf-8").read()
assert '_tool_xml_buf: list = [""]' in src, "buffer init missing"
assert "_looks_like_tool_xml" in src, "guard missing"
assert "final_content += _tool_xml_buf[0]" in src, "merge missing"
print("TOOL XML BUFFER WIRING OK")
