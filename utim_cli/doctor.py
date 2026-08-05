import sys
import os
import shutil
import json
import urllib.request
from rich.console import Console

def run_diagnostics(console: Console = None):
    """Run environmental, dependency, connectivity, and database diagnostics."""
    if console is None:
        console = Console()

    console.print("\n[bold #42bcf5][+] UTIM Doctor - System Diagnostics[/bold #42bcf5]\n")

    # 1. Environment & Python
    py_ver = sys.version.split()[0]
    console.print(f"  [bold]Python Version:[/bold]     {py_ver}")
    console.print(f"  [bold]Platform:[/bold]           {sys.platform}")
    console.print(f"  [bold]Working Directory:[/bold]  {os.getcwd()}")

    # 2. Dependency Check
    console.print("\n  [bold #42bcf5]Core Dependencies:[/bold #42bcf5]")
    core_dependencies = [
        "requests", "aiohttp", "typer", "rich",
        "prompt_toolkit", "nest_asyncio"
    ]
    for dep in core_dependencies:
        try:
            mod_name = dep.replace("-", "_")
            __import__(mod_name)
            console.print(f"    [+] {dep:<24} [green]Installed[/green]")
        except ImportError:
            console.print(f"    [-] {dep:<24} [red]Not Installed (Required)[/red]")

    console.print("\n  [bold #42bcf5]Optional Feature Dependencies:[/bold #42bcf5]")
    optional_dependencies = {
        "tree_sitter": "AST-based Knowledge Graph / dependency mapping",
        "chromadb": "RAG Vector DB feature",
        "sentence_transformers": "Dynamic embedding extraction",
        "scrapy": "Scrapy search crawler",
        "scrapy-playwright": "Playwright JS crawler",
        "pillow": "Image utilities (generate_image)",
        "openai": "Legacy ReActAgent SDK client",
        "mcp": "Model Context Protocol server integrations",
    }
    for dep, feat in optional_dependencies.items():
        try:
            mod_name = dep.replace("-", "_")
            __import__(mod_name)
            console.print(f"    [+] {dep:<24} [green]Installed[/green] [dim]({feat})[/dim]")
        except ImportError:
            console.print(f"    [ ] {dep:<24} [yellow]Not Installed[/yellow] [dim]({feat})[/dim]")

    # 3. Local Workspace State
    console.print("\n  [bold #42bcf5]Workspace Configurations:[/bold #42bcf5]")
    from utim_cli.config import get_utim_dir
    utim_dir = get_utim_dir()
    local_utim = os.path.exists(utim_dir)
    console.print(f"    * .utim/ directory:   {'[green]Exists[/green]' if local_utim else '[yellow]Missing[/yellow]'}")
    
    config_exists = os.path.exists(utim_dir / "config.json")
    console.print(f"    * config.json:        {'[green]Exists[/green]' if config_exists else '[yellow]Missing[/yellow]'}")
    
    db_exists = os.path.exists(utim_dir / "utim_local.db")
    console.print(f"    * Local SQLite DB:    {'[green]Exists[/green]' if db_exists else '[yellow]Missing[/yellow]'}")

    # 4. Model & Connectivity check
    console.print("\n  [bold #42bcf5]Connectivity & API Health:[/bold #42bcf5]")
    # 4a. Check UTIM Server Connection
    import ssl
    from utim_cli.config import config
    ssl_context = None
    if not config.verify_ssl:
        ssl_context = ssl._create_unverified_context()

    from utim_cli.auth import SERVER_URL
    console.print(f"    * Server Target URL:    {SERVER_URL}")
    try:
        req = urllib.request.Request(
            f"{SERVER_URL}/plans",
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req, timeout=5, context=ssl_context) as r:
            status = r.getcode()
            if status == 200:
                console.print("    [+] UTIM Server API:      [green]Healthy & Reachable (HTTP 200)[/green]")
            else:
                console.print(f"    [-] UTIM Server API:      [red]Status Code {status}[/red]")
    except Exception as e:
        console.print(f"    [-] UTIM Server API:      [red]Unreachable[/red] ({e})")

    # 4b. Check OpenRouter Connection
    try:
        req = urllib.request.Request(
            "https://openrouter.ai", 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        urllib.request.urlopen(req, timeout=5, context=ssl_context)
        console.print("    [+] OpenRouter connection: [green]Successful[/green]")
    except Exception as e:
        console.print(f"    [-] OpenRouter connection: [red]Failed[/red] ({e})")

    # 5. MCP Server Health
    console.print("\n  [bold #42bcf5]Model Context Protocol (MCP) Health:[/bold #42bcf5]")
    mcp_config_path = utim_dir / "mcp.json"
    if os.path.exists(mcp_config_path):
        try:
            with open(mcp_config_path, "r", encoding="utf-8") as f:
                mcp_data = json.load(f)
            servers = mcp_data.get("mcpServers", {})
            if not servers:
                console.print("    * No MCP servers configured.")
            for name, cfg in servers.items():
                cmd = cfg.get("command", "")
                console.print(f"    * [bold]{name}[/bold] (command: {cmd}):")
                if shutil.which(cmd) or cmd == sys.executable:
                    console.print("      [+] Command path: [green]Found[/green]")
                else:
                    console.print(f"      [-] Command path: [red]Not Found ('{cmd}')[/red]")
        except Exception as e:
            console.print(f"    [-] Error reading mcp.json: {e}")
    else:
        console.print("    * No local mcp.json configuration.")

    console.print("\n[bold #42bcf5][+] Diagnostics Complete.[/bold #42bcf5]\n")

if __name__ == "__main__":
    run_diagnostics()
