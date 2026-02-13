from __future__ import annotations

import os

from insurance_mcp import mcp


def main() -> None:
	host = os.getenv("MCP_HOST", "127.0.0.1")
	port = int(os.getenv("MCP_PORT", "8000"))
	stateless = os.getenv("MCP_STATELESS_HTTP", "true").strip().lower() in {"1", "true", "yes", "on"}

	mcp.run(transport="http", host=host, port=port, stateless_http=stateless)


if __name__ == "__main__":
	main()
