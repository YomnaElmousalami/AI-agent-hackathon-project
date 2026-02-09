"""Postman-friendly MCP HTTP server runner.

Goal
- Serve the MCP HTTP endpoint at: http://localhost:8000/mcp
- Keep the process alive on Windows where FastMCP/uvicorn runners may exit
  immediately due to event loop / signal handling quirks.

How it works
- We run the FastMCP-provided ASGI app (mcp.http_app()) using uvicorn's low-level
  Server.serve() inside asyncio.run(), which is more controllable.
- We disable uvicorn's signal handlers (install_signal_handlers=False) because
  they can behave oddly in some Windows terminals.

Usage (PowerShell)
  py -3.11 .\run_mcp_postman.py

Then in Postman
  MCP URL: http://localhost:8000/mcp
"""

from __future__ import annotations

import asyncio
import os

import uvicorn

from insurance_mcp import mcp


async def _serve() -> None:
    host = os.getenv("MCP_HOST", "127.0.0.1")
    port = int(os.getenv("MCP_PORT", "8000"))

    app = mcp.http_app()

    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=os.getenv("LOG_LEVEL", "info"),
        loop="asyncio",
        lifespan="on",
        timeout_graceful_shutdown=1,
    )

    server = uvicorn.Server(config)

    # Uvicorn 0.38's Server.serve() only accepts `sockets`. The config above is
    # enough for Postman; if you still see unexpected shutdowns, run from a
    # plain PowerShell terminal (not an integrated task runner).
    await server.serve(sockets=None)


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
