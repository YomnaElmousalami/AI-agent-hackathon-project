<#
Run the AutoInsuranceMCP server in a way that's compatible with Postman MCP.

Why this exists:
- On Windows + Python 3.14, FastMCP/Uvicorn can start and then immediately exit,
  which causes Postman to fail with ECONNREFUSED when connecting to SSE.
- Python 3.11 is installed on this machine and is stable for FastMCP HTTP.

Postman MCP URL (use exactly this):
  http://localhost:8000/mcp

Usage:
  .\dev_mcp_postman.ps1
#>

$ErrorActionPreference = 'Stop'

# Ensure we run from repo root.
Set-Location -Path $PSScriptRoot

# Force IPv4 for localhost so Postman doesn't try ::1 first.
$env:MCP_HOST = '127.0.0.1'
$env:MCP_PORT = '8000'
$env:MCP_STATELESS_HTTP = 'true'

Write-Host "Starting MCP HTTP server for Postman at http://localhost:8000/mcp" -ForegroundColor Cyan
Write-Host "(If Postman still tries IPv6 ::1, ensure your hosts file maps localhost -> 127.0.0.1)" -ForegroundColor DarkGray

# Use the Python launcher to force 3.11.
py -3.11 .\run_mcp_postman.py
