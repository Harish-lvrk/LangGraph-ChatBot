from langgraph_backend import llm
from langchain_core.messages import SystemMessage, HumanMessage
import re

# Simple in-memory mapping from thread_id (string) -> title
# This is intentionally lightweight; if you want persistence, swap this
# for a checkpointer-backed store or database.
_THREAD_TITLES = {}


def generate_title(first_user_message: str) -> str:
    """Generate a short, human-friendly title for a conversation.

    Uses the project's LLM (`llm`) directly. Returns a cleaned single-line
    title. This is called when the first user message in a thread arrives.
    """
    system = SystemMessage(content=(
        "You are a helpful assistant that creates concise, descriptive single-line"
        " titles (4-8 words) for conversation topics. Output only the title, with no"
        " surrounding quotes or punctuation."
    ))

    human = HumanMessage(content=f"Create a short title for this user message: {first_user_message}")

    response = llm.invoke([system, human])

    # response is a BaseMessage-like object with `content` attribute
    title = getattr(response, "content", str(response))

    # Normalize whitespace and strip quotes
    title = re.sub(r"\s+", " ", title).strip().strip('"').strip("'")

    # If the model returned multiple sentences, keep only the first line
    title = title.split('\n', 1)[0].strip()

    # Limit length to a reasonable size
    max_len = 60
    if len(title) > max_len:
        # try not to cut mid-word
        title = title[:max_len].rsplit(' ', 1)[0] + '...'

    return title


def get_thread_title(thread_id) -> str:
    """Return the human-friendly title for a thread, or the raw thread_id if none."""
    return _THREAD_TITLES.get(str(thread_id), str(thread_id))


def set_thread_title(thread_id, title: str) -> None:
    """Set or overwrite the title for a thread."""
    _THREAD_TITLES[str(thread_id)] = title


def ensure_title_for_thread(thread_id, first_user_message: str) -> str:
    """Generate and set a title for thread if it doesn't already have one.

    Returns the title (existing or newly generated).
    """
    tid = str(thread_id)
    if tid in _THREAD_TITLES and _THREAD_TITLES[tid]:
        return _THREAD_TITLES[tid]
    title = generate_title(first_user_message)
    set_thread_title(tid, title)
    return title
