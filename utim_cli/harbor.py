"""UTIM CLI Harbor Agent Adapter for Terminal-Bench evaluation harness."""

import os
import sys
import argparse
import shlex
import pathlib
from typing import Optional, Dict, Any

try:
    from harbor.agents.base import BaseAgent
    _HARBOR_AVAILABLE = True
except ImportError:
    _HARBOR_AVAILABLE = False
    BaseAgent = object


class UtimHarborAgent(BaseAgent):
    """Harbor Agent Adapter for UTIM CLI."""

    SUPPORTS_ATIF = False
    SUPPORTS_RESUME = False
    SUPPORTS_WINDOWS = True

    def __init__(self, logs_dir: Any = None, model_name: Optional[str] = None, **kwargs):
        if _HARBOR_AVAILABLE and logs_dir is not None:
            super().__init__(logs_dir=logs_dir, model_name=model_name, **kwargs)
        else:
            self.logs_dir = logs_dir
            self.model_name = model_name or os.getenv("UTIM_MODEL") or os.getenv("HARBOR_MODEL")

    @staticmethod
    def name() -> str:
        return "utim"

    def version(self) -> Optional[str]:
        try:
            from utim_cli import __version__
            return __version__
        except Exception:
            return "2.0.0"

    async def setup(self, environment: Any) -> None:
        """Setup agent inside the container environment with root permissions."""
        if environment is None or not hasattr(environment, "upload_dir"):
            return

        pkg_dir = pathlib.Path(__file__).parent.resolve()  # utim_cli directory
        
        try:
            # Install python3 and pip as root inside the container
            await environment.exec(
                "apt-get update -qq && apt-get install -y -qq python3 python3-pip python3-venv 2>/dev/null || "
                "apk add --no-cache python3 py3-pip 2>/dev/null || true",
                user="root"
            )
            await environment.exec("mkdir -p /tmp/utim_src", user="root")
            await environment.upload_dir(str(pkg_dir), "/tmp/utim_src/utim_cli")
            # Install required dependencies inside container
            deps = "requests aiohttp python-dotenv urllib3 charset-normalizer chardet typer rich prompt_toolkit nest-asyncio sqlalchemy"
            await environment.exec(
                f"python3 -m pip install --break-system-packages {deps} 2>/dev/null || "
                f"python3 -m pip install {deps} 2>/dev/null || true",
                user="root"
            )
        except Exception as e:
            if hasattr(self, "logger") and self.logger:
                self.logger.warning(f"UtimHarborAgent setup notice: {e}")

    async def run(self, instruction: str, environment: Any = None, context: Any = None) -> Dict[str, Any]:
        """Run the given task instruction in headless mode."""
        if environment is not None and hasattr(environment, "exec"):
            escaped = shlex.quote(instruction)
            model_flag = f"-m {shlex.quote(self.model_name)} " if self.model_name else ""
            
            env = {}
            for k in (
                "OPENROUTER_API_KEY",
                "OPENAI_API_KEY",
                "UTIM_API_KEY",
                "ANTHROPIC_API_KEY",
                "UTIM_EMAIL",
                "UTIM_SERVER_URL",
            ):
                if k in os.environ:
                    env[k] = os.environ[k]
            
            # Create agent log directory inside container if needed and ensure writable
            await environment.exec("mkdir -p /logs/agent && chmod 777 /logs/agent", user="root")

            cmd = (
                f"PYTHONPATH=/tmp/utim_src python3 -m utim_cli.utim run "
                f"{model_flag}{escaped} --headless 2>&1 | tee /logs/agent/utim.txt"
            )
            
            res = await environment.exec(cmd, env=env)
            ret_code = getattr(res, "returncode", 0)
            if context is not None and hasattr(context, "exit_code"):
                context.exit_code = ret_code
            return {"status": "completed" if ret_code == 0 else "failed", "exit_code": ret_code}

        from utim_cli.utim import run_headless_task
        exit_code = run_headless_task(instruction, model=self.model_name)
        return {
            "status": "completed" if exit_code == 0 else "failed",
            "exit_code": exit_code
        }

    def execute(self, instruction: str) -> int:
        """Alias for run method returning exit code directly."""
        from utim_cli.utim import run_headless_task
        return run_headless_task(instruction, model=self.model_name)


def main():
    parser = argparse.ArgumentParser(description="UTIM CLI Harbor Agent Adapter for Terminal-Bench")
    parser.add_argument("instruction", nargs="?", default=None, help="Task instruction to execute")
    parser.add_argument("-p", "--prompt", default=None, help="Task prompt")
    parser.add_argument("-m", "--model", default=None, help="Model ID")
    parser.add_argument("--sandbox", action="store_true", help="Enable sandboxing")
    args = parser.parse_args()

    prompt = args.prompt or args.instruction
    if not prompt and not sys.stdin.isatty():
        try:
            prompt = sys.stdin.read().strip()
        except Exception:
            prompt = None

    if not prompt:
        sys.stderr.write("Error: No instruction provided to Harbor agent.\n")
        sys.exit(1)

    agent = UtimHarborAgent(model_name=args.model)
    res = agent.execute(prompt)
    sys.exit(res)


if __name__ == "__main__":
    main()
