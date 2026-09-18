"""Load the YAML question bank into typesafe_sdk question objects."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml
from typesafe_sdk import Choice, Noul, Score

BANK_DIR = Path(__file__).parent / "questions"


@dataclass(frozen=True)
class QuestionSpec:
    id: str
    family: str
    type: str
    weight: float
    n_levels: int = 0


@dataclass(frozen=True)
class Bank:
    version: int
    target: str
    families: dict[str, dict[str, Any]]
    specs: dict[str, QuestionSpec]
    questions: dict[str, Noul | Choice | Score]

    def scored_ids(self) -> list[str]:
        """Question ids that contribute to the verdict (control questions do not)."""
        return [qid for qid, s in self.specs.items() if s.family != "control"]


def load_bank(name: str = "skill_bank") -> Bank:
    raw = yaml.safe_load((BANK_DIR / f"{name}.yaml").read_text())
    families = raw.get("families", {})

    specs: dict[str, QuestionSpec] = {}
    questions: dict[str, Noul | Choice | Score] = {}

    for entry in raw["questions"]:
        qid, family, qtype = entry["id"], entry["family"], entry["type"]
        instructions = " ".join(entry["instructions"].split())
        criteria = entry.get("criteria")
        weight = float(families.get(family, {}).get("weight", 0.0))

        if qtype == "noul":
            # YAML turns bare `true:`/`false:` keys into booleans; NoulCriteria
            # wants the strings.
            if isinstance(criteria, dict):
                criteria = {str(k).lower(): v for k, v in criteria.items()}
            questions[qid] = Noul(instructions=instructions, criteria=criteria)
            levels = 0
        elif qtype == "choice":
            questions[qid] = Choice(instructions=instructions, criteria=criteria)
            levels = len(criteria)
        elif qtype == "score":
            questions[qid] = Score(instructions=instructions, criteria=criteria)
            levels = len(criteria)
        else:
            raise ValueError(f"{qid}: unknown question type {qtype!r}")

        specs[qid] = QuestionSpec(qid, family, qtype, weight, levels)

    return Bank(raw["version"], raw["target"], families, specs, questions)
