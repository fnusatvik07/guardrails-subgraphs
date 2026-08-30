# Mermaid source for the structural diagrams

Paste any of these into a slide tool, or import into draw.io with
**File > Import from > Mermaid**. They are simplified versions of the SVGs in
this folder, kept editable.

---

## Where a guardrail can stand

```mermaid
flowchart LR
    IN([request]) --> BA[before_agent<br/>once, at the start]
    subgraph LOOP [model / tool loop, repeats]
        direction LR
        BM[before_model<br/>edit the prompt] --> WMC[wrap_model_call<br/>retry, fall back]
        WMC --> M{{MODEL + TOOLS}}
        M --> WTC[wrap_tool_call<br/>veto a tool call]
        WTC --> AM[after_model<br/>check the reply]
    end
    BA --> BM
    AM --> AA[after_agent<br/>once, at the end]
    AA --> OUT([reply])
```

## Defence in depth

```mermaid
flowchart TD
    R([member request]) --> L1[1 content filter<br/>before_agent]
    L1 --> L2[2 PII in<br/>before_model]
    L2 --> L3[3 tool policy<br/>wrap_tool_call]
    L3 --> L4[4 human approval<br/>HumanInTheLoopMiddleware]
    L4 --> L5[5 PII out<br/>after_model]
    L5 --> L6[6 policy judge<br/>after_agent]
    L6 --> A([answer])
    L1 -. blocked .-> X([refusal])
    L4 -. paused .-> H([reviewer])
```

## A subgraph seen from outside and inside

```mermaid
flowchart TD
    subgraph PARENT [what the parent sees]
        direction TB
        PS([START]) --> N[check_order]
        N --> PE([END])
    end
    subgraph INNER [what is actually inside check_order]
        direction TB
        IS([START]) --> F[fetch_order]
        F --> S[summarise_status]
        S --> IE([END])
    end
    N -.-> INNER
```

## The two ways to attach a subgraph

```mermaid
flowchart TB
    subgraph A [A. call it inside a node]
        direction TB
        A1["parent state: foo"] --> A2["def call_subgraph(state):<br/>sub.invoke({bar: state[foo]})<br/>return {foo: out[bar]}"]
        A2 --> A3["parent state: foo"]
    end
    subgraph B [B. add it as a node]
        direction TB
        B1["parent state: foo"] --> B2["add_node('node_1', subgraph)<br/>writes the parent's channels directly"]
        B2 --> B3["parent state: foo"]
    end
```

## Nesting and namespaces

```mermaid
flowchart TB
    subgraph P ["parent: my_key"]
        P1[parent_1] --> C
        C --> P2[parent_2]
        subgraph C ["child: my_child_key"]
            subgraph G ["grandchild: my_grandchild_key"]
                G1[grandchild_1]
            end
        end
    end
```

## Choosing a persistence mode

```mermaid
flowchart TD
    Q1{Does the subgraph need to<br/>remember previous calls?} -->|yes| PT[per-thread<br/>checkpointer=True<br/>plus ToolCallLimitMiddleware]
    Q1 -->|no| Q2{Does it do anything you<br/>would hate to repeat?}
    Q2 -->|yes| PI[per-invocation<br/>checkpointer=None]
    Q2 -->|no| Q3{Pure, cheap function<br/>of its input?}
    Q3 -->|yes| SL[stateless<br/>checkpointer=False]
    Q3 -->|no| PI
```
