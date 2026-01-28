$ErrorActionPreference = 'Stop'

Write-Host "Starting FastAPI backend on http://127.0.0.1:8001 ..." -ForegroundColor Cyan
Start-Process -NoNewWindow -FilePath "python" -ArgumentList @(".\\run_api.py")

Write-Host "Starting Vite frontend..." -ForegroundColor Cyan
npm run dev
