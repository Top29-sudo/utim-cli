import os
import sys
import base64
import requests
import json
import time

def main():
    # 1. Parse scripts/.env manually to extract keys
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if not os.path.exists(env_path):
        print(f"ERROR: .env file not found at {env_path}")
        sys.exit(1)
        
    key_id = None
    key_secret = None
    
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                if key == "RAZORPAY_KEY_ID":
                    key_id = val
                elif key in ("RAZORPAY_SECRET", "RAZORPAY_KEY_SECRET"):
                    key_secret = val
                    
    if not key_id or not key_secret:
        print("ERROR: Could not extract RAZORPAY_KEY_ID or RAZORPAY_SECRET from scripts/.env")
        sys.exit(1)
        
    print(f"Connecting to Razorpay using Key ID: {key_id[:8]}...")

    # Define base plans in INR
    base_plans = [
        {"id": "hobby", "name": "Hobbyist Node", "base_amount": 700},
        {"id": "pro", "name": "Starter Node", "base_amount": 2500},
        {"id": "max", "name": "Professional Core", "base_amount": 5500},
        {"id": "ultimate", "name": "MAX Node", "base_amount": 11000}
    ]

    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }

    # Load existing mapping if exists to avoid recreating
    out_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "utim_cli", "server")
    out_path = os.path.join(out_dir, "razorpay_discounted_plans.json")
    
    discounted_plans = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r", encoding="utf-8") as f:
                discounted_plans = json.load(f)
            print(f"Loaded {len(discounted_plans)} existing discounted plans from {out_path}")
        except Exception:
            pass

    print("\nCreating discounted plans on Razorpay (2% to 98% in steps of 2%)...\n")
    
    new_creations = 0
    for plan in base_plans:
        # Loop discounts from 2 to 98 in steps of 2
        for pct in range(2, 100, 2):
            key = f"{plan['id']}_{pct}"
            if key in discounted_plans:
                continue # Already created, skip

            # Calculate discounted amount in paise
            discounted_price = plan["base_amount"] * (1 - pct / 100)
            amount_paise = int(round(discounted_price * 100))

            payload = {
                "period": "monthly",
                "interval": 1,
                "item": {
                    "name": f"{plan['name']} - {pct}% Referral Discount",
                    "amount": amount_paise,
                    "currency": "INR",
                    "description": f"UTIM {plan['name']} Subscription with {pct}% perpetual referral discount."
                }
            }

            try:
                url = "https://api.razorpay.com/v1/plans"
                resp = requests.post(url, json=payload, headers=headers, timeout=15)
                if resp.status_code in (200, 201):
                    res_data = resp.json()
                    plan_id = res_data.get("id")
                    discounted_plans[key] = plan_id
                    new_creations += 1
                    print(f"SUCCESS: Created plan '{plan['name']} ({pct}% off)' -> ID: {plan_id} (Amount: Rs. {discounted_price:.2f})")
                    # Save progress iteratively
                    with open(out_path, "w", encoding="utf-8") as f:
                        json.dump(discounted_plans, f, indent=2)
                else:
                    print(f"FAILED: Could not create plan '{plan['name']} ({pct}% off)'. HTTP {resp.status_code}: {resp.text}")
            except Exception as e:
                print(f"ERROR: Exception while creating plan '{plan['name']} ({pct}% off)': {e}")
            
            # Rate limit mitigation
            time.sleep(0.1)

    print(f"\nCompleted! Total plans stored: {len(discounted_plans)} (New creations this run: {new_creations})")
    print(f"Mappings saved to: {out_path}")

if __name__ == "__main__":
    main()
