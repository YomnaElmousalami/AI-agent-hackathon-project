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

    await server.serve(sockets=None)


def main() -> None:
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
