import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage
import uuid

from streamlit_backend_by_agent import (
    ensure_title_for_thread,
    get_thread_title,
    set_thread_title,
)


def generate_threadid():
    return uuid.uuid4()


def reset_chat():
    thread_id = uuid.uuid4()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []


def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)


def load_conversation(thread_id):
    state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
    return state.values.get('messages', [])


## Session setup
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_threadid()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

add_thread(st.session_state['thread_id'])


st.sidebar.title('LangGraph ChatBot (by agent)')
if st.sidebar.button('New Chat'):
    reset_chat()


st.sidebar.header('My Conversations')

for thread_id in st.session_state['chat_threads'][::-1]:
    title = get_thread_title(thread_id)
    if st.sidebar.button(title):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []
        for message in messages:
            # class check: if it's a HumanMessage show role 'user', else 'assistant'
            try:
                from langchain_core.messages import HumanMessage as _HM
                is_human = isinstance(message, _HM)
            except Exception:
                is_human = False
            role = 'user' if is_human else 'assistant'
            temp_messages.append({'role': role, 'content': message.content})

        st.session_state['message_history'] = temp_messages


# Show editable title for current thread
current_tid = st.session_state['thread_id']
current_title = get_thread_title(current_tid)
new_title = st.sidebar.text_input('Edit thread title', value=current_title)
if st.sidebar.button('Save title'):
    set_thread_title(current_tid, new_title)


# Render conversation
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])


user_input = st.chat_input('Type here')

if user_input:
    # add to displayed history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    # If this is the first user message for the thread and title is raw id, generate a title
    raw_tid_str = str(st.session_state['thread_id'])
    if get_thread_title(raw_tid_str) == raw_tid_str:
        # generate and set title (may block while LLM responds)
        title = ensure_title_for_thread(raw_tid_str, user_input)
        # update displayed title in sidebar immediately
        # note: st.experimental_rerun could be used, but we simply set the session state mapping

    # Stream assistant reply
    with st.chat_message('assistant'):
        ai_message = st.write_stream(
            message_chunk.content for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode='messages',
            )
        )

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
