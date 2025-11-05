import streamlit as st
from langgraph_backend import chatbot
from langchain_core.messages import HumanMessage
import uuid # generates random thread ids
# **************************************** utility functions *************************
def generate_threadid():
    thread_id = uuid.uuid4()
    return thread_id
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
    # Check if messages key exists in state values, return empty list if not
    return state.values.get('messages', [])
  


# **************************************** Session Setup ******************************
# st.session_state -> dict -> 


if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []


if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_threadid()

if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = []

add_thread(st.session_state['thread_id'])

# **************************************** Sidebar UI *********************************


st.sidebar.title('LangGraph ChataBot')
if st.sidebar.button('New Chat'):
    reset_chat()


st.sidebar.header('My Conversastion')

for thread_id in st.session_state['chat_threads'][::-1]:
    if st.sidebar.button(str(thread_id)):
        st.session_state['thread_id'] = thread_id
        messages = load_conversation(thread_id)

        temp_messages = []

        for message in messages:
            if isinstance(message,HumanMessage):
                role = 'user'
            else:
                role = 'assistant'
            temp_messages.append({'role':role,'content':message.content})
        

        st.session_state['message_history'] = temp_messages

        




# loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.markdown(message['content'])



#{'role': 'user', 'content': 'Hi'}
#{'role': 'assistant', 'content': 'Hi=ello'}

user_input = st.chat_input('Type here')

if user_input:

    # first add the message to message_history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    # first add the message to message_history
    with st.chat_message('assistant'):

        ai_message = st.write_stream(
            message_chunk.content for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config= CONFIG,
                stream_mode= 'messages'
            )
        )

    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})