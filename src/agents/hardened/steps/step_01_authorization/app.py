"""Streamlit UI for the Entra-authorized hardened agent."""

import asyncio

import streamlit as st

from agents.hardened.steps.step_01_authorization.entra_login import (
    begin_login,
    complete_login,
    take_pending_flow,
)
from agents.hardened.steps.step_01_authorization.factory import build_agent


def _error_message(error: BaseException) -> str:
    if isinstance(error, BaseExceptionGroup):
        messages = [_error_message(child) for child in error.exceptions]
        return next((message for message in messages if message), str(error))
    return str(error) or type(error).__name__


def process_auth_callback() -> None:
    if "code" not in st.query_params:
        return

    query_parameters = st.query_params.to_dict()
    state = query_parameters.get("state", "")
    flow = st.session_state.pop("auth_flow", None)
    if flow is None or flow.get("state") != state:
        flow = take_pending_flow(state)
    if flow is None:
        st.query_params.clear()
        st.session_state.auth_error = (
            "The sign-in request expired or was already used. Start sign-in again."
        )
        return

    result = complete_login(flow, query_parameters)
    st.query_params.clear()
    if "access_token" not in result:
        st.session_state.auth_error = result.get(
            "error_description", "Microsoft Entra sign-in failed."
        )
        return

    st.session_state.access_token = result["access_token"]
    st.session_state.employee_name = result.get("id_token_claims", {}).get(
        "name", "Signed-in employee"
    )
    st.session_state.pop("auth_error", None)
    st.rerun()


st.set_page_config(page_title="MidTown Assistant", page_icon="🏦")
process_auth_callback()

st.title("MidTown Assistant")

if "access_token" not in st.session_state:
    st.subheader("Employee sign-in")
    if error := st.session_state.get("auth_error"):
        st.error(error)
    if "auth_flow" not in st.session_state:
        st.session_state.auth_flow = begin_login()
    st.link_button(
        "Sign in with Microsoft Entra",
        st.session_state.auth_flow["auth_uri"],
        type="primary",
    )
    st.stop()

with st.sidebar:
    st.header("Settings")
    model = st.selectbox("Model", ["gpt-5.1", "mistral", "deepseek"])
    st.divider()
    st.caption(st.session_state.get("employee_name", "Signed-in employee"))
    if st.button("Sign out"):
        st.session_state.clear()
        st.rerun()
    if st.button("Clear chat"):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Ask MidTown Assistant..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    loop = asyncio.new_event_loop()
    try:
        try:
            agent = loop.run_until_complete(
                build_agent(st.session_state.access_token, model)
            )
            response = loop.run_until_complete(
                agent.ainvoke({"messages": [("user", prompt)]})
            )
        except Exception as error:
            st.error(f"Request blocked or unavailable: {_error_message(error)}")
            st.stop()
    finally:
        loop.close()

    ai_message = response["messages"][-1]
    with st.chat_message("assistant"):
        for message in response["messages"][1:-1]:
            if hasattr(message, "tool_calls") and message.tool_calls:
                for tool_call in message.tool_calls:
                    st.caption(f"🔧 Called: `{tool_call['name']}`")
        st.markdown(ai_message.content)

    st.session_state.messages.append(
        {"role": "assistant", "content": ai_message.content}
    )