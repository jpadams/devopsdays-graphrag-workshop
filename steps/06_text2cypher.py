"""Step 06 — stop predicting the question: let the model write the Cypher.

    uv run steps/06_text2cypher.py

Step 04's templates were exactly right and completely rigid — four queries for
four questions somebody guessed in advance. This removes that constraint. The
model is given the graph schema and writes the query itself, so a question
nobody anticipated still gets an exact, aggregated, traversed answer.

That is the most capable tool in this workshop, and deliberately the last one
you meet, because it is also the least guaranteed. Steps 04 and 05 both produce
Cypher you wrote and can review. This produces Cypher you have never seen,
against a schema the model read a moment ago, and it runs against your
database.

Read the generated Cypher as it scrolls past — `verbose=True` prints every one.
That is the whole demo, and the habit worth taking away: with the other tools
you check the query once, with this one you check the query every time until
you trust it.
"""

import _common as c
from langchain_neo4j import GraphCypherQAChain

c.rule("Step 06 — text2cypher")

graph = c.graph()

# Introspect the live schema. This string is what gets pasted into the prompt —
# it is why the model knows that the edge is MAINTAINED_BY and not OWNS.
graph.refresh_schema()
print("\n  The schema the model is given:\n")
print("    " + graph.schema.replace("\n", "\n    ")[:1400])

chain = GraphCypherQAChain.from_llm(
    # Two models on purpose. Writing correct Cypher is the hard part and gets the
    # stronger model; turning rows into a sentence is easy. In 2023 this was
    # gpt-4 vs gpt-3.5-turbo. The split still pays, now as a reasoning-effort
    # difference rather than a model-class one.
    cypher_llm=c.chat_model(),
    qa_llm=c.chat_model(),
    graph=graph,
    verbose=True,
    # See _common.cypher_generation_prompt — it adds one rule, "return the
    # properties that identify the entities in the question". Without it the
    # Alice query below returns three task columns and no person, and the QA
    # step correctly refuses to answer. Worth deleting live to show the failure.
    cypher_prompt=c.cypher_generation_prompt(),
    # Required since langchain-neo4j 0.1. It is not a formality: this chain sends
    # model-authored Cypher to your database. Aura Agent solves the same problem
    # by only ever connecting read-only — see step 06.
    allow_dangerous_requests=True,
)

QUESTIONS = [
    # The one step 03 got wrong.
    "How many open tickets are there?",
    # Aggregation with a grouping key.
    "Which team has the most open tasks?",
    # One hop.
    "Which services depend on Database directly?",
    # Variable-length traversal — the question that is only cheap in a graph.
    "Which services depend on Database indirectly?",
    # Two hops through a node with no direct edge. Vector search cannot do this
    # at all: there is no (:Person)-[]->(:Task) edge to embed.
    "What is Alice working on?",
]

for q in QUESTIONS:
    print(f"\n{'─' * 78}\n  Q: {q}\n{'─' * 78}")
    try:
        print(f"\n  A: {chain.invoke({'query': q})['result']}\n")
    except Exception as e:  # noqa: BLE001
        # Text2cypher does fail sometimes. Say so out loud when it does — an
        # honest failure in front of the room is better material than a demo
        # that only ever works.
        print(f"\n  text2cypher failed: {type(e).__name__}: {e}\n")

print("""
  ── What just happened ─────────────────────────────────────────────────────

  Every one of those answers is correct, and none of the queries existed before
  you ran this. Compare that with step 04, where four queries answered four
  questions and a fifth question got nothing.

  "Indirectly" produced a variable-length traversal — (a)-[:DEPENDS_ON*]->(b).
  "What is Alice working on?" crossed two hops through Team, because there is
  no edge from Person to Task. The model worked both out from the schema.

  ── The whole toolkit, and where each one breaks ───────────────────────────

    step 03  vector          any question, approximate answer, cannot count
    step 04  template        exact and reviewable, only for predicted questions
    step 05  vector+Cypher   fuzzy question in, exact structure out
    step 06  text2cypher     any question, exact answer, unreviewed query

  Notice this tool is bad at step 03's job. Ask it "how will the recommendation
  service be updated?" and it writes a query matching on words rather than
  meaning, because there is no WHERE clause for a meaning.

  So no single tool wins. Which is the argument for letting something choose
  between them per question — and that is an agent.

  Next: make agent
""")
