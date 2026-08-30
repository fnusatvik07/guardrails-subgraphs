import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from svgkit import *

OUT = os.path.join(os.path.dirname(__file__), "..", "images", "diagrams")
p = lambda n: os.path.join(OUT, n)

# ----------------------------------------------------------------------------
# The tokenise / rehydrate round trip
# ----------------------------------------------------------------------------
s = Svg(1000, 604)
s.title(40, 46, "Redact for the model, rehydrate for the tool",
        "The real value leaves your process only on the way to the tool that needs it")

# what the model provider gets to see
s.rect(496, 100, 228, 222, fill="#fdfbfa", stroke=RED, r=14, dash="7 5")
s.text(610, 122, "OUTSIDE YOUR TRUST BOUNDARY", size=9.5, fill=RED, weight="700", ls="0.6")

s.box(48, 140, 200, 62, "member types", "SSN 482-11-9930", fill=WHITE, stroke=LINE, tsize=12.5)

s.arrow(248, 171, 284, 171, stroke=BLUE, marker="arwB")
s.box(288, 140, 180, 62, "before_model", "swap in a placeholder",
      fill=BLUE_SOFT, stroke=BLUE, tsize=12.5, ssize=10.5)

s.arrow(468, 171, 516, 171, stroke=BLUE, marker="arwB")
s.rect(520, 140, 180, 66, fill=INK, stroke=INK, r=12)
s.text(610, 168, "THE MODEL", size=13, fill=WHITE, weight="700", font=MONO)
s.text(610, 190, "sees only  <ssn_1>", size=11.5, fill="#7fd1a5", font=MONO)

s.arrow(610, 206, 610, 242, stroke=BLUE, marker="arwB")
s.box(508, 246, 204, 56, 'lookup(ssn="<ssn_1>")', "the model's tool call",
      fill=PANEL, stroke=LINE, tsize=11.5, ssize=10.5, mono=True)

s.arrow(508, 274, 462, 274, stroke=GREEN, marker="arwG")
s.box(268, 246, 190, 56, "wrap_tool_call", "put the real value back",
      fill=GREEN_SOFT, stroke=GREEN, tsize=12.5, ssize=10.5)

s.arrow(268, 274, 252, 274, stroke=GREEN, marker="arwG")
s.box(48, 246, 200, 56, "the tool runs", "with 482-11-9930",
      fill=WHITE, stroke=GREEN, tsize=12.5, ssize=10.5)

# the vault, written on the way in and read on the way out
s.rect(48, 356, 664, 92, fill=VIOLET_SOFT, stroke=VIOLET, r=12)
s.text(70, 384, "THE VAULT", size=11, weight="700", fill=VIOLET, anchor="start", ls="1.1")
s.text(70, 406, "<ssn_1>  ->  482-11-9930", size=13, fill=INK, anchor="start", font=MONO, weight="600")
s.text(70, 428, "in your process, keyed by thread, never sent anywhere", size=11, fill=MUTED, anchor="start")
s.text(688, 386, "written by before_model", size=11, fill=BLUE, anchor="end", font=MONO, weight="600")
s.text(688, 408, "read by wrap_tool_call", size=11, fill=GREEN, anchor="end", font=MONO, weight="600")

s.path("M 350 204 L 350 224 L 258 224 L 258 352", stroke=VIOLET, sw=1.3, dash="4 4", marker="arwV")
s.path("M 300 352 L 300 306", stroke=VIOLET, sw=1.3, dash="4 4", marker="arwV")

# the allow list
s.rect(744, 136, 216, 312, fill=WHITE, stroke=AMBER, r=14)
s.rect(744, 136, 216, 46, fill=AMBER_SOFT, stroke=AMBER, r=14)
s.rect(744, 166, 216, 16, fill=AMBER_SOFT, stroke="none", r=0)
s.text(852, 165, "the allow list", size=13, weight="700", fill=AMBER)
s.text(852, 206, "Which tool may see", size=11.5, fill=INK)
s.text(852, 224, "which kind of value.", size=11.5, fill=INK)
s.tick(768, 266, col=GREEN)
s.text(790, 266, "lookup_member", size=11, fill=INK, anchor="start", font=MONO)
s.text(790, 282, "gets 482-11-9930", size=10.5, fill=MUTED, anchor="start")
s.cross(769, 322, col=RED)
s.text(790, 322, "send_email", size=11, fill=INK, anchor="start", font=MONO)
s.text(790, 338, "gets <ssn_1>", size=10.5, fill=MUTED, anchor="start")
s.line(768, 366, 936, 366, stroke="#ecd9b6")
s.text(852, 390, "A model that decides", size=11, fill=MUTED)
s.text(852, 406, "to leak it can only", size=11, fill=MUTED)
s.text(852, 422, "leak the placeholder.", size=11, fill=MUTED)

s.text(500, 486, "The model can reason about the value, refer to it, and route it to a tool.",
       size=13, fill=INK)
s.text(500, 508, "It just never learns what it is.", size=13, fill=INK, weight="600")

s.rect(48, 532, 912, 48, fill=PANEL, stroke=LINE, r=10)
s.text(504, 554, "Why PIIMiddleware cannot do this: redact, mask and hash are all one way.",
       size=12, fill=INK)
s.text(504, 572, "Nothing turns [REDACTED_SSN] back into a number, which is exactly what they are for.",
       size=11.5, fill=MUTED)
s.save(p("gr_06_tokenise_and_rehydrate.svg"))

# ----------------------------------------------------------------------------
# Three ways to keep a value away from the model
# ----------------------------------------------------------------------------
s = Svg(1000, 500)
s.title(40, 46, "Three ways to keep a value away from the model",
        "Reach for them in this order")

cols = [
    ("1", "Never put it in the chat", GREEN, GREEN_SOFT,
     ["The member is already signed in.", "The tool reads identity from the", "session, not from the message."],
     "lookup_my_record()",
     "no arguments at all",
     ["Simplest and safest.", "Nothing to leak, because", "nothing was ever typed."],
     "Use when the value identifies the person you are already talking to."),
    ("2", "Tokenise and rehydrate", BLUE, BLUE_SOFT,
     ["The value has to travel, but", "the model only needs to route", "it, not read it."],
     'lookup(ssn="<ssn_1>")',
     "swapped back by middleware",
     ["Works for any value.", "Needs a vault, an allow list", "and an audit trail."],
     "Use when the value comes from the conversation and a tool truly needs it."),
    ("3", "Collect it out of band", VIOLET, VIOLET_SOFT,
     ["The tool pauses and asks for", "the value through a secure form", "that bypasses the chat."],
     'interrupt({"field": "ssn"})',
     "resumed straight into the tool",
     ["Never enters messages at all.", "Costs the member a round trip", "through another screen."],
     "Use when the value must never be typed into a chat box in the first place."),
]
x = 40
for num, name, col, soft, desc, code_line, code_note, points, foot in cols:
    s.rect(x, 88, 300, 340, fill=WHITE, stroke=col, r=16)
    s.rect(x, 88, 300, 60, fill=soft, stroke=col, r=16)
    s.rect(x, 132, 300, 16, fill=soft, stroke="none", r=0)
    s.circle(x + 30, 118, 15, fill=col, stroke=col)
    s.text(x + 30, 123, num, size=13, weight="700", fill=WHITE)
    s.text(x + 168, 123, name, size=13.5, weight="700", fill=col)
    y = 176
    for d in desc:
        s.text(x + 20, y, d, size=11.5, fill=INK, anchor="start")
        y += 18
    s.rect(x + 20, 236, 260, 46, fill=PANEL, stroke=LINE, r=8)
    s.text(x + 150, 258, code_line, size=11, fill=col, font=MONO, weight="600")
    s.text(x + 150, 274, code_note, size=10, fill=MUTED)
    y = 306
    for t in points:
        s.text(x + 20, y, t, size=11, fill=MUTED, anchor="start")
        y += 17
    s.line(x + 20, 372, x + 280, 372, stroke=LINE)
    words, line, lines = foot.split(), "", []
    for w in words:
        if len(line + " " + w) > 40:
            lines.append(line); line = w
        else:
            line = (line + " " + w).strip()
    lines.append(line)
    y = 392
    for ln in lines[:3]:
        s.text(x + 150, y, ln, size=10.5, fill=INK)
        y += 15
    x += 320

s.text(500, 468, "Most teams reach for 2 first. Check whether 1 is available before you do.",
       size=12.5, fill=MUTED)
s.save(p("gr_07_three_approaches.svg"))
