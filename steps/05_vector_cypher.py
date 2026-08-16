"""Step 05 — vector search that keeps going.

    uv run steps/05_vector_cypher.py

Step 03 left vector search looking bad. That was about counting, and counting is
not what it is for. This is the version that earns its place.

The idea in one line: **vector search finds the door, Cypher walks through it.**

A vector index can find "the task about making recommendations more personal"
from a question that shares no words with it. It cannot tell you who owns that
service or what breaks if the work ships badly, because those are relationships
and relationships are not in the embedded text.

So do both in one round trip. Match on meaning, then traverse from whatever
matched. That is what `VectorCypherRetriever` is: a vector search with a Cypher
fragment attached, running with `node` bound to each hit and `score` to its
similarity.

This is the first step that genuinely needs a graph. Step 03 was a vector store
and step 04 was a query you could have written against any database. This one is
neither, and it is the reason the data lives in Neo4j.

It also sits exactly between the two extremes you have just seen: step 03 took
any question and gave an approximate answer, step 04 gave an exact answer to a
question you had to predict. This takes an unpredicted question and returns
exact structure.
"""

import _common as c
from neo4j_graphrag.retrievers import VectorCypherRetriever

c.rule("Step 05 — vector + Cypher")

driver = c.driver()

# Two retrievers over the SAME index, differing only in the Cypher attached.
#
# The traversal itself lives in _common as VECTOR_CYPHER_RETRIEVAL, because step
# 07's agent and step 08's Aura Agent tool use the identical string. Open it and
# read it before running this — it is the whole content of this step.
plain = VectorCypherRetriever(
    driver,
    index_name=c.VECTOR_INDEX_NAME,
    embedder=c.embedder(),
    retrieval_query=c.PLAIN_RETRIEVAL,
    result_formatter=c.plain_result,
    neo4j_database=c.NEO4J_DATABASE,
)

enriched = VectorCypherRetriever(
    driver,
    index_name=c.VECTOR_INDEX_NAME,
    embedder=c.embedder(),
    retrieval_query=c.VECTOR_CYPHER_RETRIEVAL,
    result_formatter=c.enriched_result,
    neo4j_database=c.NEO4J_DATABASE,
)

QUESTIONS = [
    # Semantic entry point, structural answer. The words "Revenue" and "owns"
    # appear nowhere in any task description.
    "Who should I talk to about making product recommendations more personal?",
    # The DevOps question. "What is the blast radius of this piece of work?"
    "If the authentication work goes wrong, what else is affected?",
]

llm = c.chat_model()


def answer(store, question, k=2):
    docs = store.search(query_text=question, top_k=k).items
    return docs, c.text_of(
        llm.invoke(
            "Answer using only this context. If the context does not contain "
            "the answer, say so.\n\n"
            + "\n".join(d.content for d in docs)
            + f"\n\nQuestion: {question}"
        )
    ).strip()


for question in QUESTIONS:
    print(f"\n{'─' * 78}\n  Q: {question}\n{'─' * 78}")

    _, plain_answer = answer(plain, question)
    print(f"\n  Same index, plain vector search (step 03's tool):\n"
          f"    {plain_answer[:300]}")

    docs, rich_answer = answer(enriched, question)
    print("\n  With the traversal attached, the retriever returns:\n")
    for d in docs:
        print(f"    {d.content.strip()}")
    print(f"\n  ...and the answer becomes:\n    {rich_answer[:400]}")

driver.close()

print("""

  ── What changed ───────────────────────────────────────────────────────────

  Identical index. Identical embeddings. Identical question. The only
  difference is a Cypher fragment that runs after the vector hit and follows
  four relationships outward.

  Notice what the plain retriever could not do. "Revenue" appears in no task
  description, so no amount of semantic search reaches it — ownership is an
  edge, not a word. And "what else breaks" is a DEPENDS_ON traversal that has
  no textual equivalent at all.

  Notice too what step 04's template could not do. "Making recommendations more
  personal" is not a value you can bind to a parameter; there is no $variable
  for a meaning. You need the embedding to find the door before Cypher can walk
  through it — and that is still true of the text2cypher coming next.

  Two tools, each blind where the other sees, sharing one round trip and one
  database. That is the whole argument for a knowledge graph, and it is why
  this step exists.

  ── One more thing, about the Cypher itself ────────────────────────────────

  Open _common.py and compare VECTOR_CYPHER_RETRIEVAL with the
  `post_processing_cypher` in aura/devops-agent.json. They are the same string,
  character for character. In step 08 you will paste it into the Aura console.

  That is worth a moment because it was not true until recently. The retriever
  this workshop used before required its query to return exactly three columns —
  text, score, metadata — so every field had to be concatenated into one long
  string, and apoc.text.join was needed to flatten the dependents list. Aura
  wants ordinary named columns. So there were two spellings of one traversal,
  and the workshop called them a mirror.

  A retriever that does not dictate your result shape removes an entire class of
  that problem. It is a small thing here and a large one when the traversal is
  the part you are actually iterating on.

  Next: make text2cypher
""")
