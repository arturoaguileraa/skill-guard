"""Bridge to the web hub: dump scored results to the same catalog.json shape the
Jev service serves today. Lets the hub show real, at-scale results with no UI
change; later the hub can read the DB directly."""

from __future__ import annotations

import json
import time
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine

from worker.db import artifacts, results


def export_catalog(engine: Engine, out: Path, limit: int = 5000) -> int:
    with engine.begin() as conn:
        rows = conn.execute(
            select(
                results.c.artifact_hash, results.c.risk, results.c.decision,
                results.c.families, results.c.signals, results.c.model,
                artifacts.c.identity, artifacts.c.kind, artifacts.c.source,
                artifacts.c.source_url,
            )
            .join(artifacts, artifacts.c.hash == results.c.artifact_hash)
            .order_by(results.c.risk.desc())
            .limit(limit)
        ).all()

    items = [
        {
            "name": r.identity or r.artifact_hash[:12],
            "slug": r.artifact_hash[:16],
            "kind": r.kind or "skill",
            "label": "malicious" if r.decision == "block" else "benign",
            "note": r.source_url or r.source,
            "risk": round(r.risk, 4),
            "decision": r.decision,
            "correct": True,
            "families": r.families or [],
            "top_signals": r.signals or [],
            "synthetic": False,
        }
        for r in rows
    ]
    catalog = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "model": rows[0].model if rows else "jev-latest",
        "thresholds": {"block": 0.8, "review": 0.55},
        "count": len(items),
        "malicious": sum(1 for i in items if i["label"] == "malicious"),
        "benign": sum(1 for i in items if i["label"] == "benign"),
        "items": items,
    }
    out.write_text(json.dumps(catalog, indent=2))
    return len(items)
