.PHONY: help install verify load embed vector template hybrid text2cypher agent aura reset all

help:
	@echo ""
	@echo "  DevOpsDays Portland — GraphRAG on a microservices knowledge graph"
	@echo ""
	@echo "  Run these in order:"
	@echo ""
	@echo "    make verify       step 00  check Aura + OpenAI before anything else"
	@echo "    make load         step 01  load the microservices graph"
	@echo "    make embed        step 02  embed task descriptions, build vector index"
	@echo "    make vector       step 03  vector search: any question, fuzzy answer"
	@echo "    make template     step 04  fixed Cypher + params: exact, but predicted"
	@echo "    make hybrid       step 05  vector + Cypher: fuzzy in, exact structure out"
	@echo "    make text2cypher  step 06  the model writes the query; nobody reviewed it"
	@echo "    make agent        step 07  one agent choosing between all of them"
	@echo "    make aura         step 08  the same three tools, no code"
	@echo ""
	@echo "    make reset                 wipe the graph and start over"
	@echo ""

install:
	uv sync

verify:
	uv run steps/00_verify.py

load:
	uv run steps/01_load_graph.py

embed:
	uv run steps/02_embed_tasks.py

vector:
	uv run steps/03_vector_search.py

template:
	uv run steps/04_cypher_template.py

hybrid:
	uv run steps/05_vector_cypher.py

text2cypher:
	uv run steps/06_text2cypher.py

agent:
	uv run steps/07_agent.py

aura:
	uv run steps/08_aura_agent.py

# Everything up to the agent, for a facilitator dry run.
all: verify load embed vector template hybrid text2cypher agent

reset:
	@echo "Deleting all nodes and the vector index..."
	@uv run python -c "import sys; sys.path.insert(0,'steps'); import _common as c; \
d=c.driver(); s=d.session(database=c.NEO4J_DATABASE); \
s.run('MATCH (n) DETACH DELETE n').consume(); \
s.run(f'DROP INDEX {c.VECTOR_INDEX_NAME} IF EXISTS').consume(); \
print('  graph emptied, index dropped'); d.close()"
