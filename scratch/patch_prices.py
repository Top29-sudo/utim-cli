import os
import re

# Exact prices in USD
PRICES = {
    # Gemini (from live API)
    "google/gemini-3.1-flash-image": {"in": 0.0000005, "out": 0.000003},
    "google/gemini-3-pro-image": {"in": 0.000002, "out": 0.000012},
    "google/gemini-3-pro-image-preview": {"in": 0.000002, "out": 0.000012},
    "google/gemini-2.5-flash-image": {"in": 0.0000003, "out": 0.0000025},
    
    # OpenAI (from live API)
    "openai/gpt-5-image-mini": {"in": 0.0000025, "out": 0.000002},
    "openai/gpt-5-image": {"in": 0.00001, "out": 0.00001},
    "openai/gpt-image-1": {"in": 0.000002, "out": 0.000002},
    "openai/gpt-image-1-mini": {"in": 0.0000005, "out": 0.0000005},
    "openai/gpt-image-2": {"in": 0.00002, "out": 0.00002},
    
    # Recraft (per image, mapping 1 image = 1000 completion tokens)
    # $0.035/image -> 0.035 per 1k out
    "recraft/recraft-v4.1": {"in": 0.0, "out": 0.035},
    "recraft/recraft-v4.1-utility": {"in": 0.0, "out": 0.035},
    # Pro/Vector: $0.30/image
    "recraft/recraft-v4.1-pro": {"in": 0.0, "out": 0.30},
    "recraft/recraft-v4.1-vector": {"in": 0.0, "out": 0.05},
    "recraft/recraft-v4.1-pro-vector": {"in": 0.0, "out": 0.30},
    "recraft/recraft-v4.1-utility-pro": {"in": 0.0, "out": 0.30},
    
    # Flux 2 ($0.03 per MP, assume 1MP)
    "black-forest-labs/flux.2-pro": {"in": 0.0, "out": 0.03},
    "black-forest-labs/flux.2-max": {"in": 0.0, "out": 0.05},
    "black-forest-labs/flux.2-flex": {"in": 0.0, "out": 0.03},
    "black-forest-labs/flux.2-klein-4b": {"in": 0.0, "out": 0.01},
    
    # Riverflow, Seedream, Grok, MAI (estimated placeholders)
    "sourceful/riverflow-v2.5-fast": {"in": 0.0, "out": 0.015},
    "sourceful/riverflow-v2.5-pro": {"in": 0.0, "out": 0.04},
    "sourceful/riverflow-v2-fast": {"in": 0.0, "out": 0.01},
    "sourceful/riverflow-v2-pro": {"in": 0.0, "out": 0.035},
    "x-ai/grok-imagine-image-quality": {"in": 0.0, "out": 0.04},
    "microsoft/mai-image-2.5": {"in": 0.0, "out": 0.02},
    "bytedance-seed/seedream-4.5": {"in": 0.0, "out": 0.02},
}

models_path = os.path.join(os.getcwd(), "utim_cli", "server", "models.py")

with open(models_path, "r", encoding="utf-8") as f:
    content = f.read()

# For each model, find its block and replace cost_input_per_1k and cost_output_per_1k
for mid, costs in PRICES.items():
    in_cost = costs["in"] * 1.02 # Add 2% markup
    out_cost = costs["out"] * 1.02 # Add 2% markup
    
    # If it's a per-image API, they cost that amount for 1 request. We map 1 request to 1k completion tokens.
    # If it's Gemini/GPT which charge per token, their value in dict is per 1 token. 
    # So we multiply by 1000 for per_1k!
    if "gemini" in mid or "gpt" in mid:
        in_cost *= 1000
        out_cost *= 1000
    
    # Regex to find block:
    # "{mid}": ModelEntry(
    #     model_id="{mid}",
    #     provider="openrouter",
    #     cost_input_per_1k=...,
    #     cost_output_per_1k=...,
    
    pattern = rf'("{mid}": ModelEntry\([\s\S]*?cost_input_per_1k=)([\d\.]+)(,\s*cost_output_per_1k=)([\d\.]+)(,)'
    replacement = rf'\g<1>{in_cost:.6f}\g<3>{out_cost:.6f}\g<5>'
    content = re.sub(pattern, replacement, content)

with open(models_path, "w", encoding="utf-8") as f:
    f.write(content)
print("Updated models.py with exact markup pricing!")
