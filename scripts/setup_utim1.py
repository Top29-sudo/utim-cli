import sys
import subprocess
import pathlib
import winreg

# 1. Check dependencies
required_modules = [
    "requests", "aiohttp", "dotenv", "urllib3", "charset_normalizer",
    "chardet", "typer", "rich", "prompt_toolkit", "tree-sitter",
    "chromadb", "mcp", "nest_asyncio", "openai"
]

dependencies_installed = True
for mod in required_modules:
    try:
        if mod == "dotenv":
            import dotenv
        elif mod == "tree-sitter":
            import tree_sitter
        else:
            __import__(mod.replace("-", "_"))
    except ImportError:
        dependencies_installed = False
        break

workspace_dir = pathlib.Path(__file__).parent.parent.resolve()

if not dependencies_installed:
    print("Installing missing dependencies...")
    try:
        # Run pip install -r requirements.txt
        req_file = workspace_dir / "requirements.txt"
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", str(req_file)])
        # Run pip install -e .
        subprocess.check_call([sys.executable, "-m", "pip", "install", "-e", str(workspace_dir)])
        print("Dependencies successfully installed.")
    except Exception as e:
        print(f"Error installing dependencies: {e}")
        sys.exit(1)

# 2. Add bin directory to path
bin_dir = str(workspace_dir / "bin")
try:
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
    try:
        path_val, val_type = winreg.QueryValueEx(key, "Path")
    except FileNotFoundError:
        path_val = ""
        val_type = winreg.REG_SZ
    
    paths = [p.strip() for p in path_val.split(";") if p.strip()]
    if bin_dir not in paths:
        paths.append(bin_dir)
        new_path_val = ";".join(paths)
        winreg.SetValueEx(key, "Path", 0, val_type, new_path_val)
        print(f"Added {bin_dir} to User PATH.")
        print("Note: You may need to restart your terminal/IDE for PATH changes to take effect.")
    else:
        # Already in path, no need to add again
        pass
except Exception as e:
    print(f"Warning: Could not add {bin_dir} to User PATH: {e}")

# 3. Copy API keys from workspace .env to global ~/.utim/.env if not present globally
global_dir = pathlib.Path.home() / ".utim"
global_env = global_dir / ".env"
workspace_env = workspace_dir / ".env"

if workspace_env.exists():
    try:
        # Read workspace env keys
        workspace_keys = {}
        for line in workspace_env.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                workspace_keys[k.strip()] = v.strip()
        
        # Read existing global env keys
        global_keys = {}
        if global_env.exists():
            for line in global_env.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    global_keys[k.strip()] = v.strip()
        
        # Merge workspace keys that are not present globally or are different
        updated = False
        for k, v in workspace_keys.items():
            if k not in global_keys or global_keys[k] != v:
                global_keys[k] = v
                updated = True
        
        if updated:
            global_dir.mkdir(parents=True, exist_ok=True)
            lines = [f"{k}={v}" for k, v in global_keys.items()]
            global_env.write_text("\n".join(lines) + "\n", encoding="utf-8")
            print(f"Migrated API keys from workspace to global path {global_env}")
    except Exception as e:
        print(f"Warning: Could not copy API keys to global path: {e}")

# 4. Sync critical API keys into the Windows User Environment registry
#    This ensures the correct key always beats any stale value inherited
#    from old installations baked into the process environment.
REGISTRY_KEYS_TO_SYNC = ["OPENROUTER_API_KEY", "TAVILY_API_KEY", "HF_TOKEN"]
try:
    reg = winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment", 0, winreg.KEY_ALL_ACCESS)
    for env_key in REGISTRY_KEYS_TO_SYNC:
        workspace_val = workspace_keys.get(env_key, "")
        if not workspace_val:
            continue
        try:
            reg_val, _ = winreg.QueryValueEx(reg, env_key)
        except FileNotFoundError:
            reg_val = ""
        if reg_val != workspace_val:
            winreg.SetValueEx(reg, env_key, 0, winreg.REG_SZ, workspace_val)
            print(f"Synced {env_key} in Windows User Environment registry.")
    winreg.CloseKey(reg)
except Exception as e:
    print(f"Warning: Could not sync API keys to registry: {e}")

sys.exit(0)
