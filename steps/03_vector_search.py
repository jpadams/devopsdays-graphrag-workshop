"""Step 03 — vector search, and the question it gets confidently wrong.

    uv run steps/03_vector_search.py

Three parts:

  A. vector search doing what it is good at — finding the relevant task from a
     question that shares no keywords with it.

  B. the same tool asked to count, getting it wrong.

  C. the obvious fix — turn k up — appearing to work, and why that is worse than
     the original failure.

Part C is the one people argue with, so it is worth running rather than
asserting.

Note what goes into the prompt below: the retrieval query returns name,
description AND status, so each document the model sees carries every field you
see on screen. The failure in part B is NOT a trick where we hide the status
column from it — that would prove nothing. It sees the statuses and is still
wrong, which is the interesting part.
"""

import _common as c
from neo4j_graphrag.retrievers import VectorCypherRetriever

c.rule("Step 03 — vector search")

driver = c.driver()

# Step 02 already built the index, and this points at it by name so the code
# fails loudly if it did not rather than quietly building a second one.
#
# c.PLAIN_RETRIEVAL is the simplest retrieval query there is: return the matched
# node's own properties and stop. No traversal, no relationships — that is step
# 05's job, and the whole point of this step is to show what you get without it.
store = VectorCypherRetriever(
    driver,
    index_name=c.VECTOR_INDEX_NAME,
    embedder=c.embedder(),
    retrieval_query=c.PLAIN_RETRIEVAL,
    result_formatter=c.plain_result,
    neo4j_database=c.NEO4J_DATABASE,
)

QUESTION = "How many open tickets are there?"


def search(question, k):
    return store.search(query_text=question, top_k=k).items


def ask(docs):
    """Hand the retrieved documents to the LLM verbatim and ask the question."""
    return c.text_of(
        c.chat_model().invoke(
            "Answer using only this context.\n\n"
            + "\n".join(d.content for d in docs)
            + f"\n\nQuestion: {QUESTION}"
        )
    ).strip()


def show(docs):
    for d in docs:
        print(f"      - {d.metadata['name']:<22} status={d.metadata['status']}")


# ── A. what vector search is for ─────────────────────────────────────────────
print("""
  A. Semantic retrieval
  ────────────────────
  Question: "How will the recommendation service be updated?"

  The matching task never uses the words "how" or "updated". Keyword search
  would miss it. Embeddings do not care about the words.
""")

for d in search("How will the recommendation service be updated?", 3):
    print(f"    [{d.metadata['score']:.3f}] {d.metadata['name']}")

# ── B. where it fails ────────────────────────────────────────────────────────
print(f"""

  B. The same tool, asked to count
  ────────────────────────────────
  Question: "{QUESTION}"

  The model is sent each document in full — name, description AND status.
  Nothing is hidden from it. Count the open ones yourself as they go past.
""")

small = search(QUESTION, 4)
print(f"    the retriever returned {len(small)} documents:\n")
show(small)

small_open = sum(1 for d in small if d.metadata["status"] == "open")
small_answer = ask(small)

with driver.session(database=c.NEO4J_DATABASE) as session:
    truth = session.run(
        "MATCH (t:Task {status:'open'}) RETURN count(*) AS n"
    ).single()["n"]
    total = session.run("MATCH (t:Task) RETURN count(*) AS n").single()["n"]

k, unseen = len(small), total - len(small)

print(f"""
    The LLM says:  {small_answer}

    Cypher says:   {truth}

  ── Why ────────────────────────────────────────────────────────────────────

  The model counted correctly. {small_open} of the {k} documents it received are
  open, and it said {small_open}. Given its input it was right.

  Its input was the problem. There are {total} tasks in the graph and it was
  shown {k}, because k={k}. The other {unseen} were never retrieved, and nothing
  anywhere in the pipeline mentions that they exist. The retriever's contract is
  "here are the nearest k" — it has no notion of completeness, and cannot warn
  you when the answer needs it.

  So this is not a hallucination and not a prompting failure. Every component
  did its job. The composition is simply wrong for the question.
""")

# ── C. the fix that is not a fix ─────────────────────────────────────────────
print(f"""
  C. "So turn k up"
  ─────────────────
  The reasonable objection. Let's try k={total}.
""")

big = search(QUESTION, total)
big_open = sum(1 for d in big if d.metadata["status"] == "open")
big_answer = ask(big)

driver.close()

print(f"""    retrieved {len(big)} documents, {big_open} of them open

    The LLM says:  {big_answer}

    Cypher says:   {truth}

  Correct. And it is the most dangerous result in this workshop.

  It worked because k={total} is every task in the graph, so "the nearest k" and
  "all of them" happened to coincide. We did not fix retrieval; we disabled it,
  and the LLM did the counting over the full table.

  That does not transfer. On a real backlog of 40,000 tickets you cannot set
  k=40000 — it will not fit in the context window, you would pay for every token
  of it, and you have reduced your vector database to an expensive SELECT *.
  Set k=500 instead and you are back to a confidently wrong number, except now
  it is wrong by 39,500 rather than 6, and it looks far more authoritative.

  The number of documents a retriever returns is a property of the search.
  Treating it as a fact about the world is the bug, and no value of k fixes it.

  ── What comes next ────────────────────────────────────────────────────────

  Do not conclude from this that vector search is bad. Counting was never its
  job, and we chose that question precisely because it is the one it cannot do.
  It found the recommendation task in part A from a question sharing none of
  its words, which nothing else in this workshop can do.

  The next step is the smallest possible fix for the counting question — one
  line of Cypher, no model involved at all. Then, having seen both extremes,
  we spend the rest of the workshop in the middle.

  Next: make template
""")
