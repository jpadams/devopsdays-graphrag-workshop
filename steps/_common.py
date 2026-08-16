"""Shared setup for every step. Import it, do not run it.

One place for config so that a typo in .env produces one clear error at the top
of the workshop instead of five different confusing ones later.
"""

import logging
import os
import sys

from dotenv import load_dotenv

load_dotenv()

# Neo4j 2026.x reports that db.index.vector.queryNodes is deprecated in favour of
# SEARCH. That call is inside langchain-neo4j, not in anything written here, so
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
    """A Neo4j driver, connectivity already verified."""
    from neo4j import GraphDatabase

    d = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    d.verify_connectivity()
    return d


def graph():
    """LangChain's Neo4jGraph wrapper, used by the text2cypher chain.

    Note the import: `langchain_neo4j`. The 2023 blog post this workshop descends
    from used `langchain_community.graphs`, which is where these classes lived
    before Neo4j's integrations were split into their own package.
    """
    from langchain_neo4j import Neo4jGraph

    return Neo4jGraph(
        url=NEO4J_URI,
        username=NEO4J_USERNAME,
        password=NEO4J_PASSWORD,
        database=NEO4J_DATABASE,
    )


def embeddings():
    from langchain_openai import OpenAIEmbeddings

    return OpenAIEmbeddings(model=EMBEDDING_MODEL)


def chat_model(**kwargs):
    """The chat model, as a LangChain model object.

    Two deliberate choices here, both of which the workshop breaks without.

    `use_responses_api=True` routes to OpenAI's Responses API instead of
    /v1/chat/completions. This is not stylistic. On chat-completions, binding
    function tools while reasoning_effort is set fails outright:

        Function tools with reasoning_effort are not supported for
        gpt-5.6-sol in /v1/chat/completions. To use function tools, use
        /v1/responses or set reasoning_effort to 'none'.

    Step 07 binds tools, so it is Responses API or no reasoning effort. The
    Responses API is where OpenAI's reasoning models are going anyway, so we
    take that fork rather than turning reasoning off.

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
# 05, reused by the agent in step 07, and mirrored almost verbatim as the
# `post_processing_cypher` of the Aura Agent's similarity-search tool in step 08.
# One idea, three places, so keep it in one file.
#
# `node` and `score` are bound by the vector search that ran immediately before.
# langchain-neo4j requires exactly three columns back: text, score, metadata.
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
RETURN
  'task: '                        + node.name +
  ' | status: '                   + node.status +
  ' | description: '              + node.description +
  ' | service: '                  + svc.name +
  ' | service owned by: '         + coalesce(owner.name, 'NOBODY') +
  ' | task assigned to: '         + coalesce(doing.name, 'nobody') +
  ' | breaks if this goes wrong: ' +
     CASE WHEN size(dependents) = 0
          THEN 'nothing depends on it'
          ELSE apoc.text.join(dependents, ', ') END
  AS text,
  score,
  {task: node.name, service: svc.name} AS metadata
"""


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


def cypher_generation_prompt():
    """The Cypher-generation prompt, with one rule added that matters a lot.

    Left to itself, text2cypher answers "What is Alice working on?" with:

        MATCH (p:Person {name:'Alice'})-[:PART_OF]->(:Team)<-[:ASSIGNED_TO]-(t:Task)
        RETURN t.name, t.description, t.status

    That query is correct. It is also missing Alice. The QA step downstream sees
    only the returned rows — three task columns and no person — so a
    well-grounded model has no evidence these tasks are hers and answers
    "I don't know". Which is, annoyingly, the right call on the evidence it was
    given.

    This is a real and common text2cypher failure: the projection drops the
    entity that made the query meaningful. Whether you get away with it depends
    on how strictly your QA model reads its context, which is not something to
    build a live demo on.

    So we tell it to project the identifying properties too. That is also
    exactly what the Cypher *template* in step 04 does by construction — it
    pins its own RETURN clause, and cannot forget.
    """
    from langchain_core.prompts import PromptTemplate

    return PromptTemplate(
        input_variables=["schema", "question"],
        template="""Task: Generate a Cypher statement to query a graph database.

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
{question}""",
    )


def rule(title: str) -> None:
    print(f"\n{'=' * 78}\n  {title}\n{'=' * 78}")
