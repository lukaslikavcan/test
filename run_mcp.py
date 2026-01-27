#!/usr/bin/env python3
"""Runner script for the MCP server."""

import sys

def log(msg):
    print(f"[run_mcp] {msg}", file=sys.stderr, flush=True)

log("Script starting...")

try:
    log("Importing pathlib...")
    from pathlib import Path

    # Add the project root to Python path
    project_root = Path(__file__).parent
    sys.path.insert(0, str(project_root))
    log(f"Added {project_root} to path")

    log("Importing asyncio...")
    import asyncio

    log("Importing mcp...")
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import TextContent, Tool
    log("MCP imports successful")

    log("Importing src modules...")
    from src.claude_client import ClaudeClient
    from src.content_filter import ContentFilter, FilterCriteria
    from src.notion_client import NotionClient, NotionPage
    log("All imports successful")

    log("Importing main from mcp_server...")
    from src.mcp_server import main
    log("Import successful, running main...")

    asyncio.run(main())

except Exception as e:
    log(f"ERROR: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc(file=sys.stderr)
    sys.stderr.flush()
    sys.exit(1)
