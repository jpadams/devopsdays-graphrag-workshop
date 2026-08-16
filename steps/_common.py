"""Shared setup for every step. Import it, do not run it.

One place for config so that a typo in .env produces one clear error at the top
of the workshop instead of five different confusing ones later.

On the two libraries in play:

  neo4j-graphrag   Neo4j's own GraphRAG package. Every retriever in this
                   workshop comes from here. It talks to the database through
                   the plain driver and imposes no shape on your Cypher.
  langchain        Used for exactly one thing: `create_agent` in step 07, plus
                   the chat model object it needs. Nothing Neo4j-specific.

There is no `langchain-neo4j`. It was here until we found that everything it
provided — Neo4jVector, GraphCypherQAChain, Neo4jGraph — had a first-party
equivalent, and that its `retrieval_query` contract was the reason step 05's
Cypher had to be written twice. See VECTOR_CYPHER_RETRIEVAL below.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Neo4j 2026.x reports that db.index.vector.queryNodes is deprecated in favour of
# SEARCH. That call is inside the retriever, not in anything written here, so
# the notice is three lines of GQL that attendees can read but cannot act on.
# Silence it rather than have people wonder whether they broke something.
# Drop this line if you want to see server-side notifications while debugging.
logging.getLogger("neo4j").setLevel(logging.ERROR)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        sys.exit(
            f"\n  {name} is not set.\n"
            f"  Copy .env.example to .env and fill it in, then re-run.\n"
        )
    return value


NEO4J_URI = _require("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = _require("NEO4J_PASSWORD")
NEO4J_DATABASE = os.getenv("NEO4J_DATABASE", "neo4j")

OPENAI_API_KEY = _require("OPENAI_API_KEY")
# Defaults here must match .env.example. In a Codespace there may be no .env at
# all — secrets arrive as real environment variables and load_dotenv does not
# override those — so these fallbacks are what a secrets-only run actually gets.
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-sol")
OPENAI_REASONING_EFFORT = os.getenv("OPENAI_REASONING_EFFORT", "low")

EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
VECTOR_INDEX_NAME = os.getenv("VECTOR_INDEX_NAME", "task_embeddings")

# The label + property we embed. Aura Agent's vector tool needs to be pointed at
# the same three things (index, label, property), so they live here as constants
# rather than being spelled out inline in four different files.
VECTOR_NODE_LABEL = "Task"
VECTOR_TEXT_PROPERTY = "description"
VECTOR_EMBEDDING_PROPERTY = "embedding"


def driver():
    """A Neo4j driver, connectivity already verified.

    Every retriever in this workshop takes this object directly. There is no
    wrapper class in between, which is why there is no second set of connection
    settings to keep in sync.
    """
    from neo4j import GraphDatabase

    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    d.verify_connectivity()
    return d


def schema(d=None) -> str:
    """The live graph schema as a string, for the text2cypher prompt.

    Replaces LangChain's Neo4jGraph.refresh_schema(). Same idea — introspect the
    database and describe it to the model — without needing a graph wrapper
    object whose only other job was holding the connection settings again.
    """
    from neo4j_graphrag.schema import get_schema

    own = d is None
    d = d or driver()
    try:
        return get_schema(d)
    finally:
        if own:
            d.close()


def embeddings():
    """LangChain's embedder — used ONLY by step 02, for its batch call.

    `embed_documents` embeds the whole list in one request. neo4j-graphrag's
    embedder exposes `embed_query` only, so building the index with it would be
    ten sequential HTTP calls to make a point about package purity. Not worth it.
    """
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def embedder():
    """neo4j-graphrag's embedder — used by every retriever.

    Same model as `embeddings()` above, so the vectors it produces at query time
    land in the same space as the ones step 02 wrote. That is not a coincidence
    you should rely on silently: both read EMBEDDING_MODEL, which is pinned in
    .env because Aura Agent only accepts three OpenAI embedding models.
    """
    from neo4j_graphrag.embeddings import OpenAIEmbeddings

    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def graphrag_llm(**kwargs):
    """The LLM object neo4j-graphrag's retrievers take.

    `model_params` is passed straight through to the OpenAI call, which is how
    reasoning_effort gets set. Note this is the plain completion path — these
    retrievers generate Cypher, they do not bind function tools — so the
    chat-completions restriction that forces `use_responses_api` in
    `chat_model()` below does not apply here.
    """
    from neo4j_graphrag.llm import OpenAILLM

    params = dict(kwargs)
    if OPENAI_REASONING_EFFORT:
        params.setdefault("reasoning_effort", OPENAI_REASONING_EFFORT)
    return OpenAILLM(model_name=OPENAI_MODEL, model_params=params)


def chat_model(**kwargs):
    """The chat model as a LangChain object, for step 07's agent.

    `use_responses_api=True` routes to OpenAI's Responses API instead of
    /v1/chat/completions. This is not stylistic. On chat-completions, binding
    function tools while reasoning_effort is set fails outright:

        Function tools with reasoning_effort are not supported for
        gpt-5.6-sol in /v1/chat/completions. To use function tools, use
        /v1/responses or set reasoning_effort to 'none'.

    Step 07 binds tools, so it is Responses API or no reasoning effort. This is
    also exactly why the agent layer stayed on LangChain: neo4j-graphrag's own
    tool-calling path is chat-completions only, and would hit the error above.
    Its retrievers never bind tools, so they are unaffected — see graphrag_llm.

    `reasoning_effort` is pinned low — a high-effort reasoning model in a live
    workshop is a room full of people watching a spinner. See .env.example.
    """
    from langchain.chat_models import init_chat_model

    params = {
        "model_provider": "openai",
        "use_responses_api": True,
        **kwargs,
    }
    if OPENAI_REASONING_EFFORT:
        params.setdefault("reasoning_effort", OPENAI_REASONING_EFFORT)
    return init_chat_model(OPENAI_MODEL, **params)


# The traversal that turns a vector hit into a graph answer. Introduced in step
# 05, reused by the agent in step 07, and pasted verbatim as the
# `post_processing_cypher` of the Aura Agent's similarity-search tool in step 08.
#
# "Verbatim" is now literally true. Until recently this file held a different
# spelling of the same traversal: LangChain's Neo4jVector required the query to
# return exactly three columns — text, score, metadata — so every field had to be
# concatenated into one string with ' | ' separators, and apoc.text.join was
# needed to flatten the dependents list. Aura wants ordinary named columns, so
# the workshop maintained two versions of one idea and called them a mirror.
#
# neo4j-graphrag's VectorCypherRetriever imposes no column contract. So this is
# the Aura string, unchanged, and it no longer needs APOC.
#
# `node` and `score` are bound by the vector search that runs immediately before.
VECTOR_CYPHER_RETRIEVAL = """
MATCH (node)-[:LINKED_TO]->(svc:Microservice)
OPTIONAL MATCH (svc)-[:MAINTAINED_BY]->(owner:Team)
OPTIONAL MATCH (node)-[:ASSIGNED_TO]->(doing:Team)
WITH node, score, svc, owner, doing,
     COLLECT {
       MATCH (d:Microservice)-[:DEPENDS_ON]->(svc)
       OPTIONAL MATCH (d)-[:MAINTAINED_BY]->(dteam:Team)
       RETURN d.name + ' (owned by ' + coalesce(dteam.name, 'NOBODY') + ')'
     } AS dependents
RETURN node.name AS task, node.status AS status, node.description AS text, score,
       svc.name AS service,
       coalesce(owner.name, 'NOBODY') AS service_owned_by,
       coalesce(doing.name, 'nobody') AS task_assigned_to,
       dependents AS services_that_would_break
"""


# The simplest retrieval query there is: return the matched node's own
# properties and stop. No traversal, no relationships. Step 03 uses it to show
# what vector search gives you alone, and step 05 uses it as the "before" half
# of its comparison — so it lives here rather than being written twice.
PLAIN_RETRIEVAL = """
RETURN node.name AS name, node.description AS description,
       node.status AS status, score
"""


def plain_result(record):
    """One row of PLAIN_RETRIEVAL -> one 'document', as the model receives it."""
    from neo4j_graphrag.types import RetrieverResultItem

    return RetrieverResultItem(
        content=(
            f"name: {record.get('name')}\n"
            f"description: {record.get('description')}\n"
            f"status: {record.get('status')}"
        ),
        metadata={
            "name": record.get("name"),
            "status": record.get("status"),
            "score": record.get("score"),
        },
    )


def enriched_result(record):
    """Turn one row of VECTOR_CYPHER_RETRIEVAL into text for the model.

    A `result_formatter` is the seam LangChain's three-column contract did not
    have: the Cypher returns real columns, and the shaping into prose happens
    here in Python where you can read it. Aura does this step for you, which is
    why its tool config is just the Cypher.
    """
    from neo4j_graphrag.types import RetrieverResultItem

    breaks = record.get("services_that_would_break") or []
    return RetrieverResultItem(
        content=(
            f"task: {record.get('task')}"
            f" | status: {record.get('status')}"
            f" | description: {record.get('text')}"
            f" | service: {record.get('service')}"
            f" | service owned by: {record.get('service_owned_by')}"
            f" | task assigned to: {record.get('task_assigned_to')}"
            f" | breaks if this goes wrong: "
            f"{', '.join(breaks) if breaks else 'nothing depends on it'}"
        ),
        metadata={
            "task": record.get("task"),
            "service": record.get("service"),
            "score": record.get("score"),
        },
    )


def text_of(message) -> str:
    """Plain text out of a message.

    The Responses API returns `content` as a list of typed blocks, not a string,
    so printing `.content` gives you a wall of JSON with ids and annotations in
    it. `.text` flattens that; the fallbacks cover older message shapes.
    """
    content = getattr(message, "content", message)
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(
            b.get("text", "") for b in content if isinstance(b, dict)
        ).strip()
    return str(content).strip()


# The Cypher-generation prompt, with one rule added that matters a lot.
#
# Left to itself, text2cypher answers "What is Alice working on?" with:
#
#     MATCH (p:Person {name:'Alice'})-[:PART_OF]->(:Team)<-[:ASSIGNED_TO]-(t:Task)
#     RETURN t.name, t.description, t.status
#
# That query is correct. It is also missing Alice. Whatever reads the rows
# downstream — the answer-generation model in step 06, the agent in step 07 —
# sees three task columns and no person, so a well-grounded model has no evidence
# these tasks are hers and answers "I don't know". Which is, annoyingly, the
# right call on the evidence it was given.
#
# This is a real and common text2cypher failure: the projection drops the entity
# that made the query meaningful. Worth deleting live to show the failure.
#
# Note the placeholders. neo4j-graphrag's Text2CypherRetriever formats
# `{schema}`, `{examples}` and `{query_text}` — not `{question}`. And when you
# pass a custom prompt it stops fetching the schema for you, so the caller has to
# hand it in explicitly. See step 06.
CYPHER_PROMPT = """Task: Generate a Cypher statement to query a graph database.

Instructions:
Use only the provided relationship types and properties in the schema.
Do not use any other relationship types or properties that are not provided.

Always RETURN the properties that identify the entities named in the question,
not only the properties being asked about. Whatever consumes your results sees
the returned rows and nothing else — if the question names a person, a team or a
service, that name must appear in the output.

Schema:
{schema}

Note: Do not include any explanations or apologies in your responses.
Do not respond to any questions that might ask anything else than for you to
construct a Cypher statement. Do not include any text except the generated
Cypher statement.

Example:
Question: What is Bob working on?
MATCH (p:Person {{name: 'Bob'}})-[:PART_OF]->(team:Team)<-[:ASSIGNED_TO]-(t:Task)
RETURN p.name AS person, team.name AS team, t.name AS task,
       t.status AS status, t.description AS description

The question is:
{query_text}"""


# The prompt that turns returned rows into a sentence.
#
# This one is load-bearing, and the failure it prevents is a good demo. The
# default answer-generation prompt in neo4j-graphrag is deliberately bare —
# "Context: ... Question: ... Answer:" — with nothing that tells the model where
# the context came from. Ask "which services depend on Database indirectly?"
# under that prompt and the model gets four perfectly correct rows back and
# replies "None. All listed services depend on Database directly." It doubted
# the data and preferred its own instincts about how microservices work.
#
# The Cypher was right. The retrieval was right. The answer was wrong, because
# nobody told the model the rows were authoritative. LangChain's QA chain shipped
# that instruction by default, which is why this failure does not appear until
# you replace it — worth knowing if you are porting something.
#
# RagTemplate requires all three of {context}, {query_text} and {examples}; it
# raises PromptMissingPlaceholderError if you leave one out, even an unused one.
ANSWER_PROMPT = """You are answering a question about a microservices
architecture using rows returned from a Neo4j knowledge graph.

The context below is the authoritative result of a query written for this exact
question. Treat it as fact. Do not second-guess it against your own knowledge of
how microservices usually work, and do not conclude the rows are wrong because
they are not what you expected — if a row came back, it satisfied the query.

If the context is empty, say plainly that the graph holds no answer. Do not fill
the gap from general knowledge.

Context:
{context}

Examples:
{examples}

Question:
{query_text}

Answer:"""


def answer_prompt():
    """ANSWER_PROMPT wrapped as the RagTemplate object GraphRAG requires.

    GraphRAG type-checks this argument, so a bare string raises
    RagInitializationError. The text stays a plain constant above because that
    is the part worth reading.
    """
    from neo4j_graphrag.generation.prompts import RagTemplate

    return RagTemplate(template=ANSWER_PROMPT)


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n  {title}\n{'=' * 78}")
