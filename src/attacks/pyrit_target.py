"""PyRIT target wrapper: drives a MidTownBank agent variant as an attack target."""

from pyrit.models.messages.message import Message, MessagePiece
from pyrit.prompt_target import PromptTarget

from agents.baseline import build_agent as build_baseline_agent


class MidTownAgentTarget(PromptTarget):
    """Wraps an agent factory as a PyRIT attack target.

    Defaults to the baseline (vulnerable) agent; pass a different factory to
    target a hardened variant with the same attack harness.
    """

    def __init__(
        self,
        model_name: str = "gpt-5.1",
        verbose: bool = True,
        agent_factory=build_baseline_agent,
    ):
        super().__init__()
        self._model_name = model_name
        self._agent_factory = agent_factory
        self._agent = None
        self._tool_calls: list[str] = []
        self._tool_call_details: list[dict] = []
        self._verbose = verbose
        self._turn_count = 0

    async def _ensure_agent(self):
        if self._agent is None:
            if self._verbose:
                print(f"[TARGET] Initializing agent with model: {self._model_name}")
            self._agent = await self._agent_factory(self._model_name)

    async def _send_prompt_to_target_async(
        self, *, normalized_conversation: list[Message]
    ) -> list[Message]:
        await self._ensure_agent()
        self._turn_count += 1

        last_message = normalized_conversation[-1]
        user_text = last_message.message_pieces[0].converted_value

        if self._verbose:
            print(f"\n{'─'*60}")
            print(f"[TURN {self._turn_count}] ATTACKER → AGENT:")
            print(f"  {user_text}")

        response = await self._agent.ainvoke({"messages": [("user", user_text)]})

        turn_tool_calls = []
        for msg in response["messages"]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    tool_name = tc["name"]
                    tool_args = tc.get("args", {})
                    self._tool_calls.append(tool_name)
                    turn_tool_calls.append(tool_name)
                    self._tool_call_details.append(
                        {"turn": self._turn_count, "tool": tool_name, "args": tool_args}
                    )
                    if self._verbose:
                        args_short = str(tool_args)[:120]
                        print(f"  [TOOL CALL] 🔧 {tool_name}({args_short})")

            if hasattr(msg, "type") and msg.type == "tool" and self._verbose:
                print(f"  [TOOL RESULT] ← {str(msg.content)[:150]}")

        ai_content = response["messages"][-1].content
        conversation_id = last_message.message_pieces[0].conversation_id

        if self._verbose:
            print(f"\n[TURN {self._turn_count}] AGENT → ATTACKER:")
            print(f"  {ai_content[:300]}")
            print(
                f"  [Tools used this turn: {turn_tool_calls}]"
                if turn_tool_calls
                else "  [No tools called this turn]"
            )

        response_piece = MessagePiece(
            role="assistant",
            conversation_id=conversation_id,
            original_value=ai_content,
            converted_value=ai_content,
        )
        return [Message(message_pieces=[response_piece])]

    def get_tool_calls(self) -> list[str]:
        return self._tool_calls.copy()

    def get_tool_call_details(self) -> list[dict]:
        return self._tool_call_details.copy()

    def reset_tool_calls(self):
        self._tool_calls.clear()
        self._tool_call_details.clear()
        self._turn_count = 0
