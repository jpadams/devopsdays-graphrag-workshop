"""Step 01 — load the graph, then look at it.

    uv run steps/01_load_graph.py

Afterwards, open the Aura console -> Query and run this:

    MATCH p=(:Microservice)-[:DEPENDS_ON]->(:Microservice) RETURN p

Seeing the dependency graph drawn is worth more than any slide about why graphs
are useful. Spend a couple of minutes here.
"""

from pathlib import Path

import _common as c

CYPHER = Path(__file__).parent.parent / "cypher" / "01_microservices.cypher"

c.rule("Step 01 — load the microservices graph")

driver = c.driver()

# The whole file goes in as ONE statement — the relationship MERGEs at the bottom
# reference variables bound at the top. See the note in the .cypher file.
statement = CYPHER.read_text()

with driver.session(database=c.NEO4J_DATABASE) as session:
    summary = session.run(statement).consume()
    counters = summary.counters
    print(
        f"\n  nodes created         {counters.nodes_created}"
        f"\n  relationships created {counters.relationships_created}"
        f"\n  properties set        {counters.properties_set}"
    )
    if counters.nodes_created == 0:
        print("\n  (all zero = the graph was already loaded. MERGE is idempotent.)")

    print("\n  What is in there now:\n")
    rows = session.run("""
        MATCH (n)
        RETURN labels(n)[0] AS label, count(*) AS count
        ORDER BY count DESC
    """)
    for r in rows:
        print(f"    {r['label']:<16} {r['count']:>3}")

    rows = session.run("""
        MATCH ()-[r]->()
        RETURN type(r) AS type, count(*) AS count
        ORDER BY count DESC
    """)
    print()
    for r in rows:
        print(f"    :{r['type']:<15} {r['count']:>3}")

    # The number that matters later. Remember it.
    open_tasks = session.run(
        "MATCH (t:Task {status:'open'}) RETURN count(*) AS n"
    ).single()["n"]

driver.close()

print(f"""
  ── Remember this number ──────────────────────────────────────────────────

    open tasks: {open_tasks}

  Cypher counted them, so this is the truth. In step 03 we will ask a vector
  retriever the same question and get a different, confident, wrong answer.

  Next: make embed
""")
