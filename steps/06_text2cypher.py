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

Read the generated Cypher as it scrolls past — every one is printed below. That
is the whole demo, and the habit worth taking away: with the other tools you
check the query once, with this one you check the query every time until you
trust it.
"""

import _common as c
from neo4j_graphrag.generation import GraphRAG
from neo4j_graphrag.retrievers import Text2CypherRetriever

c.rule("Step 06 — text2cypher")

driver = c.driver()

# Introspect the live schema. This string is what gets pasted into the prompt —
# it is why the model knows that the edge is MAINTAINED_BY and not OWNS.
#
# Text2CypherRetriever will fetch this for you if you let it. We pass it
# explicitly because we also pass a custom prompt, and a custom prompt turns the
# automatic fetch off — the retriever cannot know where your template wants the
# schema, so it stops guessing. Forget this and {schema} renders empty.
schema = c.schema(driver)
print("\n  The schema the model is given:\n")
print("    " + schema.replace("\n", "\n    ")[:1400])

# Two models on purpose, and now you can see the split rather than infer it from
# two constructor keywords. Writing correct Cypher is the hard part and gets its
# own call; turning rows into a sentence is easy. In 2023 this was gpt-4 vs
# gpt-3.5-turbo. The split still pays, now as a reasoning-effort difference
# rather than a model-class one.
retriever = Text2CypherRetriever(
    driver=driver,
    llm=c.graphrag_llm(),
    neo4j_schema=schema,
    # See _common.CYPHER_PROMPT — it adds one rule, "return the properties that
    # identify the entities in the question". Without it the Alice query below
    # returns three task columns and no person, and the answer step correctly
    # refuses to answer. Worth deleting live to show the failure.
    custom_prompt=c.CYPHER_PROMPT,
    neo4j_database=c.NEO4J_DATABASE,
)

# GraphRAG is the thin piece on top: run the retriever, hand the rows to a model,
# get a sentence. Swap the retriever and everything else here is unchanged —
# which is exactly what step 07 does.
#
# The prompt is not optional. Read the comment on _common.ANSWER_PROMPT before
# you decide it is boilerplate: without it, the "indirectly" question below
# returns four correct rows and the model answers "None".
rag = GraphRAG(
    retriever=retriever,
    llm=c.graphrag_llm(),
    prompt_template=c.answer_prompt(),
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
        result = rag.search(query_text=q, return_context=True)
        generated = result.retriever_result.metadata.get("cypher", "(not reported)")
        print("\n  Generated Cypher:")
        print("    " + generated.strip().replace("\n", "\n    "))
        print(f"\n  A: {result.answer}\n")
    except Exception as e:  # noqa: BLE001
        # Text2cypher does fail sometimes. Say so out loud when it does — an
        # honest failure in front of the room is better material than a demo
        # that only ever works.
        print(f"\n  text2cypher failed: {type(e).__name__}: {e}\n")

driver.close()

print("""
  ── What just happened ─────────────────────────────────────────────────────

  Every one of those answers is correct, and none of the queries existed before
  you ran this. Compare that with step 04, where four queries answered four
  questions and a fifth question got nothing.

  "Indirectly" produced a variable-length traversal — (a)-[:DEPENDS_ON*]->(b).
  "What is Alice working on?" crossed two hops through Team, because there is
  no edge from Person to Task. The model worked both out from the schema.

  ── About that query running against your database ─────────────────────────

  Every generated query above was EXPLAINed before it was executed, and anything
  that came back as a write was refused rather than run. You did not configure
  that; it is what the retriever does.

  Worth dwelling on, because the previous version of this step could not say it.
  It used a chain that required allow_dangerous_requests=True — a flag whose
  honest reading is "I accept that a model is about to write SQL-equivalent
  against my database and nobody will look at it first."

  Note this is a guard rail, not a sandbox. It stops a generated MATCH ... DELETE
  from running. It does not stop a read query from returning data the asker
  should not see. In step 08 you will see Aura solve the same problem from the
  other end, by connecting read-only in the first place. Do both in production.

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
