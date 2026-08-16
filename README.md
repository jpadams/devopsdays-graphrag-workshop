# Knowledge Graphs for DevOps RAG

**DevOpsDays Portland · 2 hours · hands-on**

You have a microservices architecture. Somewhere there is a wiki page describing
it that was accurate eighteen months ago, a Jira board nobody trusts, and a
`terraform state` nobody reads. When someone asks *"if the Database goes down,
what breaks?"* the answer lives in four systems and one person's head.

This workshop puts that in one graph and asks it questions in English — twice.
Once in Python, once with no code at all.

```
                   ┌──────────────────────────────┐
                   │  "How many open tickets?"    │
                   └──────────────┬───────────────┘
                                  │
            ┌─────────────────────▼─────────────────────┐
            │                   agent                   │
            │                picks a tool               │
            └──┬─────────────────┬──────────────┬───────┘
               │                 │              │
     ┌─────────▼────────┐ ┌──────▼───────┐ ┌────▼─────────────┐
     │ Cypher template  │ │   vector +   │ │  text2cypher     │
     │ exact, predicted │ │ traversal    │ │  writes a query  │
     └─────────┬────────┘ └──────┬───────┘ └────┬─────────────┘
               │                 │              │
           ┌───▼─────────────────▼──────────────▼───┐
           │   Neo4j: one graph, both structured    │
           │             and unstructured           │
           └────────────────────────────────────────┘
```

The same three tools get built twice: as Python in steps 04–07, then in the Aura
console with no code in step 08 — where they are literally the three tool types
Aura offers.

## Before you arrive

**[PREWORK.md](PREWORK.md)**
You need a free Neo4j Aura instance and an OpenAI key (I'll provide if you don't have).

## Run it

### In the browser, nothing installed

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/jpadams/devopsdays-graphrag-workshop)

Codespaces prompts for your Aura and OpenAI credentials as secrets on creation,
installs everything, and drops you at a prompt. Then `make verify`.

### Or locally

```bash
cp .env.example .env     # fill in Aura + OpenAI credentials
make install             # <- only needed if run locally vs in codespace
make verify              # <- do this first, always
make load
```

Then `make embed`, `make vector`, `make template`, `make hybrid`,
`make text2cypher`, `make agent`, `make aura`. Each step prints the next one when it finishes, and
`make` on its own lists them all.

## The shape of it

| Step | Command | What you learn |
|---|---|---|
| 00 | `make verify` | Everything is plugged in before it matters |
| 01 | `make load` | One graph, structured *and* unstructured, side by side |
| 02 | `make embed` | Vector index, built explicitly so you can name its parts |
| 03 | `make vector` | Semantic search — and the question it answers **wrong** |
| 04 | `make template` | Fixed Cypher + parameters: exact, reviewable, rigid |
| 05 | `make hybrid` | Vector finds the door, Cypher walks through it |
| 06 | `make text2cypher` | Any question, but nobody reviewed the query |
| 07 | `make agent` | One agent choosing between them, and why tool *descriptions* are the work |
| 08 | `make aura` | The same three tools in the Aura console, no code |

The four retrieval steps are ordered by what they give up. Each one is motivated
by the previous one's limitation:

| | question | answer | you must |
|---|---|---|---|
| 03 vector | any | approximate, cannot count | accept fuzziness |
| 04 template | predicted | exact, reviewable | guess the question |
| 05 vector+Cypher | any | exact structure | write the traversal |
| 06 text2cypher | any | exact | trust an unreviewed query |

### The bit worth staying for

Step 03 asks a vector retriever *"how many open tickets are there?"* It says
**two**. The answer is **five**.

The model is handed each task in full — name, description *and* status. Nothing
is hidden from it, and it counts what it is given perfectly: 2 of its 4
documents really are open. The problem is that there are 10 tasks and it was
shown 4, because `k=4`. The other 6 were never retrieved, and nothing in the
pipeline mentions they exist. A retriever's contract is "here are the nearest
k" — it has no concept of completeness and cannot warn you when the question
needs it.

So nothing hallucinated and nothing is misconfigured. Every component did its
job; the composition is wrong for the question.

Then step 03 tries the obvious objection — *turn `k` up* — and it appears to
work, which is the most dangerous result in the workshop. `k=10` is right only
because this toy graph has exactly 10 tasks, so "nearest k" and "all of them"
coincide. On a real backlog you cannot set `k=40000`; set `k=500` and you are
confidently wrong again, now by 39,500 and far more plausibly.

Step 04 fixes it with one line of Cypher and **no model at all** —
`MATCH (t:Task {status: $status}) RETURN count(t)`. That deliberately comes
before text2cypher: the hard part of the counting question was never the
language, it was that a similarity search cannot count. Swap the tool and the
problem disappears, with nothing left to hallucinate.

But step 04 only answers questions somebody wrote down in advance. That is the
trade, and steps 05 and 06 are the two ways out of it.

### And the step that justifies the graph

Step 03 is a vector store and step 04 is a query you could run against anything.
**Step 05 is neither.** It attaches a Cypher traversal to the vector search, so
the search finds the entry point by meaning and the graph supplies the structure
around it:

```
Q: If the authentication work goes wrong, what else is affected and who owns it?

  plain vector search  →  "the context does not specify any dependencies"
  vector + traversal   →  UserService (Accounts), PaymentService (Revenue),
                          ShippingService (Fulfillment) — AuthService is owned by Platform
```

Same index, same embeddings, same question. The difference is four relationships
followed after the match. Plain vector search cannot get there — "Revenue"
appears in no task description, because ownership is an edge, not a word. And no
Cypher, generated or hand-written, can get there on its own — "the
authentication work" is not a value you can bind to a parameter or put in a
`WHERE` clause. You need the embedding to find the door before Cypher can walk
through it.

## Two paths, one graph

Everything here is deliberately arranged so the *same database* serves both the
code and the no-code path. The constraint that makes that work:

> Aura Agent's similarity-search tool only accepts OpenAI
> `text-embedding-3-small`, `-3-large`, or `ada-002`.

So `EMBEDDING_MODEL` is pinned in `.env` and used by step 02. Swap it for a local
model and the Python still works, while the no-code half silently stops matching
anything — Aura Agent would be embedding queries into a different vector space
than your index.

Both halves have been run against the same AuraDB Free instance and agree:

| Question | `make agent` (Python) | Aura Agent (no code) |
|---|---|---|
| How many open tickets are there? | 5, via text2cypher | 5, via text2cypher |
| Which team has the most open tasks? | Platform, with 3 | Platform, with 3 |
| If the auth work goes wrong, what breaks and who owns it? | UserService (Accounts), PaymentService (Revenue), ShippingService (Fulfillment) | same three, same owners |
| Which team maintains the Database? | "no team is recorded" | "No team is recorded" |

The three tool types Aura offers — `cypherTemplate`, `similaritySearch` (with an
optional `post_processing_cypher`), and `text2cypher` — are exactly steps 04, 05
and 06. That is why they are taught in that order. One version took a few
hundred lines of Python and the other took a form.

## What's in here

```
.devcontainer/                   Codespaces: image, secrets prompts, setup
cypher/01_microservices.cypher   the dataset, vendored (not fetched at runtime)
ontology.yaml                    the node/relationship/pattern contract
steps/00_verify.py .. 08_*.py    the workshop, in order
aura/devops-agent.json           Aura Agent config — the step 08 catch-up path
PREWORK.md                       what attendees do beforehand
FACILITATOR.md                   run of show, timings, failure modes
```

## Lineage

Built on Tomaz Bratanic's
[Using a Knowledge Graph to implement a DevOps RAG application](https://medium.com/neo4j/using-a-knowledge-graph-to-implement-a-devops-rag-application-b6ba24831b16)
and its [notebook](https://github.com/tomasonjo/blogs/blob/master/llm/devops_rag.ipynb).
The dataset and the "how many open tickets" lesson are his and have aged well.
The code around them has not, so it has been rewritten:

- `langchain_community.graphs` → **`langchain_neo4j`**, where the Neo4j
  integrations now live
- `create_openai_functions_agent` + `AgentExecutor` + a `hub.pull()` prompt →
  **`create_agent`**
- `GraphCypherQAChain.from_llm(...)` now requires **`allow_dangerous_requests`**
- `Neo4jVector.from_existing_graph()` → an explicit `CREATE VECTOR INDEX`, so
  step 06 has an index name, label and property it can point at
- bare `OpenAIEmbeddings()` → a **pinned** embedding model, for the reason above
- model IDs are an env var checked against your key at `make verify`, not a
  constant that rots

Structure borrows from GraphAcademy's
[workshop-genai](https://github.com/neo4j-graphacademy/workshop-genai)
(`agent_text2cypher.py`, `kg_structured_builder.py`), and the OpenAI and
`uv`/`make` conventions from
[video-context-graph](https://github.com/jpadams/video-context-graph) —
including its lesson about measuring embedding dimensions instead of assuming
them, which step 02 does.
