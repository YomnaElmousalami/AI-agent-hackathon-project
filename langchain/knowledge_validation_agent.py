import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict

from langchain_mcp_adapters.client import MultiServerMCPClient


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
	sys.path.insert(0, str(REPO_ROOT))


def mcp_server_path() -> str:
	return str(REPO_ROOT / "insurance_mcp.py")


async def setup_mcp_client():
	mcp_server_script = os.getenv("INSURANCE_MCP_SERVER", mcp_server_path())

	client = MultiServerMCPClient(
		{
			"insurance": {
				"transport": "stdio",
				"command": sys.executable,
				"args": [mcp_server_script],
				"env": {
					"MCP_TRANSPORT": "stdio",
					"INSURANCE_DB_PATH": os.getenv(
						"INSURANCE_DB_PATH", os.path.join("database", "insurance.db")
					),
				},
			}
		}
	)

	return await client.get_tools()


def _pick_tool(tools, name: str):
	for t in tools:
		if getattr(t, "name", None) == name:
			return t
	raise RuntimeError(f"Tool '{name}' not found")


async def run_cli():
	tools = await setup_mcp_client()
	questions_tool = _pick_tool(tools, "get_knowledge_questions")
	grade_tool = _pick_tool(tools, "grade_knowledge_answer")

	customer_id = int(input("Customer id: ").strip())
	qs = await questions_tool.ainvoke({"customer_id": customer_id, "limit": 3})

	print("\nKnowledge check:")
	for q in qs:
		print("\n---")
		print(q["scenario"])
		ans = input("Answer: ")
		result: Dict[str, Any] = await grade_tool.ainvoke(
			{"customer_id": customer_id, "question_id": q["id"], "answer": ans}
		)
		print(f"Result: {'correct' if result['correct'] else 'wrong'} (score={result['score']:.2f})")
		print(f"Expected: {result['expected']}")


if __name__ == "__main__":
	asyncio.run(run_cli())

