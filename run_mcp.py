#!/usr/bin/env python3
"""Runner script for the MCP server."""

import sys
print("[run_mcp] Starting...", file=sys.stderr)

try:
    from pathlib import Path

    # Add the project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    print(f"[run_mcp] Added {project_root} to path", file=sys.stderr)

    # Now run the server
    print("[run_mcp] Importing mcp_server...", file=sys.stderr)
    from src.mcp_server import main
    print("[run_mcp] Import successful", file=sys.stderr)

    import asyncio
    print("[run_mcp] Running main...", file=sys.stderr)
    asyncio.run(main())

except Exception as e:
    print(f"[run_mcp] ERROR: {e}", file=sys.stderr)
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.exit(1)
