import os
from datetime import datetime

date_str = datetime.now().strftime("%Y-%m-%d")

new_changelog = f"""## [1.44.2] - {date_str}

### Fixed
- **MCP Server Hang:** Fixed an issue where installing MCP servers (like Figma) without the `--stdio` flag would hang the CLI indefinitely. Added a 60-second initialization timeout and updated the preset registry to include required flags automatically.
- **Model Selection Crash:** Fixed an issue where the CLI would crash instantly when trying to open the `/model` selector on a production npm install due to an excluded server module.
- **Image Subagent Config:** Separated the Image Generation model and the Prompt Expander LLM in the subagent configuration UI, allowing users to configure both independently.

"""

files = [
    "CHANGELOG.md",
    "landing/src/docs_md/changelog.md",
    "utim_cli/server/CHANGELOG.md"
]

for file_path in files:
    full_path = os.path.join(os.getcwd(), file_path)
    if os.path.exists(full_path):
        with open(full_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Insert after the header
        if "# Changelog" in content:
            parts = content.split("## [", 1)
            if len(parts) == 2:
                new_content = parts[0] + new_changelog + "## [" + parts[1]
                with open(full_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Updated {file_path}")
            else:
                print(f"Could not find insert point in {file_path}")
        else:
            print(f"No # Changelog header in {file_path}")
    else:
        print(f"File not found: {file_path}")
