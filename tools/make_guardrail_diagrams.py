import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from svgkit import *

OUT = os.path.join(os.path.dirname(__file__), "..", "images", "diagrams")
os.makedirs(OUT, exist_ok=True)
p = lambda n: os.path.join(OUT, n)

# ----------------------------------------------------------------------------
# 1. Where guardrails plug in: the six middleware hooks around one agent turn
# ----------------------------------------------------------------------------
s = Svg(980, 520)
s.title(40, 46, "Where a guardrail can stand", "Six places middleware can inspect, change, or stop the run")

s.rect(40, 78, 900, 364, fill=PANEL, stroke=LINE, r=16)

s.rect(62, 100, 856, 320, fill=WHITE, stroke=VIOLET, r=14, dash="6 5")
s.text(78, 122, "run scope", size=11, fill=VIOLET, weight="700", anchor="start", ls="0.6")

s.box(80, 168, 150, 60, "before_agent", "once, at the start", fill=VIOLET_SOFT, stroke=VIOLET)
s.box(750, 168, 150, 60, "after_agent", "once, at the end", fill=VIOLET_SOFT, stroke=VIOLET)

s.rect(258, 134, 464, 264, fill=PANEL, stroke=BLUE, r=14, dash="6 5")
s.text(274, 156, "model / tool loop  (repeats)", size=11, fill=BLUE, weight="700", anchor="start", ls="0.4")

s.box(280, 172, 196, 52, "before_model", "edit the prompt", fill=BLUE_SOFT, stroke=BLUE, ssize=11)
s.box(504, 172, 196, 52, "after_model", "check the reply", fill=BLUE_SOFT, stroke=BLUE, ssize=11)
s.box(280, 240, 196, 52, "wrap_model_call", "retry / fall back", fill=BLUE_SOFT, stroke=BLUE, ssize=11)
s.box(504, 240, 196, 52, "wrap_tool_call", "veto a tool call", fill=BLUE_SOFT, stroke=BLUE, ssize=11)

s.box(360, 314, 260, 56, "MODEL  +  TOOLS", "the part you are protecting",
      fill=INK, stroke=INK, tsize=13, ssize=11, mono=True)
s.parts[-2] = s.parts[-2].replace(f'fill="{INK}" font-weight="600"', f'fill="{WHITE}" font-weight="700"')
s.parts[-1] = s.parts[-1].replace(f'fill="{MUTED}"', f'fill="#9fb0c4"')

s.arrow(232, 190, 276, 194)
s.arrow(704, 194, 748, 190)
s.line(476, 198, 504, 198, stroke=LINE)
s.line(476, 266, 504, 266, stroke=LINE)

s.text(490, 476, "Cheap, deterministic checks belong on the outside. Expensive, semantic checks belong on the inside.",
       size=12.5, fill=MUTED)
s.save(p("gr_01_hook_map.svg"))

# ----------------------------------------------------------------------------
# 2. Deterministic vs model-based
# ----------------------------------------------------------------------------
s = Svg(980, 470)
s.title(40, 46, "Two kinds of guardrail", "You almost always want both, in this order")

s.rect(40, 82, 435, 340, fill=GREEN_SOFT, stroke=GREEN, r=16)
s.text(62, 116, "DETERMINISTIC", size=13, weight="700", fill=GREEN, anchor="start", ls="1.2")
s.text(62, 140, "Rules you wrote: regex, keyword lists,", size=13, fill=INK, anchor="start")
s.text(62, 160, "numeric limits, allow-lists.", size=13, fill=INK, anchor="start")
rows = [("Speed", "microseconds"), ("Cost", "free"), ("Repeatable", "always the same answer"),
        ("Blind spot", "paraphrases slip past")]
y = 196
for k, v in rows:
    s.text(62, y, k, size=12, weight="700", fill=GREEN, anchor="start")
    s.text(196, y, v, size=12, fill=INK, anchor="start")
    s.line(62, y + 12, 452, y + 12, stroke="#c3e0ce", sw=1)
    y += 40
s.text(62, y + 8, 'e.g. PIIMiddleware("email", strategy="redact")', size=11.5, fill=MUTED,
       anchor="start", font=MONO)

s.rect(505, 82, 435, 340, fill=AMBER_SOFT, stroke=AMBER, r=16)
s.text(527, 116, "MODEL-BASED", size=13, weight="700", fill=AMBER, anchor="start", ls="1.2")
s.text(527, 140, "A second LLM reads the text and judges", size=13, fill=INK, anchor="start")
s.text(527, 160, "it: safe / unsafe, on-topic / off-topic.", size=13, fill=INK, anchor="start")
rows = [("Speed", "an extra round trip"), ("Cost", "extra tokens, every call"),
        ("Repeatable", "mostly, not guaranteed"), ("Strength", "understands meaning")]
y = 196
for k, v in rows:
    s.text(527, y, k, size=12, weight="700", fill=AMBER, anchor="start")
    s.text(661, y, v, size=12, fill=INK, anchor="start")
    s.line(527, y + 12, 917, y + 12, stroke="#ecd9b6", sw=1)
    y += 40
s.text(527, y + 8, "e.g. a small model asked SAFE or UNSAFE", size=11.5, fill=MUTED,
       anchor="start", font=MONO)

s.text(490, 450, "Run the cheap rule first. Only pay for the judge on what survives it.",
       size=12.5, fill=MUTED)
s.save(p("gr_02_deterministic_vs_model.svg"))

# ----------------------------------------------------------------------------
# 3. PII strategies
# ----------------------------------------------------------------------------
s = Svg(980, 430)
s.title(40, 46, "Four things you can do with PII", "Same detector, four different outcomes")

raw = "card 5105-1051-0510-5100"
items = [
    ("redact", "[REDACTED_CREDIT_CARD]", BLUE, BLUE_SOFT, "Model sees a placeholder. Nothing leaks."),
    ("mask",   "****-****-****-5100",    GREEN, GREEN_SOFT, "Last 4 kept so a human can confirm it."),
    ("hash",   "a8f5f167f44f...",        VIOLET, VIOLET_SOFT, "Same input maps to same token. Joinable."),
    ("block",  "PIIDetectionError",      RED, RED_SOFT, "Run stops. Nothing reaches the model."),
]
s.box(60, 218, 210, 62, "user message", raw, fill=WHITE, stroke=LINE, tsize=12, ssize=11.5)
y = 96
for name, out, col, soft, note in items:
    s.arrow(276, 249, 322, y + 30, stroke=col, sw=1.5, marker={"#2563eb":"arwB","#2f7d4f":"arwG","#6d28d9":"arwV","#c0392b":"arwR"}[col])
    s.rect(330, y, 128, 60, fill=soft, stroke=col, r=10)
    s.text(394, y + 26, name, size=13, weight="700", fill=col, font=MONO)
    s.text(394, y + 45, "strategy", size=10.5, fill=MUTED)
    s.text(478, y + 26, out, size=12, fill=INK, anchor="start", font=MONO)
    s.text(478, y + 45, note, size=11, fill=MUTED, anchor="start")
    y += 76

s.text(490, 404, "apply_to_input guards what goes in   /   apply_to_output guards what comes back   /   apply_to_tool_results guards what tools return",
       size=11.5, fill=MUTED)
s.save(p("gr_03_pii_strategies.svg"))

# ----------------------------------------------------------------------------
# 4. HITL interrupt / resume
# ----------------------------------------------------------------------------
s = Svg(980, 430)
s.title(40, 46, "Human in the loop is a pause, not a prompt", "The process may exit. The checkpoint is what resumes it.")

lanes = [("agent process", 130), ("checkpointer", 232), ("human", 334)]
for label, y in lanes:
    s.line(210, y, 930, y, stroke=LINE, sw=1.2, dash="3 4")
    s.text(196, y + 4, label, size=12, fill=MUTED, anchor="end", weight="600")

def ev(x, y, w, label, col, soft, sub=None):
    s.rect(x, y - 20, w, 40, fill=soft, stroke=col, r=8)
    s.text(x + w / 2, y + (0 if not sub else -3), label, size=11.5, weight="700", fill=col)
    if sub:
        s.text(x + w / 2, y + 12, sub, size=10, fill=MUTED)

ev(224, 130, 128, "run starts", BLUE, BLUE_SOFT)
ev(372, 130, 150, "tool needs OK", AMBER, AMBER_SOFT)
ev(372, 232, 150, "state saved", GREEN, GREEN_SOFT, "thread_id")
ev(556, 334, 168, "reviews + decides", VIOLET, VIOLET_SOFT, "approve / edit / reject")
ev(762, 130, 168, "resumes mid-tool", BLUE, BLUE_SOFT, "no replay of the past")

s.arrow(352, 130, 370, 130, stroke=BLUE, marker="arwB")
s.arrow(447, 152, 447, 210, stroke=GREEN, marker="arwG")
s.arrow(524, 240, 552, 322, stroke=VIOLET, marker="arwV")
s.arrow(724, 322, 800, 152, stroke=BLUE, marker="arwB")

s.rect(224, 366, 706, 40, fill=PANEL, stroke=LINE, r=10)
s.text(577, 391, "Command(resume={\"decisions\": [{\"type\": \"approve\"}]})   sent on the same thread_id",
       size=12, fill=INK, font=MONO)
s.save(p("gr_04_hitl_timeline.svg"))

# ----------------------------------------------------------------------------
# 5. Layered defence
# ----------------------------------------------------------------------------
s = Svg(980, 560)
s.title(40, 46, "Defence in depth", "Each layer is cheap enough that the next one rarely has to fire")

layers = [
    ("1", "Content filter", "before_agent", "banned words, obvious abuse", RED, RED_SOFT),
    ("2", "PII in", "before_model", "redact e-mail, mask card, block keys", BLUE, BLUE_SOFT),
    ("3", "Tool policy", "wrap_tool_call", "refuse a $5,000 transfer outright", AMBER, AMBER_SOFT),
    ("4", "Human approval", "HumanInTheLoop", "a person signs off on the rest", VIOLET, VIOLET_SOFT),
    ("5", "PII out", "after_model", "the reply cannot leak it back", BLUE, BLUE_SOFT),
    ("6", "Safety judge", "after_agent", "a model reads the final answer", GREEN, GREEN_SOFT),
]
x0, y = 60, 86
for num, name, hook, note, col, soft in layers:
    s.rect(x0, y, 860, 62, fill=soft, stroke=col, r=12)
    s.circle(x0 + 34, y + 31, 16, fill=col, stroke=col)
    s.text(x0 + 34, y + 36, num, size=14, weight="700", fill=WHITE)
    s.text(x0 + 66, y + 27, name, size=14, weight="700", fill=INK, anchor="start")
    s.text(x0 + 66, y + 46, note, size=11.5, fill=MUTED, anchor="start")
    s.text(x0 + 840, y + 37, hook, size=11.5, fill=col, anchor="end", weight="600", font=MONO)
    y += 72

s.text(490, 538, "A request has to pass every layer. An answer has to pass every layer on the way back.",
       size=12.5, fill=MUTED)
s.save(p("gr_05_layered_defence.svg"))
