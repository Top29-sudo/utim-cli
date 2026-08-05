import os, re
target_models = [
    'nvidia/nemotron-3-nano-30b-a3b:free',
    'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free',
    'nvidia/nemotron-3-super-120b-a12b:free',
    'nvidia/nemotron-3-ultra-550b-a55b:free',
    'nvidia/nemotron-nano-12b-v2-vl:free',
    'qwen/qwen3-coder:free'
]

def process_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    original_content = content
    
    for model in target_models:
        # Remove lines that are just the model in a list
        content = re.sub(r'^[ \t]*[\'\"]' + re.escape(model) + r'[\'\"]\s*,?[ \t]*(?:#.*)?\n', '', content, flags=re.MULTILINE)
        
        # Remove lines that are dict entries where the model is the key
        content = re.sub(r'^[ \t]*[\'\"]' + re.escape(model) + r'[\'\"]\s*:\s*.*?\n', '', content, flags=re.MULTILINE)
        
        # Remove lines where the model is in a list of dicts (like utim.py 1988)
        content = re.sub(r'^[ \t]*\{[^{}]*[\'\"]' + re.escape(model) + r'[\'\"][^{}]*\},?\n', '', content, flags=re.MULTILINE)
        
        # Inline list removal e.g. ["cohere", "...", "qwen/qwen3-coder:free"]
        content = re.sub(r',\s*[\'\"]' + re.escape(model) + r'[\'\"]', '', content)
        content = re.sub(r'[\'\"]' + re.escape(model) + r'[\'\"]\s*,', '', content)

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f'Updated {filepath}')

for root, dirs, files in os.walk('utim_cli'):
    for file in files:
        if file.endswith('.py'):
            process_file(os.path.join(root, file))
