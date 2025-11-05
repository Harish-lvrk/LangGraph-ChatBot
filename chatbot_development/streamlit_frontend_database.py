# import streamlit as st
# from langgraph_backend import chatbot,title_llm
# from langchain_core.messages import HumanMessage
# import uuid # generates random thread ids

# # --- NEW FUNCTION (FOR YOU TO IMPLEMENT) ---
# # This is where you'll put your AI call.
# # You should use a separate, simple LLM (not the stateful chatbot)
# # to generate a title.
# def get_ai_title_for_query(query: str) -> str:
#     # Generates a concise, AI-powered title (5 words or less) for a user's query
    
#     try:
#         # Make sure you have your title_llm defined
#         prompt = f"""Generate a very short, concise title (fro side bar title so only give titel) for this chat query: '{query}'"
#         """
#         response = title_llm.invoke(prompt)
#         return response.title.strip()
        
#     except Exception as e:
#         print(f"Error generating title: {e}")
#         # Fallback to a simple truncation
#         return query[:30] + "..."

    
    
#     # --- PLACEHOLDER ---
#     # Replace this placeholder with your actual LLM call from the example above.
#     print("WARNING: Using placeholder title generation. Implement get_ai_title_for_query().")
#     fallback_title = query[:35] + "..."
#     return fallback_title


# # **************************************** utility functions *************************
# def generate_threadid():
#     return str(uuid.uuid4()) # Ensure it's a string

# def reset_chat():
#     thread_id = generate_threadid()
#     st.session_state['thread_id'] = thread_id
#     add_thread(st.session_state['thread_id']) # Add with default title
#     st.session_state['message_history'] = []

# def add_thread(thread_id, title=None):
#     # --- MODIFIED ---
#     # Adds a thread to the dictionary.
#     if thread_id not in st.session_state['chat_threads']:
#         # Use provided title or a default
#         st.session_state['chat_threads'][thread_id] = title if title else f"New Chat"

# def load_conversation(thread_id):
#     try:
#         state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
#         # Check if messages key exists in state values, return empty list if not
#         return state.values.get('messages', [])
#     except Exception as e:
#         # Handle cases where the thread might not exist in the backend yet
#         print(f"Error loading conversation state: {e}")
#         return []

# # **************************************** Session Setup ******************************

# if 'message_history' not in st.session_state:
#     st.session_state['message_history'] = []

# # --- MODIFIED ---
# # chat_threads is now a dictionary: {thread_id: title}
# if 'chat_threads' not in st.session_state:
#     st.session_state['chat_threads'] = {}

# if 'thread_id' not in st.session_state:
#     st.session_state['thread_id'] = generate_threadid()
#     add_thread(st.session_state['thread_id'], "New Chat") # Add the initial chat

# # Ensure the *current* thread_id is always in the dictionary
# # This handles the very first run
# if st.session_state['thread_id'] not in st.session_state['chat_threads']:
#     add_thread(st.session_state['thread_id'], "New Chat")


# # **************************************** Sidebar UI *********************************

# st.sidebar.title('LangGraph ChataBot')
# if st.sidebar.button('New Chat'):
#     reset_chat()
#     st.rerun() # Rerun to switch to the new chat

# st.sidebar.header('My Conversations') # Corrected typo

# # --- MODIFIED ---
# # Iterate over the dictionary's items in reverse chronological order
# threads_list = reversed(list(st.session_state['chat_threads'].items()))

# for thread_id, title in threads_list:
    
#     # Use the title for the button label
#     # Use thread_id as the key to keep buttons unique even if titles are the same
#     if st.sidebar.button(title, key=thread_id, use_container_width=True):
        
#         # Set the active thread_id
#         st.session_state['thread_id'] = thread_id
        
#         # Load the conversation for this thread
#         messages = load_conversation(thread_id)
        
#         temp_messages = []
#         for message in messages:
#             role = 'user' if isinstance(message, HumanMessage) else 'assistant'
#             temp_messages.append({'role': role, 'content': message.content})
        
#         # Update the message history in session state
#         st.session_state['message_history'] = temp_messages
        
        

# # **************************************** Main Chat UI *********************************

# # loading the conversation history
# for message in st.session_state['message_history']:
#     with st.chat_message(message['role']):
#         st.markdown(message['content'])

# user_input = st.chat_input('Type here')

# if user_input:
    
#     # Check if this is the first message *before* sending it to the backend
#     # We do this by checking the backend state, not the session_state history
#     current_messages = load_conversation(st.session_state['thread_id'])
#     is_first_message = len(current_messages) == 0

#     # Add the user message to the UI
#     st.session_state['message_history'].append({'role': 'user', 'content': user_input})
#     with st.chat_message('user'):
#         st.text(user_input)

#     CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

#     ## Stream model response
#     with st.chat_message('assistant'):
#         ai_message = st.write_stream(
#             message_chunk.content
#             for message_chunk, metadata in chatbot.stream(
#                 {'messages': [HumanMessage(content=user_input)]},
#                 config=CONFIG,
#                 stream_mode='messages'
#             )
#         )

#     # Store assistant reply
#     st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})

#     # --- NEW: TITLE GENERATION LOGIC ---
#     if is_first_message:
#         # This was the first message. Generate and set the title.
#         new_title = get_ai_title_for_query(user_input)
        
#         # Update the title in our dictionary
#         st.session_state['chat_threads'][st.session_state['thread_id']] = new_title
        
#         # Rerun to update the sidebar with the new title
#         st.rerun()


import streamlit as st
import uuid
from langchain_core.messages import HumanMessage

# Import backend utilities
from langgraph_database_backend import (
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

    # Send to LangGraph
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}

    with st.chat_message("assistant"):
        ai_message = st.write_stream(
            message_chunk.content
            for message_chunk, metadata in chatbot.stream(
                {"messages": [HumanMessage(content=user_input)]},
                config=CONFIG,
                stream_mode="messages"
            )
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
