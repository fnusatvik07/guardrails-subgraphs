import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from nbbuild import build

C = []
md = lambda s: C.append(("md", s))
code = lambda s: C.append(("code", s))

md(r'''
# Subgraphs, part 1: composing graphs

**LangGraph 1.x**

This is the first of two notebooks on subgraphs. Part 1 is about **structure**:
what a subgraph is, the two ways to attach one, how nesting works, and how to see
inside a running one. Part 2 is about **memory and control**.

---

### The story

**Aurora Retail** has a support desk. Today it is one enormous graph that one team
owns, and every change is a merge conflict.

The plan is to break it up. Orders becomes its own graph, owned by the orders
team. Billing becomes its own graph, owned by the billing team. The front desk
knows nothing about how either of them works, only what to pass in and what comes
back.

That is the whole idea behind subgraphs, and it is the same idea as a function
call: **an interface you agree on, and an implementation nobody else has to read.**

### What you will learn here (part 1)

1. What a subgraph actually is
2. The two ways a parent and a subgraph can talk, and how to choose
3. Pattern A: calling a subgraph inside a node, when the schemas share nothing
4. Nesting: parent, child, grandchild, and what a namespace is
5. Pattern B: adding a subgraph straight into `add_node`, when they share a key
6. Watching a nested run go by, three different ways

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
## 1. What a subgraph is

> A subgraph is a graph that is used as a node in another graph.

That is the entire definition. From the parent's point of view it is one box with
an input and an output. Inside, it is a full graph with its own state, its own
nodes, and its own edges.

<img src="../images/diagrams/sg_01_what_is_a_subgraph.svg" width="880" alt="A subgraph seen from outside and inside">

The docs give three reasons to bother:

- **multi-agent systems**, where each agent is its own graph
- **reuse**, when the same few nodes turn up in several graphs
- **distributing development**, so different teams can own different parts, and
  as long as the interface holds, the parent does not need to know the details

Let us build the smallest possible one and look at it.
''')

code(r'''
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START


class State(TypedDict):
    foo: str


# ---- the subgraph -------------------------------------------------------
def subgraph_node_1(state: State):
    return {"foo": "hi! " + state["foo"]}


subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph = subgraph_builder.compile()

# ---- the parent ---------------------------------------------------------
builder = StateGraph(State)
builder.add_node("node_1", subgraph)      # the compiled subgraph, used as a node
builder.add_edge(START, "node_1")
graph = builder.compile()

print(graph.invoke({"foo": "foo"}))
''')

md(r'''
Now look at the same graph two ways. Without `xray` you see what the parent sees:
one node. With `xray=True` LangGraph opens the box.
''')

code(r'''
cr.rule("what the parent sees")
cr.draw(graph)

cr.rule("with xray=True, the subgraph is opened up")
cr.draw(graph, xray=True)
''')

md(r'''
That `xray` switch is the single most useful debugging tool in this notebook. Keep
it in mind.

If you want the same picture for slides, `cr.mermaid(graph, xray=True)` gives you
Mermaid source you can paste anywhere.
''')

code(r'''
print(cr.mermaid(graph, xray=True))
''')

md(r'''
## 2. How do the two graphs talk?

Everything else in this notebook follows from one question:

> **Does the subgraph read and write the same state keys as the parent?**

<img src="../images/diagrams/sg_02_two_patterns.svg" width="900" alt="The two ways to attach a subgraph">

| | Pattern A: call inside a node | Pattern B: add as a node |
| --- | --- | --- |
| **When** | schemas share no keys, or you need to transform | parent and subgraph share state keys |
| **How** | you write a wrapper function | you pass the compiled subgraph to `add_node` |
| **Mapping** | you do it, both directions | automatic, on the shared channels |
| **Good for** | private message history per agent | agents that talk over a shared `messages` list |

Pattern B is shorter. Pattern A is what you use when B is not available, and it
gives you total control.
''')

md(r'''
## 3. Pattern A: call the subgraph inside a node

Use this when the parent and the subgraph have **different state schemas with no
shared keys**. The classic case is a multi-agent system where each agent keeps its
own private message history and you do not want them mixing.

The node function does three things in order: translate parent state into
subgraph input, invoke the subgraph, translate the result back.
''')

code(r'''
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START


class SubgraphState(TypedDict):
    bar: str          # note: the parent has no "bar" at all


def subgraph_node_1(state: SubgraphState):
    return {"bar": "hi! " + state["bar"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
inner = subgraph_builder.compile()


class ParentState(TypedDict):
    foo: str          # and the subgraph has no "foo"


def call_subgraph(state: ParentState):
    # 1. translate parent state -> subgraph input
    subgraph_output = inner.invoke({"bar": state["foo"]})
    # 2. translate subgraph output -> parent state
    return {"foo": subgraph_output["bar"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", call_subgraph)
builder.add_edge(START, "node_1")
graph_a = builder.compile()

print(graph_a.invoke({"foo": "foo"}))
''')

md(r'''
`"foo"` went in, `"bar"` came out of the inner graph, and `"foo"` came back. The
two schemas never met. The only place they touch is those two lines inside
`call_subgraph`, and that is deliberate: it is one obvious place to look when the
interface changes.

### 3a. The full worked example from the docs

Same idea with two nodes inside and a private key, so you can watch the order of
events. This is the example on the docs page, run for real.
''')

code(r'''
class SubgraphState(TypedDict):
    # none of these keys are shared with the parent graph state
    bar: str
    baz: str


def subgraph_node_1(state: SubgraphState):
    return {"baz": "baz"}


def subgraph_node_2(state: SubgraphState):
    return {"bar": state["bar"] + state["baz"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_node(subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
docs_subgraph = subgraph_builder.compile()


class ParentState(TypedDict):
    foo: str


def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}


def node_2(state: ParentState):
    response = docs_subgraph.invoke({"bar": state["foo"]})
    return {"foo": response["bar"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", node_2)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
docs_graph = builder.compile()

# `updates` is an opt-in projection, so we register its transformer to get the
# raw "updates" events the docs page prints.
from langgraph.stream.transformers import UpdatesTransformer

stream = docs_graph.stream_events({"foo": "foo"}, version="v3",
                                  transformers=[UpdatesTransformer])
for event in stream:
    if event["method"] == "updates":
        print(event["params"]["namespace"], event["params"]["data"])
''')

md(r'''
Four lines, and the shape of each one tells you where it happened.

- `[]` means the parent graph itself.
- `['node_2:577b...']` means *inside the node called `node_2`*. That string is the
  **namespace**, and the random-looking suffix is the id of this particular
  invocation.

Note something important: `node_2` appears **twice**. Once with a subgraph
namespace when the inner nodes ran, and once with `[]` when the parent node
finally returned. The parent only ever learns the final `foo`.

> **A version note.** The docs page writes this loop without the
> `transformers=[UpdatesTransformer]` argument. In LangGraph 1.2 the `updates`
> projection is opt-in, so without it the loop prints nothing. Section 8 shows the
> two other ways to do this, one of which needs no extra imports at all.
''')

md(r'''
### 3b. Aurora: the orders specialist

Now the real version. The front desk state and the orders specialist state have
absolutely nothing in common, which is exactly the point: the orders team can
rename every key inside their graph and the front desk never notices.
''')

code(r'''
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START, END

ORDERS = {
    "AUR-1001": {"item": "walnut desk", "status": "in transit", "carrier": "Bluewing"},
    "AUR-1002": {"item": "task lamp", "status": "delivered", "carrier": "Northline"},
}


# ---------------------------------------------------------------- specialist
class OrderDeskState(TypedDict):
    """Private to the orders team. The front desk has never heard of these keys."""
    order_id: str
    record: dict
    trace: list[str]      # a little audit trail so we can see what ran
    answer: str


def find_order(state: OrderDeskState):
    record = ORDERS.get(state["order_id"], {})
    return {"record": record, "trace": state.get("trace", []) + ["find_order"]}


def phrase_answer(state: OrderDeskState):
    record = state["record"]
    if not record:
        text = f"I could not find order {state['order_id']}."
    else:
        text = (f"Order {state['order_id']} ({record['item']}) is "
                f"{record['status']} with {record['carrier']}.")
    return {"answer": text, "trace": state["trace"] + ["phrase_answer"]}


order_desk_builder = StateGraph(OrderDeskState)
order_desk_builder.add_node(find_order)
order_desk_builder.add_node(phrase_answer)
order_desk_builder.add_edge(START, "find_order")
order_desk_builder.add_edge("find_order", "phrase_answer")
order_desk_builder.add_edge("phrase_answer", END)
order_desk = order_desk_builder.compile()

# It is a graph in its own right, so the orders team can test it alone:
print(order_desk.invoke({"order_id": "AUR-1001", "trace": []}))
''')

code(r'''
# ---------------------------------------------------------------- front desk
class FrontDeskState(TypedDict):
    """What the front desk knows. Nothing about orders internals."""
    question: str
    ticket_id: str
    reply: str


import re


def open_ticket(state: FrontDeskState):
    return {"ticket_id": "T-77"}


def ask_orders_team(state: FrontDeskState):
    """The whole interface between the two teams lives in this function."""
    match = re.search(r"AUR-\d+", state["question"])
    order_id = match.group(0) if match else "unknown"

    # translate down
    result = order_desk.invoke({"order_id": order_id, "trace": []})

    # translate back up
    return {"reply": result["answer"]}


def close_ticket(state: FrontDeskState):
    return {"reply": f"[{state['ticket_id']}] {state['reply']}"}


front_builder = StateGraph(FrontDeskState)
front_builder.add_node(open_ticket)
front_builder.add_node("orders", ask_orders_team)
front_builder.add_node(close_ticket)
front_builder.add_edge(START, "open_ticket")
front_builder.add_edge("open_ticket", "orders")
front_builder.add_edge("orders", "close_ticket")
front_desk = front_builder.compile()

result = front_desk.invoke({"question": "where is my order AUR-1001?"})
print(result["reply"])
print()
cr.draw(front_desk, xray=True)
''')

md(r'''
Look carefully at that `xray` drawing. The node you added was called `orders`, but
the picture shows `find_order` and `phrase_answer` instead.

That is worth stopping on, because it surprises people. LangGraph **can** see
through a node function that calls `some_compiled_graph.invoke(...)` directly. It
discovers the subgraph statically and inlines it into the drawing.

What it cannot see through is **indirection**: a subgraph invoked from inside a
tool function, or behind a lambda, or chosen out of a dictionary at run time. Then
it really is an opaque node.

Why this matters beyond the picture: the same static discovery is what lets you
inspect subgraph state with `get_state(..., subgraphs=True)`, which is a topic in
part 2. If LangGraph cannot find your subgraph, you cannot inspect it either.
''')

md(r'''
## 4. Nesting: parent, child, grandchild

Nothing stops a subgraph from having a subgraph. Each level is sealed off from
the ones above and below it, and each level does its own translating.

<img src="../images/diagrams/sg_03_nesting_namespaces.svg" width="880" alt="Nesting and namespaces">

Here is the docs example, three levels deep. Watch the namespaces in the output:
they get longer as you go down, and the path is literally the address of where
that update happened.
''')

code(r'''
from typing_extensions import TypedDict
from langgraph.graph.state import StateGraph, START, END


# ------------------------------------------------------------- grandchild
class GrandChildState(TypedDict):
    my_grandchild_key: str


def grandchild_1(state: GrandChildState) -> GrandChildState:
    # child or parent keys are not accessible here
    return {"my_grandchild_key": state["my_grandchild_key"] + ", how are you"}


grandchild = StateGraph(GrandChildState)
grandchild.add_node("grandchild_1", grandchild_1)
grandchild.add_edge(START, "grandchild_1")
grandchild.add_edge("grandchild_1", END)
grandchild_graph = grandchild.compile()


# ------------------------------------------------------------------ child
class ChildState(TypedDict):
    my_child_key: str


def call_grandchild_graph(state: ChildState) -> ChildState:
    # parent or grandchild keys are not accessible here
    grandchild_graph_input = {"my_grandchild_key": state["my_child_key"]}
    grandchild_graph_output = grandchild_graph.invoke(grandchild_graph_input)
    return {"my_child_key": grandchild_graph_output["my_grandchild_key"] + " today?"}


child = StateGraph(ChildState)
child.add_node("child_1", call_grandchild_graph)
child.add_edge(START, "child_1")
child.add_edge("child_1", END)
child_graph = child.compile()


# ----------------------------------------------------------------- parent
class ParentState(TypedDict):
    my_key: str


def parent_1(state: ParentState) -> ParentState:
    return {"my_key": "hi " + state["my_key"]}


def parent_2(state: ParentState) -> ParentState:
    return {"my_key": state["my_key"] + " bye!"}


def call_child_graph(state: ParentState) -> ParentState:
    child_graph_input = {"my_child_key": state["my_key"]}
    child_graph_output = child_graph.invoke(child_graph_input)
    return {"my_key": child_graph_output["my_child_key"]}


parent = StateGraph(ParentState)
parent.add_node("parent_1", parent_1)
parent.add_node("child", call_child_graph)
parent.add_node("parent_2", parent_2)
parent.add_edge(START, "parent_1")
parent.add_edge("parent_1", "child")
parent.add_edge("child", "parent_2")
parent.add_edge("parent_2", END)
parent_graph = parent.compile()

stream = parent_graph.stream_events({"my_key": "Bob"}, version="v3",
                                    transformers=[UpdatesTransformer])
for event in stream:
    if event["method"] == "updates":
        namespace = event["params"]["namespace"]
        depth = len(namespace)
        print(f"depth {depth}  {namespace}")
        print(f"          {event['params']['data']}")
''')

md(r'''
Read the depths down the left. `0` is the parent, `1` is the child, `2` is the
grandchild. The string `"hi Bob"` was translated three times on the way down and
three times on the way back, and each level only ever saw its own key.

If you have ever debugged a nested agent system and wondered where a value came
from, this namespace path is the answer to that question.
''')

md(r'''
### 4a. Aurora: the shipping carrier grandchild

Same shape, in the story. The orders specialist does not know how to talk to a
shipping carrier, so it delegates to a carrier graph, which is owned by yet
another team.
''')

code(r'''
# --------------------------------------------------- grandchild: the carrier
class CarrierState(TypedDict):
    tracking_ref: str
    scan_history: list[str]
    eta: str


CARRIER_SCANS = {
    "Bluewing": ["left warehouse", "in transit", "out for delivery"],
    "Northline": ["left warehouse", "delivered"],
}


def pull_scans(state: CarrierState):
    return {"scan_history": CARRIER_SCANS.get(state["tracking_ref"], ["no data"])}


def estimate(state: CarrierState):
    last = state["scan_history"][-1]
    eta = "today before 6pm" if last == "out for delivery" else "unknown"
    return {"eta": eta}


carrier_builder = StateGraph(CarrierState)
carrier_builder.add_node(pull_scans)
carrier_builder.add_node(estimate)
carrier_builder.add_edge(START, "pull_scans")
carrier_builder.add_edge("pull_scans", "estimate")
carrier = carrier_builder.compile()


# ------------------------------------------- child: orders, now with tracking
class OrderDeskState2(TypedDict):
    order_id: str
    record: dict
    answer: str


def find_order_2(state: OrderDeskState2):
    return {"record": ORDERS.get(state["order_id"], {})}


def ask_carrier(state: OrderDeskState2):
    """Orders talks to the carrier team. Note the translation, again."""
    record = state["record"]
    if not record:
        return {"answer": f"I could not find order {state['order_id']}."}

    carrier_result = carrier.invoke({"tracking_ref": record["carrier"]})

    return {
        "answer": (
            f"Order {state['order_id']} ({record['item']}): "
            f"{carrier_result['scan_history'][-1]}, ETA {carrier_result['eta']}."
        )
    }


orders2_builder = StateGraph(OrderDeskState2)
orders2_builder.add_node(find_order_2)
orders2_builder.add_node(ask_carrier)
orders2_builder.add_edge(START, "find_order_2")
orders2_builder.add_edge("find_order_2", "ask_carrier")
orders_with_tracking = orders2_builder.compile()


# ----------------------------------------------------- parent: the front desk
def ask_orders_team_2(state: FrontDeskState):
    match = re.search(r"AUR-\d+", state["question"])
    order_id = match.group(0) if match else "unknown"
    return {"reply": orders_with_tracking.invoke({"order_id": order_id})["answer"]}


front2 = StateGraph(FrontDeskState)
front2.add_node(open_ticket)
front2.add_node("orders", ask_orders_team_2)
front2.add_node(close_ticket)
front2.add_edge(START, "open_ticket")
front2.add_edge("open_ticket", "orders")
front2.add_edge("orders", "close_ticket")
front_desk_2 = front2.compile()

print(front_desk_2.invoke({"question": "where is AUR-1001?"})["reply"])
print(front_desk_2.invoke({"question": "and AUR-1002?"})["reply"])
''')

md(r'''
Three teams, three graphs, three state schemas, and none of them imports the
others' types. The front desk asks about an order. Orders asks about a carrier.
Each hop is one dict in and one dict out.
''')

md(r'''
## 5. Pattern B: add the subgraph as a node

Now the shorter path. When the parent and subgraph **share state keys**, you can
hand the compiled subgraph straight to `add_node`. No wrapper function. The
subgraph reads and writes the parent's own channels.

This is how most multi-agent systems are built, because the agents usually talk
over a shared `messages` list.

The docs page illustrates it with this graph, an SQL agent whose middle node is a
whole query-checking subgraph:

<img src="../images/original/subgraph.png" width="620" alt="Official LangGraph subgraph diagram">

*(source: <https://docs.langchain.com/oss/python/langgraph/use-subgraphs>)*

The recipe is two steps:

1. define the subgraph and compile it
2. pass the compiled subgraph to `add_node`
''')

code(r'''
class State(TypedDict):
    foo: str


def subgraph_node_1(state: State):
    return {"foo": "hi! " + state["foo"]}


subgraph_builder = StateGraph(State)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_edge(START, "subgraph_node_1")
sub_b = subgraph_builder.compile()

builder = StateGraph(State)
builder.add_node("node_1", sub_b)      # the compiled subgraph goes straight in
builder.add_edge(START, "node_1")
graph_b = builder.compile()

print(graph_b.invoke({"foo": "foo"}))
''')

md(r'''
### 5a. Shared keys and private keys together

A subgraph does not have to share *everything*. It can declare extra keys that the
parent has never heard of, use them internally, and write back only on the shared
channel. This is the full example from the docs.
''')

code(r'''
class SubgraphState(TypedDict):
    foo: str      # shared with the parent graph state
    bar: str      # private to SubgraphState


def subgraph_node_1(state: SubgraphState):
    return {"bar": "bar"}


def subgraph_node_2(state: SubgraphState):
    # uses a key ('bar') that only exists in the subgraph,
    # and writes to the shared key ('foo')
    return {"foo": state["foo"] + state["bar"]}


subgraph_builder = StateGraph(SubgraphState)
subgraph_builder.add_node(subgraph_node_1)
subgraph_builder.add_node(subgraph_node_2)
subgraph_builder.add_edge(START, "subgraph_node_1")
subgraph_builder.add_edge("subgraph_node_1", "subgraph_node_2")
shared_subgraph = subgraph_builder.compile()


class ParentState(TypedDict):
    foo: str      # the parent has no idea "bar" exists


def node_1(state: ParentState):
    return {"foo": "hi! " + state["foo"]}


builder = StateGraph(ParentState)
builder.add_node("node_1", node_1)
builder.add_node("node_2", shared_subgraph)
builder.add_edge(START, "node_1")
builder.add_edge("node_1", "node_2")
shared_graph = builder.compile()

final = shared_graph.invoke({"foo": "foo"})
print("final parent state:", final)
print()
print("note there is no 'bar' in there. It lived and died inside the subgraph.")
''')

code(r'''
cr.rule("and this time xray really does see inside")
cr.draw(shared_graph, xray=True)
''')

md(r'''
Same inlining as in section 3b, for the same reason: LangGraph discovered the
subgraph statically. The difference here is that you never wrote a line of mapping
code to get it.

That is the practical argument for pattern B whenever the schemas allow it. Less
code to keep in step, and one less place for two teams to disagree about what a
key means.
''')

md(r'''
### 5b. Aurora: the billing specialist over a shared `messages` channel

`MessagesState` is just a `TypedDict` with a `messages` key and an appending
reducer. If both graphs use it, they share the conversation automatically.
''')

code(r'''
from langgraph.graph import MessagesState
from langchain.messages import AIMessage

INVOICES = {
    "AUR-1001": [("desk", 429.00), ("delivery", 0.00)],
    "AUR-1002": [("lamp", 89.00), ("delivery", 6.50)],
}


class BillingState(MessagesState):
    """Shares `messages` with the parent. `lines` is private to billing."""
    lines: list


def pull_invoice(state: BillingState):
    # The parent appended a greeting after the customer's message, so take the
    # last HUMAN message rather than the last message of any kind.
    text = next(m.text for m in reversed(state["messages"]) if m.type == "human")
    match = re.search(r"AUR-\d+", text)
    order_id = match.group(0) if match else ""
    return {"lines": INVOICES.get(order_id, [])}


def explain_invoice(state: BillingState):
    lines = state["lines"]
    if not lines:
        return {"messages": [AIMessage(content="I could not find that invoice.")]}
    total = sum(amount for _, amount in lines)
    detail = ", ".join(f"{label} ${amount:.2f}" for label, amount in lines)
    # writes on the SHARED channel, so the parent sees it
    return {"messages": [AIMessage(content=f"Invoice: {detail}. Total ${total:.2f}.")]}


billing_builder = StateGraph(BillingState)
billing_builder.add_node(pull_invoice)
billing_builder.add_node(explain_invoice)
billing_builder.add_edge(START, "pull_invoice")
billing_builder.add_edge("pull_invoice", "explain_invoice")
billing = billing_builder.compile()


# ------------------------------------------------------------ the front desk
def greet(state: MessagesState):
    return {"messages": [AIMessage(content="Aurora Retail billing, one moment.")]}


desk_builder = StateGraph(MessagesState)
desk_builder.add_node(greet)
desk_builder.add_node("billing", billing)      # straight in, no wrapper
desk_builder.add_edge(START, "greet")
desk_builder.add_edge("greet", "billing")
billing_desk = desk_builder.compile()

out = billing_desk.invoke(
    {"messages": [{"role": "user", "content": "Why was I charged for AUR-1002?"}]}
)
cr.show_messages(out, "shared messages channel")
print("keys the parent ended up with:", list(out.keys()))
''')

md(r'''
The billing subgraph appended to `messages` and the front desk simply has it. No
translation code anywhere. And `lines`, the private key, is not in the parent's
final state at all.

There is a trap hidden in `pull_invoice`, and it is worth pointing at on screen.
The obvious way to write that node is `state["messages"][-1]`. It breaks, because
by the time billing runs, the last message is the front desk's own greeting and
not the customer's question.

**A shared channel is shared in both directions.** Take pattern B and you inherit
whatever else the parent decided to put on the channel, so read it defensively.

That is the trade in one screen:

- **Pattern A** gives isolation and costs you two lines of mapping per hop.
- **Pattern B** gives convenience and costs you a shared vocabulary.
''')

md(r'''
## 6. Watching a nested run go by

When something goes wrong three levels down, you need to see it. There are three
ways, and they suit different jobs.

<img src="../images/diagrams/sg_06_streaming.svg" width="880" alt="Two views of the same nested run">
''')

code(r'''
# The graph from section 5a: parent node_1, then a two-node subgraph as node_2.

cr.rule("1. stream.subgraphs, the recommended way")
stream = shared_graph.stream_events({"foo": "foo"}, version="v3")

for sg in stream.subgraphs:
    print(f"  subgraph {sg.graph_name!r} at path {sg.path}")
    for snapshot in sg.values:
        print("     state:", snapshot)
''')

md(r'''
No namespace strings to parse, no transformer to register. Each nested run comes
back as a handle with a `graph_name`, a `path`, and its own `values` and
`messages` projections. This is the one to reach for.
''')

code(r'''
cr.rule("2. raw protocol events, when you want everything")
stream = shared_graph.stream_events({"foo": "foo"}, version="v3",
                                    transformers=[UpdatesTransformer])
for event in stream:
    if event["method"] == "updates":
        print(" ", event["params"]["namespace"], event["params"]["data"])
''')

code(r'''
cr.rule("3. the classic .stream(subgraphs=True), still perfectly good")
for namespace, chunk in shared_graph.stream({"foo": "foo"},
                                            subgraphs=True, stream_mode="updates"):
    print(" ", namespace, chunk)
''')

md(r'''
Which to use:

| Way | Use it when |
| --- | --- |
| `stream.subgraphs` | you want structure: which nested run, what did it do |
| raw events with `UpdatesTransformer` | you want the complete firehose, in order |
| `.stream(subgraphs=True)` | you are already using `.stream()` and just want depth |

All three show the same run. Pick by what you want to read, not by which is newer.
''')

md(r'''
## 7. Recap

| | Pattern A | Pattern B |
| --- | --- | --- |
| Attach with | `sub.invoke()` inside a node function | `add_node("name", sub)` |
| Requires | nothing shared | at least one shared state key |
| Mapping | you write it | automatic |
| `xray` drawing shows inner nodes | no | yes |
| LangGraph can inspect its state | no | yes |

The mental model that carries you through part 2:

1. A subgraph is a function whose argument is a dict and whose return is a dict.
2. The namespace is the address of a running subgraph, and it grows one segment
   per level of nesting.
3. If you can share a key, share it. Pattern B is shorter and LangGraph can see
   inside it.

**Part 2** answers the question this notebook has been carefully avoiding: when
the same subgraph is called twice, should it remember the first call?

---

### Exercises

1. Take `order_desk` from section 3b and convert it to pattern B by giving both
   graphs a shared key. Which version would you rather hand to another team?
2. Add a fourth level under the carrier graph, a `customs` graph, and predict the
   namespace depth before you run it.
3. In section 5a, make `subgraph_node_2` write to a key the parent does not have.
   What happens, and does it fail loudly or quietly?
4. Use `stream.subgraphs` on the three-level `parent_graph` from section 4 and
   explain why it reports what it does.

### Reference

- Subgraphs: <https://docs.langchain.com/oss/python/langgraph/use-subgraphs>
- Graph API: <https://docs.langchain.com/oss/python/langgraph/graph-api>
- Event streaming: <https://docs.langchain.com/oss/python/langgraph/event-streaming>
''')

build(C, os.path.join(os.path.dirname(__file__), "..", "notebooks",
                      "03_subgraphs_composing_graphs.ipynb"))
