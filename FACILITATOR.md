# Facilitator notes

Run of show, the click-through for step 06, verified questions, and the things
that go wrong.

---

## Run of show — 120 minutes

| Time | Block | Notes |
|---|---|---|
| 0:00 | **Framing + `make verify`** (10) | Shared key on the slide. Get *everyone* green before you talk. |
| 0:10 | **`make load` + explore** (12) | Console → Query. Draw the dependency graph. |
| 0:22 | **`make embed`** (8) | Explicit index. Note the index name and model. |
| 0:30 | **`make vector`** (13) | **The money beat.** 2 vs 5, then part C. Do not rush it. |
| 0:43 | **`make template`** (10) | The fix, with no model in it. |
| 0:53 | **`make hybrid`** (12) | **The graph beat.** Vector + Cypher. |
| 1:05 | **`make text2cypher`** (12) | Now let the model write it. Read every query aloud. |
| 1:17 | **`make agent`** (13) | Tool descriptions are the lesson, not `create_agent`. |
| 1:30 | **Step 08 in the console** (25) | No code. Everyone builds it. |
| 1:55 | **Close** (5) | Invoke it as an endpoint / MCP — *your* agent, not theirs. Paid feature; see Close. |

The four retrieval steps are ordered by what they give up, and each is motivated
by the previous one's limitation. Say that out loud at 0:30 so the room knows a
shape is coming rather than four unrelated demos:

| | question | answer | you must |
|---|---|---|---|
| 03 vector | any | approximate, cannot count | accept fuzziness |
| 04 template | predicted | exact, reviewable | guess the question |
| 05 vector+Cypher | any | exact structure | write the traversal |
| 06 text2cypher | any | exact | trust an unreviewed query |

Buffer is thin at 0:30, 0:53 and 1:30 — the blocks worth protecting. Steps 06
and 07 are the ones to compress: both ship five or six questions and you only
need to *run* three live, so drop the tail rather than rushing 05 or 08.

**Measured runtimes** on AuraDB Free with `gpt-5.6-sol` at `reasoning_effort=low`,
on good wifi. Every slot is mostly you talking, which is the intent:

| | |
|---|---|
| `make verify` + `load` + `embed` | ~13 s total |
| `make vector` (3 LLM calls) | ~10 s |
| `make template` (**no LLM at all**) | ~3 s |
| `make hybrid` (4 LLM calls) | ~19 s |
| `make text2cypher` (5 questions) | ~33 s |
| `make agent` (6 questions) | ~53 s |

So the code is never the bottleneck — but 40 people hitting OpenAI at once is
slower than one, and conference wifi is slower still. Budget 2–3× these.

### Slot 0:00 — get everyone green first

Do not start teaching until the room has run `make verify`. A person whose key
is broken is not listening to you, they are fighting pip. Put the shared key on
the slide, walk the room, and use the time to talk about the problem rather than
the tooling.

### Slot 0:30 — the beat everything else hangs on

Ask the room to predict the answer before you run it. Then:

- the retriever returns **4** of the graph's **10** tasks, because `k=4`
- **2** of those 4 are open, and the LLM says **2**
- Cypher says **5**

Land this carefully, because the lazy version of this demo is a cheat and a
sharp room will catch it. The model is sent each document **in full, including
`status`** — you can point at the printed statuses and say "it saw exactly
that." It then counts correctly. It is not hallucinating and it is not being
tricked; it was shown 4 of 10 tasks and nothing told it the other 6 existed.

> An earlier version of this workshop sent only the task *descriptions* to the
> model while printing the statuses on screen. It produced a punchier number
> (the model said "4", counting documents) — and it was rigged, because the
> status column the audience could see never reached the model. If someone asks
> "doesn't it see the status right there?", the answer is now genuinely yes.

The point to land: *no amount of prompt engineering fixes this.* The retrieval
contract is "give me the nearest k". Completeness is not something a vector
index can offer.

**Then run part C**, because someone always says "so raise k". At `k=10` it
answers **5** — correctly. Sit with that for a second before explaining it:
`k=10` is every task in the graph, so retrieval was not fixed, it was switched
off, and the LLM counted the whole table. On 40,000 tickets you cannot do that;
at `k=500` you are wrong by 39,500 and it looks more authoritative than before.
Part C converts the skeptic in the room better than any amount of assertion.

### Slot 0:43 — the fix with no model in it

Short block, and the easiest one to under-sell. The whole thing is:

    MATCH (t:Task {status: $status}) RETURN count(t) AS tasks

Five. Correct. No OpenAI call anywhere in the step — point that out explicitly,
because it is the only moment in the workshop where the database's answer
reaches the room unmediated by a model. Nothing here *can* hallucinate, because
nothing here is generating anything.

Two things to draw out:

- **Reviewability.** You can read these four queries, check them against the
  schema, and know what they do. So can the person on call at 3am. Hold that
  thought until step 06, where the query is written fresh each time and nobody
  reviews it.
- **Coverage is the cost.** Four queries, four questions, and somebody had to
  guess all four. Ask a fifth and you get nothing. Step 03's weakness was
  accuracy; this one's is coverage — and that framing sets up the next two
  steps as the two different ways out.

This is also, exactly, an Aura `cypherTemplate` tool. Flag it now so step 08
feels like recognition rather than new material.

### Slot 0:53 — the step that justifies the graph

Everything before this could be done without a graph. Say so out loud: step 03
is a vector store, step 04 is an LLM writing queries, and neither needs Neo4j.
This is the one that does.

Run it and let the A/B do the work. The plain retriever answers *"the context
does not specify any dependencies"*. Same index, same embeddings, same question,
plus four relationships followed after the match — and you get UserService
(Accounts), PaymentService (Revenue), ShippingService (Fulfillment).

Two things to point at:

- **"Revenue" appears in no task description.** Ownership is an edge, not a word,
  so no amount of better embedding reaches it.
- **"The authentication work" is not a `WHERE` clause.** Text2cypher cannot find
  the entry point, because the entry point is a meaning.

The retrieval query lives in `steps/_common.py` as `VECTOR_CYPHER_RETRIEVAL`.
Put it on screen — `node` and `score` are bound by the vector search that just
ran, and everything after is an ordinary traversal. That is the entire trick.

> **Worth telling on yourself.** The first version of this traversal returned
> dependent service *names* but not their owners. Asked who owns them, the agent
> answered anyway — and put PaymentService under Fulfillment. It is Revenue. Nothing
> flagged it; the sentence read exactly like the correct ones.
>
> Returning the owners in the Cypher fixed it. The lesson: **if your retriever
> returns half a fact, the model will supply the other half**, and it will not
> tell you which half it made up. Grounding is a property of what you return,
> not of how sternly you prompt.

### Slot 1:17 — the actual lesson of step 07

`create_agent(model, tools)` is one line and nobody learns anything from it.
The work is in the docstrings. Show them the "Do NOT use this to count" sentence
and delete it live — the agent starts answering "how many" from vector search
again. That demo is worth more than the rest of the block.

Tomaz's original blog post ends by admitting his tool descriptions needed work.
Worth quoting; it is the honest version of what everyone's first agent does.

---

## Step 08 — the console click-through

Aura console → **Agents** → *Create agent*.

The form, in the order it presents the fields — the console's labels, not the
JSON's:

| Console field | What to put in it |
|---|---|
| **Name** | `DevOps Graph Agent` |
| **Description** | the `description` from `aura/devops-agent.json` |
| **Prompt instruction** | the `system_prompt` from that same file (or write one live). Note the console calls it *Prompt instruction*, not "system prompt" |
| **Instance** | the one from step 01 |
| **Agent location** | pre-filled from the instance; nothing to do |
| **Access** | **leave it on Internal.** See below |
| **Enable MCP server** | greyed out, and stays that way. It needs External |

> **Say something about Access before anyone clicks past it.** The two options
> are **Internal** — *"Available to members of this Aura project"*, marked
> **Free**, and selected by default — and **External** — *"Provided via an
> auto-generated endpoint"*, marked **$0.35 / hour**. Internal is correct for
> everyone in the room, and the default is already right, so this is a "notice
> it, don't touch it" moment rather than a step.
>
> The MCP toggle sitting greyed out underneath is the tell for why: the endpoint
> and the MCP server are the same paid thing. Worth pointing at for ten seconds —
> it sets up the close.

> Aura can **auto-generate** the whole agent from a system prompt plus the graph
> schema. Show it — it is a genuinely good demo. Then edit the tools by hand, so
> people see what it actually generated rather than trusting it.

> **Build the tools in teaching order** — `cypherTemplate`, then
> `similaritySearch`, then `text2cypher`. That is steps 04, 05 and 06, and
> building them in that sequence makes this block recognition rather than new
> material. It is also easiest-to-hardest, so nobody is stuck on the fiddly one.
>
> Under **Add tool** the console spells these **Cypher Template**, **Similarity
> Search** and **Text2Cypher**. The camelCase names above are the API `type`
> values in `aura/devops-agent.json` — same three things, two spellings, and
> attendees are reading the console ones.

### Tool 1 — Cypher template (step 04)

Start here, because it is the one they can fully read. Paste the "what is one
person working on" query from `steps/04_cypher_template.py` into **Cypher
query**, then use **+ Add parameter** to declare it.

| Console field | Value |
|---|---|
| **Parameters** | `personName`, type string, described as *"The person's first name as recorded in the graph, e.g. Alice."* |
| **Cypher query** | the step 04 query, with `$personName` where the name goes |

> Mind the rename. Step 04's Python calls the parameter `$person`; the Aura tool
> calls it `$personName`, and that is what `aura/devops-agent.json` ships. Either
> works as long as the template and the declaration agree — but if someone is
> diffing the two files, that is the difference they will find.

The **Parameters** section is also where the point lands: the agent may choose
the *value*, never the query. Note the description field on the parameter itself
— that is what tells the model what to put there, and it is the same
"descriptions are the engineering" lesson one level down.

The teaching point is the same as slot 0:43: this tool cannot go wrong, and it
cannot go anywhere it was not pointed. It also encodes the two-hop path through
Team that free-form text2cypher is most likely to fumble.

> Each tool has its own **Test** tab next to Configure. Use it — you can prove a
> tool works before the agent exists, which makes debugging in front of a room
> much less alarming than invoking the whole agent and guessing which tool failed.

The teaching point is the same as slot 0:43: this tool cannot go wrong, and it
cannot go anywhere it was not pointed. It also encodes the two-hop path through
Team that free-form text2cypher is most likely to fumble.

### Tool 2 — Similarity search (step 05)

The one worth doing by hand, and worth building in **two stages** so the room
sees the difference.

**Stage 1** — plain vector search. Pick the index step 02 built, and leave
**Return connected graph data** unticked:

| Console field | Value |
|---|---|
| **Index** | `task_embeddings` — a dropdown, so it only lists indexes that exist. If it is empty, step 02 did not run |
| **Top K** | `4` |
| **Embedding provider** | `OpenAI` |
| **Embedding model** | `text-embedding-3-small` |
| **Vector Dimensions** | greyed out, fills itself in as `1536` from the model |
| **Return connected graph data** | leave unticked for now |

Test it on the tool's own **Test** tab with *"if the authentication work goes
wrong, what else is affected?"* — same shrug as step 05's plain retriever.

**Stage 2** — tick **Return connected graph data** ("Include connected nodes and
relationships"). That reveals the **Graph query** box, which is step 05's
traversal. Ask again and watch the answer acquire teams and blast radius. One
checkbox and one field, and the no-code agent gains the capability that step 05
built in Python.

> The checkbox is the whole beat, so do not let anyone tick it early. Unticked,
> this is a vector store. Ticked, it is GraphRAG. That is the entire argument of
> the workshop expressed as one form control.

The Cypher goes in the field the console calls **Graph query**; in
`aura/devops-agent.json` the same thing is `config.post_processing_cypher`. It is
the same string as `VECTOR_CYPHER_RETRIEVAL` in `steps/_common.py` — character
for character, not merely equivalent. Attendees paste the exact fragment they
read in step 05.

> There is a **Generate draft with AI** panel above that box that will write the
> traversal from a plain-language description. Worth showing *after* they have
> pasted the real one, not before — the point of the step is that they recognise
> the Cypher, not that something produced it for them.

> Worth saying out loud if anyone asks why that is remarkable. It was not true
> of the earlier version of this workshop: LangChain's `Neo4jVector` required
> the retrieval query to return exactly `text`, `score`, `metadata`, so the
> Python half concatenated every field into one string (and needed
> `apoc.text.join` to do it) while Aura took ordinary named columns. Two
> spellings of one traversal, presented as a mirror. `VectorCypherRetriever`
> imposes no column contract, so there is now genuinely one string.

> This is the beat that lands the whole two-path argument: the no-code tool is
> not a toy subset. It does vector-plus-traversal GraphRAG, configured in a
> form.

**Description** — the same prose as the Python docstring, including the
"do not use for counting" sentence. Same lesson, same words, no code.

> Worth pointing out: there is **no node-label or text-property field**. The
> vector index already knows it is on `(:Task)` and which property it indexes,
> so naming the index names all three. That is the payoff for step 02 having
> created the index explicitly instead of letting a helper conjure one.

> Note `top_k: 4` — the same k as step 03. So this tool has exactly the same
> counting failure, which is why the system prompt spells out that a similarity
> result count is a property of the search and not of the graph. Good moment to
> ask the room "so what happens if I ask *this* how many tickets are open?"

> If the embedding model does not match `EMBEDDING_MODEL` from step 02, the tool
> returns nothing useful and gives no error. Single most likely thing to go
> wrong in this block.

The exact API shape, verified live (`aura/devops-agent.json` has it in full):

```json
{ "name": "Task impact and ownership", "type": "similaritySearch", "enabled": true,
  "description": "...",
  "config": { "provider": "openai", "model": "text-embedding-3-small",
              "index": "task_embeddings", "top_k": 4, "dimensions": 1536,
              "post_processing_cypher": "MATCH (node)-[:LINKED_TO]->..." } }
```

`type` must be exactly one of `text2cypher`, `cypherTemplate`, `similaritySearch`.
`provider`, `model`, `index` and `top_k` are required; `dimensions` and
`post_processing_cypher` are optional. All keys are snake_case, and **unknown
keys are silently dropped** — no error, no warning, the tool just quietly lacks
the capability you thought you configured. Read the tool back with
`neo4j-cli aura agent get <id>` after any edit.

Tool names come back with spaces turned into underscores (`Task impact and
ownership` → `Task_impact_and_ownership`) — cosmetic, but it shows up in traces.

### Tool 3 — Text2Cypher (step 06)

Add it, give it a description, done. No configuration — it reads the schema
itself.

### Then test the whole agent

Same questions as step 05. Watch which tool it picks.

Two places to test, and the difference matters when something misbehaves. Each
tool has its own **Test** tab, which exercises that tool alone — use it to prove
a tool works. The agent's chat panel exercises the *routing*, which is the thing
step 07 says is the real engineering. A wrong answer from the chat panel and a
right answer from the tool's own Test tab means the descriptions are at fault,
not the Cypher.

### The closing beat

```bash
neo4j-cli aura agent list
neo4j-cli aura agent invoke <id> --input "how many open tickets are there?" --rw
```

The thing they just built by clicking is an HTTP endpoint and, with
`--is-mcp-enabled`, an MCP server. Nothing was deployed. For a DevOpsDays room
that lands better than any amount of framework talk.

> **Do this from your own account, and do not ask the room to follow along.**
> The console's **External** access setting — the auto-generated endpoint and the
> MCP server — is priced at **$0.35 / hour** and needs a card. New agents default
> to **Internal**, which is free and correct for the room. An Internal agent
> **cannot be invoked through the API at all**: `agent invoke` returns
> `agent invocation forbidden: agent may be disabled or private` (the API calls
> this `is_private`; the console calls it Internal — same setting). Console chat
> only.
>
> You can see which you have at a glance: in the Agents list an Internal agent
> shows a padlock and the label **Free** next to its name. If anyone's agent is
> missing the padlock, they have switched to External and are being billed for
> it — worth a scan of the room before you finish.
>
> So this beat is a demo you give, not an exercise they do. Create yours with
> `uv run steps/08_aura_agent.py create --external` before the session, show it,
> and delete it after — it bills for as long as it exists:
>
> ```bash
> neo4j-cli aura agent delete <id> --rw
> ```
>
> Verify your own agent answers before the session. If you would rather not pay
> for the demo at all, cut this beat: everything the workshop argues is already
> proven by the console chat panel in step 08.

---

## Verified questions

Rehearse against these. Anything not on this list, treat as live improv.

**Vector search is right for these** (step 03 / similarity tool)

- How will the recommendation service be updated?
- Which tasks are about performance optimization?
- Is anyone working on encryption?

**Cypher is right for these** (step 06 / text2cypher)

- How many open tickets are there? → **5**
- Which team has the most open tasks? → **Platform** (3 of the 5)
- Which services depend on Database directly? → Catalog, Order, User, Payment,
  Inventory, Auth
- Which services depend on Database indirectly? → variable-length traversal;
  overlaps with the direct answer, which is a property of the data, not a bug
- What is Alice working on? → 4 tasks, two hops via Platform
- Which team maintains the Database? → **nobody** — the honest-answer test

**Vector + traversal is right for these** (step 05 / similarity + post-processing)

- Who should I talk to about making product recommendations more personal?
  → the **Revenue** team, which owns RecommendationService
- If the authentication work goes wrong, what else is affected and who owns it?
  → UserService (Accounts), PaymentService (Revenue), ShippingService
  (Fulfillment); AuthService itself is owned by Platform

**Multi-hop** (step 07 / the agent)

- What tasks are linked to services that depend on the Database? → BugFix,
  FeatureAdd, Refactor, Optimize, Update, ImproveSecurity

**Questions that expose the seams** — good if the room is sharp, risky otherwise

- "What work is **planned** on services that depend on the Database?" →
  reliably answers *"the graph contains no answer"*. Nothing is broken: no Task
  has status `planned` (they are open / in progress / completed), so the model
  filters on a value that does not exist and honestly reports nothing. Swap
  "planned" for "linked to" and it works. A tidy demonstration that text2cypher
  is only as good as the fit between the user's vocabulary and the schema —
  and that an honest empty answer looks exactly like a broken one.

- "Which is the most important service?" — not in the graph. A good agent says
  so; a bad one invents a ranking.
- "Who should I page if checkout is broken?" — requires inferring that Order
  depends on Payment and reading off team ownership. Sometimes lovely,
  sometimes a mess.

---

## Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| `OPENAI_MODEL exists` fails | Model ID moved | `make verify` prints valid IDs; edit `.env` |
| `insufficient_quota` | New key, $0 balance | Shared key, or add $5 |
| Aura connection refused | Free instance paused | Resume in console, ~60s |
| `unauthorized` on a correct password | `NEO4J_USERNAME`/`NEO4J_DATABASE` assumed to be `neo4j` | Some instances use the instance id for both. `make verify` names the other candidate |
| Local Python is a mess | any laptop-env problem | Send them to Codespaces; it is why we ship a devcontainer |
| Vector search returns nothing | Index built at wrong dimension, or step 02 not run | `make reset`, re-run 01 and 02 |
| Aura Agent tool returns nothing | Embedding model mismatch | Must equal `EMBEDDING_MODEL` from step 02 |
| No **Agents** in the console | Org settings | GenAI assistance + Aura Agent, org level — see PREWORK.md |
| Can't create an agent | Not project admin | Personal free account instead of company org |
| `agent invocation forbidden: agent may be disabled or private` | The agent is private, which is the free tier | Expected, not a permissions bug. Private agents are console-chat only; API/MCP access is paid. `08_aura_agent.py ask` now says this rather than passing the raw error through |
| `Could not use APOC procedures` | `NEO4J_URI` points at a plain local Neo4j, not Aura | Aura bundles APOC Core. `make verify` catches this now |
| text2cypher writes bad Cypher | It happens | Say so out loud. Step 06 prints every generated query — debug it live |
| Whole room rate-limited | Everyone on the shared key | Fall back to `make text2cypher` as a demo from the podium |

### Questions you will get about model config

Two get asked every time, and both have been measured on this graph rather than
reasoned about, so you can answer with numbers.

**"Would a higher reasoning effort fix the refusals?"** No. `gpt-5.6-terra`
refused the long Alice context 6/6, 5/6, 6/6 at low, medium and high. It is fast
when it refuses (~1.3s vs sol's ~3.5s) because it is not thinking harder, it is
declining sooner. Model choice fixes this; the effort knob does not.

**"Should we use low effort to write Cypher and higher effort to synthesise?"**
Architecturally reasonable — it is the modern version of the 2023 gpt-4-for-
Cypher / gpt-3.5-for-QA split, and step 04 still sets `cypher_llm` and `qa_llm`
separately so you can demo it. But on this graph it buys nothing measurable:
sweeping the Cypher-generation effort across low/medium/high produced the same
queries and the same answers on four hard questions, at 4.5s / 4.6s / 4.8s.
Four labels and five relationship types is not enough schema to strain a
reasoning model. Say that honestly rather than implying the split is doing work.

### If Aura Agent is down entirely

Step 06 becomes a demo from your machine against a pre-built agent. Keep one
alive in your own project as insurance and know its agent id.

### If OpenAI is down entirely

Steps 01 and 04 still work if you hand-write Cypher. Pivot the back half to
"what makes a good tool description" using the graph in the console. Not the
workshop you planned, still worth the room's time.

---

## Before the day

Already done once, on a fresh AuraDB Free instance, with both paths agreeing:

- [x] `make reset && make all` end to end, timed
- [x] `aura/devops-agent.json` carries the real three-tool config, including the
      `similaritySearch` shape (probed from the API — it is not in the docs)
- [x] Aura Agent built, invoked, and confirmed to give the same answers as the
      Python path

Still yours to do:

- [ ] **Re-run `make verify` the morning of.** `OPENAI_MODEL` is the item most
      likely to have rotted. Model IDs moved twice while this was being written.
- [ ] **Walk step 06 in the console yourself.** The click-through here was
      written from the API shape; the console's field labels may differ, and you
      want to have seen the actual screens before 40 people do.
- [ ] Shared key created, capped, on the slide; calendar reminder to revoke it
- [ ] Both paths on conference-grade wifi (tether to a phone and try)
- [ ] Confirm the Free instance has not paused — it will, after 3 idle days
- [ ] Keep a spare agent alive in your own project as step 06 insurance, and
      write its agent id somewhere you can find it from the podium
