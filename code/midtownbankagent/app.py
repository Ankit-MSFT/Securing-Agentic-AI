import asyncio
import streamlit as st
from pathlib import Path

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent

from config import get_llm

SYSTEM_PROMPT = (Path(__file__).parent / "system_prompt.txt").read_text()
MCP_SERVER_PATH = str(Path(__file__).parent.parent / "midtownbank" / "mcp_server.py")

@st.cache_resource
def get_agent(model_name: str):
    """Initialize MCP client + agent (cached across reruns)."""
    loop = asyncio.new_event_loop()
    
    client = MultiServerMCPClient(
        {
            "midtownbank": {
                "command": "python",
                "args": [MCP_SERVER_PATH],
                "transport": "stdio",
            }
        }
    )
    tools = loop.run_until_complete(client.get_tools())
    
    llm = get_llm(model_name)
    agent = create_react_agent(llm, tools, prompt=SYSTEM_PROMPT)
    return agent, loop

st.set_page_config(page_title="MidTown Assistant", page_icon="🏦")
st.title("MidTown Assistant")

# Sidebar — model selector
with st.sidebar:
    st.header("Settings")
    model = st.selectbox("Model", ["gpt-4.1-mini", "llama", "deepseek"])
    st.divider()
    st.caption("Role: Customer Service (Teller)")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

    # Initialize chat history
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask MidTown Assistant..."):
    # Show user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Get agent response
    agent, loop = get_agent(model)
    response = loop.run_until_complete(
        agent.ainvoke({"messages": [("user", prompt)]})
    )

    # Extract AI response + tool calls
    ai_message = response["messages"][-1]
    
    # Show tool calls (intermediate messages) for visibility
    with st.chat_message("assistant"):
        # Show any tool calls that happened
        for msg in response["messages"][1:-1]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    st.caption(f"🔧 Called: `{tc['name']}`")
        st.markdown(ai_message.content)

    st.session_state.messages.append({"role": "assistant", "content": ai_message.content})