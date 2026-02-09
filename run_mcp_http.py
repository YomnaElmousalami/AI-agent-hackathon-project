"""Run the AutoInsuranceMCP FastMCP server over HTTP (for Postman MCP testing).

Why this exists:
- Postman expects a stable HTTP MCP endpoint like: http://127.0.0.1:8000/mcp
- Some shells/environments can exit early when relying on env-var based branching.

Usage (PowerShell):
  python .\\run_mcp_http.py

Then in Postman:
	MCP URL: http://127.0.0.1:8000/mcp

Notes:
- Change HOST/PORT via env vars MCP_HOST / MCP_PORT.
- If you need stateless HTTP, set MCP_STATELESS_HTTP=true.

Troubleshooting:
- Postman MCP uses SSE under the hood. In practice, FastMCP's `streamable_http`
	transport is the most compatible with Postman on Windows.
- If Postman tries IPv6 first (::1) and fails, use 127.0.0.1 explicitly.
"""

from __future__ import annotations

import os

from insurance_mcp import mcp


def main() -> None:
	# Bind to IPv4 loopback by default; Postman sometimes tries ::1 first, so
	# always use 127.0.0.1 as the URL in Postman.
	host = os.getenv("MCP_HOST", "127.0.0.1")
	port = int(os.getenv("MCP_PORT", "8000"))
	# Default to stateless HTTP for robustness with Postman MCP + Windows.
	stateless = os.getenv("MCP_STATELESS_HTTP", "true").strip().lower() in {"1", "true", "yes", "on"}

	# FastMCP serves the MCP endpoint at /mcp by default for HTTP transport.
	# Run this file with Python 3.11 on Windows (see dev_mcp_postman.ps1) for the
	# most reliable behavior with Postman MCP.
	mcp.run(transport="http", host=host, port=port, stateless_http=stateless)


if __name__ == "__main__":
	main()
