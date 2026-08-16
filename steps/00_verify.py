"""Step 00 — prove the plumbing works before 40 people are watching.

Checks, in order:
  1. .env is filled in
  2. Neo4j Aura is reachable and we can read from it
  3. the OpenAI key works
  4. the model ID in .env is one your key can actually see
  5. the embedding model works, and reports its real dimension

Run this the moment you sit down. Every failure here is a five-minute fix at
09:00 and a dead workshop at 09:35.

    uv run steps/00_verify.py
"""

import sys

import _common as c

ok = True


def check(label: str, fn):
    global ok
    print(f"  {label:.<52}", end=" ", flush=True)
    try:
        detail = fn()
        print(f"ok  {detail or ''}")
        return True
    except Exception as e:  # noqa: BLE001 — this is a diagnostic, we want them all
        print("FAILED")
        print(f"      -> {type(e).__name__}: {e}")
        ok = False
        return False


c.rule("Step 00 — preflight")

print(f"\n  Aura instance : {c.NEO4J_URI}")
print(f"  chat model    : {c.OPENAI_MODEL}  (reasoning_effort={c.OPENAI_REASONING_EFFORT})")
print(f"  embedding     : {c.EMBEDDING_MODEL}")
print(f"  vector index  : {c.VECTOR_INDEX_NAME}\n")


def _neo4j():
    """Wait for the instance rather than failing on the first refused connection.

    A just-created Aura Free instance takes a few minutes to come up, and an
    idle one pauses after 3 days and has to be resumed. Both look identical from
    here — a connection that fails now and works shortly. So retry for a couple
    of minutes with a visible countdown instead of making people re-run this.
    """
    import time

    from neo4j.exceptions import AuthError, ClientError

    deadline = time.monotonic() + 150
    attempt = 0
    while True:
        attempt += 1
        try:
            d = c.driver()
            with d.session(database=c.NEO4J_DATABASE) as s:
                n = s.run("MATCH (n) RETURN count(n) AS n").single()["n"]
            d.close()
            if attempt > 1:
                # We printed a progress line; re-print the label so the "ok"
                # lands in the same column as every other check.
                print(f"\n  {'Neo4j Aura reachable (came up)':.<52}", end=" ")
            return f"({n} nodes — 0 is fine before step 01)"
        except (AuthError, ClientError) as e:
            # Never retry these. A wrong username is wrong on the 30th attempt
            # too, and hammering the endpoint for 150 seconds is a good way to
            # get auth-throttled on top of the original problem.
            #
            # The username trap is worth naming explicitly: it is NOT always
            # "neo4j". Some Aura instances use the instance id (the 8 characters
            # in the hostname) as both the username and the database name, and
            # the resulting failure just says "unauthorized".
            host = c.NEO4J_URI.split("://")[-1].split(".")[0]
            raise RuntimeError(
                f"{type(e).__name__}: could not authenticate.\n"
                f"      Check NEO4J_USERNAME and NEO4J_DATABASE against the\n"
                f"      credentials file Aura gave you — copy all four values\n"
                f"      verbatim rather than assuming any of them.\n"
                f"      Currently trying username={c.NEO4J_USERNAME!r}, "
                f"database={c.NEO4J_DATABASE!r}.\n"
                f"      For this instance the other candidate is {host!r}."
            ) from e
        except Exception:
            if time.monotonic() >= deadline:
                raise
            if attempt == 1:
                print("\n      instance not answering yet — waiting up to 150s", end="")
            print(".", end="", flush=True)
            time.sleep(5)


check("Neo4j Aura reachable", _neo4j)


def _apoc():
    """Steps 04 and 05 need APOC.

    LangChain's Neo4jGraph.refresh_schema() introspects the graph via
    apoc.meta.data(). Aura bundles APOC Core, so this passes there — but if you
    point NEO4J_URI at a plain local Neo4j container it will not, and the failure
    surfaces two steps later as a wall of traceback rather than a missing plugin.
    """
    d = c.driver()
    with d.session(database=c.NEO4J_DATABASE) as s:
        s.run("CALL apoc.meta.data() YIELD label RETURN label LIMIT 1").consume()
    d.close()
    return ""


check("APOC available (needed by steps 04/05)", _apoc)


def _openai_key():
    from openai import OpenAI

    models = OpenAI(api_key=c.OPENAI_API_KEY).models.list()
    return f"({len(list(models.data))} models visible)"


key_ok = check("OpenAI key valid", _openai_key)


def _chat():
    """The one check worth having.

    Model IDs churn faster than workshop material, so OPENAI_MODEL is a knob and
    this is what proves the knob is set to something real.

    Note that we test it by *calling* it rather than by looking it up in
    models.list(). Those disagree: `gpt-5.6` is a working alias that resolves to
    `gpt-5.6-sol`, but the bare alias is absent from the model list. Checking
    membership therefore rejects working configurations — which, at 09:00 with a
    room waiting, is a worse failure than not checking at all.

    So: make a real call. If it fails, then go and ask what is available.
    """
    try:
        reply = c.chat_model().invoke("Reply with the single word: ready")
        # The Responses API returns a list of content blocks rather than a bare
        # string, so go through .text rather than .content.
        text = getattr(reply, "text", None) or str(reply.content)
        return f"({text.strip()[:20]!r})"
    except Exception as e:
        if "model_not_found" not in str(e) and "does not exist" not in str(e):
            raise
        from openai import OpenAI

        ids = sorted(
            m.id
            for m in OpenAI(api_key=c.OPENAI_API_KEY).models.list().data
            if m.id.startswith("gpt-5") and not m.id[-1].isdigit()
        )
        raise RuntimeError(
            f"OPENAI_MODEL={c.OPENAI_MODEL!r} was rejected by the API.\n"
            f"      Set OPENAI_MODEL in .env to one of:\n"
            + "\n".join(f"        {i}" for i in ids[:12])
        ) from e


if key_ok:
    check(f"chat model works ({c.OPENAI_MODEL})", _chat)


def _embed():
    """Verify the embedding dimension from a real call rather than assuming 1536.

    Step 02 creates the vector index with whatever this reports. Assuming the
    dimension and being wrong gives you an index that silently returns nothing.
    """
    vec = c.embeddings().embed_query("hello")
    return f"({len(vec)} dimensions)"


if key_ok:
    check("embedding model responds", _embed)

if ok:
    print("\n  All good. Run: make load\n")
else:
    print("\n  Fix the above before continuing. See PREWORK.md.\n")
    sys.exit(1)
