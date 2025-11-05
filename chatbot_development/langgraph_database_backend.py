# from langgraph.graph import StateGraph,START,END
# from typing import TypedDict,Annotated
# from langchain_core.messages import BaseMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langgraph.checkpoint.sqlite import SqliteSaver
# from langgraph.graph.message import add_messages
# from dotenv import load_dotenv
# from pydantic import BaseModel, Field
# from langchain_core.messages import HumanMessage
# import sqlite3

# load_dotenv()


# load_dotenv()

# llm = ChatGoogleGenerativeAI(model = 'gemini-2.5-flash')

# class TitleOnly(BaseModel):
#     title: str = Field(description="Short chat title, max 5 words")

# title_llm = llm.with_structured_output(TitleOnly)

# class ChatState(TypedDict):
#     messages: Annotated[list[BaseMessage], add_messages]

# def chat_node(state: ChatState):
#     messages = state['messages']
#     response = llm.invoke(messages)
#     return {"messages": [response]}

# conn = sqlite3.connect(database='chatbot.db',check_same_thread=False) # false helps to handle with the multiple threads
# # Checkpointer
# checkpointer = SqliteSaver(conn= conn)

# graph = StateGraph(ChatState)
# graph.add_node("chat_node", chat_node)
# graph.add_edge(START, "chat_node")
# graph.add_edge("chat_node", END)

# chatbot = graph.compile(checkpointer=checkpointer)

# # print(chatbot.invoke({'messages':'hi'},config= {'configurable': {'thread_id': 'thread-1'}}))
# # response = title_llm.invoke("Hello, can you give a short title for this chat? qurey: How's the weather today?    ")
# # print(response.title)
# # CONFIG = {'configurable':{'thread_id':'thread-2'}}
# # response = chatbot.invoke(
# #                     {'messages':[HumanMessage(content="explain about the qlora")]},
# #                     config= CONFIG
# #                         )
# # print(response)

# all_threads = set()

# for checkpoint in checkpointer.list(None):
#     all_threads.add(checkpoint.config['configurable']['thread_id'])
# print(all_threads)

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import sqlite3

load_dotenv()

# ---------------------- LLM ----------------------
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

class TitleOnly(BaseModel):
    title: str = Field(description="Short chat title, max 5 words")

title_llm = llm.with_structured_output(TitleOnly)

# ---------------------- Graph State ----------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

def chat_node(state: ChatState):
    messages = state["messages"]
    response = llm.invoke(messages)
    return {"messages": [response]}

# ---------------------- SQLite + Checkpointer ----------------------
conn = sqlite3.connect("chatbot.db", check_same_thread=False)

# Create table for storing sidebar chat titles
conn.execute("""
CREATE TABLE IF NOT EXISTS threads (
    thread_id TEXT PRIMARY KEY,
    title TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
""")
conn.commit()

# Store title in DB
def save_thread_title(thread_id: str, title: str):
    conn.execute(
        "INSERT OR REPLACE INTO threads (thread_id, title) VALUES (?, ?)",
        (thread_id, title)
    )
    conn.commit()

# Fetch all thread titles from DB -> dict format {thread_id: title}
def get_all_threads():
    cursor = conn.execute("SELECT thread_id, title FROM threads ORDER BY created_at DESC")
    return {row[0]: row[1] for row in cursor.fetchall()}

# LangGraph checkpointing (stores chat messages)
checkpointer = SqliteSaver(conn=conn)

graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")
graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

# ---------------------- For debugging only ----------------------
# Print existing thread IDs in message DB
def list_message_threads():
    threads = set()
    for checkpoint in checkpointer.list(None):
        threads.add(checkpoint.config["configurable"]["thread_id"])
    return threads

if __name__ == "__main__":
    # CONFIG = {'configurable':{'thread_id':'thread-1'}}
    # response = chatbot.invoke(
    #                 {'messages':[HumanMessage(content="explain about the qlora")]},
    #                 config= CONFIG
    #                     )
    # print(response)
    print("Message threads in checkpoint store:", list_message_threads())
    print("Title records in DB:", get_all_threads())
