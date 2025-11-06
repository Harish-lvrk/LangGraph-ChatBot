from __future__ import annotations
from typing import TypedDict, Annotated, Dict, List
import sqlite3
from dotenv import load_dotenv
from pydantic import BaseModel, Field

from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages
from langgraph.checkpoint.sqlite import SqliteSaver
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()

# ---------- LLM ----------
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

class TitleOnly(BaseModel):
    title: str = Field(description="Short chat title, max 5 words")

title_llm = llm.with_structured_output(TitleOnly)

# ---------- Graph State ----------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    msgs = state["messages"]
    resp = llm.invoke(msgs)
    return {"messages": [resp]}

# ---------- DB ----------
conn = sqlite3.connect("Enhanced_chatbot.db", check_same_thread=False)
conn.execute("PRAGMA journal_mode=WAL;")

conn.execute("""
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    title TEXT NOT NULL
)
""")
conn.commit()

checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)
chatbot = graph.compile(checkpointer=checkpointer)

# ---------- API ----------
def save_thread_title(thread_id: str, title: str):
    conn.execute(
        "INSERT OR REPLACE INTO threads(thread_id, title) VALUES(?, ?)",
        (thread_id, title)
    )
    conn.commit()

def get_all_threads(search: str = "") -> Dict[str, str]:
    if search:
        cur = conn.execute(
            "SELECT thread_id, title FROM threads WHERE LOWER(title) LIKE LOWER(?) ORDER BY rowid DESC",
            (f"%{search}%",),
        )
    else:
        cur = conn.execute("SELECT thread_id, title FROM threads ORDER BY rowid DESC")
    return {row[0]: row[1] for row in cur.fetchall()}

def update_thread_title(thread_id: str, new_title: str):
    conn.execute("UPDATE threads SET title=? WHERE thread_id=?", (new_title, thread_id))
    conn.commit()

def delete_thread(thread_id: str):
    conn.execute("DELETE FROM threads WHERE thread_id=?", (thread_id,))
    try:
        conn.execute("DELETE FROM checkpoints WHERE thread_id=?", (thread_id,))
        conn.execute("DELETE FROM checkpoint_blobs WHERE thread_id=?", (thread_id,))
        conn.execute("DELETE FROM writes WHERE thread_id=?", (thread_id,))
    except:
        pass
    conn.commit()

def touch_thread(thread_id: str):
    pass  # no-op, we removed last_activity feature
