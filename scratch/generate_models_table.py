import sys
import os

# Ensure parent and grandparent directories are in sys.path
_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from utim_cli.server.models import MODEL_REGISTRY

# Categorize models
free_models = []
premium_models = []
image_models = []

for m_id, entry in MODEL_REGISTRY.items():
    is_free = m_id.endswith(":free") or m_id == "openrouter/free" or "free" in entry.tags
    is_image = "image" in entry.tags or "image" in entry.capabilities or "image_generation" in entry.capabilities
    
    item = {
        "id": m_id,
        "input_cost": entry.cost_input_per_1k,
        "output_cost": entry.cost_output_per_1k,
        "context": entry.context_window,
        "capabilities": ", ".join(entry.capabilities)
    }
    
    if is_free:
        free_models.append(item)
    elif is_image:
        image_models.append(item)
    else:
        premium_models.append(item)

# Sort premium models by input cost
premium_models.sort(key=lambda x: x["input_cost"])

print("### A. Free / Standard Models")
print("| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |")
print("| :--- | :--- | :--- | :--- | :--- |")
for m in free_models:
    print(f"| `{m['id']}` | {m['input_cost']:.4f} | {m['output_cost']:.4f} | {m['context']:,} | {m['capabilities']} |")

print("\n### B. Premium Text & Code Models")
print("| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |")
print("| :--- | :--- | :--- | :--- | :--- |")
for m in premium_models:
    print(f"| `{m['id']}` | {m['input_cost']:.4f} | {m['output_cost']:.4f} | {m['context']:,} | {m['capabilities']} |")

print("\n### C. Image Generation Models")
print("| Model ID | Input Cost (credits/1K) | Output Cost (credits/1K) | Context Window | Capabilities |")
print("| :--- | :--- | :--- | :--- | :--- |")
for m in image_models:
    print(f"| `{m['id']}` | {m['input_cost']:.4f} | {m['output_cost']:.4f} | {m['context']:,} | {m['capabilities']} |")
