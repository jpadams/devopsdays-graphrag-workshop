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
matched. In langchain-neo4j that is the `retrieval_query` parameter: a Cypher
fragment that runs after the vector search, with `node` bound to each hit and
`score` to its similarity.

This is the first step that genuinely needs a graph. Step 03 was a vector store
and step 04 was a query you could have written against any database. This one is
neither, and it is the reason the data lives in Neo4j.

It also sits exactly between the two extremes you have just seen: step 03 took
any question and gave an approximate answer, step 04 gave an exact answer to a
question you had to predict. This takes an unpredicted question and returns
exact structure.
"""

import _common as c
from langchain_neo4j import Neo4jVector

c.rule("Step 05 — vector + Cypher")

# The traversal itself lives in _common as VECTOR_CYPHER_RETRIEVAL, because the
# agent in step 05 and the Aura Agent tool in step 06 use the same one. Open it
# and read it before running this — it is the whole content of this step.
#
# `node` and `score` are bound by the vector search that ran just before it.
# Everything after is an ordinary traversal outward from the matched Task.
plain = Neo4jVector.from_existing_index(
    embedding=c.embeddings(),
    url=c.NEO4J_URI,
    username=c.NEO4J_USERNAME,
    password=c.NEO4J_PASSWORD,
    database=c.NEO4J_DATABASE,
    index_name=c.VECTOR_INDEX_NAME,
    text_node_properties=["name", "description", "status"],
)

enriched = Neo4jVector.from_existing_index(
    embedding=c.embeddings(),
    url=c.NEO4J_URI,
    username=c.NEO4J_USERNAME,
    password=c.NEO4J_PASSWORD,
    database=c.NEO4J_DATABASE,
    index_name=c.VECTOR_INDEX_NAME,
    retrieval_query=c.VECTOR_CYPHER_RETRIEVAL,
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
    docs = store.similarity_search(question, k=k)
    return docs, c.text_of(
        llm.invoke(
            "Answer using only this context. If the context does not contain "
            "the answer, say so.\n\n"
            + "\n".join(d.page_content for d in docs)
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
        print(f"    {d.page_content.strip()}")
    print(f"\n  ...and the answer becomes:\n    {rich_answer[:400]}")

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

  Next: make text2cypher
""")
