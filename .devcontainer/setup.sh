#!/usr/bin/env bash
#
# Runs once, when the Codespace is created (postCreateCommand).
#
# Deliberately does NOT overwrite an existing .env — this script also has to be
# safe to run on a laptop that already has real credentials in it.

set -euo pipefail

cd "$(dirname "$0")/.."

echo
echo "=== installing uv ==========================================="
if command -v uv >/dev/null 2>&1; then
  echo "  uv already present: $(uv --version)"
else
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# Codespaces starts a fresh login shell for the terminal, which will not have
# uv on PATH unless we put it there.
if ! grep -qs 'astral\|\.local/bin' "$HOME/.bashrc" 2>/dev/null; then
  echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
fi
export PATH="$HOME/.local/bin:$PATH"

echo
echo "=== installing dependencies ================================="
# --frozen installs exactly what uv.lock pins and never re-resolves. The lock
# is committed, so every attendee gets the same versions we tested with —
# rather than each of them resolving fresh against PyPI on the day, where one
# yanked release is enough to fail postCreate for the whole room.
uv sync --frozen

echo
echo "=== configuration ==========================================="
# Three ways to be configured, in the order we prefer them:
#
#   1. Codespaces secrets  -> real env vars, nothing to write. Best.
#   2. an existing .env    -> leave it alone. It is probably deliberate.
#   3. neither             -> lay down a .env from the example to fill in.
#
if [ -n "${NEO4J_URI:-}" ] && [ -n "${NEO4J_PASSWORD:-}" ] && [ -n "${OPENAI_API_KEY:-}" ]; then
  echo "  Credentials found in the environment (Codespaces secrets)."
  echo "  No .env needed — env vars take precedence over it anyway."
  if [ -z "${NEO4J_USERNAME:-}" ] || [ -z "${NEO4J_DATABASE:-}" ]; then
    echo
    echo "  WARNING: NEO4J_USERNAME and/or NEO4J_DATABASE are not set, so the"
    echo "  defaults ('neo4j') will be used. That is right for most Aura"
    echo "  instances and wrong for some — a few use the instance id instead,"
    echo "  and the failure just says 'unauthorized'. If 'make verify' cannot"
    echo "  authenticate, set them from your credentials file."
  fi
elif [ -f .env ]; then
  echo "  .env already exists; leaving it untouched."
else
  cp .env.example .env
  echo "  Wrote .env from .env.example. Fill in NEO4J_URI, NEO4J_PASSWORD"
  echo "  and OPENAI_API_KEY before running 'make verify'."
fi

# Optional: the Neo4j CLI, only needed if you want to drive step 08 from the
# terminal instead of the Aura console. Never fail the build over it.
echo
echo "=== neo4j-cli (optional, for step 08) ======================="
if command -v neo4j-cli >/dev/null 2>&1; then
  echo "  already installed"
elif curl -fsSL --max-time 60 https://neo4j.com/cli/install.sh -o /tmp/neo4j-cli.sh 2>/dev/null; then
  sh /tmp/neo4j-cli.sh >/dev/null 2>&1 \
    && echo "  installed" \
    || echo "  skipped (install failed) — the console path in step 08 needs none of this"
else
  echo "  skipped (could not download) — the console path in step 08 needs none of this"
fi

cat <<'BANNER'

================================================================
  Ready.

    make verify     check Aura + OpenAI before anything else
    make            list every step

  If 'make verify' cannot reach Aura, the most likely reason is
  that a free instance paused after 3 idle days. Resume it at
  console.neo4j.io and re-run; verify waits up to 150s for it.
================================================================

BANNER
