import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from nbbuild import build

C = []
md = lambda s: C.append(("md", s))
code = lambda s: C.append(("code", s))

md(r'''
# Subgraphs, part 2: memory and control

This continues `03_subgraphs_composing_graphs.ipynb`. Same company, same desk.

### The question part 1 avoided

Aurora Retail's front desk now delegates to specialists. A customer asks about
their order, then two minutes later asks a follow-up.

**Should the specialist remember the first question?**

There is no universally right answer, and that is precisely why LangGraph makes
you choose. A billing expert working through a disputed invoice probably should
remember. An order lookup almost certainly should not, and if it does you have
just built a memory leak with a state machine attached.

You make the choice with exactly one argument:

```python
subgraph = builder.compile(checkpointer=...)   # None, True, or False
```

### What you will learn here (part 2)

1. The three persistence modes and what each one actually does to your data
2. Durable execution: why a crash mid-run behaves so differently in each mode
3. Namespaces, and why two per-thread subagents can overwrite each other
4. Reading a subgraph's state from the parent
5. Pausing inside a subgraph for human approval, and resuming into it

### Source

<https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
''')

md(r'''
## 0. Setup
''')

code(r'''
import sys, pathlib

sys.path.insert(0, str(pathlib.Path.cwd()))
import classroom as cr

cr.quiet()
print("env file :", cr.load_env())
print("versions :", cr.versions())
''')

md(r'''
## 1. The three modes

<img src="../images/diagrams/sg_04_persistence_modes.svg" width="900" alt="The three subgraph persistence modes">

| Mode | `checkpointer=` | What happens between calls |
| --- | --- | --- |
| **Per-invocation** | `None` (default) | fresh state each call, but durable *within* a call |
| **Per-thread** | `True` | state accumulates on the thread |
| **Stateless** | `False` | nothing is written down at all |

One rule before anything else:

> **The parent graph must be compiled with a real checkpointer.** Everything in
> this notebook is about how the subgraph relates to the parent's checkpointer.
> If the parent has none, there is nothing to relate to.

### Seeing all three in one go

Here is a specialist that counts how many times it has been asked something. No
model calls, so the behaviour is completely deterministic and you can run it as
many times as you like in class.
''')

code(r'''
from langgraph.graph import START, StateGraph, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langchain.messages import AIMessage


class SpecialistState(MessagesState):
    """Shares `messages` with the front desk. `visits` is the specialist's own."""
    visits: int


def build_desk(checkpointer_setting):
    """Build a front desk whose specialist is compiled with the given setting."""

    def handle(state: SpecialistState):
        visit = state.get("visits", 0) + 1
        return {
            "visits": visit,
            "messages": [AIMessage(content=f"this is visit #{visit} for me")],
        }

    specialist_builder = StateGraph(SpecialistState)
    specialist_builder.add_node(handle)
    specialist_builder.add_edge(START, "handle")

    if checkpointer_setting is None:
        specialist = specialist_builder.compile()                 # per-invocation
    else:
        specialist = specialist_builder.compile(checkpointer=checkpointer_setting)

    desk = StateGraph(MessagesState)
    desk.add_node("specialist", specialist)
    desk.add_edge(START, "specialist")
    return desk.compile(checkpointer=MemorySaver())     # the parent, always real


QUESTIONS = ["where is my order", "and the delivery date", "and the invoice"]

rows = []
for label, setting in [("per-invocation", None), ("per-thread", True), ("stateless", False)]:
    desk = build_desk(setting)
    config = {"configurable": {"thread_id": "customer-1"}}
    replies = []
    for question in QUESTIONS:
        result = desk.invoke({"messages": [{"role": "user", "content": question}]}, config)
        replies.append(result["messages"][-1].text.replace("this is ", ""))
    rows.append([label, f"checkpointer={setting}", *replies])

cr.table(rows, ["mode", "compiled with", "call 1", "call 2", "call 3"])
''')

md(r'''
Three calls on the **same thread**, three completely different behaviours.

- **Per-thread** counts up. The specialist picked up where it left off.
- **Per-invocation** and **stateless** both reset every time.

So if per-invocation and stateless look identical here, why have both? Because
this table only shows what happens *between* calls. The difference shows up
*inside* one call, and that is the next section.
''')

md(r'''
## 2. Durable execution: the difference nobody sees until it costs them

Per-invocation subgraphs **inherit the parent's checkpointer for the duration of
one call**. Stateless ones do not inherit anything.

That sounds abstract. Here is what it means in practice.

Imagine a specialist that does something expensive first (charges a card, calls a
paid API, spends thirty seconds on a report) and then pauses for human approval.
The human approves an hour later. **Does the expensive step run again?**
''')

code(r'''
from typing_extensions import TypedDict
from langgraph.types import interrupt, Command


class RefundState(TypedDict):
    order_id: str
    note: str


def build_refund_desk(checkpointer_setting):
    """A specialist that does expensive work, then asks a human to approve."""
    counters = {"expensive_calls": 0}

    def compile_refund_report(state: RefundState):
        # Pretend this is slow and costs money.
        counters["expensive_calls"] += 1
        return {"note": state["note"] + "[report compiled]"}

    def ask_approval(state: RefundState):
        decision = interrupt("Approve this refund?")
        return {"note": state["note"] + f"[{decision}]"}

    builder = StateGraph(RefundState)
    builder.add_node(compile_refund_report)
    builder.add_node(ask_approval)
    builder.add_edge(START, "compile_refund_report")
    builder.add_edge("compile_refund_report", "ask_approval")

    if checkpointer_setting is None:
        specialist = builder.compile()
    else:
        specialist = builder.compile(checkpointer=checkpointer_setting)

    desk = StateGraph(RefundState)
    desk.add_node("refunds", specialist)
    desk.add_edge(START, "refunds")
    return desk.compile(checkpointer=MemorySaver()), counters


rows = []
for label, setting in [("per-invocation", None), ("stateless", False)]:
    desk, counters = build_refund_desk(setting)
    config = {"configurable": {"thread_id": "refund-1"}}

    desk.invoke({"order_id": "AUR-1001", "note": ""}, config)      # runs, then pauses
    at_pause = counters["expensive_calls"]

    final = desk.invoke(Command(resume="approved"), config)        # a human approves
    after_resume = counters["expensive_calls"]

    rows.append([label, at_pause, after_resume, final["note"]])

cr.table(rows, ["mode", "expensive calls at pause", "after resume", "final note"])
''')

md(r'''
Read the middle two columns. Both modes paused correctly and both resumed
correctly, so at first glance they look the same.

But the stateless one ran the expensive step **twice**. With no checkpoint of its
own to restart from, the subgraph had to be replayed from its first node.

That is what "durable execution" means, and it is why per-invocation is the
default. If your subgraph only reads data, nobody notices. If it charges a card,
sends an e-mail, or writes a row, somebody notices very quickly.

> The docs table marks interrupts as unsupported for stateless subgraphs. As you
> can see, the interrupt does surface and the resume does complete, because the
> **parent's** checkpointer is doing that work. What you lose is everything the
> subgraph would have remembered: the replay above, and state inspection in
> section 5. Treat stateless as "safe only for pure functions".
''')

md(r'''
## 3. Why the modes behave differently: namespaces

None of this is magic. Each running subgraph writes its checkpoints into a
**namespace**, and the mode decides how that namespace is chosen.

Let us just look at the namespaces directly.
''')

code(r'''
def namespaces_after_three_calls(setting):
    desk = build_desk(setting)
    config = {"configurable": {"thread_id": "customer-1"}}
    for question in QUESTIONS:
        desk.invoke({"messages": [{"role": "user", "content": question}]}, config)

    seen = []
    for checkpoint in desk.checkpointer.list({"configurable": {"thread_id": "customer-1"}}):
        namespace = checkpoint.config["configurable"].get("checkpoint_ns", "")
        if namespace and namespace not in seen:
            seen.append(namespace)
    return seen


for label, setting in [("per-invocation", None), ("per-thread", True), ("stateless", False)]:
    found = namespaces_after_three_calls(setting)
    cr.rule(f"{label}: {len(found)} subgraph namespace(s)")
    for namespace in found:
        print("   ", namespace)
''')

md(r'''
There it is, in plain text.

- **Per-invocation** made a *new* namespace for every call, each one the node name
  plus a fresh id. Three calls, three separate little state stores, none of which
  can see the others. That is why the counter reset, and it is also why two
  parallel calls never collide.
- **Per-thread** used one namespace, `specialist`, taken from the node name. Every
  call wrote into the same store, so the counter kept going.
- **Stateless** wrote nothing at all.

Everything in the comparison table falls out of this one mechanism.
''')

md(r'''
## 4. Per-thread in a real multi-agent setup

Now with actual models. This is the pattern from the docs page: specialists
wrapped as tools for an outer agent.

Two Aurora specialists, one compiled per-invocation and one per-thread, asked two
questions in a row on the same thread. Watch the message count inside each
specialist.
''')

code(r'''
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.tools import tool


@tool
def order_lookup(order_id: str) -> str:
    """Look up an Aurora Retail order by its ID."""
    return f"Order {order_id}: walnut desk, in transit with Bluewing."


def run_desk(specialist_checkpointer, use_limit_middleware):
    """Build a front desk with one specialist, ask it two questions, report sizes."""
    kwargs = {}
    if specialist_checkpointer is not None:
        kwargs["checkpointer"] = specialist_checkpointer

    specialist = create_agent(
        model=cr.WORKER_MODEL,
        tools=[order_lookup],
        system_prompt="You are the Aurora orders expert. Use order_lookup. One sentence.",
        **kwargs,
    )

    sizes = []

    @tool
    def ask_orders_expert(question: str) -> str:
        """Ask the Aurora orders expert. Use for ALL order questions."""
        reply = specialist.invoke({"messages": [{"role": "user", "content": question}]})
        sizes.append(len(reply["messages"]))
        return reply["messages"][-1].text

    # Per-thread subagents cannot handle two parallel calls, so we cap the outer
    # agent to one call per run. More on this in the warning below.
    middleware = (
        [ToolCallLimitMiddleware(tool_name="ask_orders_expert", run_limit=1)]
        if use_limit_middleware else []
    )

    desk = create_agent(
        model=cr.WORKER_MODEL,
        tools=[ask_orders_expert],
        system_prompt="Always delegate order questions to ask_orders_expert.",
        middleware=middleware,
        checkpointer=MemorySaver(),
    )

    config = {"configurable": {"thread_id": "1"}}
    desk.invoke({"messages": [{"role": "user", "content": "Where is AUR-1001?"}]}, config)
    desk.invoke({"messages": [{"role": "user", "content": "And AUR-1002?"}]}, config)
    return sizes


per_invocation_sizes = run_desk(None, use_limit_middleware=False)
per_thread_sizes = run_desk(True, use_limit_middleware=True)

cr.table(
    [
        ["per-invocation", *per_invocation_sizes, "starts fresh, forgets AUR-1001"],
        ["per-thread", *per_thread_sizes, "carries the first conversation forward"],
    ],
    ["mode", "messages after call 1", "after call 2", "meaning"],
)
''')

md(r'''
The per-invocation specialist has the same number of messages both times: each
call is a clean slate. The per-thread one roughly doubles, because the second
call started with everything from the first still in its state.

That is a real feature and a real bill. Per-thread subagents grow, and nothing
trims them for you. If you take this route, plan for summarisation.

### The parallel-call warning

Notice `ToolCallLimitMiddleware` in the per-thread branch. It is there for a
specific reason.

A model with a specialist available as a tool will happily call it **twice in
parallel**: once for AUR-1001 and once for AUR-1002, in the same turn. With
per-invocation that is fine, because each call gets its own fresh namespace. With
per-thread both calls write into the same namespace, and they conflict.

`ToolCallLimitMiddleware(tool_name=..., run_limit=1)` prevents that by capping the
tool to one call per run. If you are working in raw LangGraph rather than
`create_agent`, you have to prevent it yourself, for example by turning off
parallel tool calling on the model.
''')

md(r'''
## 5. Namespace isolation: two per-thread specialists

Here is a subtler trap, and it is the reason the docs recommend a wrapper.

When you call subgraphs **inside a node**, LangGraph assigns their namespaces by
**call order**: first call, second call, and so on. That is fine until somebody
reorders the code, at which point the veggie expert loads the fruit expert's
memory.

<img src="../images/diagrams/sg_05_namespace_isolation.svg" width="880" alt="Namespace isolation with a one-node wrapper">

The fix is three lines: wrap each specialist in its own one-node `StateGraph` with
a unique node name. The namespace then comes from the name, which is stable
whatever order the model decides to call things in.
''')

code(r'''
@tool
def billing_lookup(order_id: str) -> str:
    """Look up the invoice for an Aurora Retail order."""
    return f"Invoice for {order_id}: item $429.00, delivery $0.00, total $429.00."


def create_sub_agent(model, *, name, **kwargs):
    """Wrap an agent in a one-node graph so it gets a stable, unique namespace."""
    agent = create_agent(model=model, name=name, **kwargs)
    return (
        StateGraph(MessagesState)
        .add_node(name, agent)          # unique name -> stable namespace
        .add_edge("__start__", name)
        .compile()
    )


orders_expert = create_sub_agent(
    cr.WORKER_MODEL, name="orders_expert",
    tools=[order_lookup],
    system_prompt="Aurora orders expert. Use order_lookup. One sentence.",
    checkpointer=True,
)
billing_expert = create_sub_agent(
    cr.WORKER_MODEL, name="billing_expert",
    tools=[billing_lookup],
    system_prompt="Aurora billing expert. Use billing_lookup. One sentence.",
    checkpointer=True,
)

sizes = {"orders": [], "billing": []}


@tool
def ask_orders_expert(question: str) -> str:
    """Ask the Aurora orders expert. Use for delivery and tracking questions."""
    reply = orders_expert.invoke({"messages": [{"role": "user", "content": question}]})
    sizes["orders"].append(len(reply["messages"]))
    return reply["messages"][-1].text


@tool
def ask_billing_expert(question: str) -> str:
    """Ask the Aurora billing expert. Use for invoice and charge questions."""
    reply = billing_expert.invoke({"messages": [{"role": "user", "content": question}]})
    sizes["billing"].append(len(reply["messages"]))
    return reply["messages"][-1].text


front_desk = create_agent(
    model=cr.WORKER_MODEL,
    tools=[ask_orders_expert, ask_billing_expert],
    system_prompt=(
        "You are the Aurora Retail front desk. Delivery questions go to "
        "ask_orders_expert. Invoice questions go to ask_billing_expert. "
        "Always delegate."
    ),
    middleware=[
        ToolCallLimitMiddleware(tool_name="ask_orders_expert", run_limit=1),
        ToolCallLimitMiddleware(tool_name="ask_billing_expert", run_limit=1),
    ],
    checkpointer=MemorySaver(),
)

config = {"configurable": {"thread_id": "1"}}
front_desk.invoke(
    {"messages": [{"role": "user", "content":
                   "Where is AUR-1001, and what was I charged for it?"}]},
    config,
)
front_desk.invoke(
    {"messages": [{"role": "user", "content":
                   "Now the same two questions for AUR-1002."}]},
    config,
)

cr.table(
    [["orders_expert", *sizes["orders"]], ["billing_expert", *sizes["billing"]]],
    ["specialist", "messages after turn 1", "after turn 2"],
)
''')

md(r'''
Both specialists grew, and they grew **independently**. The orders expert
remembers only order conversations, the billing expert only billing ones, and
neither ever saw the other's history.

Without the wrapper, that separation depends on the order the model happened to
call the tools in, which is not something you want to depend on.

> Subgraphs [added as a node](#) already get a name-based namespace automatically.
> The wrapper only matters for subagents invoked from inside a tool function.
''')

md(r'''
## 6. Reading a subgraph's state from the parent

You have a bug three levels down. You want to see what the inner graph thinks is
going on. There are two situations, and they need different calls.

### While the run is paused

`get_state(config, subgraphs=True)` returns pending tasks, and each task carries
the state of the subgraph that is sitting there waiting.
''')

code(r'''
class State(TypedDict):
    foo: str


def subgraph_node_1(state: State):
    value = interrupt("Provide value:")
    return {"foo": state["foo"] + value}


subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()          # per-invocation, inherits the parent

builder = StateGraph(State)
builder.add_node("node_1", subgraph)
builder.add_edge(START, "node_1")
graph = builder.compile(checkpointer=MemorySaver())

config = {"configurable": {"thread_id": "1"}}
graph.invoke({"foo": "start"}, config)

snapshot = graph.get_state(config, subgraphs=True)
cr.show_state(snapshot, "paused: the parent can see into the subgraph")

print("resumed:", graph.invoke(Command(resume="-done"), config))
''')

md(r'''
### After the run has finished

Once nothing is pending there are no tasks to look at, so this call returns an
empty list. For a **per-thread** subgraph the state is still on disk though, under
its own namespace, and you can read it by naming that namespace.
''')

code(r'''
persistent_desk = build_desk(True)          # checkpointer=True on the specialist
config = {"configurable": {"thread_id": "customer-9"}}

for question in ["first", "second", "third"]:
    persistent_desk.invoke({"messages": [{"role": "user", "content": question}]}, config)

parent_snapshot = persistent_desk.get_state(config, subgraphs=True)
print("pending tasks now the run is over:", len(parent_snapshot.tasks))
print("parent message count               :", len(parent_snapshot.values["messages"]))
print()

# The specialist was added as a node called "specialist", so that is its namespace.
specialist_snapshot = persistent_desk.get_state(
    {"configurable": {"thread_id": "customer-9", "checkpoint_ns": "specialist"}}
)
print("specialist's own accumulated state:")
print("   visits  :", specialist_snapshot.values["visits"])
print("   messages:", len(specialist_snapshot.values["messages"]))
''')

md(r'''
Two useful facts fell out of that:

1. `tasks` is about what is **pending**, not what happened. After a completed run
   it is empty, in every mode.
2. Per-thread state lives under a namespace named after the node, and you can read
   it by asking for that namespace directly.

And one limitation worth saying out loud in class:

> Inspecting subgraph state needs LangGraph to be able to **find** the subgraph.
> Added as a node, or invoked directly inside a node function, both work. A
> subgraph called from inside a **tool** function does not, because the framework
> cannot see through the tool. Interrupts still propagate from there, but state
> inspection does not.
''')

md(r'''
## 7. Human approval inside a specialist

Putting it together: a specialist deep inside the graph pauses for a human, and
the interrupt travels all the way up to whoever called the front desk.

This works even through a tool function, which is exactly the case where state
inspection does not. Interrupts propagate regardless of nesting.
''')

code(r'''
REFUNDED: list[str] = []


@tool
def issue_refund(order_id: str, amount: float) -> str:
    """Refund an Aurora Retail order. Requires approval."""
    decision = interrupt(f"Approve a ${amount:.2f} refund on {order_id}?")
    if decision != "approve":
        return f"Refund on {order_id} was declined by a reviewer."
    REFUNDED.append(order_id)
    return f"Refunded ${amount:.2f} on {order_id}."


refunds_expert = create_agent(
    model=cr.WORKER_MODEL,
    tools=[issue_refund],
    system_prompt="Aurora refunds expert. Use issue_refund. Report the outcome in one sentence.",
)


@tool
def ask_refunds_expert(question: str) -> str:
    """Ask the Aurora refunds expert to handle a refund."""
    reply = refunds_expert.invoke({"messages": [{"role": "user", "content": question}]})
    return reply["messages"][-1].text


refund_desk = create_agent(
    model=cr.WORKER_MODEL,
    tools=[ask_refunds_expert],
    system_prompt="Send all refund requests to ask_refunds_expert.",
    checkpointer=MemorySaver(),
)

REQUEST = {"messages": [{"role": "user", "content":
                         "Please refund $429.00 on order AUR-1001."}]}

for label, decision in [("approve", "approve"), ("decline", "decline")]:
    REFUNDED.clear()
    config = {"configurable": {"thread_id": f"refund-{label}"}}

    stream = refund_desk.stream_events(REQUEST, config=config, version="v3")
    stream.output                                  # drive the stream to completion

    cr.rule(f"reviewer will {label}")
    print("  interrupted :", stream.interrupted)
    print("  asking      :", stream.interrupts[0].value)

    resumed = refund_desk.stream_events(Command(resume=decision), config=config, version="v3")
    print("  final reply :", resumed.output["messages"][-1].text[:90])
    print("  refunds made:", REFUNDED)
    print()
''')

md(r'''
The `interrupt()` call is two levels down: inside a tool, inside a specialist
agent, inside the front desk. It still surfaced at the top as
`stream.interrupts`, and `Command(resume=...)` still went straight back to the
line it stopped on.

This is the piece that makes subgraphs usable for real approval workflows. You do
not have to thread approval state up and down by hand.
''')

md(r'''
## 8. The whole comparison, in one table

This is the table from the docs page, and every row in it is something you have
now seen run.

| Feature | Per-invocation (`None`) | Per-thread (`True`) | Stateless (`False`) |
| --- | --- | --- | --- |
| Interrupts (human in the loop) | yes | yes | parent-driven only, and replays |
| Multi-turn memory | no | yes | no |
| Durable execution | yes | yes | no |
| Multiple calls to different subgraphs | yes | needs unique namespaces | yes |
| Multiple calls to the same subgraph | yes | no, they conflict | yes |
| State inspection | while paused | yes | no |

### How to choose

Three questions, in order:

1. **Does the subgraph need to remember previous calls?**
   Yes: per-thread, and add `ToolCallLimitMiddleware` or turn off parallel tool
   calls. No: keep reading.
2. **Does it do anything you would hate to repeat?** Charge a card, send mail,
   write a row. Yes: per-invocation, the default. No: keep reading.
3. **Is it a pure, cheap function of its input?** Then stateless is fine, and you
   save the bookkeeping.

Most subgraphs stop at question two, which is why per-invocation is the default
and why you should need a reason to change it.
''')

md(r'''
## 9. Recap of both notebooks

**Part 1, structure.**

- A subgraph is a graph used as a node: one dict in, one dict out.
- Different schemas: call it inside a node and translate by hand.
- Shared keys: hand the compiled subgraph to `add_node` and skip the translation.
- The namespace is the address of a running subgraph, one segment per level.
- `stream.subgraphs` is the sane way to watch a nested run.

**Part 2, memory and control.**

- `checkpointer=None` is the default: fresh each call, durable within a call.
- `checkpointer=True` accumulates on the thread. It grows, and it does not like
  parallel calls.
- `checkpointer=False` writes nothing, so anything with a side effect can run
  twice on resume.
- Namespaces explain all three, and a one-node wrapper gives per-thread subagents
  stable ones.
- Interrupts propagate from any depth. State inspection needs LangGraph to be able
  to find the subgraph.

---

### Exercises

1. Take the refund specialist in section 7 and compile it with
   `checkpointer=False`. Add a print inside `issue_refund` before the
   `interrupt()`. How many times does it print across a pause and a resume?
2. Give the per-thread orders expert a fourth and fifth turn and plot the message
   count. At what point would you add summarisation?
3. Remove `ToolCallLimitMiddleware` from section 4 and ask a question that invites
   two parallel lookups. Describe what you see.
4. Build a three-level graph where the middle level is per-thread and the deepest
   is per-invocation, and predict the namespaces before you list them.

### Reference

- Subgraphs: <https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
- Persistence: <https://docs.langchain.com/oss/python/langgraph/persistence>
- Interrupts: <https://docs.langchain.com/oss/python/langgraph/interrupts>
- Checkpointers and threads: <https://docs.langchain.com/oss/python/langgraph/checkpointers>
''')

build(C, os.path.join(os.path.dirname(__file__), "..", "notebooks",
                      "04_subgraphs_memory_and_control.ipynb"))
