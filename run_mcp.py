#!/usr/bin/env python3
"""Runner script for the MCP server."""

import sys
from pathlib import Path

# Add the project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Now run the server
from src.mcp_server import main
import asyncio

if __name__ == "__main__":
    asyncio.run(main())
