# Before the workshop — about 15 minutes

Ideally do this **before** you arrive or as you're waiting for the session to
kick off. It is all account signup and waiting for things to provision.

If you get stuck, come 10 minutes early and find me. If something is broken on
the day, there is a fallback for every step below, so come anyway.

---

## 1. A free Neo4j Aura instance

1. Sign up at **[console.neo4j.io](https://console.neo4j.io)** (free, no card).
2. Create a new instance → choose **AuraDB Free**.
3. **Download the credentials file when it offers.** That `.txt` is the only
   time Aura shows you the password. If you lose it you have to reset the
   instance.
4. Wait for the status to go from *creating* to *running* — a few minutes.

You should end up with something like:

```
NEO4J_URI=neo4j+s://a1b2c3d4.databases.neo4j.io
NEO4J_USERNAME=neo4j # (or maybe a1b2c3d4)
NEO4J_PASSWORD=<a long random string>
NEO4J_DATABASE=neo4j
```

> **Copy all four verbatim — do not assume the username.** It is usually
> `neo4j`, but some instances use the instance id (the 8 characters at the
> start of the hostname) as both the username and the database name. When that
> happens the only error you get is *"the client is unauthorized"*, which reads
> like a wrong password and sends you hunting in the wrong place. `make verify`
> catches this specifically and tells you the other value to try.

> **Free instances pause after 3 days idle and are deleted after 30.** If you set
> this up well in advance, just check it is still running the night before.

## 2. Turn on Aura Agent

This is the part people miss, and it is an **organization-level** setting, not an
instance one. Step 06 does not work without it.

In the Aura console:

1. **Organization settings** (top-left org switcher → *Settings*)
2. Enable **Generative AI assistance**
3. Enable **Aura Agent** (it only appears once GenAI assistance is on)
4. Enable **tool authentication** for your project

You need the **project admin** role to create agents. On a personal account you
already have it. If you are using a company Aura org, you may not — in that
case make a personal free account for the workshop instead.

## 3. An OpenAI API key

1. Get a key at **[platform.openai.com/api-keys](https://platform.openai.com/api-keys)**
2. **Set a spend limit.** Billing → Limits → set $5. The workshop uses a few
   cents; the limit is so a stray loop cannot cost you real money.

You need a small amount of credit on the account — a brand-new key with a $0
balance returns a quota error on the first call. $5 is plenty.

> **Forgot, or your card was declined?** There is a shared workshop key on a
> slide at the start of the session. It has a hard cap and gets revoked
> afterwards. Use it and don't worry about it — but if you can bring your own,
> please do, because 40 people through one key means rate limits.

## 4. Somewhere to run it — pick one

### Option A: GitHub Codespaces (recommended, nothing to install)

Click **Code → Codespaces → Create codespace on main** in the repo. The
container installs Python, `uv` and every dependency for you, and takes about
two minutes.

It will offer to store your credentials as Codespaces secrets during creation.
Fill in all five (`NEO4J_URI`, `NEO4J_USERNAME`, `NEO4J_PASSWORD`,
`NEO4J_DATABASE`, `OPENAI_API_KEY`) and you never need a `.env` file — the
workshop reads real environment variables in preference to one.

Prefer pasting a `.env`? Skip the secrets prompts; the container writes a
`.env` template for you to fill in. Both work.

Codespaces is free for personal accounts up to a monthly hour allowance, and
this workshop uses about two of those hours. **Stop the codespace when we
finish** so it does not idle against your quota.

### Option B: your own laptop

```bash
git clone https://github.com/jpadams/devopsdays-graphrag-workshop.git
cd devopsdays-graphrag-workshop
curl -LsSf https://astral.sh/uv/install.sh | sh   # if you don't have uv
make install
```

`uv` handles the Python version itself, so you do not need a particular one
installed. On Windows, use WSL or
`powershell -c "irm https://astral.sh/uv/install.ps1 | iex"`.

## 5. The Neo4j CLI (optional — step 06 only)

Only needed if you want to drive Aura Agent from the terminal rather than the
console. The console path needs none of this.

```bash
curl -fsSL https://neo4j.com/cli/install.sh | sh
neo4j-cli credential aura-client add   # needs an Aura API key from the console
```

---

## Check it works

On a laptop, or in a Codespace where you skipped the secrets:

```bash
cp .env.example .env
# fill in all four NEO4J_* from your credentials file, and OPENAI_API_KEY
make verify
```

In a Codespace with secrets set, there is nothing to copy — just:

```bash
make verify
```

You want all five green:

```
  Neo4j Aura reachable................................ ok  (0 nodes — 0 is fine before step 01)
  APOC available (needed by steps 04/05).............. ok
  OpenAI key valid.................................... ok  (132 models visible)
  chat model works (gpt-5.6-sol)...................... ok  ('ready')
  embedding model responds............................ ok  (1536 dimensions)

  All good. Run: make load
```

Zero nodes is correct at this point — you have not loaded anything yet.

If **chat model works** fails, the API rejected `OPENAI_MODEL`; the check then
prints the model IDs your key can use, so copy one into `.env`. Model IDs move
faster than workshop material — they changed twice while this was being written,
which is exactly why this is a checked setting rather than a hardcoded constant.

> The check calls the model rather than looking it up in a list, because those
> two disagree: `gpt-5.6` is callable but does not appear in `models.list()`.
> Trusting the list would reject configurations that work perfectly.

If **Neo4j Aura reachable** hangs for a bit, that is fine and deliberate — it
retries for up to 150 seconds so a still-starting or paused instance gets a
chance to wake up rather than failing instantly.

**That is it.** Do not run `make load` yet — we do that together.
