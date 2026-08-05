import json
import urllib.request

try:
    req = urllib.request.Request("https://openrouter.ai/api/v1/models")
    with urllib.request.urlopen(req) as response:
        data = json.loads(response.read())
        
    all_models = data.get("data", [])
    
    print("Finding recraft models:")
    for m in all_models:
        if "recraft" in m["id"].lower():
            print(f"ID: {m['id']}")
            print(f"Pricing: {m.get('pricing')}")
            
    print("\nFinding flux models:")
    for m in all_models:
        if "flux" in m["id"].lower():
            print(f"ID: {m['id']}")
            print(f"Pricing: {m.get('pricing')}")

except Exception as e:
    print(f"Error fetching: {e}")
