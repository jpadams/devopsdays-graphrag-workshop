"""Step 08 — the same agent, no code.

Everything in steps 03-05 exists as a configurable tool inside the Aura console:

    step 04  fixed Cypher + params  ->  Aura Agent "cypher template" tool
    step 05  vector + traversal    ->  "similarity search" + post-processing
    step 06  text2cypher chain     ->  Aura Agent "text2cypher" tool
    step 07  create_agent()        ->  the agent itself, plus its system prompt

The order is not a coincidence: the three tool types Aura offers are the three
you just built by hand, in the same sequence.
             tool docstrings    ->  each tool's description field

The main path for this step is the CONSOLE, by hand — that is the point of the
exercise, and it takes about ten minutes. FACILITATOR.md has the click-through.

This script is the other two paths:

    uv run steps/08_aura_agent.py create   # import the vendored config
    uv run steps/08_aura_agent.py ask "how many open tickets are there?"

`create` is the catch-up path for anyone whose console is misbehaving. `ask` is
the payoff: the agent you just built with no code is an HTTP endpoint, and an
MCP server, without deploying anything.

Requires the Neo4j CLI, authenticated:
    neo4j-cli credential aura-client add ...
    neo4j-cli aura workspace use <org-id>/<project-id>
"""

import json
import subprocess
import sys
from pathlib import Path

import _common as c

CONFIG = Path(__file__).parent.parent / "aura" / "devops-agent.json"


def run(args: list[str]) -> dict:
    proc = subprocess.run(
        ["neo4j-cli", *args, "--format", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        sys.exit(f"\n  neo4j-cli failed:\n{proc.stderr or proc.stdout}\n")
    return json.loads(proc.stdout or "{}")


def dbid() -> str:
    """The Aura instance id — the first 8 chars of the Aura hostname."""
    host = c.NEO4J_URI.split("://")[-1].split(".")[0]
    return host


def create() -> None:
    cfg = json.loads(CONFIG.read_text())

    # Be loud about what this path does NOT give you. Until the vendored config
    # carries a similarity-search tool, an agent created from it can count and
    # traverse but cannot answer "how will the recommendation service be
    # updated?" — and an agent that is quietly missing a tool is worse than one
    # that failed, because it answers anyway.
    types = {t["type"] for t in cfg["tools"]}
    if "vector" not in types and "similaritySearch" not in types:
        print("""
  NOTE: this config has no similarity-search tool, so the agent you are about
  to create will be text2cypher + Cypher template only. It will handle "how
  many open tickets" but not "how will the recommendation service be updated".

  Add the vector tool in the console afterwards — index 'task_embeddings',
  label 'Task', property 'description', model 'text-embedding-3-small'.
  FACILITATOR.md step 08 has the click-through.
""")

    print(f"\n  Creating agent {cfg['name']!r} against instance {dbid()} ...")

    result = run([
        "aura", "agent", "create",
        "--name", cfg["name"],
        "--description", cfg["description"],
        "--dbid", dbid(),
        "--system-prompt", cfg["system_prompt"],
        "--tools", json.dumps(cfg["tools"]),
        "--is-mcp-enabled",
        "--rw",
    ])
    data = result.get("data", result)
    print(f"""
  Created.

    id       {data.get('id')}
    endpoint {data.get('endpoint_link')}
    mcp      {data.get('mcp_endpoint_link')}

  Try it:  uv run steps/08_aura_agent.py ask "how many open tickets are there?"
""")


def ask(question: str) -> None:
    agents = run(["aura", "agent", "list"]).get("data", [])
    cfg = json.loads(CONFIG.read_text())
    match = next((a for a in agents if a["name"] == cfg["name"]), None)
    if not match:
        sys.exit(
            f"\n  No agent named {cfg['name']!r} found.\n"
            f"  Build it in the console (FACILITATOR.md step 08), or run:\n"
            f"      uv run steps/08_aura_agent.py create\n"
        )

    print(f"\n  Q: {question}")
    data = run(
        ["aura", "agent", "invoke", match["id"], "--input", question, "--rw"]
    ).get("data", {})

    # The response is a list of typed blocks — thinking, tool_use, tool_result,
    # text — in the order the agent produced them. Show which tool it reached
    # for and the final answer; the raw tool_result blocks are megabytes of node
    # properties and nobody wants them on a projector.
    blocks = data.get("content", [])
    for name in [b.get("name") for b in blocks if b.get("type") == "tool_use"]:
        if name:
            print(f"    -> tool: {name}")

    answers = [b["text"] for b in blocks if b.get("type") == "text" and b.get("text")]
    print(f"\n  A: {answers[-1].strip() if answers else '(no answer returned)'}\n")


if __name__ == "__main__":
    c.rule("Step 08 — Aura Agent")
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "create":
        create()
    elif cmd == "ask":
        ask(" ".join(sys.argv[2:]) or "How many open tickets are there?")
    else:
        print(__doc__)
