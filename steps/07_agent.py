"""Step 07 — one agent, all the tools, routing between them.

    uv run steps/07_agent.py
    uv run steps/07_agent.py "who maintains the payment service?"

Nothing new is built here. The enriched retriever from step 05 and the
text2cypher chain from step 06 are wrapped as tools and handed to a model that
picks between them.

The interesting engineering is not the agent. It is the tool descriptions.

The author of the blog post this workshop descends from ended it by admitting
his tool descriptions needed work — the agent kept reaching for the wrong one.
The descriptions below are the fix, and they are worth reading closely: each one
says what the tool is for AND what it is not for, because "not for counting" is
the sentence that stops the agent using vector search to answer "how many".
"""

import sys

import _common as c
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_neo4j import GraphCypherQAChain, Neo4jVector

c.rule("Step 07 — the agent")

# The enriched retriever from step 05, not the plain one from step 03. It
# strictly dominates: same vector search, plus the ownership and dependency
# traversal attached. There is no reason to give an agent the weaker tool.
store = Neo4jVector.from_existing_index(
    embedding=c.embeddings(),
    url=c.NEO4J_URI,
    username=c.NEO4J_USERNAME,
    password=c.NEO4J_PASSWORD,
    database=c.NEO4J_DATABASE,
    index_name=c.VECTOR_INDEX_NAME,
    retrieval_query=c.VECTOR_CYPHER_RETRIEVAL,
)

graph = c.graph()
graph.refresh_schema()

cypher_chain = GraphCypherQAChain.from_llm(
    cypher_llm=c.chat_model(),
    qa_llm=c.chat_model(),
    graph=graph,
    verbose=False,
    cypher_prompt=c.cypher_generation_prompt(),
    allow_dangerous_requests=True,
)


@tool("search_task_descriptions")
def search_task_descriptions(query: str) -> str:
    """Semantic search over engineering task descriptions, with graph context.

    Use this for questions that start from a fuzzy description rather than an
    exact value: what a task involves, what someone means to change, work
    matching a theme like "performance" or "security", who to talk to about a
    piece of work, or what would be affected if it goes wrong.

    For every match it also returns the service the task touches, the team that
    owns that service, the team doing the work, and every service that depends
    on it — so it answers ownership and blast-radius questions that begin with a
    description rather than a name.

    Do NOT use this to count, total, rank, or aggregate anything: it returns a
    fixed number of nearest matches, so counting its results tells you about the
    search parameters and nothing about the graph.
    """
    docs = store.similarity_search(query, k=4)
    return "\n\n".join(d.page_content for d in docs)


@tool("query_the_graph")
def query_the_graph(question: str) -> str:
    """Answer a question by generating and running a Cypher query.

    Use this for anything countable, rankable, or relational: how many tasks are
    open, which team owns the most work, which services depend on the Database
    directly or indirectly, who is on which team, what a given person is
    working on.

    This is the right tool whenever the answer is a number, a list drawn from the
    whole graph, or anything that follows relationships between nodes. Pass the
    user's full question as a sentence, not keywords.
    """
    return str(cypher_chain.invoke({"query": question})["result"])


agent = create_agent(
    model=c.chat_model(),
    tools=[search_task_descriptions, query_the_graph],
    system_prompt=(
        "You answer questions about a microservices architecture stored in a "
        "Neo4j knowledge graph.\n\n"
        "Routing rule: if the answer is a count, a ranking, or requires "
        "following relationships between services, teams, people or tasks, use "
        "query_the_graph. If it is about what a task means or describes, use "
        "search_task_descriptions.\n\n"
        "The graph is the only source of truth. If it holds no answer — for "
        "example no team is recorded as maintaining a given service — say so "
        "plainly. Do not fill the gap from general knowledge about "
        "microservices. Name the tool you used."
    ),
)

QUESTIONS = sys.argv[1:] or [
    # Should route to the graph. This is the step 03 question.
    #"How many open tickets are there?",
    # Should route to vector search.
    #"Which tasks are about performance optimization?",
    # Needs step 05's traversal: a fuzzy description as the entry point, then
    # ownership and dependencies as the answer. Neither tool alone gets there.
    #"If the authentication work goes wrong, what else is affected and who owns it?",
    # Graph: two hops, Person -> Team <- Task.
    #"What is Alice working on?",
    # Graph, and the honest answer is "nobody is recorded".
    #"Which team maintains the Database?",
    # Three hops: Task -> Microservice -> Database.
    #
    # Note the wording. An earlier draft asked "what work is *planned* on
    # services that depend on the Database?" and got "the graph contains no
    # answer" — correctly, because no Task has status 'planned'; they are open,
    # in progress or completed. The model wrote a filter on a value that does
    # not exist and honestly reported nothing back.
    #
    # Worth showing if there is time: text2cypher is only as good as the fit
    # between your vocabulary and the graph's. "Planned" is a perfectly natural
    # word that this schema has no idea about.
    #"What tasks are linked to services that depend on the Database?",
    "Which team might need more people?",
]

for q in QUESTIONS:
    print(f"\n{'─' * 78}\n  Q: {q}\n{'─' * 78}")
    result = agent.invoke({"messages": [{"role": "user", "content": q}]})

    for msg in result["messages"]:
        for call in getattr(msg, "tool_calls", None) or []:
            arg = next(iter(call["args"].values()), "")
            print(f"    -> tool: {call['name']}({str(arg)[:70]!r})")

    print(f"\n  A: {c.text_of(result['messages'][-1])}\n")

print("""
  ── The point ──────────────────────────────────────────────────────────────

  Three components: a vector retriever, a text2cypher chain, a router. Roughly
  90 lines, most of which is prose in the tool docstrings.

  Now go and build exactly this in the Aura console without writing any of it.

  Next: make aura   (or open FACILITATOR.md and do step 08 by hand)
""")
