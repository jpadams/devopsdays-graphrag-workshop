"""Step 02 — embed the task descriptions and build the vector index.

    uv run steps/02_embed_tasks.py

This is the step that makes the no-code half possible, so it is worth being
explicit about what it does rather than letting a helper do it invisibly.

The 2023 original called:

    Neo4jVector.from_existing_graph(OpenAIEmbeddings(), ...)

which embeds and creates the index in one line. Convenient, and wrong for us,
for two reasons:

  1. It creates the index implicitly. In step 06 we have to tell Aura Agent the
     index name, node label, and text property. Anything we cannot name, we
     cannot configure.
  2. Bare `OpenAIEmbeddings()` takes the library's default model. Aura Agent's
     vector tool only accepts text-embedding-3-{small,large} and ada-002, so the
     model has to be a deliberate choice, not a default. See .env.example.

So: embed explicitly, read the real dimension off the vector, create the index
to match, write the vectors back.
"""

import _common as c

c.rule("Step 02 — embeddings + vector index")

driver = c.driver()
embedder = c.embeddings()

with driver.session(database=c.NEO4J_DATABASE) as session:
    tasks = list(session.run(f"""
        MATCH (t:{c.VECTOR_NODE_LABEL})
        WHERE t.{c.VECTOR_TEXT_PROPERTY} IS NOT NULL
        RETURN elementId(t) AS id, t.name AS name, t.{c.VECTOR_TEXT_PROPERTY} AS text
        ORDER BY name
    """))

    if not tasks:
        raise SystemExit("  No Tasks found. Run `make load` first.")

    print(f"\n  Embedding {len(tasks)} task descriptions with {c.EMBEDDING_MODEL} ...")
    vectors = embedder.embed_documents([t["text"] for t in tasks])

    # Read the dimension off a real vector. Do not assume 1536 — if you ever
    # switch to text-embedding-3-large it is 3072, and an index created at the
    # wrong dimension does not error, it just quietly matches nothing.
    dimension = len(vectors[0])
    print(f"  Vector dimension (measured, not assumed): {dimension}")

    session.run(f"""
        CREATE VECTOR INDEX {c.VECTOR_INDEX_NAME} IF NOT EXISTS
        FOR (t:{c.VECTOR_NODE_LABEL})
        ON (t.{c.VECTOR_EMBEDDING_PROPERTY})
        OPTIONS {{ indexConfig: {{
            `vector.dimensions`: {dimension},
            `vector.similarity_function`: 'cosine'
        }} }}
    """).consume()
    print(f"  Vector index '{c.VECTOR_INDEX_NAME}' created (or already existed).")

    # Write vectors back by elementId, NOT by name. Two different tasks in this
    # dataset are both called 'Optimize' — matching on name would give one of
    # them both embeddings and leave the other with none.
    session.run(
        f"""
        UNWIND $rows AS row
        MATCH (t) WHERE elementId(t) = row.id
        CALL db.create.setNodeVectorProperty(
            t, '{c.VECTOR_EMBEDDING_PROPERTY}', row.vector
        )
        """,
        rows=[{"id": t["id"], "vector": v} for t, v in zip(tasks, vectors)],
    ).consume()

    session.run(
        f"CALL db.awaitIndex('{c.VECTOR_INDEX_NAME}', 300)"
    ).consume()

    embedded = session.run(f"""
        MATCH (t:{c.VECTOR_NODE_LABEL})
        WHERE t.{c.VECTOR_EMBEDDING_PROPERTY} IS NOT NULL
        RETURN count(*) AS n
    """).single()["n"]

driver.close()

print(f"""
  {embedded}/{len(tasks)} tasks now carry a {dimension}-dimension embedding,
  and the index is online.

  Write these two down — step 06 asks for them when you configure the Aura
  Agent similarity-search tool:

    index name      {c.VECTOR_INDEX_NAME}
    embedding model {c.EMBEDDING_MODEL}

  You will NOT be asked for the node label ({c.VECTOR_NODE_LABEL}) or the text
  property ({c.VECTOR_TEXT_PROPERTY}), because the index already carries both.
  That is the payoff for creating the index explicitly here rather than letting
  a helper create one implicitly under a name you never chose.

  Next: make vector
""")
