"""Everything that touches the model or reads the schema lives here.

Two reasons this is its own module:
  * the schema is read from the live database, never hand-typed into a prompt,
    so the agent can't drift out of sync with the tables;
  * swapping model providers means editing one file.
"""

from __future__ import annotations

import os
import sqlite3
import sys
from getpass import getpass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------------------------------
# Provider configuration. Everything here is driven by environment variables
# so the project can be pointed at a different LLM without code changes.
#
#   LLM_PROVIDER   anthropic (default) | openai | bedrock | vertex
#   LLM_MODEL      model id for that provider
#   LLM_BASE_URL   optional, for gateways and proxies (LiteLLM, OpenRouter,
#                  vLLM, an internal endpoint)
#   LLM_API_KEY    optional; provider-specific vars below are used otherwise
# --------------------------------------------------------------------------
PROVIDER = os.getenv("LLM_PROVIDER", "anthropic").strip().lower()
BASE_URL = os.getenv("LLM_BASE_URL") or None

DEFAULT_MODELS = {
    "anthropic": "claude-sonnet-5",
    "openai": "gpt-4o",
    "bedrock": "anthropic.claude-3-5-sonnet-20241022-v2:0",
    "vertex": "claude-3-5-sonnet-v2@20241022",
}
MODEL = (
    os.getenv("LLM_MODEL")
    or os.getenv("ANTHROPIC_MODEL")           # kept for backwards compatibility
    or DEFAULT_MODELS.get(PROVIDER, "claude-sonnet-5")
)

# Which environment variable holds the key, per provider.
KEY_VARS = {
    "anthropic": "ANTHROPIC_API_KEY",
    "openai": "OPENAI_API_KEY",
}

DB_PATH = Path(__file__).parent.parent / "bookstore.db"

SQL_SYSTEM = """You translate questions about a bookstore into SQLite queries.

Rules:
- Return ONE SQLite SELECT statement and nothing else. No prose, no markdown
  fences, no trailing semicolon.
- Use only the tables and columns in the schema you are given.
- Revenue is always SUM(order_items.quantity * order_items.unit_price).
  Never use books.price for revenue: it is the current list price, while
  unit_price is what the customer actually paid and may be discounted.
- Dates are ISO text (YYYY-MM-DD); compare them as strings.
- Give computed columns a readable alias, e.g. AS total_revenue.
- Round money to 2 decimal places.
- If the question is ambiguous, choose the most common interpretation rather
  than asking a question: a human reviews your query before it runs."""

SUMMARY_SYSTEM = """You explain query results to a bookstore manager.

Write 2-4 plain sentences answering the question directly, quoting the key
figures from the rows. No preamble, no markdown headings, no bullet points.
If the result set is empty, say so plainly and suggest what might be missing."""


SERVICE = "ask-the-bookstore"
ACCOUNT = f"{PROVIDER}-api-key"

# Resolved once per process. Without this the key is re-requested for every
# API call, which means two prompts in a single run.
_CACHED_KEY: str | None = None
_CACHED_CLIENT: Anthropic | None = None


def resolve_api_key() -> str:
    """Find the API key, in order of preference.

    1. ANTHROPIC_API_KEY in the environment (shell profile, CI secret, .env)
    2. the OS keychain, if `keyring` is installed
    3. an interactive prompt, with the option to save to the keychain

    The key is never written into the project folder by any of these paths.
    The result is cached for the life of the process, so you are asked at
    most once per run.
    """
    global _CACHED_KEY
    if _CACHED_KEY:
        return _CACHED_KEY

    key = os.getenv("LLM_API_KEY") or os.getenv(KEY_VARS.get(PROVIDER, ""), "")
    if key:
        _CACHED_KEY = key
        return key

    try:
        import keyring

        key = keyring.get_password(SERVICE, ACCOUNT)
        if key:
            _CACHED_KEY = key
            return key
    except ImportError:
        keyring = None  # type: ignore[assignment]

    if not sys.stdin.isatty():
        raise RuntimeError(
            f"No API key found and no terminal to ask on. Set "
            f"{KEY_VARS.get(PROVIDER, 'LLM_API_KEY')}, or run "
            f"`python setup_key.py` to store one in your OS keychain."
        )

    print(f"\n  No API key found for provider '{PROVIDER}'.")
    if PROVIDER == "anthropic":
        print("  Get one at https://console.anthropic.com/settings/keys")
    key = getpass("  Paste your key (it will not be echoed): ").strip()
    if not key:
        raise RuntimeError("No key entered.")

    if keyring is not None:
        answer = input("  Save it to your OS keychain for next time? [y/N] ")
        if answer.strip().lower().startswith("y"):
            keyring.set_password(SERVICE, ACCOUNT, key)
            print("  Saved. It will be picked up automatically from now on.")
        else:
            print("  Not saved. It will be used for this run only.")

    _CACHED_KEY = key
    return key


def _client():
    """Build the provider client once and reuse it."""
    global _CACHED_CLIENT
    if _CACHED_CLIENT is not None:
        return _CACHED_CLIENT

    if PROVIDER == "anthropic":
        from anthropic import Anthropic

        kwargs = {"api_key": resolve_api_key()}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        _CACHED_CLIENT = Anthropic(**kwargs)

    elif PROVIDER == "openai":
        # Covers OpenAI itself and anything speaking its API: Azure OpenAI via
        # a gateway, OpenRouter, LiteLLM, vLLM, most internal proxies.
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError(
                "LLM_PROVIDER=openai needs the openai package: pip install openai"
            ) from exc
        kwargs = {"api_key": resolve_api_key()}
        if BASE_URL:
            kwargs["base_url"] = BASE_URL
        _CACHED_CLIENT = OpenAI(**kwargs)

    elif PROVIDER == "bedrock":
        # Uses the standard AWS credential chain; no API key needed.
        from anthropic import AnthropicBedrock

        _CACHED_CLIENT = AnthropicBedrock(
            aws_region=os.getenv("AWS_REGION", "us-east-1")
        )

    elif PROVIDER == "vertex":
        from anthropic import AnthropicVertex

        _CACHED_CLIENT = AnthropicVertex(
            region=os.getenv("GOOGLE_CLOUD_REGION", "us-east5"),
            project_id=os.getenv("GOOGLE_CLOUD_PROJECT"),
        )

    else:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{PROVIDER}'. "
            f"Choose one of: {', '.join(DEFAULT_MODELS)}."
        )

    return _CACHED_CLIENT


def _complete(system: str, prompt: str, max_tokens: int) -> str:
    """One completion, whichever provider is configured.

    Both API shapes are simple enough that a small adapter beats pulling in a
    framework: Anthropic takes `system` as its own argument, OpenAI takes it
    as the first message.
    """
    client = _client()

    if PROVIDER in ("anthropic", "bedrock", "vertex"):
        response = client.messages.create(
            model=MODEL,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(b.text for b in response.content if b.type == "text").strip()

    response = client.chat.completions.create(
        model=MODEL,
        max_tokens=max_tokens,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
    )
    return (response.choices[0].message.content or "").strip()


def get_schema(db_path: Path = DB_PATH) -> str:
    """Read the real CREATE TABLE statements out of the database.

    The comments in seed.py's schema come along for free and act as
    documentation for the model."""
    if not db_path.exists():
        raise FileNotFoundError(
            f"{db_path.name} not found. Run `python seed.py` first."
        )
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    conn.close()
    return "\n\n".join(r[0] for r in rows)


def generate_sql(question: str, schema: str, feedback: str | None = None) -> str:
    """Ask the model for a query. `feedback` carries the reason a previous
    attempt was rejected -- by the guards or by the human -- so the retry is
    informed rather than a blind re-roll."""
    prompt = f"Schema:\n{schema}\n\nQuestion: {question}"
    if feedback:
        prompt += (
            f"\n\nYour previous attempt was rejected for this reason:\n{feedback}\n"
            "Write a corrected query that addresses it."
        )
    return _complete(SQL_SYSTEM, prompt, max_tokens=1000)


def summarize(question: str, sql: str, columns: list[str], rows: list[tuple]) -> str:
    """Turn the result set into a short written answer."""
    preview = "\n".join(str(r) for r in rows[:20])
    if len(rows) > 20:
        preview += f"\n... and {len(rows) - 20} more rows"
    prompt = (
        f"Question: {question}\n\nQuery that ran:\n{sql}\n\n"
        f"Columns: {', '.join(columns)}\nRows ({len(rows)} total):\n{preview}"
    )
    return _complete(SUMMARY_SYSTEM, prompt, max_tokens=600)


if __name__ == "__main__":
    # `python -m agent.llm`         prints the schema (no API key needed)
    # `python -m agent.llm --check` makes one tiny call to test connectivity
    if "--check" in sys.argv:
        print(f"  provider : {PROVIDER}")
        print(f"  model    : {MODEL}")
        print(f"  base url : {BASE_URL or '(provider default)'}")
        try:
            reply = _complete("Reply with the single word: ok", "ping", 10)
            print(f"  response : {reply}\n  Connection works.")
        except Exception as exc:
            print(f"\n  Failed: {type(exc).__name__}: {exc}")
            sys.exit(1)
    else:
        print(get_schema())
