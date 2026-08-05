import os
import sys
import subprocess
import shutil

def parse_env(file_path):
    variables = {}
    if not os.path.exists(file_path):
        return variables
    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'").strip('"')
                variables[key] = val
    return variables

def main():
    print("--- UTIM Railway Environment Syncer ---")
    
    # 1. Update/Install latest Railway CLI
    print("Installing/Updating to the latest Railway CLI via npm...")
    try:
        npm_cmd = "npm.cmd" if os.name == "nt" else "npm"
        subprocess.run([npm_cmd, "install", "-g", "@railway/cli", "--force"], check=True)
        print("Railway CLI updated successfully.")
    except Exception as e:
        print(f"Warning: Failed to update Railway CLI via npm: {e}")
        print("We will attempt to use the existing CLI anyway.")

    # Locate CLI path
    railway_cmd = shutil.which("railway") or "railway"

    # 2. Gather environment variables from root .env and discounted plans
    root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_env = os.path.join(root_dir, ".env")
    env_vars = parse_env(root_env)

    # Also check scripts/.env
    scripts_env = os.path.join(root_dir, "scripts", ".env")
    env_vars.update(parse_env(scripts_env))

    # Read razorpay_discounted_plans.json
    discounted_plans_path = os.path.join(root_dir, "utim_cli", "server", "razorpay_discounted_plans.json")
    if os.path.exists(discounted_plans_path):
        print(f"Reading discounted plans from {discounted_plans_path}...")
        try:
            import json
            with open(discounted_plans_path, "r", encoding="utf-8") as f:
                plans_map = json.load(f)
            for key, val in plans_map.items():
                parts = key.split("_")
                if len(parts) == 2:
                    plan_id, pct = parts
                    plan_id = plan_id.upper()
                    env_vars[f"RAZORPAY_PLAN_{plan_id}_{pct}"] = val
                    if plan_id == "PRO":
                        env_vars[f"RAZORPAY_PLAN_STARTER_{pct}"] = val
                    elif plan_id == "MAX":
                        env_vars[f"RAZORPAY_PLAN_PROFESSIONAL_{pct}"] = val
        except Exception as e:
            print(f"Warning: Failed to read discounted plans JSON: {e}")

    if not env_vars:
        print("ERROR: No environment variables found in .env, scripts/.env or razorpay_discounted_plans.json.")
        sys.exit(1)

    print(f"\nFound {len(env_vars)} variables to sync:")
    for k in env_vars.keys():
        print(f"  - {k}")

    # 3. Construct and run Railway CLI commands in batches to avoid command line length limits
    items = list(env_vars.items())
    batch_size = 20
    batches = [items[i:i + batch_size] for i in range(0, len(items), batch_size)]

    print(f"\nSyncing variables to Railway in {len(batches)} batches of {batch_size}...")
    
    success_count = 0
    failed_count = 0
    for idx, batch in enumerate(batches):
        cmd = [railway_cmd, "variables", "set"]
        for k, v in batch:
            cmd.append(f"{k}={v}")
            
        print(f"Syncing batch {idx+1}/{len(batches)} ({len(batch)} variables)...")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                success_count += len(batch)
            else:
                failed_count += len(batch)
                print(f"Batch {idx+1} failed: {res.stderr.strip()}")
                if "No linked project found" in res.stderr:
                    print("\nTip: Make sure you have linked the project folder to Railway first by running:")
                    print("  railway link")
                    sys.exit(1)
        except Exception as e:
            failed_count += len(batch)
            print(f"Error running batch {idx+1}: {e}")

    print(f"\nSync Complete: {success_count} succeeded, {failed_count} failed.")

if __name__ == "__main__":
    main()
