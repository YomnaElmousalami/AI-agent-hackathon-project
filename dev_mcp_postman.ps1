$ErrorActionPreference = 'Stop'

Set-Location -Path $PSScriptRoot

$env:MCP_HOST = '127.0.0.1'
$env:MCP_PORT = '8000'
$env:MCP_STATELESS_HTTP = 'true'

Write-Host "Starting MCP HTTP server for Postman at http://localhost:8000/mcp" -ForegroundColor Cyan
Write-Host "(If Postman still tries IPv6 ::1, ensure your hosts file maps localhost -> 127.0.0.1)" -ForegroundColor DarkGray

py -3.11 .\run_mcp_postman.py
