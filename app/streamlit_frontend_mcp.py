import streamlit as st
import uuid
import queue
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, AIMessageChunk

# Import backend utilities from the new MCP backend
from langraph_mcp_backend import (
    chatbot,
    title_llm,
    save_thread_title,
    get_all_threads,
    delete_thread,
    submit_async_task
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

    # Insert new chat at the beginning (so it appears at top)
    st.session_state['chat_threads'] = {thread_id: "New Chat", **st.session_state['chat_threads']}

    st.session_state['message_history'] = []

def delete_chat(thread_id):
    # Delete from backend
    delete_thread(thread_id)

    # Remove from session state
    if thread_id in st.session_state['chat_threads']:
        del st.session_state['chat_threads'][thread_id]

    # If we're deleting the current chat, switch to a new one
    if st.session_state['thread_id'] == thread_id:
        reset_chat()

def load_conversation(thread_id):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        return state.values.get('messages', [])
    except Exception as e:
        print(f"Error loading conversation: {e}")
        return []

def extract_message_content(message):
    """Extract clean text content from AIMessage objects"""
    content = message.content
    if isinstance(content, list):
        # Extract text parts from structured content
        text_parts = [
            part.get("text", "")
            for part in content
            if isinstance(part, dict) and part.get("type") == "text"
        ]
        return "".join(text_parts)
    return str(content)

# -------------------- Initialize session state --------------------
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = []

# Load previous chat titles from DB if empty
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = get_all_threads()

if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_threadid()
    # Insert at beginning so new chat appears at top
    st.session_state['chat_threads'] = {st.session_state['thread_id']: "New Chat", **st.session_state['chat_threads']}

# Ensure current thread exists
if st.session_state['thread_id'] not in st.session_state['chat_threads']:
    # Insert at beginning so it appears at top
    st.session_state['chat_threads'] = {st.session_state['thread_id']: "New Chat", **st.session_state['chat_threads']}

# Initialize delete confirmations
if 'delete_confirmations' not in st.session_state:
    st.session_state.delete_confirmations = {}

# -------------------- Sidebar --------------------
st.sidebar.title("LangGraph MCP ChatBot")

if st.sidebar.button("New Chat"):
    reset_chat()
    st.rerun()

st.sidebar.subheader("My Conversations")

threads_list = list(st.session_state['chat_threads'].items())

# Create a container for delete confirmations
if 'delete_confirmations' not in st.session_state:
    st.session_state.delete_confirmations = {}

for thread_id, title in threads_list:
    # Check if we need to show confirmation dialog for this thread
    if st.session_state.delete_confirmations.get(thread_id):
        col1, col2, col3 = st.sidebar.columns([3, 1, 1])
        with col1:
            st.sidebar.write(f"Delete '{title}'?")
        with col2:
            if st.sidebar.button("✅", key=f"confirm_{thread_id}"):
                delete_chat(thread_id)
                st.session_state.delete_confirmations[thread_id] = False
                st.rerun()
        with col3:
            if st.sidebar.button("❌", key=f"cancel_{thread_id}"):
                st.session_state.delete_confirmations[thread_id] = False
                st.rerun()
    else:
        col1, col2 = st.sidebar.columns([4, 1])
        with col1:
            if st.button(title, key=thread_id, use_container_width=True):
                st.session_state['thread_id'] = thread_id
                messages = load_conversation(thread_id)

                temp_messages = []
                for message in messages:
                    # Skip ToolMessage (raw JSON tool output)
                    if isinstance(message, ToolMessage):
                        continue

                    # Skip AIMessage with empty content (tool call requests)
                    if isinstance(message, AIMessage) and not message.content:
                        continue

                    role = "user" if isinstance(message, HumanMessage) else "assistant"
                    # Extract clean text content from structured AIMessages
                    content = extract_message_content(message)
                    temp_messages.append({"role": role, "content": content})

                st.session_state['message_history'] = temp_messages
        with col2:
            # Add delete button for each chat
            if st.button("🗑️", key=f"delete_{thread_id}", use_container_width=True):
                st.session_state.delete_confirmations[thread_id] = True
                st.rerun()

# **************************************** Main Chat UI *********************************

current_thread = st.session_state['thread_id']
messages = st.session_state['message_history']

# Show placeholder title ONLY before first question
if len(messages) == 0:
    st.title("Start an MCP conversation")

# Show chat history
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
    CONFIG = {
        "configurable": {"thread_id": st.session_state["thread_id"]},
        "metadata": {"thread_id": st.session_state["thread_id"]},
        "run_name": "chat_turn",
    }

    # Assistant streaming block
    with st.chat_message("assistant"):
        status_holder = {"box": None}
        message_placeholder = st.empty()
        full_response = ""

        def ai_only_stream():
            event_queue = queue.Queue()

            async def run_stream():
                try:
                    async for message_chunk, metadata in chatbot.astream(
                        {"messages": [HumanMessage(content=user_input)]},
                        config=CONFIG,
                        stream_mode="messages",
                    ):
                        event_queue.put((message_chunk, metadata))
                except Exception as exc:
                    event_queue.put(("error", exc))
                finally:
                    event_queue.put(None)

            submit_async_task(run_stream())

            collected_text = ""
            while True:
                try:
                    item = event_queue.get(timeout=30)
                    if item is None:
                        break
                    
                    if isinstance(item, tuple) and item[0] == "error":
                        st.error(f"Error: {item[1]}")
                        break
                    
                    message_chunk, _ = item

                    # Handle ToolMessage
                    if isinstance(message_chunk, ToolMessage):
                        tool_name = getattr(message_chunk, "name", "tool")
                        if status_holder["box"] is None:
                            status_holder["box"] = st.status(f"🔧 Using `{tool_name}` …", expanded=True)
                        else:
                            status_holder["box"].update(label=f"🔧 Using `{tool_name}` …", state="running")
                        continue

                    # Handle AIMessage or AIMessageChunk
                    if isinstance(message_chunk, (AIMessage, AIMessageChunk)):
                        content = message_chunk.content
                        if isinstance(content, list):
                            text_parts = [
                                part.get("text", "")
                                for part in content
                                if isinstance(part, dict) and part.get("type") == "text"
                            ]
                            content = "".join(text_parts)
                        
                        if content:
                            collected_text += str(content)
                            message_placeholder.markdown(collected_text + "▌")
                    
                except queue.Empty:
                    break
            
            return collected_text.strip()

        # Run and display the assistant message
        ai_message = ai_only_stream()

        # Update tool status if any were used
        if status_holder["box"] is not None:
            status_holder["box"].update(label="✅ Tool finished", state="complete", expanded=False)

        # Final clean display
        if ai_message:
            message_placeholder.markdown(ai_message)
            st.session_state['message_history'].append({"role": "assistant", "content": ai_message})

    # Handle first-message title creation + DB saving
    if is_first_message:
        new_title = get_ai_title_for_query(user_input)
        thread_id = st.session_state['thread_id']
        save_thread_title(thread_id, new_title)
        st.session_state['chat_threads'][thread_id] = new_title
        st.rerun()
