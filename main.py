import streamlit as st
from app.agent.core import Agent

st.set_page_config(page_title="Microscopy AI Agent Demo", layout="wide")

st.title("Microscopy AI Agent Demo")
st.write("This is a demo for testing a local LLM tool calling agent with microscopy functions.")

@st.cache_resource
def get_agent():
    return Agent()

agent = get_agent()

st.subheader("Chat with the Agent")
user_input = st.text_input("Enter your command:")

if user_input:
    st.write(f"You said: {user_input}")
    with st.spinner("Thinking..."):
        response = agent.chat(user_input)
        st.write(response)