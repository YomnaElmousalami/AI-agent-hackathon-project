"""Stable local runner for the FastAPI backend (Windows-friendly).

This project previously ran uvicorn programmatically to work around VS Code
terminal quirks. On newer Python versions (notably 3.14) and some VS Code
terminal combinations, embedding uvicorn in-process can lead to spurious
KeyboardInterrupts when other terminals run commands.

The most reliable approach is to spawn uvicorn as a separate process.

Usage (PowerShell):
  python .\\run_api.py
"""

from __future__ import annotations

import os
import subprocess
import sys


def main() -> None:
	port = os.getenv("PORT", "8001")
	host = os.getenv("HOST", "127.0.0.1")
	log_level = os.getenv("LOG_LEVEL", "info")

	cmd = [
		sys.executable,
		"-m",
		"uvicorn",
		"api_server:app",
		"--host",
		host,
		"--port",
		str(port),
		"--log-level",
		str(log_level),
	]

	creationflags = 0
	kwargs: dict[str, object] = {}
	if os.name == "nt":
		creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
		kwargs["stdin"] = subprocess.DEVNULL
		kwargs["stdout"] = None
		kwargs["stderr"] = None

	proc = subprocess.Popen(cmd, creationflags=creationflags, **kwargs)  # type: ignore[arg-type]
	print(f"uvicorn started (pid={proc.pid}) on http://{host}:{port}")
	print("Close this terminal or Ctrl+C here to stop this launcher; the server is detached.")
	raise SystemExit(proc.wait())


if __name__ == "__main__":
	main()
