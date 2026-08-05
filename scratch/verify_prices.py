import json
import urllib.request

IMAGE_MODELS = [
    "recraft/recraft-v4.1", "recraft/recraft-v4.1-pro", "recraft/recraft-v4.1-utility", "recraft/recraft-v4.1-utility-pro",
    "recraft/recraft-v4.1-vector", "recraft/recraft-v4.1-pro-vector", "x-ai/grok-imagine-image-quality", "microsoft/mai-image-2.5",
    "sourceful/riverflow-v2.5-fast", "sourceful/riverflow-v2.5-pro", "google/gemini-3-pro-image", "google/gemini-3.1-flash-image",
    "openai/gpt-image-1", "openai/gpt-image-1-mini", "openai/gpt-image-2", "google/gemini-2.5-flash-image", "openai/gpt-5-image",
    "openai/gpt-5-image-mini", "google/gemini-3-pro-image-preview", "black-forest-labs/flux.2-pro", "black-forest-labs/flux.2-flex",
    "black-forest-labs/flux.2-max", "bytedance-seed/seedream-4.5", "black-forest-labs/flux.2-klein-4b", "sourceful/riverflow-v2-fast",
    "sourceful/riverflow-v2-pro"
]

try:
    req = urllib.request.Request("https://openrouter.ai/api/v1/models")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        
    all_models = data.get("data", [])
    
    found = {}
    for m in all_models:
        if m["id"] in IMAGE_MODELS:
            found[m["id"]] = m
            
    print(f"Total matching models found on OpenRouter: {len(found)} / {len(IMAGE_MODELS)}")
    for mid, m in found.items():
        print(f"[{mid}]")
        print(f"  Prompt cost: {m['pricing']['prompt']}")
        print(f"  Completion cost: {m['pricing']['completion']}")
        
    print("\nModels not found on OpenRouter API directly:")
    for mid in IMAGE_MODELS:
        if mid not in found:
            print(f"- {mid}")

except Exception as e:
    print(f"Error fetching: {e}")
