import os
# Fix for GRPC errors on macOS
os.environ["GRPC_ENABLE_FORK_SUPPORT"] = "0"
os.environ["GRPC_PYTHON_ASYNC_IO_THREADS"] = "1"

from langgraph.graph import StateGraph, START, END
from typing import TypedDict, Annotated
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph.message import add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from langchain_community.tools import DuckDuckGoSearchRun
from langchain_core.tools import tool, BaseTool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import aiosqlite
import sqlite3
import requests
import asyncio
import threading
import os 
from datetime import datetime

load_dotenv()

# Dedicated async loop for backend tasks
_ASYNC_LOOP = asyncio.new_event_loop()
_ASYNC_THREAD = threading.Thread(target=_ASYNC_LOOP.run_forever, daemon=True)
_ASYNC_THREAD.start()

def _submit_async(coro):
    return asyncio.run_coroutine_threadsafe(coro, _ASYNC_LOOP)

def run_async(coro):
    return _submit_async(coro).result()

def submit_async_task(coro):
    """Schedule a coroutine on the backend event loop."""
    return _submit_async(coro)

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
search_tool = DuckDuckGoSearchRun(region="us-en")

@tool
def get_stock_price(symbol: str) -> dict:
    """
    Fetch latest stock price for a given symbol (e.g. 'AAPL', 'TSLA') 
    using Alpha Vantage with API key in the URL.
    """
    url = f"https://www.alphavantage.co/query?function=GLOBAL_QUOTE&symbol={symbol}&apikey={os.environ.get('ALPHA_VANTAGE_API')}"
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

@tool
def get_current_datetime() -> dict:
    """
    Get the current date and time.
    Use this tool when the user asks about today's date, current time, day, or datetime.
    """
    now = datetime.now()
    return {
        "date": now.strftime("%Y-%m-%d"),
        "time": now.strftime("%H:%M:%S"),
        "day": now.strftime("%A"),
        "formatted": now.strftime("%A, %B %d, %Y at %I:%M %p")
    }

# MCP Client Configuration
server_config = {
    "math": {
        "transport": "stdio",
        "command": "/Users/hareesh/Projects/MCPs/.venv/bin/python",
        "args": [
            "/Users/hareesh/Projects/MCPs/mcp_servers/basic_server.py"
        ],
    },
    "expenses": {
        "transport": "http",
        "url": "https://scientific-gold-iguana.fastmcp.app/mcp",
        "headers": {
            "Authorization": "Bearer fmcp_TXWqxiZBiklvK-P8ppubP9cAhXmQHjdHS4V3CKtG6o4"
        }
    },
    "manim-server": {
        "transport": "stdio",
        "command": "/Users/hareesh/Projects/manim-mcp-server/.venv/bin/python",
        "args": [
            "/Users/hareesh/Projects/manim-mcp-server/src/manim_server.py"
        ],
        "env": {
            "MANIM_EXECUTABLE": "/Users/hareesh/Projects/manim-mcp-server/.venv/bin/manim"
        }
    }
}

client = MultiServerMCPClient(server_config)

def load_mcp_tools() -> list[BaseTool]:
    try:
        return run_async(client.get_tools())
    except Exception as e:
        print(f"Error loading MCP tools: {e}")
        return []

mcp_tools = load_mcp_tools()

# Fix for missing 'type' in MCP tool schema properties which breaks Pydantic validation in Gemini
for t in mcp_tools:
    if hasattr(t, "args_schema") and isinstance(t.args_schema, dict):
        props = t.args_schema.get("properties", {})
        for prop_name, prop_def in props.items():
            if isinstance(prop_def, dict) and "type" not in prop_def:
                prop_def["type"] = "string"

tools = [search_tool, get_stock_price, get_weather_data, get_current_datetime, *mcp_tools]
llm_with_tools = llm.bind_tools(tools) if tools else llm

# -------------------
# 3. Graph State
# -------------------
class ChatState(TypedDict):
    messages: Annotated[list[BaseMessage], add_messages]

# -------------------
# 4. Nodes
# -------------------
async def chat_node(state: ChatState):
    """LLM node that may answer or request a tool call."""
    print("DEBUG: Entering chat_node", flush=True)
    messages = state["messages"]
    
    # System instruction for model behavior and tool usage
    system_prompt = SystemMessage(content=(
        "You are a helpful assistant with access to several tools. "
        "IMPORTANT: When calling a tool, you MUST provide all required arguments as specified in the tool's schema. "
        "For example, when using 'add_expense', you MUST provide 'date', 'amount', and 'category'. "
        "If the user doesn't provide enough information, ask them for the missing details before calling the tool.\n\n"
        "ANIMATION RULES: When generating code for Manim animations, you MUST NOT use LaTeX. "
        "The environment does not support it. Use `Text()` instead of `MathTex()`, "
        "and avoid any LaTeX-specific formatting or symbols."
    ))
    
    # Prepend the system prompt to the messages sent to the LLM
    print("DEBUG: Calling LLM...", flush=True)
    response = await llm_with_tools.ainvoke([system_prompt] + messages)
    print(f"DEBUG: LLM Response received. Content: {response.content[:100]}...", flush=True)
    
    # Safeguard: Ensure tool_calls 'args' are not None to avoid Pydantic validation errors
    if hasattr(response, "tool_calls") and response.tool_calls:
        print(f"DEBUG: Tool Calls generated: {response.tool_calls}", flush=True)
        for tc in response.tool_calls:
            if tc.get("args") is None:
                print(f"DEBUG: Fixing null args for tool {tc.get('name')}", flush=True)
                tc["args"] = {}
        
    return {"messages": [response]}

tool_node = ToolNode(tools) if tools else None

# -------------------
# 5. Checkpointer
# -------------------
async def _init_checkpointer():
    # Regular connection for standard operations
    conn = await aiosqlite.connect(database="chatbot.db")
    # Initialize threads table
    await conn.execute("""
    CREATE TABLE IF NOT EXISTS threads (
        thread_id TEXT PRIMARY KEY,
        title TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    await conn.commit()
    return AsyncSqliteSaver(conn)

checkpointer = run_async(_init_checkpointer())

# -------------------
# 6. Graph
# -------------------
graph = StateGraph(ChatState)
graph.add_node("chat_node", chat_node)
graph.add_edge(START, "chat_node")

if tool_node:
    graph.add_node("tools", tool_node)
    graph.add_conditional_edges("chat_node", tools_condition)
    graph.add_edge("tools", "chat_node")
else:
    graph.add_edge("chat_node", END)

chatbot = graph.compile(checkpointer=checkpointer)

# -------------------
# 7. Helper
# -------------------

# Store title in DB (Keep sync interface for frontend if possible, or use run_async)
def save_thread_title(thread_id: str, title: str):
    def _save():
        conn_sync = sqlite3.connect("chatbot.db")
        conn_sync.execute(
            "INSERT OR REPLACE INTO threads (thread_id, title) VALUES (?, ?)",
            (thread_id, title)
        )
        conn_sync.commit()
        conn_sync.close()
    
    _save()

# Fetch all thread titles from DB -> dict format {thread_id: title}
def get_all_threads():
    conn_sync = sqlite3.connect("chatbot.db")
    cursor = conn_sync.execute("SELECT thread_id, title FROM threads ORDER BY created_at DESC")
    results = {row[0]: row[1] for row in cursor.fetchall()}
    conn_sync.close()
    return results

# Delete a thread from both the database and checkpoint storage
def delete_thread(thread_id: str):
    try:
        conn_sync = sqlite3.connect("chatbot.db")
        # Delete from threads table
        conn_sync.execute("DELETE FROM threads WHERE thread_id = ?", (thread_id,))
        
        # Manually delete checkpoint data to avoid SqliteSaver issues
        conn_sync.execute("DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,))
        conn_sync.execute("DELETE FROM writes WHERE thread_id = ?", (thread_id,))
        conn_sync.commit()
        conn_sync.close()
    except Exception as e:
        print(f"Warning: Could not delete thread {thread_id}: {e}")

# ---------------------- For debugging ----------------------
async def _alist_threads():
    all_threads = set()
    async for checkpoint in checkpointer.alist(None):
        all_threads.add(checkpoint.config["configurable"]["thread_id"])
    return list(all_threads)

def retrieve_all_threads():
    return run_async(_alist_threads())

if __name__ == "__main__":
    print("Available tools:", [t.name for t in tools])
    print("Threads record in DB:", get_all_threads())
