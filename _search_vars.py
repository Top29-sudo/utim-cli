import re
data = open('utim_cli/orchestrator.py', encoding='utf-8').read()
for var in ['_proxy', '_term_width', 'printed_header', 'live_printed', '_line_buf']:
    matches = [data[:m.start()].count('\n') + 1 for m in re.finditer(r'\b' + var + r'\b', data)]
    print(f'{var}: {matches}')