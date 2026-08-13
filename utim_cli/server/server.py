"""
UTIM Production Server — Entry Point
Run locally:   python -m utim_cli.server.server
Railway runs:  uvicorn utim_cli.server.router:app --host 0.0.0.0 --port $PORT
"""
from __future__ import annotations

import sys
import os

# Ensure parent and grandparent directories are in sys.path to import 'utim_cli'
_dir = os.path.dirname(os.path.abspath(__file__))
for _pd in [os.path.dirname(os.path.dirname(_dir)), os.path.dirname(_dir)]:
    if _pd and _pd not in sys.path:
        sys.path.insert(0, _pd)

import uvicorn


def main():
    host = os.environ.get("HOST", "0.0.0.0")
    port = int(os.environ.get("PORT", 8080))

    # Warn about missing env vars but DO NOT exit — server must start




    required = {
        "DATABASE_URL": os.environ.get("DATABASE_URL"),
        "OPENROUTER_API_KEY": os.environ.get("OPENROUTER_API_KEY"),
        "UTIM_MASTER_KEY": os.environ.get("UTIM_MASTER_KEY"),
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(f"[WARNING] Missing env vars: {', '.join(missing)} — some features will be degraded.")
        print("          Set these in Railway → Service → Variables")

    print(f" UTIM Production Server")
    print(f"    http://{host}:{port}")
    print(f"    Docs:   http://{host}:{port}/docs")

    try:
        uvicorn.run(
            "utim_cli.server.router:app",
            host=host,
            port=port,
            reload=False,
            workers=1,
            # Do NOT pass log_config=None — keep default logging so errors are visible
        )
    except Exception as exc:
        print(f"[FATAL] uvicorn failed to start: {exc}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
