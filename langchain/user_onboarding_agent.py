import asyncio
import os
import sys
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from llm.llama import get_llm

def mcp_server_path() -> str:
    repo_root = Path(__file__).resolve().parents[1]
    return str(repo_root / "insurance_mcp.py")


async def setup_mcp_client():
    """Connect to MCP Server."""

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


async def initialize_agent():
    llm = get_llm()
    tools = await setup_mcp_client()

    agent = create_react_agent(
        model=llm,
        tools=tools,
        #name: str, age: int, state: str, vehicleName: str, coverageType: str
        prompt=(
            "You are a helpful user onboarding assistant for an auto insurance learning app.\n"
            "Your job is to collect the user's profile id, name, age, state, vehicleName, coverageType and store it using the get_customer_info function.\n"
            "id must be an integer, name should be a string, age should be an integer, state should be a string, vehicleName should be a string, and coverageType should be a string.\n"
            "Be concise, ask one question at a time, and confirm details before storing.\n"
            "Always be polite and thorough in your responses.\n"
        ),
    )
    return agent


async def run_agent(agent, user_query: str):
    """Execute agent with user input"""
    async for chunk in agent.astream({
        "messages": [{"role": "user", "content": user_query}]
    }):
        print(chunk)


async def chat():
    """
        A chat interface where users can enter their credentials for onboarding.
    """

    agent = await initialize_agent()

    print("Hello and welcome to Auto Insurance User Onboarding")
    print("Please type in your credentials and press Enter")
    print("Once you're done, type 'exit' to quit")
    print("Here is a sample message: ")
    print("Hey. My id is 2, my name is Samuel, I'm 16, I live in NY, my vehicle is a Toyota Camry, and my coverage type is full coverage.")
    print()

    while True:
        user_query = input("> ").strip()
        if not user_query:
            continue
        if user_query.lower() in {"exit", "quit"}:
            break

        await run_agent(agent, user_query)


async def main():
    await chat()


if __name__ == "__main__":
    asyncio.run(main())