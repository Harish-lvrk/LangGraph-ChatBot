
from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool
from langgraph.graph.message import add_messages
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import sqlite3
import requests
import os 

load_dotenv()


# -------------------
# 1. LLM
# -------------------
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash")

class TitleOnly(BaseModel):
    title: str = Field(description="Short chat title, max 5 words")

title_llm = llm.with_structured_output(TitleOnly)


# -------------------
# 2. Tools
# -------------------
# Tools
search_tool = DuckDuckGoSearchRun(region="us-en")
@tool
def calculator(first_num: float, second_num: float, operation: str) -> dict:
    """
    Perform a basic arithmetic operation on two numbers.
    Supported operations: add, sub, mul, div
    """
    try:
        if operation == "add":
            result = first_num + second_num
        elif operation == "sub":
            result = first_num - second_num
        elif operation == "mul":
            result = first_num * second_num
        elif operation == "div":
            if second_num == 0:
                return {"error": "Division by zero is not allowed"}
            result = first_num / second_num
        else:
            return {"error": f"Unsupported operation '{operation}'"}
        
        return {"first_num": first_num, "second_num": second_num, "operation": operation, "result": result}
    except Exception as e:
        return {"error": str(e)}
    
@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey=C9PE94QUEW9VWGFM"
    r = requests.get(url)
    return r.json()

@tool
def get_weather_data(city: str) -> str:
    """
    This function fetches the current weather data for a given city
    """
    WEATHER_STACK_API = os.environ.get('WEATHER_STACK_API')
    url = f'https://api.weatherstack.com/current?access_key={WEATHER_STACK_API}&query={city}'
    response = requests.get(url)
    return response.json()

#bind the llm with tools
tools = [search_tool, get_stock_price, calculator,get_weather_data]
llm_with_tools = llm.bind_tools(tools)

# -------------------
# 3. Graph State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 4. Nodes
# -------------------
def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    messages = state["messages"]
    response = llm_with_tools.invoke(messages)
    return {"messages": [response]}

tool_node = ToolNode(tools)

# ---------------------- SQLite + Checkpointer ----------------------
# -------------------
# 5. Checkpointer
# -------------------

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

# LangGraph checkpointing (stores chat messages)
checkpointer = SqliteSaver(conn=conn)

# -------------------
# 6. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_node("tools", tool_node)

graph.add_edge(START, "chat_node")

graph.add_conditional_edges("chat_node",tools_condition)
graph.add_edge('tools', 'chat_node')

chatbot = graph.compile(checkpointer=checkpointer)



# -------------------
# 7. Helper
# -------------------

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
