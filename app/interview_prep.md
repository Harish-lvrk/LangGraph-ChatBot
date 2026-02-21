# LangGraph ChatBot - Interview Preparation Guide

This document explains the architecture, flow, and technical details of the LangGraph ChatBot project. Use this to prepare for your interview.

## 1. Project Overview
This project is a **Smart AI Assistant** built using **LangGraph** (for agentic workflow) and **Streamlit** (for the frontend user interface). unlike a simple chatbot, this agent can use **Tools** (search, calculator, stocks, weather) to answer real-time questions.

**Key Tech Stack:**
*   **Frontend:** Streamlit (Python-based UI).
*   **Backend Logic:** LangGraph (Stateful agent orchestration).
*   **LLM:** Google Gemini 2.5 Flash (via `langchain-google-genai`).
*   **Database:** SQLite (for persisting chat history and thread titles).
*   **Tools:** DuckDuckGo Search, Alpha Vantage (Stocks), WeatherStack, Calculator.

---

## 2. High-Level Architecture
The application is split into two main layers:

1.  **The Frontend (`streamlit_frontend_tool.py`)**:
    *   Handles User Input.
    *   Displays Chat History.
    *   Manages Sessions (New Chat, switching threads).
    *   Streaming response display.

2.  **The Backend (`langgraph_tool_backend.py`)**:
    *   Defines the **Graph** (Nodes & Edges).
    *   Manages **State** (History of messages).
    *   Executes **Tools**.
    *   Persists memory using `SqliteSaver`.

---

## 3. The "Flow" (How it Works)

When a user types a message (e.g., *"What is the stock price of Apple?"*):

### Step 1: User Input (Frontend)
1.  The user types into the Streamlit chat input.
2.  The app appends this message to `st.session_state['message_history']`.
3.  The app invokes the Backend via `chatbot.stream(...)`.

### Step 2: LangGraph Processing (Backend)
1.  **Start Node**: The graph receives the message.
2.  **Chat Node**: The LLM (Gemini) analyzes the message.
    *   *Decision*: Does it need a tool?
    *   *If Yes*: It outputs a "Tool Call" (e.g., calling `get_stock_price('AAPL')`).
    *   *If No*: It just answers directly.
3.  **Conditional Edge (`tools_condition`)**:
    *   Checks if the LLM requested a tool.
    *   lines the path to the **Tool Node** if needed.
4.  **Tool Node**:
    *   Executes the Python function (e.g., requests Alpha Vantage API).
    *   Returns the result (e.g., `{"price": "150.00"}`).
    *   **Loop Back**: Returns to the **Chat Node** with the tool output.
5.  **Chat Node (Re-run)**:
    *   The LLM sees usage: `User: stock price?` -> `AI: Call Tool` -> `Tool: 150.00`.
    *   The LLM generates the final natural language answer: *"The current price of Apple is $150.00."*

### Step 3: Response Display (Frontend)
1.  Streamlit receives chunks of the response.
2.  It detects `ToolMessage` events to show status indicators (e.g., "🔧 Using `get_stock_price`...").
3.  It streams the final AI text to the user.
4.  Updates the SQLite database with the full conversation history.

---

## 4. Key Technical Concepts to Mention

### **LangGraph vs. Standard LangChain**
*   **Explain this:** "I used LangGraph because it allows for **cyclic graphs** (loops). A standard chain is linear, but an Agent needs to decide, act, observe, and potentially act again. LangGraph handles this loop perfectly."

### **State Management**
*   **Frontend**: Uses `st.session_state` to handle the UI state (which chat is open, what was typed).
*   **Backend**: Uses `SqliteSaver` (Checkpointer). This allows the bot to "remember" the conversation even if we restart the app, as long as we have the `thread_id`.

### **Tool Binding**
*   We use `llm.bind_tools(tools)`. This converts our Python functions into a JSON schema that the Gemini model understands. The model doesn't "run" the function; it just tells us *which* function to run and *with what arguments*.

---

## 5. Potential Interview Questions

**Q: Why did you choose SQLite?**
*   **A:** It's lightweight, serverless, and perfect for local development or small-scale apps to persist chat history without needing a full Postgres setup.

**Q: How do you handle API keys?**
*   **A:** I use `dotenv` to load them from a `.env` file, ensuring they aren't hardcoded in the script for security.

**Q: What happens if the Tool fails (e.g., API down)?**
*   **A:** The tool function has a `try-except` block. If it errors, it returns an error message string. The LLM sees this error and can explain to the user, *"I couldn't fetch the data because of an error,"* rather than crashing the app.

**Q: Flow of the 'New Chat' feature?**
*   **A:** When clicked, we generate a new `uuid` (Thread ID). This gives us a fresh "memory space" in LangGraph. The old threads are still saved in SQLite and can be reloaded.

---

## 6. Code Snippet explanations

*   `chatbot = graph.compile(checkpointer=checkpointer)`: This builds the executable application from the graph definition and attaches the database memory.
*   `st.rerun()`: Used in Streamlit to refresh the UI immediately after a state change (like creating a new chat).
