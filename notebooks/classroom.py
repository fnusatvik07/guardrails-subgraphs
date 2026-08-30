"""
Small helpers shared by the four notebooks in this folder.

Nothing here is LangChain magic. It is only printing and environment setup,
kept in one file so the notebooks stay about the ideas rather than about
formatting message lists.
"""

from __future__ import annotations

import os
import textwrap
from pathlib import Path

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------

# The two models used throughout the class. Swap these once here and every
# notebook follows. `WORKER` does the actual work; `JUDGE` is the small, cheap
# model we use for model-based guardrails.
WORKER_MODEL = "gpt-5.4-mini"
JUDGE_MODEL = "gpt-5.4-mini"


def load_env() -> str:
    """Read the .env sitting next to this repo and confirm the OpenAI key is there.

    Returns the name of the file it loaded, so the notebook can print it.
    """
    from dotenv import load_dotenv

    here = Path(__file__).resolve().parent
    for candidate in (here / ".env", here.parent / ".env"):
        if candidate.exists():
            load_dotenv(candidate, override=False)
            if not os.environ.get("OPENAI_API_KEY"):
                raise RuntimeError(f"{candidate} exists but has no OPENAI_API_KEY in it.")
            return str(candidate)
    raise FileNotFoundError(
        "No .env found. Copy .env.example to .env and put your OPENAI_API_KEY in it."
    )


def versions() -> str:
    from importlib.metadata import version

    parts = [f"{name} {version(name)}" for name in
             ("langchain", "langchain-core", "langgraph", "langchain-openai")]
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Printing
# ---------------------------------------------------------------------------

WIDTH = 92

_ROLE = {
    "HumanMessage": "USER",
    "AIMessage": "AGENT",
    "ToolMessage": "TOOL",
    "SystemMessage": "SYSTEM",
    "AIMessageChunk": "AGENT",
}


def rule(label: str = "", char: str = "=") -> None:
    """A labelled horizontal line, so long outputs stay readable."""
    if not label:
        print(char * WIDTH)
        return
    pad = WIDTH - len(label) - 3
    print(f"{char * 2} {label} {char * max(pad, 0)}")


def _body(message) -> str:
    """Text of a message, whether its content is a string or a list of blocks."""
    text = getattr(message, "text", None)
    if text:
        return text
    calls = getattr(message, "tool_calls", None) or []
    if calls:
        return " ".join(f"calls {c['name']}({c['args']})" for c in calls)
    return "(no text)"


def show_messages(result, title: str = "", show_tools: bool = True) -> None:
    """Print an agent result as a readable transcript.

    `result` is whatever `agent.invoke(...)` gave back, or a plain list of messages.
    """
    if title:
        rule(title)
    messages = result["messages"] if isinstance(result, dict) else result
    for message in messages:
        kind = type(message).__name__
        role = _ROLE.get(kind, kind)
        if role == "TOOL" and not show_tools:
            continue
        text = _body(message)
        wrapped = textwrap.fill(
            text, width=WIDTH - 10, subsequent_indent=" " * 10, initial_indent=" " * 10
        )
        print(f"{role:>8}  {wrapped.strip()}")
    print()


def show_state(snapshot, title: str = "") -> None:
    """Print the interesting parts of a LangGraph StateSnapshot."""
    if title:
        rule(title)
    print(f"  values : {snapshot.values}")
    print(f"  next   : {snapshot.next}")
    for task in snapshot.tasks:
        inner = getattr(task, "state", None)
        inner_values = getattr(inner, "values", inner)
        print(f"  task   : {task.name}  ->  {inner_values}")
    print()


def table(rows, headers) -> None:
    """A plain fixed-width table. Easier to read in a slide than a DataFrame."""
    rows = [[" ".join(str(c).split()) for c in r] for r in rows]
    widths = [
        max(len(headers[i]), *(len(r[i]) for r in rows)) if rows else len(headers[i])
        for i in range(len(headers))
    ]
    line = "  ".join("-" * w for w in widths)
    print("  ".join(h.ljust(widths[i]) for i, h in enumerate(headers)))
    print(line)
    for r in rows:
        print("  ".join(r[i].ljust(widths[i]) for i in range(len(headers))))
    print()


def draw(graph, xray: bool = False) -> None:
    """ASCII picture of a compiled graph. Works with no browser and no network.

    `xray=True` opens up any subgraphs so you can see their nodes too.
    """
    print(graph.get_graph(xray=xray).draw_ascii())


def mermaid(graph, xray: bool = False) -> str:
    """Mermaid source for a compiled graph, for pasting into slides or docs."""
    return graph.get_graph(xray=xray).draw_mermaid()


def quiet() -> None:
    """Silence the beta-API warnings so class output stays clean.

    `stream_events(version="v3")` is marked experimental and warns every time it
    is called. That is useful in an application and noise in a lecture.
    """
    import warnings

    from langchain_core._api import LangChainBetaWarning

    warnings.simplefilter("ignore", LangChainBetaWarning)
    warnings.filterwarnings("ignore", message=".*v3 streaming protocol.*")
