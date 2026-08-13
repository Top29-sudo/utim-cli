import json
import re

with open('scratch/all_66_models.json', 'r', encoding='utf-8') as f:
    models_data = json.load(f)

print(f'Loaded {len(models_data)} models from JSON')

# Format as JavaScript array literal
js_code = 'const MODELS = [\n'
for m in models_data:
    free_bool = 'true' if m['free'] else 'false'
    js_code += '  {\n'
    js_code += f"    id: '{m['id']}',\n"
    js_code += f"    name: '{m['name']}',\n"
    js_code += f"    provider: '{m['provider']}',\n"
    js_code += f"    tier: '{m['tier']}',\n"
    js_code += f"    category: '{m['category']}',\n"
    js_code += f"    cost: '{m['cost']}',\n"
    if m['freeCost']:
        js_code += f"    freeCost: '{m['freeCost']}',\n"
        js_code += f"    paidCost: '{m['paidCost']}',\n"
    js_code += f"    context: '{m['context']}',\n"
    js_code += f"    maxOutput: '{m['maxOutput']}',\n"
    js_code += f"    speed: '{m['speed']}',\n"
    js_code += f"    recommendedFor: '{m['recommendedFor']}',\n"
    js_code += f"    free: {free_bool},\n"
    js_code += '  },\n'
js_code += '];\n'

with open('landing/src/components/ModelRegistryExplorer.jsx', 'r', encoding='utf-8') as f:
    content = f.read()

new_content = re.sub(r'const MODELS = \[.*?\];', js_code, content, flags=re.DOTALL)

with open('landing/src/components/ModelRegistryExplorer.jsx', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Updated ModelRegistryExplorer.jsx with all 66 models!')
