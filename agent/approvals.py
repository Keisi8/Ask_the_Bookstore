"""A record of queries a human has approved.

Once you approve a query for a given question, the exact SQL is saved here.
Later runs replay that SQL instead of asking the model again, so the recurring
report becomes unattended work while staying auditable.

The safety property is the cache key: it hashes the question text *and* the
database schema. Change either one and the entry no longer matches, so the
query goes back through generation, the guards and a human. An approval is
therefore a statement about one specific question against one specific schema,
never a blanket permission.

approvals.json is meant to be committed: it is the reviewed playbook, and its
diff shows exactly which queries a human signed off and when.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

STORE_PATH = Path(__file__).parent.parent / "approvals.json"
VERSION = 1


def fingerprint(question: str, schema: str) -> str:
    """Stable key for a question asked against a particular schema."""
    normalized = " ".join(question.lower().split())
    digest = hashlib.sha256()
    digest.update(normalized.encode("utf-8"))
    digest.update(b"\x00")
    digest.update(schema.encode("utf-8"))
    return digest.hexdigest()[:16]


def _load_raw() -> dict[str, Any]:
    if not STORE_PATH.exists():
        return {"version": VERSION, "approvals": {}}
    try:
        data = json.loads(STORE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        print("  approvals.json is not valid JSON; ignoring it this run.")
        return {"version": VERSION, "approvals": {}}
    if data.get("version") != VERSION:
        print("  approvals.json was written by another version; ignoring it.")
        return {"version": VERSION, "approvals": {}}
    return data


def lookup(question: str, schema: str) -> dict[str, Any] | None:
    """Return the stored approval for this question, or None."""
    return _load_raw()["approvals"].get(fingerprint(question, schema))


def remember(question: str, schema: str, sql: str, kpi: str = "") -> None:
    """Record that a human approved this SQL for this question."""
    data = _load_raw()
    data["approvals"][fingerprint(question, schema)] = {
        "question": " ".join(question.split()),
        "kpi": kpi,
        "sql": sql,
        "approved_at": datetime.now().isoformat(timespec="seconds"),
    }
    STORE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def forget(fp: str | None = None) -> int:
    """Remove one approval, or all of them. Returns how many were removed."""
    data = _load_raw()
    if fp is None:
        count = len(data["approvals"])
        data["approvals"] = {}
    else:
        count = 1 if data["approvals"].pop(fp, None) else 0
    STORE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return count


def listing() -> list[tuple[str, dict[str, Any]]]:
    """Every stored approval, newest first."""
    items = _load_raw()["approvals"].items()
    return sorted(items, key=lambda kv: kv[1].get("approved_at", ""), reverse=True)
