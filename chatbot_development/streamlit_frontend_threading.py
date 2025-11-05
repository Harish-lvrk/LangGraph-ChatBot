import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage
import uuid  # Used to generate unique thread IDs


# =============================== Utility Functions ===============================

def generate_threadid():
    """Generate a unique UUID for a new chat thread."""
    return uuid.uuid4()


def reset_chat():
    """Reset the current chat to a new conversation thread."""
    thread_id = generate_threadid()
    st.session_state['thread_id'] = thread_id
    add_thread(thread_id)
    st.session_state['message_history'] = []


def add_thread(thread_id):
    """Store thread ID in session if not already present."""
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)


def load_conversation(thread_id):
    """
    Load stored conversation messages for a thread from LangGraph state.
    Returns message list or empty list if no data exists.
    """
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get('messages', [])


# =============================== Session State Setup ===============================

# Initialize message history if missing
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# Initialize thread id if missing
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_threadid()

# Initialize thread list if missing
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

# Ensure current thread is tracked
add_thread(st.session_state['thread_id'])


# =============================== Sidebar UI ===============================

st.sidebar.title('LangGraph ChatBot')

# New chat button — resets to fresh thread
if st.sidebar.button('New Chat'):
    reset_chat()

st.sidebar.header('My Conversations')

# Display thread buttons (latest first)
for thread_id in st.session_state['chat_threads'][::-1]:
    if st.sidebar.button(str(thread_id)):
        st.session_state['thread_id'] = thread_id

        # Load previous conversation messages from backend
        messages = load_conversation(thread_id)
        formatted_messages = []

        for message in messages:
            role = 'user' if isinstance(message, HumanMessage) else 'assistant'
            formatted_messages.append({'role': role, 'content': message.content})

        st.session_state['message_history'] = formatted_messages


# =============================== Display Chat History ===============================

for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])


# =============================== Chat Input & Response Streaming ===============================

user_input = st.chat_input('Type here')

if user_input:
    # Display user message and add to history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.write(user_input)

    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    # Stream model response
    with st.chat_message('assistant'):
        ai_message = st.write_stream(
            message_chunk.content
            for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages'
            )
        )

    # Store assistant reply
    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
