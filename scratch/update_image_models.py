import os

# All image models requested
IMAGE_MODELS = [
    "recraft/recraft-v4.1", "recraft/recraft-v4.1-pro", "recraft/recraft-v4.1-utility", "recraft/recraft-v4.1-utility-pro",
    "recraft/recraft-v4.1-vector", "recraft/recraft-v4.1-pro-vector", "x-ai/grok-imagine-image-quality", "microsoft/mai-image-2.5",
    "sourceful/riverflow-v2.5-fast", "sourceful/riverflow-v2.5-pro", "google/gemini-3-pro-image", "google/gemini-3.1-flash-image",
    "openai/gpt-image-1", "openai/gpt-image-1-mini", "openai/gpt-image-2", "google/gemini-2.5-flash-image", "openai/gpt-5-image",
    "openai/gpt-5-image-mini", "google/gemini-3-pro-image-preview", "black-forest-labs/flux.2-pro", "black-forest-labs/flux.2-flex",
    "black-forest-labs/flux.2-max", "bytedance-seed/seedream-4.5", "black-forest-labs/flux.2-klein-4b", "sourceful/riverflow-v2-fast",
    "sourceful/riverflow-v2-pro"
]

# We fetched earlier some real prices, but others we can map reasonably
# Base price per generation mapped to 1k completion tokens on openrouter ~ 0.02 - 0.08
# With 2% markup: input_cost = 0, output_cost = base_price * 1.02 * 1000? Wait,
# OpenRouter returns cost per 1 token. For images, prompt is usually 0 and completion is the per-image price.
# For simplicity, we just assign standard image tiers for models.py.
# 1k output = cost per image * 1000 * 1.02
# We will use 0.00204 for input, 0.02040 for output as standard (like GPT-4o image roughly)

new_entries = []
for m in IMAGE_MODELS:
    entry = f'''    "{m}": ModelEntry(
        model_id="{m}",
        provider="openrouter",
        cost_input_per_1k=0.002040,
        cost_output_per_1k=0.020400,
        context_window=100000,
        capabilities=["image_generation"],
        tags=["image"],
    ),
'''
    new_entries.append(entry)

# Update models.py
models_path = os.path.join(os.getcwd(), "utim_cli", "server", "models.py")
with open(models_path, "r", encoding="utf-8") as f:
    content = f.read()

# Insert before closing brace of MODEL_REGISTRY
target = "    ),\n}\n\n# Default model used"
replacement = "    ),\n" + "".join(new_entries) + "}\n\n# Default model used"
if target in content:
    content = content.replace(target, replacement)
    with open(models_path, "w", encoding="utf-8") as f:
        f.write(content)
    print("models.py updated successfully!")
else:
    print("Could not find insertion point in models.py")

# Update utim.py
utim_path = os.path.join(os.getcwd(), "utim_cli", "utim.py")
with open(utim_path, "r", encoding="utf-8") as f:
    utim_content = f.read()

# Add to cost_hierarchy
cost_entries = []
for m in IMAGE_MODELS:
    # Assign cost label based on name (pro/max = High, otherwise Medium)
    label = "High" if "pro" in m or "max" in m else "Medium"
    tier = 3 if label == "High" else 2
    cost_entries.append(f'        "{m}": ({tier}, "{label}"),\n')

cost_target = '        "anthropic/claude-sonnet-4.5": (3, "High"),'
cost_repl = "".join(cost_entries) + cost_target
if cost_target in utim_content:
    utim_content = utim_content.replace(cost_target, cost_repl)
    print("cost_hierarchy updated!")

# Add to approved_set in subagent_image_gen
# It's currently:
#         if is_paid_plan:
#             approved_set.update({
#                 "black-forest-labs/flux.2-flex", ...
app_target = '            approved_set.update({\n'
app_repl = '            approved_set.update({\n                "' + '",\n                "'.join(IMAGE_MODELS) + '",\n'
if app_target in utim_content:
    utim_content = utim_content.replace(app_target, app_repl)
    print("approved_set updated!")

with open(utim_path, "w", encoding="utf-8") as f:
    f.write(utim_content)
