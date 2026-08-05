import os
import shutil

def main():
    site_packages = "C:\\Users\\user\\AppData\\Local\\Programs\\Python\\Python311\\Lib\\site-packages"
    if not os.path.exists(site_packages):
        print(f"Error: {site_packages} does not exist.")
        return

    workspace_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # Source files in workspace
    files_to_copy = {
        "utim_cli/orchestrator.py": "orchestrator.py",
        "utim_cli/utim.py": "utim.py",
        "utim_cli/reflection.py": "reflection.py",
        "utim_cli/tools.py": "tools.py",
        "utim_cli/blender_agent.py": "blender_agent.py",
        "utim_cli/_version.py": "_version.py",
        "utim_cli/server/models.py": "server/models.py",
        "utim_cli/server/router.py": "server/router.py",
        "utim_cli/server/db.py": "server/db.py",
        "utim_cli/server/routes/quota_routes.py": "server/routes/quota_routes.py",
        "utim_cli/tui/model_dialog.py": "tui/model_dialog.py",
        "utim_cli/client_utils.py": "client_utils.py",
        "utim_cli/server/routes/completion_routes.py": "server/routes/completion_routes.py"
    }

    # Find all directories in site-packages containing 'utim', 'tim_cli', or 'im_cli' (handles ~tim_cli, ~~im_cli etc.)
    dirs_to_patch = []
    for d in os.listdir(site_packages):
        d_path = os.path.join(site_packages, d)
        if os.path.isdir(d_path) and any(x in d.lower() for x in ("utim", "tim_cli", "im_cli")):
            dirs_to_patch.append(d_path)

    if not dirs_to_patch:
        print("No directories containing 'utim' found in site-packages.")
        return

    print(f"Found {len(dirs_to_patch)} directories to patch:")
    for d in dirs_to_patch:
        print(f"  - {d}")

    for target_dir in dirs_to_patch:
        print(f"\nPatching {target_dir}...")
        for src_rel, dest_rel in files_to_copy.items():
            src_path = os.path.join(workspace_dir, src_rel)
            dest_path = os.path.join(target_dir, dest_rel)
            
            # Ensure target parent folder exists (e.g. server/ for models.py)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            if os.path.exists(src_path):
                try:
                    shutil.copy2(src_path, dest_path)
                    print(f"  SUCCESS: Copied {src_rel} -> {dest_rel}")
                except Exception as e:
                    print(f"  FAILED to copy {src_rel}: {e}")
            else:
                print(f"  Source file not found: {src_path}")

        # Recursively copy docs_md folder
        src_docs = os.path.join(workspace_dir, "utim_cli", "server", "docs_md")
        dest_docs = os.path.join(target_dir, "server", "docs_md")
        if os.path.exists(src_docs):
            try:
                shutil.copytree(src_docs, dest_docs, dirs_exist_ok=True)
                print("  SUCCESS: Copied docs_md folder -> server/docs_md")
            except Exception as e:
                print(f"  FAILED to copy docs_md folder: {e}")

    print("\nPatching complete.")

if __name__ == "__main__":
    main()
