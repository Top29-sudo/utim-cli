import json
import urllib.request

models_to_find = [
    "recraft/recraft-v4.1", "recraft/recraft-v4.1-pro", "recraft/recraft-v4.1-utility", "recraft/recraft-v4.1-utility-pro",
    "recraft/recraft-v4.1-vector", "recraft/recraft-v4.1-pro-vector", "x-ai/grok-imagine-image-quality", "microsoft/mai-image-2.5",
    "sourceful/riverflow-v2.5-fast", "sourceful/riverflow-v2.5-pro", "google/gemini-3-pro-image", "google/gemini-3.1-flash-image",
    "openai/gpt-image-1", "openai/gpt-image-1-mini", "openai/gpt-image-2", "google/gemini-2.5-flash-image", "openai/gpt-5-image",
    "openai/gpt-5-image-mini", "google/gemini-3-pro-image-preview", "black-forest-labs/flux.2-pro", "black-forest-labs/flux.2-flex",
    "black-forest-labs/flux.2-max", "bytedance-seed/seedream-4.5", "black-forest-labs/flux.2-klein-4b", "sourceful/riverflow-v2-fast",
    "sourceful/riverflow-v2-pro"
]

req = urllib.request.Request("https://openrouter.ai/api/v1/models")
try:
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        
    found_models = []
    for model in data.get("data", []):
        if model["id"] in models_to_find:
            found_models.append(model)
            
    # Also some might not exist literally on openrouter if they are made up or future models, 
    # but we will get what we can.
    
    print("Found models:")
    for m in found_models:
        in_cost = float(m["pricing"]["prompt"]) * 1.02 * 1000
        out_cost = float(m["pricing"]["completion"]) * 1.02 * 1000
        # Image models usually charge per generation (which is mapped to completion tokens on openrouter, or prompt tokens)
        print(f'    "{m["id"]}": ModelEntry(')
        print(f'        model_id="{m["id"]}",')
        print(f'        provider="openrouter",')
        print(f'        cost_input_per_1k={in_cost:.6f},')
        print(f'        cost_output_per_1k={out_cost:.6f},')
        print(f'        context_window={m["context_length"]},')
        print(f'        capabilities=["image_generation"],')
        print(f'        tags=["image"],')
        print(f'    ),')

except Exception as e:
    print(f"Error fetching: {e}")
