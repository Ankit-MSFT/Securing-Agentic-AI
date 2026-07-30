import asyncio
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from config import get_llm


SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()

MCP_SERVER_PATH = str(Path(__file__).parent.parent / "midtownbank" / "mcp_server.py")


async def main():
    # 1. Connect to MCP server
    client = MultiServerMCPClient(
        {
            "midtownbank": {
                "command": "python",
                "args": [MCP_SERVER_PATH],
                "transport": "stdio",
            }
        }
    )

    # 2. Get tools from MCP
    tools = await client.get_tools()
    print(f"Loaded {len(tools)} tools from MidTownBank MCP server")

    # 3. Create ReAct agent
    llm = get_llm()
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    # 4. Chat loop
    print("\nMidTown Assistant ready. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break

        response = await agent.ainvoke(
            {"messages": [("user", user_input)]}
        )

        ai_message = response["messages"][-1]
        print(f"\nAssistant: {ai_message.content}\n")

if __name__ == "__main__":
    asyncio.run(main())