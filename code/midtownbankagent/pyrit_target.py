"""PyRIT target wrapper for MidTown Assistant agent."""

import asyncio
import uuid
from pathlib import Path

from pyrit.models.messages.message import Message, MessagePiece
from pyrit.prompt_target import PromptTarget

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from config import get_llm

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()
MCP_SERVER_PATH = str(Path(__file__).parent.parent / "midtownbank" / "mcp_server.py")


class MidTownAgentTarget(PromptTarget):
    """Wraps the MidTown Assistant as a PyRIT attack target."""

    def __init__(self, model_name: str = "gpt-4.1-mini", verbose: bool = True):
        super().__init__()
        self._model_name = model_name
        self._agent = None
        self._tool_calls: list[str] = []
        self._tool_call_details: list[dict] = []  # Full details for logging
        self._verbose = verbose
        self._turn_count = 0

    async def _ensure_agent(self):
        """Lazy-init the agent on first use."""
        if self._agent is None:
            if self._verbose:
                print(f"[TARGET] Initializing agent with model: {self._model_name}")
            client = MultiServerMCPClient(
                {
                    "midtownbank": {
                        "command": "python",
                        "args": [MCP_SERVER_PATH],
                        "transport": "stdio",
                    }
                }
            )
            tools = await client.get_tools()
            if self._verbose:
                print(f"[TARGET] Loaded {len(tools)} MCP tools")
            llm = get_llm(self._model_name)
            self._agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)

    async def _send_prompt_to_target_async(
        self, *, normalized_conversation: list[Message]
    ) -> list[Message]:
        """Send the conversation to the agent and return the response."""
        await self._ensure_agent()
        self._turn_count += 1

        # Extract the last user message text
        last_message = normalized_conversation[-1]
        user_text = last_message.message_pieces[0].converted_value

        if self._verbose:
            print(f"\n{'─'*60}")
            print(f"[TURN {self._turn_count}] ATTACKER → AGENT:")
            print(f"  {user_text}")

        # Invoke the agent
        response = await self._agent.ainvoke(
            {"messages": [("user", user_text)]}
        )

        # Track and log tool calls
        turn_tool_calls = []
        for msg in response["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})
                    self._tool_calls.append(tool_name)
                    turn_tool_calls.append(tool_name)
                    detail = {"turn": self._turn_count, "tool": tool_name, "args": tool_args}
                    self._tool_call_details.append(detail)

                    if self._verbose:
                        args_short = str(tool_args)[:120]
                        print(f"  [TOOL CALL] 🔧 {tool_name}({args_short})")

            # Log tool responses
            if hasattr(msg, "type") and msg.type == "tool" and self._verbose:
                content_short = str(msg.content)[:150]
                print(f"  [TOOL RESULT] ← {content_short}")

        # Build response Message
        ai_content = response["messages"][-1].content
        conversation_id = last_message.message_pieces[0].conversation_id

        if self._verbose:
            print(f"\n[TURN {self._turn_count}] AGENT → ATTACKER:")
            print(f"  {ai_content[:300]}")
            if turn_tool_calls:
                print(f"  [Tools used this turn: {turn_tool_calls}]")
            else:
                print(f"  [No tools called this turn]")

        response_piece = MessagePiece(
            role="assistant",
            conversation_id=conversation_id,
            original_value=ai_content,
            converted_value=ai_content,
        )
        return [Message(message_pieces=[response_piece])]

    def get_tool_calls(self) -> list[str]:
        """Return all tool calls made (for custom scoring)."""
        return self._tool_calls.copy()

    def get_tool_call_details(self) -> list[dict]:
        """Return full details of all tool calls."""
        return self._tool_call_details.copy()

    def reset_tool_calls(self):
        """Clear tool call history between runs."""
        self._tool_calls.clear()
        self._tool_call_details.clear()
        self._turn_count = 0

    def reset_tool_calls(self):
        """Clear tool call history between runs."""
        self._tool_calls.clear()