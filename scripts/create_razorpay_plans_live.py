import os
import sys
import base64
import requests

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
                elif key == "RAZORPAY_SECRET" or key == "RAZORPAY_KEY_SECRET":
                    key_secret = val
                    
    if not key_id or not key_secret:
        print("ERROR: Could not extract RAZORPAY_KEY_ID or RAZORPAY_SECRET from scripts/.env")
        sys.exit(1)
        
    print(f"Connecting to Razorpay using Key ID: {key_id[:8]}... (extracted from scripts/.env)")
    
    # 2. Define plans directly in INR with the exact prices requested
    plans_config = [
        # Hobbyist Node
        {
            "name": "Hobbyist Node - Monthly",
            "amount_paise": 700 * 100, # Rs. 700
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_HOBBY"
        },
        {
            "name": "Hobbyist Node - Yearly",
            "amount_paise": int(700 * 12 * 0.9 * 100), # Rs. 7560 (10% discount)
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_HOBBY_YEARLY"
        },
        # Starter Node
        {
            "name": "Starter Node - Monthly",
            "amount_paise": 2500 * 100, # Rs. 2500
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_STARTER"
        },
        {
            "name": "Starter Node - Yearly",
            "amount_paise": int(2500 * 12 * 0.9 * 100), # Rs. 27000 (10% discount)
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_STARTER_YEARLY"
        },
        # Professional Core
        {
            "name": "Professional Core - Monthly",
            "amount_paise": 5500 * 100, # Rs. 5500
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_PROFESSIONAL"
        },
        {
            "name": "Professional Core - Yearly",
            "amount_paise": int(5500 * 12 * 0.9 * 100), # Rs. 59400 (10% discount)
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_PROFESSIONAL_YEARLY"
        },
        # MAX Node
        {
            "name": "MAX Node - Monthly",
            "amount_paise": 11000 * 100, # Rs. 11000
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_ULTIMATE"
        },
        {
            "name": "MAX Node - Yearly",
            "amount_paise": int(11000 * 12 * 0.9 * 100), # Rs. 118800 (10% discount)
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_ULTIMATE_YEARLY"
        }
    ]
    
    auth_str = base64.b64encode(f"{key_id}:{key_secret}".encode()).decode()
    headers = {
        "Authorization": f"Basic {auth_str}",
        "Content-Type": "application/json"
    }
    
    print("\nCreating plans on Razorpay...\n")
    
    created_plans = {}
    for plan in plans_config:
        payload = {
            "period": plan["period"],
            "interval": 1,
            "item": {
                "name": plan["name"],
                "amount": plan["amount_paise"],
                "currency": "INR",
                "description": f"UTIM {plan['name']} Subscription Plan"
            }
        }
        
        try:
            url = "https://api.razorpay.com/v1/plans"
            resp = requests.post(url, json=payload, headers=headers, timeout=15)
            if resp.status_code in (200, 201):
                res_data = resp.json()
                plan_id = res_data.get("id")
                created_plans[plan["env_key"]] = plan_id
                print(f"SUCCESS: Created '{plan['name']}' -> ID: {plan_id} (Amount: Rs. {plan['amount_paise']/100:.2f})")
            else:
                print(f"FAILED: Could not create plan '{plan['name']}'. HTTP {resp.status_code}: {resp.text}")
        except Exception as e:
            print(f"ERROR: Exception while creating plan '{plan['name']}': {e}")
            
    if created_plans:
        print("\n" + "="*80)
        print("RAZORPAY PLANS CREATED SUCCESSFULLY!")
        print("Copy the following environment variables and add them to your Railway server settings:")
        print("="*80)
        for key, val in created_plans.items():
            print(f"{key}={val}")
        print("="*80 + "\n")
    else:
        print("\nNo plans were created. Please check your credentials and try again.")

if __name__ == "__main__":
    main()
