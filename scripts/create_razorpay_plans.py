import os
import sys
import base64
import requests

# Set path to include parent directory
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utim_cli.server.exchange_rate import ExchangeRateStore

def main():
    # 1. Read Razorpay Credentials
    key_id = os.environ.get("RAZORPAY_KEY_ID")
    key_secret = os.environ.get("RAZORPAY_KEY_SECRET")
    
    if not key_id or not key_secret:
        print("ERROR: RAZORPAY_KEY_ID and RAZORPAY_KEY_SECRET must be set in your environment variables.")
        print("Please run this script with these variables set, e.g.:")
        print("  $env:RAZORPAY_KEY_ID='rzp_live_xxx'")
        print("  $env:RAZORPAY_KEY_SECRET='secret_xxx'")
        print("  python scripts/create_razorpay_plans.py")
        sys.exit(1)
        
    print(f"Connecting to Razorpay with Key ID: {key_id[:8]}...")
    
    # 2. Get Exchange Rate
    print("Fetching live exchange rate...")
    rate = ExchangeRateStore.fetch_live_rate()
    print(f"Current USD to INR exchange rate: {rate:.4f} (1 USD = {rate:.4f} INR)")
    
    # 3. Define Plans
    # Plans map of name -> USD monthly price, USD yearly total, display name
    plans_config = [
        # Hobbyist Node
        {
            "id": "hobby",
            "name": "Hobbyist Node - Monthly",
            "usd_amount": 7.00,
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_HOBBY"
        },
        {
            "id": "hobby_yearly",
            "name": "Hobbyist Node - Yearly",
            "usd_amount": 75.60,
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_HOBBY_YEARLY"
        },
        # Starter Node
        {
            "id": "starter",
            "name": "Starter Node - Monthly",
            "usd_amount": 25.00,
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_STARTER"
        },
        {
            "id": "starter_yearly",
            "name": "Starter Node - Yearly",
            "usd_amount": 270.00,
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_STARTER_YEARLY"
        },
        # Professional Core
        {
            "id": "professional",
            "name": "Professional Core - Monthly",
            "usd_amount": 55.00,
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_PROFESSIONAL"
        },
        {
            "id": "professional_yearly",
            "name": "Professional Core - Yearly",
            "usd_amount": 594.00,
            "period": "yearly",
            "env_key": "RAZORPAY_PLAN_PROFESSIONAL_YEARLY"
        },
        # MAX Node
        {
            "id": "ultimate",
            "name": "MAX Node - Monthly",
            "usd_amount": 110.00,
            "period": "monthly",
            "env_key": "RAZORPAY_PLAN_ULTIMATE"
        },
        {
            "id": "ultimate_yearly",
            "name": "MAX Node - Yearly",
            "usd_amount": 1188.00,
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
        # Calculate amount in paise (1 INR = 100 paise)
        inr_amount = plan["usd_amount"] * rate
        amount_paise = int(round(inr_amount * 100))
        
        payload = {
            "period": plan["period"],
            "interval": 1,
            "item": {
                "name": plan["name"],
                "amount": amount_paise,
                "currency": "INR",
                "description": f"UTIM subscription: {plan['name']} (${plan['usd_amount']} USD at 1 USD = {rate:.2f} INR)"
            }
        }
        
        try:
            url = "https://api.razorpay.com/v1/plans"
            resp = requests.post(url, json=payload, headers=headers, timeout=10)
            if resp.status_code == 200 or resp.status_code == 201:
                res_data = resp.json()
                plan_id = res_data.get("id")
                created_plans[plan["env_key"]] = plan_id
                print(f"SUCCESS: Created plan '{plan['name']}' -> ID: {plan_id} (Amount: {inr_amount:.2f} INR)")
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
