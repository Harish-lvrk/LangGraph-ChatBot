import streamlit as st
import uuid, time
from langchain_core.messages import HumanMessage
from langgraph_backend import (
    chatbot, title_llm, save_thread_title, get_all_threads,
    update_thread_title, delete_thread
)

# --- PAGE UI ---
st.set_page_config(page_title="Chat", layout="wide")
st.session_state.setdefault("thread_id", None)
st.session_state.setdefault("chat_threads", get_all_threads())
st.session_state.setdefault("message_history", [])
st.session_state.setdefault("rename_thread", None)
st.session_state.setdefault("confirm_delete", None)
st.session_state.setdefault("search_query", "")
st.session_state.setdefault("stop", False)

# --- Helpers ---
def load_messages(tid):
    try:
        state = chatbot.get_state({"configurable": {"thread_id": tid}})
        msgs = state.values.get("messages", [])
        return [{"role":"user" if isinstance(m,HumanMessage) else "assistant","content":m.content} for m in msgs]
    except:
        return []

def new_chat():
    st.session_state.thread_id = None
    st.session_state.message_history=[]
    st.rerun()

def gen_title(text):
    try:
        r = title_llm.invoke(f"Short title max 5 words: {text}")
        return r.title.strip()
    except:
        return text[:15]

# --- SIDEBAR ---
st.sidebar.title("Chats")
if st.sidebar.button("➕ New Chat"):
    new_chat()

st.session_state.search_query = st.sidebar.text_input("Search", st.session_state.search_query)
threads = get_all_threads(st.session_state.search_query)

if st.session_state.rename_thread:
    tid=st.session_state.rename_thread
    new = st.sidebar.text_input("Rename chat", st.session_state.chat_threads.get(tid,""))
    c1,c2 = st.sidebar.columns(2)
    if c1.button("Save"):
        update_thread_title(tid,new)
        st.session_state.chat_threads[tid]=new
        st.session_state.rename_thread=None; st.rerun()
    if c2.button("Cancel"):
        st.session_state.rename_thread=None; st.rerun()
    st.sidebar.write("---")

if st.session_state.confirm_delete:
    tid=st.session_state.confirm_delete
    st.sidebar.error(f"Delete '{st.session_state.chat_threads.get(tid)}'?")
    c1,c2=st.sidebar.columns(2)
    if c1.button("Yes"):
        delete_thread(tid)
        st.session_state.chat_threads.pop(tid,None)
        if st.session_state.thread_id==tid: new_chat()
        st.session_state.confirm_delete=None; st.rerun()
    if c2.button("Cancel"):
        st.session_state.confirm_delete=None; st.rerun()
    st.sidebar.write("---")

for tid,title in threads.items():
    c1,c2,c3 = st.sidebar.columns([7,1,1])
    if c1.button(title, key="open_"+tid): 
        st.session_state.thread_id=tid
        st.session_state.message_history = load_messages(tid)
    if c2.button("✏️", key="rn_"+tid):
        st.session_state.rename_thread=tid; st.rerun()
    if c3.button("🗑️", key="del_"+tid):
        st.session_state.confirm_delete=tid; st.rerun()

# --- MAIN CHAT UI ---
st.title("Start a conversation" if len(st.session_state.message_history)==0 else "")

for m in st.session_state.message_history:
    with st.chat_message(m["role"]):
        st.write(m["content"])

col1,col2 = st.columns([3,1])
user = col1.chat_input("Type your message...")
if col2.button("⛔ Stop"): st.session_state.stop=True

if user:
    if st.session_state.thread_id is None:
        tid=str(uuid.uuid4())
        st.session_state.thread_id=tid
        save_thread_title(tid,"New Chat")
        st.session_state.chat_threads[tid]="New Chat"

    tid = st.session_state.thread_id
    backend = load_messages(tid)
    first = len(backend)==0
    st.session_state.stop=False

    st.session_state.message_history.append({"role":"user","content":user})
    with st.chat_message("user"): st.write(user)

    with st.chat_message("assistant"):
        placeholder = st.empty()

        # spinner + dots
        with st.spinner("Thinking..."):
            for d in ["•","••","•••"]*2:
                if st.session_state.stop: placeholder.markdown("*Stopped*"); break
                placeholder.markdown(f"*Thinking {d}*"); time.sleep(0.2)

        placeholder.empty()

        # stream
        ai=""
        for chunk,_ in chatbot.stream({"messages":[HumanMessage(user)]},
                                      config={"configurable":{"thread_id":tid}},
                                      stream_mode="messages"):
            if st.session_state.stop:
                ai+="\n\n*Stopped by user*"
                break
            ai+=chunk.content
            placeholder.markdown(ai)

    st.session_state.message_history.append({"role":"assistant","content":ai})

    if first:
        title = gen_title(user)
        save_thread_title(tid,title)
        st.session_state.chat_threads[tid]=title

    st.rerun()
