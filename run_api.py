"""Convenience entrypoint for running the FastAPI backend locally.

Why this exists:
- In some Windows/VS Code environments, launching `uvicorn api_server:app` can
  exit immediately due to terminal lifecycle / signal handling.
- Running uvicorn programmatically keeps the process attached to the current
  Python interpreter and is often more stable.

Usage:
  python .\\run_api.py
"""

from __future__ import annotations

import os

import uvicorn

from api_server import app


def main() -> None:
	port = int(os.getenv("PORT", "8001"))
	uvicorn.run(
		app,
		host=os.getenv("HOST", "127.0.0.1"),
		port=port,
		log_level=os.getenv("LOG_LEVEL", "info"),
		reload=os.getenv("RELOAD", "0") not in {"0", "false", "False"},
	)


if __name__ == "__main__":
	main()
