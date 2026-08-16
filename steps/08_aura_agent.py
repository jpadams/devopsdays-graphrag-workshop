"""Step 08 — the same agent, no code.

Everything in steps 04-07 exists as a configurable tool inside the Aura console:

    step 04  fixed Cypher + params  ->  Aura Agent "cypher template" tool
    step 05  vector + traversal     ->  "similarity search" + post-processing
    step 06  text2cypher retriever  ->  Aura Agent "text2cypher" tool
    step 07  create_agent()         ->  the agent itself, plus its system prompt
             tool docstrings        ->  each tool's description field

The order is not a coincidence: the three tool types Aura offers are the three
you just built by hand, in the same sequence.

Step 05's traversal needs no adaptation to get here. `VECTOR_CYPHER_RETRIEVAL`
in _common.py and `config.post_processing_cypher` in aura/devops-agent.json are
the same string, character for character — paste it across unchanged.

The main path for this step is the CONSOLE, by hand — that is the point of the
exercise, and it takes about ten minutes. FACILITATOR.md has the click-through.

This script is the other two paths:

    uv run steps/08_aura_agent.py create   # import the vendored config
    uv run steps/08_aura_agent.py ask "how many open tickets are there?"

`create` is the catch-up path for anyone whose console is misbehaving. `ask` is
the payoff: the agent you just built with no code answers over the API, with no
deployment, no server and no application code — just the config you filled in.

`create` makes the agent PRIVATE. Aura can also expose it as a public HTTP
endpoint and an MCP server, which is the more impressive demo and a paid one —
roughly $0.35/hour, card required. That is the wrong default for a room on
AuraDB Free, so it is opt-in:

    uv run steps/08_aura_agent.py create --external

Facilitators with an account that can absorb it may want to run that once, show
the MCP endpoint, and delete it afterwards:

    neo4j-cli aura agent delete <id> --rw

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


def find(name: str) -> dict | None:
    """The agent record from `agent list`, which carries the endpoint links."""
    agents = run(["aura", "agent", "list"]).get("data", [])
    return next((a for a in agents if a["name"] == name), None)


def create(external: bool = False) -> None:
    """Build the agent from the vendored config.

    Private by default, and that default is load-bearing. An agent created with
    external access — a public HTTP endpoint and an MCP server — bills at about
    $0.35/hour and needs a card on file. Attendees are on AuraDB Free, following
    a PREWORK that promises the workshop costs nothing beyond an OpenAI key, so
    the default has to be the free one.

    Know what private costs you, though: a private agent cannot be invoked
    through the API at all. `neo4j-cli aura agent invoke` returns

        agent invocation forbidden: agent may be disabled or private

    so the `ask` path below does NOT work against it. A private agent is usable
    from the console's chat panel and nowhere else, which is fine — the console
    is the main path for this step and the one attendees are meant to follow.

    Vocabulary, because the two halves disagree: this API flag is `is_private`,
    while the console calls the same setting **Internal** ("Available to members
    of this Aura project", marked Free) as against **External** ("Provided via an
    auto-generated endpoint", $0.35/hour). Internal is the default for a new
    agent, and the Enable MCP server toggle stays greyed out until you leave it.

    If you specifically want `ask`, or the MCP demo, that is `--external` and it
    is the paid tier. There is no free configuration that answers over the API.
    """
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

    args = [
        "aura", "agent", "create",
        "--name", cfg["name"],
        "--description", cfg["description"],
        "--dbid", dbid(),
        "--system-prompt", cfg["system_prompt"],
        "--tools", json.dumps(cfg["tools"]),
        "--rw",
    ]
    if external:
        print("""
  Creating with EXTERNAL access: a public endpoint and MCP server.
  This is a paid feature — roughly $0.35/hour for as long as the agent exists,
  and it requires a card on the account. Delete the agent when you are done:

      neo4j-cli aura agent delete <id> --rw
""")
        args.append("--is-mcp-enabled")
    else:
        args.append("--is-private")

    result = run(args)
    data = result.get("data", result)

    # The create response carries the id but not the endpoint links — those only
    # appear on the list record, so read them back rather than printing None.
    created = find(cfg["name"]) or data

    print(f"""
  Created.

    id       {created.get('id') or data.get('id')}
    access   {'external — public endpoint + MCP, billed hourly'
              if external else 'private (free) — invoke with your own credentials'}""")

    if external:
        print(f"""    endpoint {created.get('endpoint_link', '(not reported)')}
    mcp      {created.get('mcp_endpoint_link', '(not reported)')}""")

    if external:
        print("""
  Try it:  uv run steps/08_aura_agent.py ask "how many open tickets are there?"
""")
    else:
        print("""
  Chat with it in the console: Aura -> Agents -> DevOps Graph Agent.

  Note `ask` will NOT work against a private agent — the API refuses to invoke
  one. That is the trade for it being free. If you need the API or the MCP
  endpoint, delete this and re-create with --external (paid, ~$0.35/hour).
""")


def ask(question: str) -> None:
    cfg = json.loads(CONFIG.read_text())
    match = find(cfg["name"])
    if not match:
        sys.exit(
            f"\n  No agent named {cfg['name']!r} found.\n"
            f"  Build it in the console (FACILITATOR.md step 08), or run:\n"
            f"      uv run steps/08_aura_agent.py create\n"
        )

    # Fail with the actual reason. The CLI's own message for this is "agent
    # invocation forbidden: agent may be disabled or private", which sends people
    # looking for a permissions problem they do not have.
    if match.get("is_private"):
        sys.exit(
            f"\n  {cfg['name']!r} has Internal access (the console's word for\n"
            f"  what the API calls private), and an Internal agent cannot be\n"
            f"  invoked through the API — only chatted with in the console.\n\n"
            f"  That is the free tier and the right setting for a workshop, so\n"
            f"  this is expected, not a permissions problem.\n\n"
            f"  Either chat with it in the console (Aura -> Agents), or switch to\n"
            f"  External access, which is billed at about $0.35/hour:\n\n"
            f"      neo4j-cli aura agent delete {match.get('id')} --rw\n"
            f"      uv run steps/08_aura_agent.py create --external\n"
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
        create(external="--external" in sys.argv)
    elif cmd == "ask":
        ask(" ".join(sys.argv[2:]) or "How many open tickets are there?")
    else:
        print(__doc__)
