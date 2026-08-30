import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from svgkit import *

OUT = os.path.join(os.path.dirname(__file__), "..", "images", "diagrams")
os.makedirs(OUT, exist_ok=True)
p = lambda n: os.path.join(OUT, n)

DARKTXT = '#9fb0c4'
def invert(s):
    s.parts[-2] = s.parts[-2].replace(f'fill="{INK}" font-weight="600"', f'fill="{WHITE}" font-weight="700"')
    s.parts[-1] = s.parts[-1].replace(f'fill="{MUTED}"', f'fill="{DARKTXT}"')

# ----------------------------------------------------------------------------
# 1. What a subgraph is
# ----------------------------------------------------------------------------
s = Svg(980, 430)
s.title(40, 46, "A subgraph is a graph used as a node", "From the outside it is one box. Inside it is a whole graph of its own.")

s.rect(40, 92, 420, 296, fill=PANEL, stroke=LINE, r=16)
s.text(60, 120, "WHAT THE PARENT SEES", size=11, weight="700", fill=MUTED, anchor="start", ls="1.1")
s.box(180, 142, 140, 44, "START", fill=WHITE, stroke=LINE, tsize=12, mono=True)
s.arrow(250, 186, 250, 220)
s.box(150, 220, 200, 60, "check_order", "one node", fill=BLUE_SOFT, stroke=BLUE)
s.arrow(250, 280, 250, 314)
s.box(180, 314, 140, 44, "END", fill=WHITE, stroke=LINE, tsize=12, mono=True)

s.rect(520, 92, 420, 296, fill=PANEL, stroke=LINE, r=16)
s.text(540, 120, "WHAT IS ACTUALLY INSIDE", size=11, weight="700", fill=MUTED, anchor="start", ls="1.1")
s.rect(548, 132, 364, 240, fill=BLUE_SOFT, stroke=BLUE, r=12, dash="6 5")
s.box(650, 148, 160, 38, "START", fill=WHITE, stroke=LINE, tsize=11, mono=True)
s.arrow(730, 186, 730, 208)
s.box(600, 208, 260, 46, "fetch_order", fill=WHITE, stroke=BLUE, tsize=12, mono=True)
s.arrow(730, 254, 730, 276)
s.box(600, 276, 260, 46, "summarise_status", fill=WHITE, stroke=BLUE, tsize=12, mono=True)
s.arrow(730, 322, 730, 340)
s.box(650, 340, 160, 30, "END", fill=WHITE, stroke=LINE, tsize=11, mono=True)

s.text(490, 414, "Reusable, independently testable, and a different team can own it.",
       size=12.5, fill=MUTED)
s.save(p("sg_01_what_is_a_subgraph.svg"))

# ----------------------------------------------------------------------------
# 2. The two wiring patterns
# ----------------------------------------------------------------------------
s = Svg(1000, 560)
s.title(40, 46, "Two ways to attach a subgraph", "The state schemas decide which one you are allowed to use")

# LEFT
s.rect(40, 86, 448, 396, fill=WHITE, stroke=AMBER, r=16)
s.rect(40, 86, 448, 46, fill=AMBER_SOFT, stroke=AMBER, r=16)
s.rect(40, 116, 448, 16, fill=AMBER_SOFT, stroke="none", r=0)
s.text(64, 116, "A.  Call it inside a node", size=14.5, weight="700", fill=AMBER, anchor="start")
s.text(64, 158, "Schemas share nothing. You translate.", size=12.5, fill=INK, anchor="start")

s.box(96, 186, 336, 44, "parent state:  {\"foo\": str}", fill=PANEL, stroke=LINE, tsize=12, mono=True)
s.arrow(264, 230, 264, 258, stroke=AMBER, marker=None)
s.rect(96, 258, 336, 128, fill=AMBER_SOFT, stroke=AMBER, r=12)
s.text(264, 282, "def call_subgraph(state):", size=12, fill=INK, font=MONO, weight="600")
s.text(264, 306, 'out = sub.invoke({"bar": state["foo"]})', size=11.5, fill=AMBER, font=MONO)
s.text(264, 328, "(the subgraph runs)", size=11, fill=MUTED)
s.text(264, 352, 'return {"foo": out["bar"]}', size=11.5, fill=AMBER, font=MONO)
s.text(264, 374, "you map both directions by hand", size=10.5, fill=MUTED)
s.arrow(264, 386, 264, 414, stroke=AMBER, marker=None)
s.box(96, 414, 336, 44, "parent state:  {\"foo\": str}", fill=PANEL, stroke=LINE, tsize=12, mono=True)

# RIGHT
s.rect(512, 86, 448, 396, fill=WHITE, stroke=GREEN, r=16)
s.rect(512, 86, 448, 46, fill=GREEN_SOFT, stroke=GREEN, r=16)
s.rect(512, 116, 448, 16, fill=GREEN_SOFT, stroke="none", r=0)
s.text(536, 116, "B.  Add it as a node", size=14.5, weight="700", fill=GREEN, anchor="start")
s.text(536, 158, "Schemas share a key. No translation.", size=12.5, fill=INK, anchor="start")

s.box(568, 186, 336, 44, "parent state:  {\"foo\": str}", fill=PANEL, stroke=LINE, tsize=12, mono=True)
s.arrow(736, 230, 736, 258, stroke=GREEN, marker=None)
s.rect(568, 258, 336, 128, fill=GREEN_SOFT, stroke=GREEN, r=12)
s.text(736, 284, 'builder.add_node("node_1", subgraph)', size=11.5, fill=GREEN, font=MONO, weight="600")
s.text(736, 312, "the subgraph reads and writes", size=11.5, fill=INK)
s.text(736, 332, "the parent's own channels directly", size=11.5, fill=INK)
s.text(736, 362, "private keys stay private inside", size=10.5, fill=MUTED)
s.arrow(736, 386, 736, 414, stroke=GREEN, marker=None)
s.box(568, 414, 336, 44, "parent state:  {\"foo\": str}", fill=PANEL, stroke=LINE, tsize=12, mono=True)

s.text(500, 522, "Different schemas: you must use A.   Shared key: B is shorter, and LangGraph can see inside it.",
       size=12.5, fill=MUTED)
s.save(p("sg_02_two_patterns.svg"))

# ----------------------------------------------------------------------------
# 3. Nesting + namespaces
# ----------------------------------------------------------------------------
s = Svg(980, 470)
s.title(40, 46, "Nesting and namespaces", "Every level is sealed off from the ones above and below it")

s.rect(40, 92, 570, 330, fill=WHITE, stroke=VIOLET, r=16)
s.text(62, 120, "parent   {\"my_key\": str}", size=12.5, weight="700", fill=VIOLET, anchor="start", font=MONO)
s.rect(70, 136, 510, 272, fill=VIOLET_SOFT, stroke=VIOLET, r=13, dash="5 4", sw=1.2)

s.rect(96, 160, 458, 224, fill=WHITE, stroke=BLUE, r=13)
s.text(118, 186, "child   {\"my_child_key\": str}", size=12.5, weight="700", fill=BLUE, anchor="start", font=MONO)
s.rect(126, 200, 402, 168, fill=BLUE_SOFT, stroke=BLUE, r=12, dash="5 4", sw=1.2)

s.rect(152, 224, 350, 122, fill=WHITE, stroke=GREEN, r=12)
s.text(174, 250, "grandchild   {\"my_grandchild_key\": str}", size=12.5, weight="700", fill=GREEN, anchor="start", font=MONO)
s.rect(180, 264, 294, 66, fill=GREEN_SOFT, stroke=GREEN, r=10, dash="5 4", sw=1.2)
s.text(327, 292, "grandchild_1", size=13, fill=INK, font=MONO, weight="600")
s.text(327, 312, "cannot see my_key or my_child_key", size=10.5, fill=MUTED)

s.text(640, 122, "The namespace you see when streaming", size=13, weight="700", fill=INK, anchor="start")
ns = [(["[]"], "the parent itself", VIOLET),
      (["['child:2e26...']"], "one level down", BLUE),
      (["['child:2e26...',", " 'child_1:781b...']"], "two levels down, and the", GREEN),
      ([], "path is the full address", GREEN)]
y = 158
for codes, note, col in ns:
    for c in codes:
        s.text(640, y, c, size=11.5, fill=col, anchor="start", font=MONO, weight="600")
        y += 17
    s.text(640, y + 2, note, size=11, fill=MUTED, anchor="start")
    y += 40

s.rect(636, 348, 306, 60, fill=PANEL, stroke=LINE, r=10)
s.text(789, 374, "Passing data down is your job:", size=11.5, fill=INK)
s.text(789, 392, "one dict in, one dict out, at each hop.", size=11.5, fill=MUTED)
s.save(p("sg_03_nesting_namespaces.svg"))

# ----------------------------------------------------------------------------
# 4. Persistence modes
# ----------------------------------------------------------------------------
s = Svg(1000, 470)
s.title(40, 46, "Three ways a subgraph can remember", "Set with one argument:  builder.compile(checkpointer=...)")

cols = [
    ("checkpointer=None", "Per-invocation", BLUE, BLUE_SOFT,
     ["Fresh state on every call.", "Inherits the parent's", "checkpointer for the", "duration of one call."],
     ["interrupt / resume", "durable execution", "parallel calls are safe"],
     ["no memory between calls"],
     ("The default. Use this unless you", "have a reason not to.")),
    ("checkpointer=True", "Per-thread", GREEN, GREEN_SOFT,
     ["State accumulates on the", "thread. Call two picks up", "where call one stopped.", ""],
     ["interrupt / resume", "durable execution", "multi-turn memory"],
     ["parallel calls collide"],
     ("For a subagent that must remember", "the conversation.")),
    ("checkpointer=False", "Stateless", AMBER, AMBER_SOFT,
     ["Nothing is written down.", "Behaves like an ordinary", "function call.", ""],
     ["no bookkeeping cost"],
     ["no durable execution", "no state inspection"],
     ("For pure, cheap work with no", "side effects to protect.")),
]
x = 40
for code, name, col, soft, desc, yes, no, foot in cols:
    s.rect(x, 88, 300, 328, fill=WHITE, stroke=col, r=16)
    s.rect(x, 88, 300, 68, fill=soft, stroke=col, r=16)
    s.rect(x, 140, 300, 16, fill=soft, stroke="none", r=0)
    s.text(x + 150, 116, name, size=15, weight="700", fill=col)
    s.text(x + 150, 138, code, size=11.5, fill=MUTED, font=MONO)
    y = 182
    for d in desc:
        s.text(x + 22, y, d, size=12, fill=INK, anchor="start")
        y += 19
    y += 8
    for t in yes:
        s.tick(x + 24, y, col=GREEN)
        s.text(x + 44, y, t, size=11.5, fill=INK, anchor="start")
        y += 24
    for t in no:
        s.cross(x + 25, y, col=RED)
        s.text(x + 44, y, t, size=11.5, fill=MUTED, anchor="start")
        y += 24
    s.line(x + 22, 362, x + 278, 362, stroke=LINE)
    s.text(x + 150, 384, foot[0], size=11, fill=MUTED)
    s.text(x + 150, 401, foot[1], size=11, fill=MUTED)
    x += 320

s.text(500, 450, "The parent must be compiled with a real checkpointer for any of this to matter.",
       size=12.5, fill=MUTED)
s.save(p("sg_04_persistence_modes.svg"))

# ----------------------------------------------------------------------------
# 5. Namespace isolation
# ----------------------------------------------------------------------------
s = Svg(980, 470)
s.title(40, 46, "Why per-thread subagents need their own name",
        "Namespaces are the folder each subgraph saves its state into")

s.rect(40, 92, 440, 300, fill=WHITE, stroke=RED, r=16)
s.text(62, 122, "WITHOUT A WRAPPER", size=11.5, weight="700", fill=RED, anchor="start", ls="1.1")
s.text(62, 146, "Namespaces come from call order.", size=12.5, fill=INK, anchor="start")
rows = [("call fruit first  ->", "ns  1", "fruit's state"),
        ("call veggie next  ->", "ns  2", "veggie's state"),
        ("reorder the calls ->", "ns  1", "now veggie loads fruit's state")]
y = 182
for a, b, c in rows:
    s.text(62, y, a, size=11.5, fill=MUTED, anchor="start", font=MONO)
    s.rect(206, y - 16, 62, 24, fill=RED_SOFT, stroke=RED, r=6, sw=1.2)
    s.text(237, y, b, size=11.5, fill=RED, font=MONO, weight="700")
    s.text(282, y, c, size=11.5, fill=INK, anchor="start")
    y += 46
s.rect(62, 316, 396, 56, fill=RED_SOFT, stroke=RED, r=10)
s.text(260, 340, "The state you load depends on the order", size=12, fill=RED, weight="600")
s.text(260, 358, "you happened to write the calls in.", size=12, fill=RED, weight="600")

s.rect(516, 92, 424, 300, fill=WHITE, stroke=GREEN, r=16)
s.text(538, 122, "WITH A ONE-NODE WRAPPER", size=11.5, weight="700", fill=GREEN, anchor="start", ls="1.1")
s.text(538, 146, "Namespaces come from the node name.", size=12.5, fill=INK, anchor="start")
rows = [('add_node("fruit_agent", ...)', "ns  fruit_agent"),
        ('add_node("veggie_agent", ...)', "ns  veggie_agent")]
y = 186
for a, b in rows:
    s.text(538, y, a, size=11.5, fill=MUTED, anchor="start", font=MONO)
    s.rect(538, y + 10, 200, 26, fill=GREEN_SOFT, stroke=GREEN, r=6, sw=1.2)
    s.text(638, y + 28, b, size=11.5, fill=GREEN, font=MONO, weight="700")
    y += 66
s.rect(538, 316, 380, 56, fill=GREEN_SOFT, stroke=GREEN, r=10)
s.text(728, 340, "Stable and unique, whatever order", size=12, fill=GREEN, weight="600")
s.text(728, 358, "the model decides to call them in.", size=12, fill=GREEN, weight="600")

s.text(490, 434, "A subgraph added with add_node already gets a name-based namespace. This wrapper just gives one to a subagent called from a tool.",
       size=11.5, fill=MUTED)
s.save(p("sg_05_namespace_isolation.svg"))

# ----------------------------------------------------------------------------
# 6. Streaming through nesting
# ----------------------------------------------------------------------------
s = Svg(980, 480)
s.title(40, 46, "Seeing inside a running subgraph", "Two views of the same run")

s.rect(40, 92, 440, 330, fill=WHITE, stroke=LINE, r=16)
s.text(62, 122, "RAW EVENTS", size=11.5, weight="700", fill=MUTED, anchor="start", ls="1.1")
s.text(62, 146, "One flat list. You read the namespace.", size=12.5, fill=INK, anchor="start")
ev = [("[]", "node_1", VIOLET),
      ("['node_2:e58e...']", "subgraph_node_1", BLUE),
      ("['node_2:e58e...']", "subgraph_node_2", BLUE),
      ("[]", "node_2", VIOLET)]
y = 184
for ns, node, col in ev:
    s.rect(62, y - 18, 396, 44, fill=PANEL, stroke=LINE, r=8)
    s.text(78, y + 2, ns, size=11, fill=col, anchor="start", font=MONO, weight="600")
    s.text(300, y + 2, node, size=11.5, fill=INK, anchor="start", font=MONO)
    y += 56
s.text(260, 400, "depth is a string you have to parse", size=11, fill=MUTED)

s.rect(516, 92, 424, 330, fill=WHITE, stroke=BLUE, r=16)
s.text(538, 122, "stream.subgraphs", size=11.5, weight="700", fill=BLUE, anchor="start", ls="0.6", font=MONO)
s.text(538, 146, "Already grouped, one handle per run.", size=12.5, fill=INK, anchor="start")
s.rect(538, 168, 380, 208, fill=BLUE_SOFT, stroke=BLUE, r=12)
s.text(728, 196, "for sg in stream.subgraphs:", size=12, fill=INK, font=MONO, weight="600")
s.text(728, 222, "sg.graph_name   ->  'node_2'", size=11.5, fill=BLUE, font=MONO)
s.text(728, 244, "sg.path         ->  ('node_2:e58e...',)", size=11.5, fill=BLUE, font=MONO)
s.text(728, 266, "sg.values       ->  each state snapshot", size=11.5, fill=BLUE, font=MONO)
s.text(728, 288, "sg.messages     ->  tokens from inside", size=11.5, fill=BLUE, font=MONO)
s.line(566, 308, 890, 308, stroke="#c3d5f7")
s.text(728, 334, "No string parsing. Works at any depth.", size=11.5, fill=INK)
s.text(728, 356, "This is the one to reach for.", size=11.5, fill=MUTED)

s.text(490, 452, "Both come from  graph.stream_events(input, version=\"v3\")",
       size=12.5, fill=MUTED, font=MONO)
s.save(p("sg_06_streaming.svg"))
