"""Streamlit UI for the baseline agent."""

import asyncio

import streamlit as st

from agents.baseline import build_agent


@st.cache_resource
def get_agent(model_name: str):
    loop = asyncio.new_event_loop()
    agent = loop.run_until_complete(build_agent(model_name))
    return agent, loop


st.set_page_config(page_title="MidTown Assistant", page_icon="🏦")
st.title("MidTown Assistant")

with st.sidebar:
    st.header("Settings")
    model = st.selectbox("Model", ["gpt-5.1", "mistral", "deepseek"])
    st.divider()
    st.caption("Role: Customer Service (Teller)")
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if prompt := st.chat_input("Ask MidTown Assistant..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    agent, loop = get_agent(model)
    response = loop.run_until_complete(
        agent.ainvoke({"messages": [("user", prompt)]})
    )
    ai_message = response["messages"][-1]

    with st.chat_message("assistant"):
        for msg in response["messages"][1:-1]:
            if hasattr(msg, "tool_calls") and msg.tool_calls:
                for tc in msg.tool_calls:
                    st.caption(f"🔧 Called: `{tc['name']}`")
        st.markdown(ai_message.content)

    st.session_state.messages.append({"role": "assistant", "content": ai_message.content})
