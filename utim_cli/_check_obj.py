f = open('orchestrator.py', encoding='utf-8').read()
idx = f.find('Active Objective')
snippet = f[idx:idx+150]
print('Found:', 'Active Objective' in snippet)
print('Has 600:', '[:600]' in snippet)
print('Has 200:', '[:200]' in snippet)
# Write to file to avoid encoding issues
open('_check.txt', 'w', encoding='utf-8').write(snippet)
print('Written to _check.txt')