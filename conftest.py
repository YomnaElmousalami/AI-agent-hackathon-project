"""Pytest configuration shared across the repo.

Note: We *don't* hard-require `pytest-asyncio` here because some dev
environments/venvs may not have it installed. When it *is* installed, pytest
will auto-discover it via entrypoints and async tests will run as expected.
"""
