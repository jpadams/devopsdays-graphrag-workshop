"""Step 04 — the other extreme: a fixed query with parameters.

    uv run steps/04_cypher_template.py

Step 03 asked "how many open tickets are there?" and got 2. The answer is 5.
Here is the smallest possible thing that gets it right.

    MATCH (t:Task {status: $status}) RETURN count(t) AS n

No LLM writes this. No LLM reads the graph. You wrote the query, the database
ran it, and the number is correct because a database counting rows is the thing
databases are best at. `$status` is a parameter, so one query answers the
question for open, in progress, or completed.

Note what this step does NOT use: there is no OpenAI call anywhere in it. That
is deliberate. Before we let a model write queries, it is worth seeing that the
hard part of the counting question was never the language — it was that a
similarity search cannot count. Swap in the right tool and the problem vanishes.

The trade is obvious once you look at it. This query answers exactly one
question. You had to know, in advance, that someone would ask it. Step 03's
vector search took a question nobody anticipated; this takes a question somebody
already wrote down.

Neither extreme is where you want to live. Steps 05 and 06 are the middle.

This is also, precisely, an Aura Agent `cypherTemplate` tool — same query, same
parameters. Step 08 configures this exact thing in a form.
"""

import _common as c

c.rule("Step 04 — a fixed query with parameters")

# Each of these is a question somebody anticipated, written down once, with the
# parts that vary pulled out as parameters. This is what a "query template" is.
TEMPLATES = {
    "count tasks by status": (
        "MATCH (t:Task {status: $status}) RETURN count(t) AS tasks",
        {"status": "open"},
    ),
    "which team has the most open work": (
        """
        MATCH (t:Task {status: $status})-[:ASSIGNED_TO]->(team:Team)
        RETURN team.name AS team, count(t) AS open_tasks
        ORDER BY open_tasks DESC
        """,
        {"status": "open"},
    ),
    "what is one person working on": (
        """
        MATCH (p:Person {name: $person})-[:PART_OF]->(team:Team)<-[:ASSIGNED_TO]-(t:Task)
        OPTIONAL MATCH (t)-[:LINKED_TO]->(svc:Microservice)
        RETURN p.name AS person, team.name AS team, t.name AS task,
               t.status AS status, svc.name AS service
        ORDER BY status, task
        """,
        {"person": "Alice"},
    ),
    "blast radius of a service": (
        """
        MATCH (dependent:Microservice)-[:DEPENDS_ON]->(svc:Microservice {name: $service})
        OPTIONAL MATCH (dependent)-[:MAINTAINED_BY]->(team:Team)
        RETURN dependent.name AS would_break,
               coalesce(team.name, 'NOBODY') AS owned_by
        ORDER BY would_break
        """,
        {"service": "AuthService"},
    ),
}

driver = c.driver()

with driver.session(database=c.NEO4J_DATABASE) as session:
    for title, (cypher, params) in TEMPLATES.items():
        print(f"\n{'─' * 78}\n  {title}\n{'─' * 78}")
        print(f"  parameters: {params}\n")
        for record in session.run(cypher, **params):
            values = "   ".join(f"{k}={v}" for k, v in record.data().items())
            print(f"    {values}")

driver.close()

print("""

  ── What this bought, and what it cost ─────────────────────────────────────

  Bought: the right answer, every time, with no model in the loop. Nothing here
  can hallucinate, because nothing here is generating anything. You can read
  these four queries, check them against the schema, and know what they do —
  and so can your reviewer, and so can whoever is on call at 3am.

  This matters more than it sounds. Everything else in this workshop puts an
  LLM somewhere in the path. A parameterised query is the one option where the
  database's answer reaches the user unmediated.

  Cost: somebody had to write these four queries, in advance, having guessed
  the four questions. Ask a fifth question and you get nothing. Step 03's
  weakness was accuracy; this one's weakness is coverage.

  ── The middle ─────────────────────────────────────────────────────────────

  So we have two extremes:

    vector search      any question, approximate answer, cannot aggregate
    fixed template     exact answer, but only for questions you predicted

  The next two steps are the interesting middle ground.

    make hybrid     (step 05)  start from a fuzzy question like step 03, then
                               traverse the graph like step 04 — one round
                               trip, both strengths.

    make text2cypher (step 06) let the model write the query, so you stop
                               having to predict the question. That is the
                               most powerful option and the least guaranteed,
                               which is why it comes last rather than first.

  Next: make hybrid
""")
