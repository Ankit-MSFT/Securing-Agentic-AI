"""Baseline agent CLI (intentionally vulnerable)."""

import asyncio

from agents.baseline import build_agent


async def main():
    agent = await build_agent()
    print("\nMidTown Assistant ready. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if user_input.lower() in ("quit", "exit"):
            break
        response = await agent.ainvoke({"messages": [("user", user_input)]})
        print(f"\nAssistant: {response['messages'][-1].content}\n")


if __name__ == "__main__":
    asyncio.run(main())
