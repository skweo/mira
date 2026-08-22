#!/usr/bin/env python3
"""Canonical names and legacy aliases for Mira's four public stages."""

from __future__ import annotations

import re
from typing import Final


STAGES: Final[tuple[str, ...]] = ("analysis", "modeling", "implementation", "paper")
STAGE_NUMBERS: Final[dict[str, int]] = {
    stage: index for index, stage in enumerate(STAGES, start=1)
}

STAGE_ALIASES: Final[dict[str, str]] = {
    # Stage 1: problem and data understanding.
    "analysis": "analysis",
    "startup": "analysis",
    "setup": "analysis",
    "delivery": "analysis",
    "privacy": "analysis",
    "privacy_gate": "analysis",
    "boundary": "analysis",
    "problem": "analysis",
    "problem_gate": "analysis",
    "data": "analysis",
    "data_audit": "analysis",
    "data_quality": "analysis",
    "cleaning": "analysis",
    "data_cleaning": "analysis",
    "p0": "analysis",
    "d0": "analysis",
    "0": "analysis",
    "1": "analysis",
    "g0": "analysis",
    "g1": "analysis",
    # Stage 2: model construction and derivation.
    "modeling": "modeling",
    "model": "modeling",
    "plan": "modeling",
    "method": "modeling",
    "method_gate": "modeling",
    "model_plan_gate": "modeling",
    "model_gate": "modeling",
    "2": "modeling",
    "g2": "modeling",
    "g3": "modeling",
    # Stage 3: executable implementation, results, and visuals.
    "implementation": "implementation",
    "code": "implementation",
    "result": "implementation",
    "results": "implementation",
    "figure": "implementation",
    "figures": "implementation",
    "diagram": "implementation",
    "diagrams": "implementation",
    "structural_diagram": "implementation",
    "diagram_router": "implementation",
    "poc": "implementation",
    "poc_gate": "implementation",
    "freeze": "implementation",
    "freeze_gate": "implementation",
    "3": "implementation",
    "4": "implementation",
    "5": "implementation",
    "6": "implementation",
    "g4": "implementation",
    "g5": "implementation",
    "benchmark": "implementation",
    "regression": "implementation",
    # Stage 4: paper production and final verification.
    "paper": "paper",
    "writing": "paper",
    "draft_gate": "paper",
    "draft_review": "paper",
    "verify": "paper",
    "verification": "paper",
    "final": "paper",
    "delivery_final": "paper",
    "final_gate": "paper",
    "submission_gate": "paper",
    "iteration": "paper",
    "revision": "paper",
    "repair": "paper",
    "7": "paper",
    "8": "paper",
    "9": "paper",
    "g6": "paper",
    "g7": "paper",
}


def normalize_stage(value: str) -> str:
    """Map a public stage or legacy Mira phase/gate name to four stages."""
    raw = str(value or "analysis").strip().lower()
    key = re.sub(r"^phase\s*", "", raw).strip().replace("-", "_")
    compact_key = key.replace(" ", "")
    stage = STAGE_ALIASES.get(key) or STAGE_ALIASES.get(compact_key)
    if stage:
        return stage
    raise ValueError(
        f"unknown Mira stage {value!r}; use analysis, modeling, implementation, or paper"
    )


def normalize_stage_path(value: str, default: str = "paper") -> str:
    """Normalize a legacy combined return path to its earliest public stage."""
    raw = str(value or "").strip().lower()
    try:
        return normalize_stage(raw)
    except ValueError:
        pass

    candidates: list[str] = []
    for token in re.findall(r"(?:phase\s*|g)?\d+(?:\.\d+)?", raw, flags=re.I):
        try:
            candidates.append(normalize_stage(token))
        except ValueError:
            number = float(re.search(r"\d+(?:\.\d+)?", token).group(0))
            if number <= 1:
                candidates.append("analysis")
            elif number <= 2.5:
                candidates.append("modeling")
            elif number <= 6:
                candidates.append("implementation")
            else:
                candidates.append("paper")
    if candidates:
        return min(candidates, key=STAGES.index)
    if any(token in raw for token in ("problem", "data", "attachment", "material", "delivery")):
        return "analysis"
    if any(token in raw for token in ("model", "method", "derivation", "validation", "symbol")):
        return "modeling"
    if any(token in raw for token in ("code", "result", "solver", "figure", "visual", "run")):
        return "implementation"
    return normalize_stage(default)
