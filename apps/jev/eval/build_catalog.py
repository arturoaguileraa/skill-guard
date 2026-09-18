"""Build eval/catalog.json — the data behind the web "Analyzed skills" hub.

Reuses the cached Jev readings (eval/.readings_cache.json) so it makes ZERO API
calls: it re-scores each labeled fixture through the current tuned bank and
emits a compact, honest catalog. Entries are our synthetic-but-grounded corpus,
flagged `synthetic: true` so the hub never pretends to be an authoritative
verdict on real third-party skills.

Run: uv run python eval/build_catalog.py
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

from skillguard.bank import load_bank
from skillguard.engine import Reading
from skillguard.extract import extract_skill
from skillguard.score import Thresholds, score

EVAL = Path(__file__).parent
FIX = EVAL / "fixtures"


def parse_labels_with_notes() -> dict[str, dict[str, str]]:
    """Parse labels.yaml by hand to keep each fixture's trailing # comment
    (the provenance / technique note), which a YAML parse would discard."""
    out: dict[str, dict[str, str]] = {}
    section = None
    for raw in (EVAL / "labels.yaml").read_text().splitlines():
        s = raw.strip()
        if s.startswith("malicious:"):
            section = "malicious"
        elif s.startswith("benign:"):
            section = "benign"
        m = re.match(r"-\s+([A-Za-z0-9_-]+)\s*(?:#\s*(.*))?$", s)
        if m and section:
            name, note = m.group(1), (m.group(2) or "").strip()
            out[f"{section}/{name}"] = {"label": section, "note": note}
    return out


def main() -> None:
    bank = load_bank()
    th = Thresholds()
    cache = json.loads((EVAL / ".readings_cache.json").read_text())["clean"]
    labels = parse_labels_with_notes()

    items = []
    for key, meta in labels.items():
        cls, name = key.split("/", 1)
        skill_dir = FIX / cls / name
        if not (skill_dir / "SKILL.md").exists() or key not in cache:
            continue
        art = extract_skill(skill_dir)
        c = cache[key]
        reading = Reading(
            artifact=art,
            values=c.get("values", {}),
            confidence=c.get("confidence", {}),
            detail={},
            input_tokens=0,
            latency_ms=0.0,
            error=c.get("error"),
        )
        v = score(reading, bank, th)
        correct = (meta["label"] == "malicious") == (v.decision.value == "block")
        items.append({
            "name": art.identity,
            "slug": name,
            "kind": art.kind,
            "label": meta["label"],
            "note": meta["note"],
            "risk": round(v.risk, 4),
            "decision": v.decision.value,
            "correct": correct,
            "families": [
                {"family": f, "label": bank.families.get(f, {}).get("label", f),
                 "risk": round(r, 4)}
                for f, r in sorted(v.family_risk.items(), key=lambda kv: kv[1], reverse=True)
                if r > 0.05
            ][:4],
            "top_signals": [
                {"id": q, "value": round(val, 4)}
                for q, val in v.top_signals[:4] if val > 0.3
            ],
            "synthetic": True,
        })

    items.sort(key=lambda it: it["risk"], reverse=True)
    catalog = {
        "generated_at": time.strftime("%Y-%m-%d"),
        "model": "jev-latest",
        "thresholds": {"block": th.block, "review": th.review},
        "count": len(items),
        "malicious": sum(1 for it in items if it["label"] == "malicious"),
        "benign": sum(1 for it in items if it["label"] == "benign"),
        "items": items,
    }
    (EVAL / "catalog.json").write_text(json.dumps(catalog, indent=2))
    print(f"wrote catalog.json: {len(items)} items "
          f"({catalog['malicious']} mal / {catalog['benign']} ben)")


if __name__ == "__main__":
    main()
