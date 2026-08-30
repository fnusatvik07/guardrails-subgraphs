import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from nbbuild import build

C = []
md = lambda s: C.append(("md", s))
code = lambda s: C.append(("code", s))

md(r'''
# Guardrails, part 3: redacted for the model, real for the tool

This answers a question that comes up every time guardrails are taught:

> "I do not want to send my ID card or my SSN to the model. But I still want the
> agent to look my details up. The tool needs the real number. How does that
> work?"

It is a fair question, and the honest answer is that **`PIIMiddleware` on its own
cannot do it.** Redact, mask and hash are all one way by design. Once the model
sees `[REDACTED_SSN]`, nothing can turn that back into a number, and your lookup
tool receives a useless string.

This notebook builds the thing that does work, and then shows two simpler options
you should check for first.

### What you will learn

1. Why a plain redaction guardrail breaks a lookup, demonstrated
2. **Tokenise and rehydrate**: a placeholder for the model, the real value for the tool
3. An **allow list**, so only the tools that need a value can ever get it
4. What happens when the model invents a placeholder
5. The uncomfortable detail: your own checkpointer sees more than the model does
6. Two approaches that avoid the whole problem: session identity, and out of band collection

Same company as parts 1 and 2: **Northwind Health**.

### Source

The middleware hooks used here are all on
<https://docs.langchain.com/oss/python/langchain/guardrails>
and <https://docs.langchain.com/oss/python/langchain/middleware>.
The tokenise-and-rehydrate pattern itself is not in the docs. It is assembled from
`before_model` and `wrap_tool_call`.
''')

md(r'''
## 0. Setup
''')

code(r'''
import sys, pathlib, re, json

sys.path.insert(0, str(pathlib.Path.cwd()))
import classroom as cr

cr.quiet()
print("env file :", cr.load_env())
print("versions :", cr.versions())
''')

code(r'''
from langchain.agents import create_agent
from langchain.tools import tool

# A stand-in for the member database. The key is the SSN, which is exactly the
# situation that makes this awkward: the lookup key IS the sensitive value.
MEMBERS = {
    "482-11-9930": {"name": "John Doe", "plan": "Gold PPO", "deductible_left": 320.00},
    "119-40-2277": {"name": "Ada Reyes", "plan": "Silver HMO", "deductible_left": 0.00},
}

# What each tool actually received, so we can check it rather than trust it.
TOOL_SAW: list[tuple[str, str]] = []
SENT_MAIL: list[dict] = []


@tool
def lookup_member_by_ssn(ssn: str) -> str:
    """Look up a Northwind Health member record by their SSN."""
    TOOL_SAW.append(("lookup_member_by_ssn", ssn))
    record = MEMBERS.get(ssn)
    if record is None:
        return f"No member found for {ssn}."
    return (f"{record['name']}, plan {record['plan']}, "
            f"deductible remaining ${record['deductible_left']:.2f}")


@tool
def send_summary_email(to: str, body: str) -> str:
    """E-mail a summary to the member."""
    TOOL_SAW.append(("send_summary_email", body))
    SENT_MAIL.append({"to": to, "body": body})
    return f"summary sent to {to}"


SSN_PATTERN = r"\b\d{3}-\d{2}-\d{4}\b"
MEMBER_ASKS = "Look up my details please, my SSN is 482-11-9930."

print("tools ready")
''')

md(r'''
## 1. Watch the obvious approach break

Part 1 taught `PIIMiddleware`. So let us try it: redact the SSN on the way in, and
see what the lookup tool receives.
''')

code(r'''
from langchain.agents.middleware import PIIMiddleware

redacting_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_member_by_ssn],
    system_prompt="You are Northwind Health support. Use the lookup tool when given an SSN.",
    middleware=[
        PIIMiddleware("ssn", detector=SSN_PATTERN, strategy="redact", apply_to_input=True),
    ],
)

TOOL_SAW.clear()
result = redacting_agent.invoke({"messages": [{"role": "user", "content": MEMBER_ASKS}]})
cr.show_messages(result, "redact: the SSN is safe, and the lookup is broken")

print("what the tool actually received:", TOOL_SAW)
''')

md(r'''
Look at the last line. The tool was handed the literal string `[REDACTED_SSN]`,
found nothing, and the agent then politely asked the member to **send their SSN
again**. We have achieved the worst of both worlds: the feature does not work,
and we have taught the member to keep typing their SSN into a chat box.

### Would a different strategy help?

No, and it is worth being precise about why.

| Strategy | What the tool gets | Can you get the number back? |
| --- | --- | --- |
| `redact` | `[REDACTED_SSN]` | no, every SSN maps to the same string |
| `mask` | `***-**-9930` | no, the first five digits are gone |
| `hash` | `<ssn_hash:a8f5f167>` | no, that is the point of a hash |
| `block` | nothing, it raises | no, the run never happens |

All four are **one way on purpose**. That is a feature when you are protecting a
log, and a wall when a tool downstream needs the real value.

What we need is something none of them offer: a placeholder that we can undo, but
only in one specific place.
''')

md(r'''
## 2. Three ways out

Before building anything, know the options, because the best answer is often the
one that involves no cryptography at all.

<img src="../images/diagrams/gr_07_three_approaches.svg" width="900" alt="Three ways to keep a value away from the model">

Sections 3 to 8 build option 2, because it is the general one and it is what the
question is actually asking for. Sections 9 and 10 show options 1 and 3, which are
simpler when they apply.
''')

md(r'''
## 3. The idea: tokenise and rehydrate

<img src="../images/diagrams/gr_06_tokenise_and_rehydrate.svg" width="920" alt="Tokenise for the model, rehydrate for the tool">

Read the picture as a round trip:

1. **On the way in**, a middleware finds `482-11-9930` and replaces it with
   `<ssn_1>`. The real value goes into a **vault** that lives in your process.
2. **The model** sees `<ssn_1>`. It can reason about it, refer to it, and decide
   which tool it belongs to. It cannot read it, because there is nothing to read.
3. **On the way to the tool**, a second middleware looks at the tool call
   arguments, finds `<ssn_1>`, checks whether *this* tool is allowed to see *this
   kind* of value, and if so swaps the real number back in.
4. **On the way back**, anything sensitive in the tool result is tokenised again
   before the model sees it.

The key property is in step 3: the value is revealed **once, to one tool, at the
last possible moment**, and never in a message.
''')

md(r'''
## 4. Build the vault

The vault is the only place the real values exist. Three things matter about its
design:

- **Stable tokens.** The same value must always get the same token inside one
  conversation, or the model cannot refer back to it.
- **Scoped by thread.** One member's `<ssn_1>` must never be another member's.
- **An audit trail.** Every reveal is a disclosure, so write down who asked.
''')

code(r'''
from typing import Any

from langgraph.config import get_config

# What a placeholder looks like: <kind_number>
TOKEN_PATTERN = re.compile(r"<([a-z][a-z0-9]*)_(\d+)>")


class Vault:
    """Holds the real values. Nothing else in the system does."""

    def __init__(self) -> None:
        self._threads: dict[str, dict[str, Any]] = {}
        self.audit: list[dict[str, str]] = []

    def _store(self, thread_id: str | None = None) -> dict[str, Any]:
        """One bucket per conversation, so tokens never leak across members."""
        if thread_id is None:
            try:
                thread_id = get_config()["configurable"].get("thread_id", "default")
            except Exception:
                # get_config() only works inside a running graph
                thread_id = "default"
        return self._threads.setdefault(
            thread_id, {"to_real": {}, "to_token": {}, "counts": {}}
        )

    def tokenize(self, kind: str, value: str, thread_id: str | None = None) -> str:
        """Turn a real value into a placeholder. Same value, same placeholder."""
        store = self._store(thread_id)
        if value in store["to_token"]:
            return store["to_token"][value]
        store["counts"][kind] = store["counts"].get(kind, 0) + 1
        token = f"<{kind}_{store['counts'][kind]}>"
        store["to_real"][token] = value
        store["to_token"][value] = token
        return token

    def resolve(self, token: str, *, requested_by: str,
                thread_id: str | None = None) -> str | None:
        """Turn a placeholder back into a real value, and record that we did."""
        real = self._store(thread_id)["to_real"].get(token)
        self.audit.append({
            "token": token,
            "requested_by": requested_by,
            "result": "released" if real is not None else "unknown token",
        })
        return real

    def contents(self, thread_id: str) -> dict[str, str]:
        return dict(self._store(thread_id)["to_real"])

    def restore(self, text: str, thread_id: str) -> str:
        """Put every real value back. Only ever call this at the very edge."""
        for token, real in self.contents(thread_id).items():
            text = text.replace(token, real)
        return text


def tokenize_text(text: str, rules: dict[str, re.Pattern], vault: Vault,
                  thread_id: str | None = None) -> tuple[str, bool]:
    """Replace every match of every rule with a placeholder."""
    changed = False
    for kind, pattern in rules.items():
        def replace(match, kind=kind):
            nonlocal changed
            changed = True
            return vault.tokenize(kind, match.group(0), thread_id)
        text = pattern.sub(replace, text)
    return text, changed


# quick check, no agent involved
demo_vault = Vault()
RULES = {"ssn": re.compile(SSN_PATTERN)}
text, _ = tokenize_text("mine is 482-11-9930 and hers is 119-40-2277, mine again 482-11-9930",
                        RULES, demo_vault, thread_id="demo")
print(text)
print(demo_vault.contents("demo"))
''')

md(r'''
Note the third mention of `482-11-9930` came back as `<ssn_1>` again, not
`<ssn_3>`. Stability matters: if the same value produced a new token every time,
the model would think it was dealing with three different people.
''')

md(r'''
## 5. Build the middleware

Now the two halves. One middleware class carries both, because they share the
vault and the rules.

- `before_model` tokenises what the model is about to see
- `after_model` catches anything the model somehow produced in the clear
- `wrap_tool_call` is where the real value is put back, for allowed tools only
''')

code(r'''
from langchain.agents.middleware import AgentMiddleware, AgentState
from langchain.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.runtime import Runtime


class TokenVaultMiddleware(AgentMiddleware):
    r"""Placeholders for the model, real values for the tools that are allowed them.

    Args:
        rules: pii kind -> regex, e.g. {"ssn": r"\d{3}-\d{2}-\d{4}"}
        vault: where the real values live
        detokenize_for: tool name -> the set of kinds that tool may receive in the
            clear. A tool missing from this mapping gets placeholders and nothing else.
    """

    def __init__(self, rules: dict[str, str], vault: Vault,
                 detokenize_for: dict[str, set[str]]):
        super().__init__()
        self.rules = {kind: re.compile(pattern) for kind, pattern in rules.items()}
        self.vault = vault
        self.detokenize_for = detokenize_for

    # ---------------------------------------------------------------- inbound
    def _swap_in_messages(self, messages, kinds):
        """Rewrite matching messages in place, keeping their ids so state updates."""
        new = list(messages)
        modified = False
        for i, message in enumerate(new):
            if not isinstance(message, kinds) or not isinstance(message.content, str):
                continue
            text, changed = tokenize_text(message.content, self.rules, self.vault)
            if changed:
                new[i] = message.model_copy(update={"content": text})
                modified = True
        return new, modified

    def before_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Nothing sensitive reaches the model: not the member's words, not tool output."""
        messages, modified = self._swap_in_messages(
            state["messages"], (HumanMessage, ToolMessage)
        )
        return {"messages": messages} if modified else None

    def after_model(self, state: AgentState, runtime: Runtime) -> dict[str, Any] | None:
        """Belt and braces: if the model ever emits a raw value, tokenise that too."""
        messages, modified = self._swap_in_messages(state["messages"], (AIMessage,))
        return {"messages": messages} if modified else None

    # --------------------------------------------------------------- outbound
    def _rehydrate(self, value, allowed, tool_name, report):
        """Walk the tool arguments, at any nesting depth, swapping allowed tokens."""
        if isinstance(value, dict):
            return {k: self._rehydrate(v, allowed, tool_name, report)
                    for k, v in value.items()}
        if isinstance(value, list):
            return [self._rehydrate(v, allowed, tool_name, report) for v in value]
        if not isinstance(value, str):
            return value

        for match in TOKEN_PATTERN.finditer(value):
            token, kind = match.group(0), match.group(1)
            if kind not in allowed:
                # This tool is not entitled to this kind of value. Leave the
                # placeholder in: the tool call still happens, just without the secret.
                report.setdefault("withheld", []).append(token)
                continue
            real = self.vault.resolve(token, requested_by=tool_name)
            if real is None:
                report.setdefault("unknown", []).append(token)
                continue
            value = value.replace(token, real)
            report.setdefault("released", []).append(token)
        return value

    def wrap_tool_call(self, request, handler):
        tool_name = request.tool_call["name"]
        allowed = self.detokenize_for.get(tool_name, set())
        report: dict[str, list[str]] = {}

        args = self._rehydrate(request.tool_call["args"], allowed, tool_name, report)

        # A placeholder we never issued means the model made one up. Do not run
        # the tool with a guess; say so and let the model recover.
        if report.get("unknown"):
            return ToolMessage(
                content=(f"Rejected: {', '.join(report['unknown'])} is not a placeholder "
                         f"this conversation issued. Ask the member for the value again; "
                         f"do not guess it."),
                tool_call_id=request.tool_call["id"],
                status="error",
            )

        if report.get("released"):
            request = request.override(tool_call={**request.tool_call, "args": args})

        result = handler(request)

        # And tokenise whatever the tool handed back, before the model sees it.
        if isinstance(result, ToolMessage) and isinstance(result.content, str):
            text, changed = tokenize_text(result.content, self.rules, self.vault)
            if changed:
                result = result.model_copy(update={"content": text})
        return result


print("middleware defined")
''')

md(r'''
## 6. Run it

One more detail before we do. The model has to be told what these placeholders
are, or it will try to be helpful and invent a plausible SSN. One sentence in the
system prompt is enough.
''')

code(r'''
from langgraph.checkpoint.memory import InMemorySaver

VAULT_PROMPT = (
    "You are Northwind Health member support. "
    "Text like <ssn_1> is a secure placeholder for a value you are not allowed to "
    "see. Pass placeholders to tools exactly as written, character for character. "
    "Never invent a placeholder and never guess the value behind one. "
    "When you report a result, say which placeholder it was for."
)

vault = Vault()
checkpointer = InMemorySaver()

vault_middleware = TokenVaultMiddleware(
    rules={"ssn": SSN_PATTERN},
    vault=vault,
    detokenize_for={
        "lookup_member_by_ssn": {"ssn"},     # this tool needs the real number
        # send_summary_email is deliberately absent: it gets placeholders only
    },
)

vault_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_member_by_ssn, send_summary_email],
    system_prompt=VAULT_PROMPT,
    middleware=[vault_middleware],
    checkpointer=checkpointer,
)

TOOL_SAW.clear()
config = {"configurable": {"thread_id": "member-1"}}
result = vault_agent.invoke({"messages": [{"role": "user", "content": MEMBER_ASKS}]}, config)

cr.show_messages(result, "the lookup works, and the model never saw the number")
''')

code(r'''
cr.rule("what the tool received")
for name, value in TOOL_SAW:
    print(f"  {name}  ->  {value!r}")

cr.rule("what is in the vault")
print(" ", vault.contents("member-1"))

cr.rule("the disclosure log")
for entry in vault.audit:
    print(" ", entry)
''')

md(r'''
That is the whole answer to the question. The member typed a real SSN, the tool
received a real SSN, and the model in between only ever handled `<ssn_1>`.

### Prove it rather than believe it

A guardrail you have not checked is a guardrail you do not have. Search every
message for the raw value.
''')

code(r'''
RAW = "482-11-9930"

messages = vault_agent.get_state(config).values["messages"]
leaks = [(type(m).__name__, m.text) for m in messages if RAW in (m.text or "")]

cr.rule("scan of the conversation")
print("  messages checked  :", len(messages))
print("  containing the SSN:", len(leaks))
for kind, text in leaks:
    print("   !!", kind, text[:80])

# Tool call arguments are not message text, so check those separately.
tool_call_leaks = [
    call for m in messages for call in (getattr(m, "tool_calls", None) or [])
    if RAW in json.dumps(call["args"])
]
print("  tool call args containing the SSN:", len(tool_call_leaks))
''')

md(r'''
## 7. The allow list is the part that does the work

Tokenising is only half of it. The interesting half is deciding **which tool may
un-tokenise what**.

`lookup_member_by_ssn` genuinely needs the number. `send_summary_email` does not,
and an e-mail is exactly the sort of place a value escapes to. So the e-mail tool
is simply absent from `detokenize_for`, and it gets placeholders.

### First, the mechanism on its own

Before involving a model, put the *identical* tool call through the middleware
twice, once under each tool name, and see what comes out. No model, no randomness,
same answer every time you run it in class.
''')

code(r'''
from langchain.agents.middleware.types import ToolCallRequest

bench_vault = Vault()
bench_middleware = TokenVaultMiddleware(
    rules={"ssn": SSN_PATTERN},
    vault=bench_vault,
    detokenize_for={"lookup_member_by_ssn": {"ssn"}},
)
bench_token = bench_vault.tokenize("ssn", "482-11-9930")


def what_the_tool_gets(tool_name: str):
    """Push one tool call through the middleware and record both directions."""
    seen = {}

    def stub_tool(request):
        seen["received"] = request.tool_call["args"]["text"]
        return ToolMessage(content=f"record for {request.tool_call['args']['text']}",
                           tool_call_id="call_bench")

    request = ToolCallRequest(
        tool_call={"name": tool_name,
                   "args": {"text": f"member {bench_token}"},
                   "id": "call_bench", "type": "tool_call"},
        tool=None, state=None, runtime=None,
    )
    returned = bench_middleware.wrap_tool_call(request, stub_tool)
    return seen["received"], returned.content


rows = []
for tool_name in ("lookup_member_by_ssn", "send_summary_email"):
    received, returned = what_the_tool_gets(tool_name)
    on_list = "yes" if tool_name in bench_middleware.detokenize_for else "no"
    rows.append([tool_name, on_list, received, returned])

print("the model's tool call carried:", f"member {bench_token}")
print()
cr.table(rows, ["tool", "on the allow list", "what the tool receives",
                "what returns to the model"])
''')

md(r'''
Two things happened in that table, and both matter.

**Going out.** The same placeholder became `482-11-9930` for the tool on the allow
list, and stayed `<ssn_1>` for the tool that is not on it. The tool name is the
only thing that differed.

**Coming back.** The lookup tool's *result* quoted the real number, and the
middleware tokenised it again on the way back, so `<ssn_1>` is what returns to the
model. The value went out to one tool and did not come back into the conversation.

### Now the same thing with a real model

Ask the agent to do exactly the wrong thing and see how far it gets.
''')

code(r'''
TOOL_SAW.clear()
SENT_MAIL.clear()
config_2 = {"configurable": {"thread_id": "member-2"}}

result = vault_agent.invoke(
    {"messages": [{"role": "user", "content":
        "My SSN is 482-11-9930. Look me up, then e-mail a confirmation to "
        "john.doe@example.com that quotes my SSN in the body so I can check it."}]},
    config_2,
)
cr.show_messages(result, "the model tries to put the SSN in an e-mail")

cr.rule("what each tool actually received")
for name, value in TOOL_SAW:
    print(f"  {name}")
    print(f"      {value!r}")
''')

md(r'''
What the model does here varies between runs, and both outcomes make the point.

**Often it simply refuses**, as in the run saved above: it declines to put an SSN
in an e-mail and offers to send something harmless instead. Good behaviour, and
worth nothing as a guarantee, because it is a decision the model made and could
make differently tomorrow.

**Sometimes it complies** and calls `send_summary_email` with the placeholder in
the body. Check `TOOL_SAW` above: if the e-mail tool ran, look at what it was
handed. It is `<ssn_1>`, not the number.

That is the difference between a policy and a guarantee:

| | Depends on | Holds when |
| --- | --- | --- |
| "never put SSNs in e-mails" in the prompt | the model agreeing | usually |
| the value not being in the model's context | nothing | always |

The model could not leak the number because it never had it. Notice that the
refusal and the guarantee are independent: you want both, and only one of them is
something you can promise a compliance officer.
''')

md(r'''
## 8. When the model makes a placeholder up

Models produce plausible text. Sooner or later one will emit `<ssn_7>` because it
looked like the right shape. If we silently passed that through, the tool would do
a lookup on a string the member never provided.

The middleware rejects it and tells the model why, so it can recover instead of
failing silently.
''')

code(r'''
TOOL_SAW.clear()
config_3 = {"configurable": {"thread_id": "member-3"}}

result = vault_agent.invoke(
    {"messages": [{"role": "user", "content": "Look up member <ssn_7> for me."}]},
    config_3,
)
cr.show_messages(result, "a placeholder this conversation never issued")

print("tools that actually ran:", TOOL_SAW)
cr.rule("the disclosure log now shows the refusal")
for entry in vault.audit[-2:]:
    print(" ", entry)
''')

md(r'''
The tool never ran, the refusal is in the audit log, and the model explained the
problem to the member in its own words. Compare that with the redaction demo in
section 1, where the failure was silent and the recovery advice was "please send
your SSN again".
''')

md(r'''
## 9. Two details that matter in production

### 9a. Your checkpointer sees more than the model does

Here is the part that is easy to miss, and it is worth showing rather than
describing.

`before_model` runs **inside** the graph. By the time it runs, LangGraph has
already written the incoming state to the checkpointer, raw SSN and all. The
model never saw it. Your own database did.
''')

code(r'''
def checkpoints_containing(checkpointer, config, needle: str) -> tuple[int, int]:
    saved = list(checkpointer.list(config))
    hits = sum(1 for c in saved if needle in json.dumps(c.checkpoint, default=str))
    return hits, len(saved)

hits, total = checkpoints_containing(checkpointer, config, RAW)
print(f"checkpoints on thread 'member-1' containing the raw SSN: {hits} of {total}")
''')

md(r'''
Whether that matters depends on who can read your checkpoint store. Often it is
fine: it is your own database, inside your own boundary, and the point of the
exercise was to keep the number away from the model provider.

When it is not fine, the fix is to **tokenise before the graph is ever called**,
in whatever handles the inbound request. The graph then never receives the real
value at all.
''')

code(r'''
edge_vault = Vault()
edge_checkpointer = InMemorySaver()
edge_rules = {"ssn": re.compile(SSN_PATTERN)}

edge_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_member_by_ssn],
    system_prompt=VAULT_PROMPT,
    middleware=[TokenVaultMiddleware({"ssn": SSN_PATTERN}, edge_vault,
                                     {"lookup_member_by_ssn": {"ssn"}})],
    checkpointer=edge_checkpointer,
)

edge_config = {"configurable": {"thread_id": "edge-1"}}

# This is the important line: tokenise in your request handler, not in the graph.
safe_text, _ = tokenize_text(MEMBER_ASKS, edge_rules, edge_vault, thread_id="edge-1")
print("what the member typed  :", MEMBER_ASKS)
print("what enters the graph  :", safe_text)
print()

TOOL_SAW.clear()
result = edge_agent.invoke({"messages": [{"role": "user", "content": safe_text}]}, edge_config)

hits, total = checkpoints_containing(edge_checkpointer, edge_config, RAW)
print("tool still received    :", TOOL_SAW)
print(f"checkpoints with the raw SSN: {hits} of {total}")
print("answer:", result["messages"][-1].text.replace("\n", " ")[:110])
''')

md(r'''
Zero. Same behaviour, same working lookup, and the real number now exists in
exactly one place: the vault.

Keep the middleware anyway. It is your second line of defence for values that
arrive from somewhere other than the front door, such as a tool result or a
retrieved document.

### 9b. Putting the value back for the member

The member owns their own SSN, so it is reasonable to show it back to them, even
though the model was never allowed to see it. Do that at the very last moment, on
the way out to that one person, and never feed the restored text back into the
model.
''')

code(r'''
model_answer = "I looked up the record for <ssn_1> and found your Gold PPO plan."
member_sees = vault.restore(model_answer, "member-1")

cr.rule("the same sentence, at two different points")
print("  as the model wrote it :", model_answer)
print("  as the member sees it :", member_sees)
''')

md(r'''
Worth saying out loud: this step is a **disclosure**, so it belongs behind the
same authorisation check as any other. Restore for the member who owns the value.
Do not restore into a log, a support console, or a transcript that someone else
will read.
''')

md(r'''
## 10. Option 1: do not put it in the chat at all

Now the approach you should try before any of the above.

Most of the time the sensitive value is **the identity of the person you are
already talking to**. They logged in. You already know who they are. So the agent
does not need an SSN argument at all: the tool can read identity from the session.

Nothing to tokenise, nothing to rehydrate, nothing to leak.
''')

code(r'''
from dataclasses import dataclass

from langchain.tools import ToolRuntime


@dataclass
class Session:
    """Set by your authentication layer, never by the conversation."""
    ssn: str
    member_name: str


@tool
def lookup_my_record(runtime: ToolRuntime[Session]) -> str:
    """Look up the signed-in member's own record. Takes no arguments."""
    ssn = runtime.context.ssn          # from the session, not from the message
    TOOL_SAW.append(("lookup_my_record", ssn))
    record = MEMBERS.get(ssn)
    if record is None:
        return "No record found for the signed-in member."
    return (f"{record['name']}, plan {record['plan']}, "
            f"deductible remaining ${record['deductible_left']:.2f}")


session_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_my_record],
    system_prompt=(
        "You are Northwind Health support. The member is already signed in, so use "
        "lookup_my_record. Never ask a member for their SSN."
    ),
    context_schema=Session,
)

TOOL_SAW.clear()
result = session_agent.invoke(
    {"messages": [{"role": "user", "content": "What plan am I on, and what is left on my deductible?"}]},
    context=Session(ssn="482-11-9930", member_name="John Doe"),
)
cr.show_messages(result, "no SSN anywhere in the conversation")
print("tool resolved identity from the session:", TOOL_SAW)
''')

md(r'''
Notice the tool call arguments: `{}`. There is nothing to redact because there is
nothing to send. The member did not type an SSN, so no guardrail had to catch one.

**This is the answer whenever the value identifies the person you are talking to.**
Tokenisation is what you fall back to when the value is something else: a
*different* member's ID that a caseworker is looking up, a policy number read off
a letter, a claim reference from an e-mail.
''')

md(r'''
## 11. Option 3: let the tool collect it out of band

The third option, for when the value must never be typed into a chat box at all.

The tool pauses with `interrupt()` and asks your application to collect the value
through a proper secure form. Your application resumes the run with the value, and
it goes **straight into the tool**. It never becomes a message, so there is nothing
for the model to see and nothing for a guardrail to scrub.

This is the human-in-the-loop machinery from part 2, pointed at data entry instead
of approval.
''')

code(r'''
from langgraph.types import Command, interrupt


@tool
def lookup_via_secure_form(reason: str) -> str:
    """Look up a member. Collects their SSN through the secure form, not the chat."""
    ssn = interrupt({"secure_field": "ssn", "reason": reason})
    TOOL_SAW.append(("lookup_via_secure_form", ssn))
    record = MEMBERS.get(ssn)
    if record is None:
        return "No member found."
    return f"{record['name']}, plan {record['plan']}"


secure_agent = create_agent(
    model=cr.WORKER_MODEL,
    tools=[lookup_via_secure_form],
    system_prompt=(
        "You are Northwind Health support. Never ask a member to type an SSN into "
        "the chat. Call lookup_via_secure_form and it will collect it securely."
    ),
    checkpointer=InMemorySaver(),
)

TOOL_SAW.clear()
secure_config = {"configurable": {"thread_id": "secure-1"}}

paused = secure_agent.invoke(
    {"messages": [{"role": "user", "content": "What plan am I on?"}]}, secure_config
)
cr.rule("the run pauses and asks your application for a field")
print(" ", paused["__interrupt__"][0].value)

# Your web app shows a proper form, collects the value, and resumes.
# The value goes into the tool. It is never a message.
done = secure_agent.invoke(Command(resume="482-11-9930"), secure_config)
cr.show_messages(done, "resumed")

print("tool received out of band :", TOOL_SAW)
print("SSN present in any message:",
      any(RAW in (m.text or "") for m in done["messages"]))
''')

md(r'''
The transcript contains no SSN at any point, because one was never typed there.
The cost is a round trip through another screen, which is a real cost to a member
in a hurry, and the reason this is not the default answer.
''')

md(r'''
## 12. Choosing, and a hardening checklist

### Which one

| Situation | Use |
| --- | --- |
| The value identifies the signed-in member | **session identity** (section 10) |
| The value arrives in the conversation and a tool needs it | **tokenise and rehydrate** (sections 3 to 9) |
| The value must never be typed into a chat box | **out of band collection** (section 11) |
| Nothing downstream needs the real value | plain `PIIMiddleware`, from part 1 |

### If you ship the tokenising version

- **Tokenise at the edge**, not only in middleware, if your own storage is in
  scope. Keep the middleware too, for values that arrive from tools.
- **Keep the allow list small.** Every tool on it is a place the value can leave.
  A tool that only formats or e-mails should never be on it.
- **Scope the vault by thread and give it a TTL.** A vault that never forgets
  becomes the database you were trying not to build.
- **Audit every resolve.** You now have a system that deliberately reveals
  sensitive data. That is fine, and it needs a log.
- **Reject unknown placeholders loudly.** Never let a made up token reach a tool.
- **Check your streaming path.** If you stream tokens to a browser, the
  placeholders are what should arrive there, not the real values.
- **Test the leak, not the feature.** The useful test is section 7: ask the agent
  to put the value somewhere it should not go, and assert that it could not.

### What to remember

1. Redaction is one way on purpose. If a tool needs the value back, redaction is
   the wrong tool.
2. A placeholder plus a vault lets the model **route** a value it cannot **read**.
3. The allow list, not the tokenising, is what actually contains the blast radius.
4. Ask first whether the value needs to be in the conversation at all. Very often
   it does not.

---

### Exercises

1. Add a second rule for `member_id` with a different pattern, and give
   `send_summary_email` permission to see member IDs but still not SSNs. Confirm
   with a single request that both rules hold at once.
2. Make `lookup_member_by_ssn` return a record that itself contains an SSN. Show
   that the tool result is tokenised before the model sees it, and work out which
   line of the middleware does that.
3. Turn section 7 into a test, in the shape used at the end of part 2: a table of
   requests and the tool arguments you expect, asserting the SSN never appears
   outside the allow list.
4. Give the vault a TTL and a maximum size. What should happen when the model
   refers to a placeholder that has expired?
5. Argue the other side: for a support agent where the member is always signed in,
   is any of section 3 to 9 needed at all?

### Reference

- Guardrails: <https://docs.langchain.com/oss/python/langchain/guardrails>
- Middleware: <https://docs.langchain.com/oss/python/langchain/middleware>
- Human in the loop: <https://docs.langchain.com/oss/python/langchain/human-in-the-loop>
- Tools and `ToolRuntime`: <https://docs.langchain.com/oss/python/langchain/tools>
''')

build(C, os.path.join(os.path.dirname(__file__), "..", "notebooks",
                      "05_guardrails_redact_but_still_look_up.ipynb"))
