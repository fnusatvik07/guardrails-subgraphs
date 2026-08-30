import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from nbbuild import build

C = []
md = lambda s: C.append(("md", s))
code = lambda s: C.append(("code", s))

md(r'''
# Guardrails, part 1: stopping the bad input

**LangChain 1.x, `create_agent` + middleware**

This is the first of two notebooks on guardrails. Together they follow one story
from start to finish, so you can run them in class top to bottom.

---

### The story

You have been asked to ship a support agent for **Northwind Health**, a small
health insurer. Members chat with it about their claims. It can look a claim up,
write a note into the audit log, and e-mail a summary.

That sounds harmless until you write down what a member actually types:

> *"Hi, my name is John Doe, member ID 482-11-9930, my card 5105-1051-0510-5100 was
> charged twice for claim CLM-4471. Can you e-mail me at john.doe@gmail.com?"*

Every one of those numbers is now going to travel to a model provider, land in a
log file, and possibly come back out in an e-mail. That is the problem guardrails
solve.

### What you will learn here (part 1)

1. What a guardrail actually is in LangChain, and the six places one can sit
2. The difference between a **deterministic** guardrail and a **model-based** one
3. `PIIMiddleware`: the four strategies, and input vs output vs tool results
4. Writing your own deterministic guardrail with `before_agent`
5. Vetoing a single tool call with `wrap_tool_call`

Part 2 covers the expensive half: model-based judgement, human approval, and
assembling all of it into one agent.

### Source

Everything here follows the official page, with the stub examples turned into
things that actually run:
<https://docs.langchain.com/oss/python/langchain/guardrails>
''')

md(r'''
## 0. Setup

Run this once. It reads your `OPENAI_API_KEY` out of the `.env` file at the top of
this folder and prints the library versions, because the API moved around a lot
in LangChain 1.x and it is worth knowing exactly what you are running.
''')

code(r'''
import sys, pathlib

# so `import classroom` works no matter which directory Jupyter was started from
sys.path.insert(0, str(pathlib.Path.cwd()))

import classroom as cr

cr.quiet()
print("env file :", cr.load_env())
print("versions :", cr.versions())
print("worker   :", cr.WORKER_MODEL)
''')

md(r'''
> **One naming difference to know about.**
> The docs page writes `create_agent(model=..., prompt="You are ...")`.
> In the installed version the argument is called **`system_prompt`**.
> Everything else on the page matches. We use `system_prompt` throughout.
''')

md(r'''
## 1. The Northwind agent, with no guardrails at all

Let us build the thing badly first. It is much easier to see why a guardrail
matters once you have watched the unguarded version misbehave.

Three tools, deliberately ordinary:
''')

code(r'''
from langchain.tools import tool

# A stand-in for a claims database. Real one would be a SQL query.
CLAIMS = {
    "CLM-4471": {"status": "duplicate charge under review", "amount": 240.00},
    "CLM-9002": {"status": "paid", "amount": 85.50},
}

# A stand-in for an audit log. We keep it in a list so we can inspect it later,
# which is the whole point: this is what your compliance team would read.
AUDIT_LOG: list[str] = []
SENT_MAIL: list[dict] = []


@tool
def lookup_claim(claim_id: str) -> str:
    """Look up the status of a Northwind Health claim by its claim ID."""
    claim = CLAIMS.get(claim_id)
    if claim is None:
        return f"No claim found with id {claim_id}."
    return f"{claim_id}: {claim['status']}, amount ${claim['amount']:.2f}"


@tool
def save_audit_note(note: str) -> str:
    """Save a short note about this conversation to the compliance audit log."""
    AUDIT_LOG.append(note)
    return "note saved"


@tool
def send_summary_email(to: str, body: str) -> str:
    """E-mail a summary of the conversation to the member."""
    SENT_MAIL.append({"to": to, "body": body})
    return f"summary sent to {to}"
''')

code(r'''
from langchain.agents import create_agent

SUPPORT_PROMPT = (
    "You are the Northwind Health member support agent. "
    "Look up claims when asked. Always call save_audit_note with a one line "
    "summary of what the member told you, quoting their own details so the "
    "compliance team can match records. Keep replies to two sentences."
)

naive_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_claim, save_audit_note, send_summary_email],
    system_prompt=SUPPORT_PROMPT,
)

MEMBER_MESSAGE = (
    "Hi, my name is John Doe, member ID 482-11-9930, my card "
    "5105-1051-0510-5100 was charged twice for claim CLM-4471. "
    "Can you e-mail me at john.doe@gmail.com?"
)

AUDIT_LOG.clear()
SENT_MAIL.clear()

result = naive_agent.invoke({"messages": [{"role": "user", "content": MEMBER_MESSAGE}]})
cr.show_messages(result, "unguarded run")
''')

code(r'''
cr.rule("what ended up in the compliance audit log")
for line in AUDIT_LOG:
    print(" ", line)

cr.rule("what ended up in outbound mail")
for mail in SENT_MAIL:
    print(" to  :", mail["to"])
    print(" body:", mail["body"][:200])
''')

md(r'''
Read that audit log line carefully. The member's card number, their member ID, or
their e-mail address is now sitting in a plain Python list that stands in for a
log file, and it got there because the model was told to quote the member's own
details.

Nobody wrote a bug. The agent did exactly what it was asked. That is the point:
**you cannot fix this with a better prompt**, because a prompt is a request and
not a constraint. You need something outside the model.
''')

md(r'''
## 2. So what is a guardrail?

A guardrail is a piece of **middleware**: code that runs at a fixed point in the
agent's execution and is allowed to look at what is passing through, change it,
or stop the run.

LangChain gives you six such points. Four of them sit inside the model/tool loop
and run on every turn. Two sit outside it and run once per request.

<img src="../images/diagrams/gr_01_hook_map.svg" width="880" alt="The six middleware hook points around an agent turn">

| Hook | Runs | Typical guardrail |
| --- | --- | --- |
| `before_agent` | once, before anything | reject the whole request |
| `before_model` | every turn, before the model call | scrub the prompt |
| `wrap_model_call` | around the model call | retry, fall back, cap tokens |
| `wrap_tool_call` | around each tool call | veto a specific action |
| `after_model` | every turn, after the reply | scrub the reply |
| `after_agent` | once, at the very end | final check on the answer |

The official diagram from the docs page shows the same loop:

<img src="../images/original/middleware_final.png" width="380" alt="Official LangChain middleware flow diagram">

*(source: <https://docs.langchain.com/oss/python/langchain/middleware>)*
''')

md(r'''
## 3. Two flavours of guardrail

Every guardrail you will ever write falls into one of two camps, and the choice
is a straight cost/coverage trade.

<img src="../images/diagrams/gr_02_deterministic_vs_model.svg" width="880" alt="Deterministic versus model-based guardrails">

The practical rule: **run the cheap rule first and only pay for the judge on
what survives it.** Part 1 of this class is entirely deterministic guardrails.
Part 2 adds the judge.
''')

md(r'''
## 4. Built-in guardrail: PII detection

`PIIMiddleware` is the deterministic guardrail you will reach for most often. You
give it a type of personal data, and a strategy for what to do when it sees it.

<img src="../images/diagrams/gr_03_pii_strategies.svg" width="880" alt="The four PII strategies">

Five types are built in: `email`, `credit_card` (Luhn checked, so it will not fire
on any old 16 digits), `ip`, `mac_address`, `url`. Anything else you supply
yourself as a regex or a function via `detector=`.
''')

md(r'''
### 4a. The four strategies, side by side

Here is a small experiment. The same sentence goes through four agents that
differ only in strategy, and we print the **user message as the model finally saw
it**. The middleware rewrites the message in place before the model call, so
printing the transcript shows you exactly what left your machine.
''')

code(r'''
from langchain.agents.middleware import PIIMiddleware
from langchain.agents.middleware import PIIDetectionError  # raised by strategy="block"

SAMPLE = "card 5105-1051-0510-5100 and mail me at ada@northwind.example"

def first_user_message_as_seen(strategy: str) -> str:
    """Run a one-shot agent and return the user message after the middleware ran."""
    probe = create_agent(
        model=cr.WORKER_MODEL,
        tools=[],
        system_prompt="Reply with the single word OK. Nothing else.",
        middleware=[
            PIIMiddleware("credit_card", strategy=strategy, apply_to_input=True),
            PIIMiddleware("email", strategy=strategy, apply_to_input=True),
        ],
    )
    out = probe.invoke({"messages": [{"role": "user", "content": SAMPLE}]})
    return out["messages"][0].text


rows = []
for strategy in ("redact", "mask", "hash"):
    rows.append([strategy, first_user_message_as_seen(strategy)])

# `block` never reaches the model at all, so it needs its own handling.
try:
    first_user_message_as_seen("block")
    rows.append(["block", "(unexpectedly allowed)"])
except PIIDetectionError as err:
    rows.append(["block", f"raised {type(err).__name__}: {err}"])

cr.rule("original")
print(" ", SAMPLE)
print()
cr.table(rows, ["strategy", "what the model received"])
''')

md(r'''
Which one do you want?

- **`redact`** is the default and the right answer most of the time. The model
  still knows *that* there was an e-mail address, which is usually enough for it
  to reason ("I will send this to the address on file").
- **`mask`** when a human further down the line needs to eyeball it. Last four
  digits of a card are the classic case.
- **`hash`** when you need to *join* on the value later without storing it. The
  same input always gives the same hash, so you can group by member without ever
  holding their e-mail.
- **`block`** for things that should never have been typed at all. An API key in a
  chat box is not something to redact politely, it is something to refuse.

Notice `block` raises. That is deliberate: it is the only strategy that is not
recoverable, so it is loud.
''')

md(r'''
### 4b. Custom detectors

Northwind member IDs look like `482-11-9930`. There is no built-in type for that,
so we pass our own regex. The first argument is just a label used in the redaction
placeholder, so pick something readable.
''')

code(r'''
MEMBER_ID_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"

member_id_guard = PIIMiddleware(
    "member_id",
    detector=MEMBER_ID_PATTERN,
    strategy="redact",
    apply_to_input=True,
)

probe = create_agent(
    model=cr.WORKER_MODEL,
    tools=[],
    system_prompt="Repeat the user message back verbatim.",
    middleware=[member_id_guard],
)
out = probe.invoke({"messages": [{"role": "user", "content": "member ID 482-11-9930 please"}]})
print("model saw:", out["messages"][0].text)
''')

md(r'''
### 4c. Input, output, tool results: three separate switches

This is the part people get wrong. A single `PIIMiddleware` guards **one
direction**, and by default it only guards the input.

| Flag | Default | Guards |
| --- | --- | --- |
| `apply_to_input` | `True` | user messages, before the model sees them |
| `apply_to_output` | `False` | the model's own replies |
| `apply_to_tool_results` | `False` | whatever your tools hand back |

Why would a model produce PII if you scrubbed the input? Because it can come from
somewhere else: a tool that reads a database, a retrieved document, or the model
simply repeating something from earlier in the thread. Here is that leak, live.
''')

code(r'''
@tool
def fetch_member_record(member_name: str) -> str:
    """Fetch the stored contact record for a member. Returns internal data."""
    # This is the leak: the data was never typed by the user, it came from a
    # system of record, so an input-only guard never sees it.
    return "name=John Doe, email=john.doe@gmail.com, ip=192.168.4.19"


def run_leak_demo(middleware, label):
    agent = create_agent(
        model=cr.WORKER_MODEL,
        tools=[fetch_member_record],
        system_prompt=(
            "Call fetch_member_record for the member, then state their contact "
            "details back to the user in one line."
        ),
        middleware=middleware,
    )
    out = agent.invoke({"messages": [{"role": "user", "content": "Show me John Doe's record."}]})
    cr.show_messages(out, label)


run_leak_demo(
    [PIIMiddleware("email", strategy="redact", apply_to_input=True)],
    "input guarded only: the tool result and the reply still leak",
)
''')

code(r'''
run_leak_demo(
    [
        PIIMiddleware("email", strategy="redact", apply_to_input=True,
                      apply_to_output=True, apply_to_tool_results=True),
        PIIMiddleware("ip", strategy="redact", apply_to_input=True,
                      apply_to_output=True, apply_to_tool_results=True),
    ],
    "all three directions guarded",
)
''')

md(r'''
Same agent, same tool, same question. The only difference is two extra keyword
arguments, and the address never reaches the transcript.

The lesson to say out loud in class: **guarding the input is the easy half.**
Most real leaks come back out of a tool.
''')

md(r'''
### 4d. Northwind, second attempt

Let us put the PII guards on the original agent and re-run the exact message from
section 1.
''')

code(r'''
pii_guards = [
    PIIMiddleware("credit_card", strategy="mask", apply_to_input=True,
                  apply_to_output=True, apply_to_tool_results=True),
    PIIMiddleware("email", strategy="redact", apply_to_input=True,
                  apply_to_output=True, apply_to_tool_results=True),
    PIIMiddleware("member_id", detector=MEMBER_ID_PATTERN, strategy="redact",
                  apply_to_input=True, apply_to_output=True, apply_to_tool_results=True),
]

guarded_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_claim, save_audit_note, send_summary_email],
    system_prompt=SUPPORT_PROMPT,
    middleware=pii_guards,
)

AUDIT_LOG.clear()
SENT_MAIL.clear()

result = guarded_agent.invoke({"messages": [{"role": "user", "content": MEMBER_MESSAGE}]})
cr.show_messages(result, "guarded run")

cr.rule("compliance audit log now contains")
for line in AUDIT_LOG:
    print(" ", line)
''')

md(r'''
The claim still gets looked up. The member still gets an answer. The audit log no
longer contains a card number.

That is what a good guardrail looks like: the useful work is untouched and only
the dangerous part is gone.
''')

md(r'''
## 5. Writing your own deterministic guardrail

`PIIMiddleware` is one packaged rule. For anything specific to your business you
write your own, and the simplest place to start is `before_agent`, which runs
**once**, before any model call happens.

That "once" matters. A check in `before_agent` costs you nothing per turn and can
end the run before you have spent a single token.

Two syntaxes exist and do the same thing. Use the class when the guardrail has
configuration, use the decorator when it does not.
''')

md(r'''
### 5a. Class syntax
''')

code(r'''
from typing import Any

from langchain.agents.middleware import AgentMiddleware, AgentState, hook_config
from langgraph.runtime import Runtime


class ContentFilterMiddleware(AgentMiddleware):
    """Block a request outright if the first user message contains a banned word.

    This is the crudest guardrail there is, and it is still worth having: it costs
    nothing, it is completely predictable, and it stops the obvious cases before
    you pay for a model call.
    """

    def __init__(self, banned_keywords: list[str], refusal: str | None = None):
        super().__init__()
        self.banned_keywords = [kw.lower() for kw in banned_keywords]
        self.refusal = refusal or (
            "I cannot help with that request. If this is about a claim, "
            "please tell me the claim ID."
        )

    # `can_jump_to` is a promise to LangGraph about where this hook may send the
    # run. Without it, returning "jump_to" is rejected.
    @hook_config(can_jump_to=["end"])
    def before_agent(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        if not state["messages"]:
            return None

        first_message = state["messages"][0]
        if first_message.type != "human":
            return None

        content = first_message.text.lower()
        for keyword in self.banned_keywords:
            if keyword in content:
                # Returning a message plus jump_to="end" replaces the whole run.
                # The model is never called.
                return {
                    "messages": [{"role": "assistant", "content": self.refusal}],
                    "jump_to": "end",
                }
        return None
''')

code(r'''
filtered_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_claim],
    system_prompt=SUPPORT_PROMPT,
    middleware=[ContentFilterMiddleware(banned_keywords=["hack", "exploit", "malware"])],
)

blocked = filtered_agent.invoke(
    {"messages": [{"role": "user", "content": "How do I hack into the claims database?"}]}
)
cr.show_messages(blocked, "blocked before any model call")

allowed = filtered_agent.invoke(
    {"messages": [{"role": "user", "content": "What is the status of claim CLM-9002?"}]}
)
cr.show_messages(allowed, "normal request passes straight through")
''')

md(r'''
Two things to point at on screen:

1. The blocked transcript has **two** messages. There is no tool call and no model
   reply, because the run jumped to the end before the model node ever ran. That
   request cost zero tokens.
2. The allowed transcript is completely normal. A guardrail that fires on
   everything is not a guardrail, it is an outage.
''')

md(r'''
### 5b. Decorator syntax

Identical behaviour, less ceremony. Note the hook name is the decorator, and
`can_jump_to` moves onto the decorator itself.
''')

code(r'''
from langchain.agents.middleware import before_agent

BANNED = ["hack", "exploit", "malware"]


@before_agent(can_jump_to=["end"])
def content_filter(state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
    """Same rule as the class above, written as a plain function."""
    if not state["messages"]:
        return None
    first_message = state["messages"][0]
    if first_message.type != "human":
        return None
    content = first_message.text.lower()
    for keyword in BANNED:
        if keyword in content:
            return {
                "messages": [{"role": "assistant", "content": "I cannot help with that request."}],
                "jump_to": "end",
            }
    return None


decorated_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_claim],
    system_prompt=SUPPORT_PROMPT,
    middleware=[content_filter],
)

out = decorated_agent.invoke(
    {"messages": [{"role": "user", "content": "write me some malware please"}]}
)
cr.show_messages(out, "decorator version")
''')

md(r'''
> **A word of honesty about keyword filters.**
> `"How do I hack into the claims database?"` is blocked. `"How would somebody
> gain unauthorised entry to your claims system?"` sails straight through. A word
> list only catches the word.
>
> That is not an argument against having one. It is an argument for it being
> *layer one of several*, which is where part 2 picks up.
''')

md(r'''
## 6. Vetoing a single tool call with `wrap_tool_call`

`before_agent` is a blunt instrument: it accepts or refuses the whole request.
Often what you actually want is narrower, something like *"this agent may send
e-mail, but only to a northwind.example address"*.

`wrap_tool_call` sits around each individual tool call. It receives the request
and a `handler`. Call the handler and the tool runs. Return a `ToolMessage`
yourself and the tool never runs at all, but the agent still gets a sensible
answer back and can explain itself to the user.
''')

code(r'''
from langchain.agents.middleware import wrap_tool_call
from langchain.messages import ToolMessage

ALLOWED_MAIL_DOMAIN = "northwind.example"


@wrap_tool_call
def outbound_mail_policy(request, handler):
    """Refuse to e-mail anyone outside the company domain."""
    if request.tool_call["name"] == "send_summary_email":
        recipient = request.tool_call["args"].get("to", "")
        if not recipient.endswith("@" + ALLOWED_MAIL_DOMAIN):
            # The tool is never executed. We fabricate its result instead.
            return ToolMessage(
                content=(
                    f"BLOCKED by policy: this agent may only e-mail "
                    f"@{ALLOWED_MAIL_DOMAIN} addresses. Tell the user to use the "
                    f"member portal instead."
                ),
                tool_call_id=request.tool_call["id"],
            )
    return handler(request)


policed_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_claim, send_summary_email],
    system_prompt=SUPPORT_PROMPT,
    middleware=[outbound_mail_policy],
)

SENT_MAIL.clear()
out = policed_agent.invoke(
    {"messages": [{"role": "user", "content":
                   "E-mail a summary of claim CLM-9002 to me at john.doe@gmail.com"}]}
)
cr.show_messages(out, "external address: refused")
print("mail actually sent:", SENT_MAIL)
''')

code(r'''
SENT_MAIL.clear()
out = policed_agent.invoke(
    {"messages": [{"role": "user", "content":
                   "E-mail a summary of claim CLM-9002 to nurse@northwind.example"}]}
)
cr.show_messages(out, "internal address: allowed")
print("mail actually sent:", SENT_MAIL)
''')

md(r'''
Note what happened in the refused case. The agent did not crash and did not go
silent. It read the blocked tool result, understood it, and explained the policy
to the member in its own words. That is why returning a `ToolMessage` is better
than raising: the model gets to recover.

`wrap_tool_call` is where most real production guardrails live, because most real
damage is done by a tool and not by a sentence.
''')

md(r'''
## 7. Where we got to

Starting from an agent that dumped a card number into the audit log, we added
three deterministic layers, and none of them called a model:

| Layer | Hook | What it stops |
| --- | --- | --- |
| Content filter | `before_agent` | obviously bad requests, before spending a token |
| PII scrubbing | `before_model` / `after_model` / tool results | personal data in either direction |
| Tool policy | `wrap_tool_call` | a specific dangerous action |

All three are fast, free, and completely predictable. They are also all blind to
meaning: none of them would notice a politely worded request for something
harmful, or a confidently worded wrong answer.

**Part 2** adds the two guardrails that can: a model that judges the output, and
a human who approves the action.

---

### Exercises

1. Add a `PIIMiddleware` for `url` with `strategy="block"` and find a message that
   trips it. Why might blocking URLs be reasonable for a support agent?
2. `ContentFilterMiddleware` only inspects `state["messages"][0]`. Write a version
   that inspects the most recent user message instead, and explain when each is
   the right choice.
3. Extend `outbound_mail_policy` so that instead of a flat refusal it strips
   attachments over a size limit and lets the call through. This is the "modify,
   do not veto" shape of `wrap_tool_call`.
4. Time it. Wrap one guarded and one unguarded invocation in `time.perf_counter()`
   and measure the cost of the deterministic layers. It should be close to zero.

### Reference

- Guardrails: <https://docs.langchain.com/oss/python/langchain/guardrails>
- Middleware: <https://docs.langchain.com/oss/python/langchain/middleware>
- Middleware API: <https://reference.langchain.com/python/langchain/middleware/>
''')

build(C, os.path.join(os.path.dirname(__file__), "..", "notebooks",
                      "01_guardrails_stopping_bad_input.ipynb"))
