import streamlit as st

st.set_page_config(page_title="Microscopy AI Agent Demo", layout="wide")

st.title("Microscopy AI Agent Demo")
st.write("This is a demo for testing a local LLM tool calling agent with microscopy functions.")

# Placeholder for chat interface
st.subheader("Chat with the Agent")
user_input = st.text_input("Enter your command:")

if user_input:
    st.write(f"You said: {user_input}")
    # TODO: Integrate agent here
