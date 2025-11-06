import streamlit as st
import uuid
from langchain_core.messages import HumanMessage,AIMessage,ToolMessage

# Import backend utilities
from langgraph_tool_backend import (
    chatbot,
    title_llm,
    save_thread_title,
    get_all_threads
)

# -------------------- Title generation LLM --------------------
def get_ai_title_for_query(query: str) -> str:
    try:
        prompt = f"Generate a very short title (max 5 words) for this user query: '{query}'. Only output the title."
        response = title_llm.invoke(prompt)
        return response.title.strip()
    except Exception as e:
        print(f"Title generation error: {e}")
        return query[:30] + "..."

# -------------------- Utility functions --------------------
def generate_threadid():
    return str(uuid.uuid4())

def reset_chat():
    thread_id = generate_threadid()
    st.session_state['thread_id'] = thread_id

    # Insert placeholder title first
    st.session_state['chat_threads'][thread_id] = "New Chat"

    st.session_state['message_history'] = []

def load_conversation(thread_id):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        return state.values.get('messages', [])
    except Exception as e:
        print(f"Error loading conversation: {e}")
        return []

# -------------------- Initialize session state --------------------
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# Load previous chat titles from DB if empty
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = get_all_threads()

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_threadid()
    st.session_state['chat_threads'][st.session_state['thread_id']] = "New Chat"

# Ensure current thread exists
if st.session_state['thread_id'] not in st.session_state['chat_threads']:
    st.session_state['chat_threads'][st.session_state['thread_id']] = "New Chat"

# -------------------- Sidebar --------------------
st.sidebar.title("LangGraph ChatBot")

if st.sidebar.button("New Chat"):
    reset_chat()
    st.rerun()

st.sidebar.subheader("My Conversations")

threads_list = reversed(list(st.session_state['chat_threads'].items()))

for thread_id, title in threads_list:
    if st.sidebar.button(title, key=thread_id, use_container_width=True):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        for message in messages:
            role = "user" if isinstance(message, HumanMessage) else "assistant"
            temp_messages.append({"role": role, "content": message.content})

        st.session_state['message_history'] = temp_messages

# **************************************** Main Chat UI *********************************

current_thread = st.session_state['thread_id']
messages = st.session_state['message_history']

# Show placeholder title ONLY before first question
if len(messages) == 0:
    st.title("Start a conversation")  # or any good placeholder line

# Show chat history (after first message, title disappears)
for message in messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_input = st.chat_input("Type here...")

if user_input:
    # Identify if first message for this thread
    current_messages = load_conversation(st.session_state['thread_id'])
    is_first_message = len(current_messages) == 0
   

    # Display user message
    st.session_state['message_history'].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # Send to LangGraph and langsmith
    CONFIG = {
        "configurable": {"thread_id": st.session_state["thread_id"]},
        "metadata": {"thread_id": st.session_state["thread_id"]},
        "run_name": "chat_turn",
    }

    # Assistant streaming block
    with st.chat_message("assistant"):
        # Use a mutable holder so the generator can set/modify it
        status_holder = {"box": None}

        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages",
            ):
                # Lazily create & update the SAME status container when any tool runs
                if isinstance(message_chunk, ToolMessage):
                    tool_name = getattr(message_chunk, "name", "tool")
                    if status_holder["box"] is None:
                        status_holder["box"] = st.status(
                            f"🔧 Using `{tool_name}` …", expanded=True
                        )
                    else:
                        status_holder["box"].update(
                            label=f"🔧 Using `{tool_name}` …",
                            state="running",
                            expanded=True,
                        )

                # Stream ONLY assistant tokens
                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content

        ai_message = st.write_stream(ai_only_stream())

        # Finalize only if a tool was actually used
        if status_holder["box"] is not None:
            status_holder["box"].update(
                label="✅ Tool finished", state="complete", expanded=False
            )

    # Save to session history
    st.session_state['message_history'].append({"role": "assistant", "content": ai_message})

    # Handle first-message title creation + DB saving
    if is_first_message:
        new_title = get_ai_title_for_query(user_input)

        thread_id = st.session_state['thread_id']

        # Save title in DB
        save_thread_title(thread_id, new_title)

        # Update UI dictionary
        st.session_state['chat_threads'][thread_id] = new_title

        st.rerun()
