import json
import sys
from typing import Any, Dict

_PIPED_LINE_BUFFER: list[str] | None = None


def read_prompt_or_stdin(prompt: str) -> str:
	"""Read a single value from stdin if piped, otherwise use input().

	This makes CLIs work with both:
	- interactive: `python .\\langchain\\some_agent.py`
	- piped: `"value" | python .\\langchain\\some_agent.py`
	"""
	global _PIPED_LINE_BUFFER
	if sys.stdin is not None and not sys.stdin.isatty():
		if _PIPED_LINE_BUFFER is None:
			raw = sys.stdin.read() or ""
			_PIPED_LINE_BUFFER = raw.splitlines()
		val = ""
		if _PIPED_LINE_BUFFER:
			val = str(_PIPED_LINE_BUFFER.pop(0)).strip()
		print(prompt, end="")
		print(val)
		return val
	try:
		return input(prompt).strip()
	except EOFError:
		return ""


def prompt_text(
	prompt: str,
	*,
	allow_empty: bool = False,
	invalid_message: str | None = None,
) -> str:
	"""Prompt the user for a text value safely.

	- Avoids raising EOFError (EOF is treated as empty input).
	- Keeps prompting until a valid value is provided.
	"""
	while True:
		s = read_prompt_or_stdin(prompt)
		if s or allow_empty:
			return s
		print(invalid_message or "Please enter a value.")


def prompt_int(
	prompt: str,
	*,
	min_value: int | None = None,
	max_value: int | None = None,
	default: int | None = None,
	invalid_message: str | None = None,
) -> int:
	"""Prompt the user for an integer safely and keep asking until valid."""
	while True:
		raw = read_prompt_or_stdin(prompt)
		if default is not None and str(raw).strip() == "":
			val = int(default)
			# still validate bounds
			if min_value is not None and val < min_value:
				print(invalid_message or f"Please enter a number >= {min_value}.")
				continue
			if max_value is not None and val > max_value:
				print(invalid_message or f"Please enter a number <= {max_value}.")
				continue
			return val
		try:
			val = int(str(raw).strip())
		except Exception:
			print(invalid_message or "Please enter a number.")
			continue
		if min_value is not None and val < min_value:
			print(invalid_message or f"Please enter a number >= {min_value}.")
			continue
		if max_value is not None and val > max_value:
			print(invalid_message or f"Please enter a number <= {max_value}.")
			continue
		return val


def prompt_int_optional(
	prompt: str,
	*,
	min_value: int | None = None,
	max_value: int | None = None,
	invalid_message: str | None = None,
) -> int | None:
	"""Prompt for an optional integer (blank => None)."""
	while True:
		raw = read_prompt_or_stdin(prompt)
		s = str(raw).strip()
		if s == "":
			return None
		try:
			val = int(s)
		except Exception:
			print(invalid_message or "Please enter a number (or leave blank).")
			continue
		if min_value is not None and val < min_value:
			print(invalid_message or f"Please enter a number >= {min_value}.")
			continue
		if max_value is not None and val > max_value:
			print(invalid_message or f"Please enter a number <= {max_value}.")
			continue
		return val


def prompt_yes_no_optional(prompt: str) -> bool | None:
	"""Prompt for y/n with blank allowed => None."""
	while True:
		s = read_prompt_or_stdin(prompt).strip().lower()
		if s in {"", "unknown", "?"}:
			return None
		if s in {"y", "yes"}:
			return True
		if s in {"n", "no"}:
			return False
		print("Please enter y, n, or leave blank.")


def coerce_tool_result(res: Any) -> Dict[str, Any]:
	"""Coerce MCP tool results into a dict.

	Depending on MCP adapter/transport versions, tool invocation can return:
	- a dict (ideal)
	- a list of parts/messages (often containing one dict or a JSON string)
	- a dict wrapped as {'type': 'text', 'text': '{...json...}'}
	"""
	if isinstance(res, dict):
		if "text" in res and isinstance(res.get("text"), str):
			try:
				parsed = json.loads(res["text"])
				if isinstance(parsed, dict):
					return parsed
			except Exception:
				pass
		return res

	if isinstance(res, list):
		for item in res:
			if isinstance(item, dict):
				if "text" in item and isinstance(item.get("text"), str):
					try:
						parsed = json.loads(item["text"])
						if isinstance(parsed, dict):
							return parsed
					except Exception:
						pass
				return item
			if isinstance(item, str):
				try:
					parsed = json.loads(item)
					if isinstance(parsed, dict):
						return parsed
				except Exception:
					pass
		if res and hasattr(res[0], "get"):
			return res[0]

	return {"raw": res}
