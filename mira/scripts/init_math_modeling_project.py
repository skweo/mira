#!/usr/bin/env python3
"""Initialize the folder skeleton for a Chinese math-modeling contest paper."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from delivery_contract import new_manifest


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR.parent / "assets" / "templates"


def powershell_script_command(script_name: str, arguments: str) -> str:
    executable = str(Path(sys.executable).resolve()).replace('"', '`"')
    script = str(SCRIPT_DIR / script_name).replace('"', '`"')
    return f'& "{executable}" "{script}" {arguments}'


DIRS = [
    "problem",
    "planning",
    "data_raw",
    "data_clean",
    "code",
    "code/python",
    "code/matlab",
    "results",
    "results/tables",
    "results/logs",
    "results/audits",
    "results/figures_data",
    "figures",
    "diagrams",
    "paper",
    "supporting",
    "checks",
    "revisions",
    "output",
    "output/contest_final",
    "materials",
    "materials/raw",
    "materials/raw/contest_papers",
    "materials/raw/research_papers",
    "materials/raw/model_notes",
    "materials/raw/textbooks_or_courses",
    "materials/raw/code_examples",
    "materials/raw/datasets",
    "materials/raw/rules_and_templates",
    "materials/extracted",
    "materials/extracted/knowledge-cards",
]


DELIVERY_BRIEF = """# Delivery Brief

| Field | Value |
|---|---|
| Output level | to_be_decided |
| Contest | to_be_decided |
| Problem | to_be_decided |
| Language | Chinese |
| Format engine | to_be_decided |
| Contest template family | to_be_selected |
| Final artifact | output/contest_final/paper.pdf |
| Source files | to_be_filled |
| Subquestion count | to_be_parsed |
| Workflow lane | to_be_selected |
| Current stage | analysis |
"""


WORKFLOW_LANE = """# Workflow Lane

- Selected lane: to_be_selected
- Reason: to_be_decided

## Skipped Granular Skills

- to_be_decided

## References To Load Now

- references/workflow-orchestration.md
- references/adaptive-workflow-lanes.md
- references/phase-contracts.md

## Expansion Triggers

- a stage check fails
- model choice materially changes numerical answers
- data fields, units, or extraction rules are unclear
- heuristic results lack baseline, seed, convergence, or sensitivity evidence
- PoC/prototype result exists but has no method-screening decision
- risky method choice needs domain knowledge card retrieval
- paper comparison exposes a non-local quality regression

## Artifact Budget

- to_be_decided
"""


REFERENCE_ROUTE = f"""# Mira Reference Route

- Generated: not_generated
- Stage: **analysis**
- Lane: **to_be_selected**

Run:

```powershell
{powershell_script_command("route_references.py", "--root . --stage analysis --write")}
```

Load only the references listed under `Load Now`. Other references are optional
until a stage risk, failed diagnostic, or iteration item names them.
"""


AGENT_STATE = """# Agent State

| Stage | Status | Canonical evidence | Notes |
|---|---|---|---|
| analysis | pending | planning/delivery_brief.md, planning/problem_analysis.md | Clarify real choices as requires_user_decision |
| modeling | pending | planning/modeling_plan.md, planning/validation_plan.md | Define and derive the model before coding |
| implementation | pending | code/, results/, figures/, planning/result_ledger.* | Run code and freeze traceable evidence |
| paper | pending | paper/main.*, compiled PDF, consistency and delivery reports | contest_final requires a READY manifest |
"""


MIRA_STATE = {
    "version": 2,
    "updated_at": "",
    "root": "",
    "stage": {"current": "analysis", "requested": "analysis"},
    "phase": {"current": "analysis", "requested": "analysis"},
    "markers": [],
    "requires_user_decision": [],
    "gates": {},
    "open_items": [],
    "stale": [],
    "verdict": "PASS",
}


MIRA_STATE_MD = f"""# Mira Shared State

- Generated: not_generated
- Verdict: **PASS**
- State: `planning/mira_state.json`

Run:

```powershell
{powershell_script_command("mira_state.py", "--root . --stage analysis --write --write-report planning\\mira_state.md")}
```
"""


ITERATION_QUEUE = {
    "version": 1,
    "updated_at": "",
    "items": [],
}


def write_if_missing(path: Path, content: str, dry_run: bool) -> str:
    if path.exists():
        return "exists"
    if dry_run:
        return "would-create"
    path.write_text(content, encoding="utf-8")
    return "created"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", nargs="?", default=".", help="Project root to initialize")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    args = parser.parse_args()

    root = Path(args.target).resolve()
    actions: list[tuple[str, str]] = []

    for rel in DIRS:
        path = root / rel
        if path.exists():
            actions.append(("exists", str(path)))
        elif args.dry_run:
            actions.append(("would-create", str(path)))
        else:
            path.mkdir(parents=True, exist_ok=True)
            actions.append(("created", str(path)))

        keep = path / ".gitkeep"
        actions.append((write_if_missing(keep, "", args.dry_run), str(keep)))

    state_path = root / "planning" / "agent_state.md"
    actions.append((write_if_missing(state_path, AGENT_STATE, args.dry_run), str(state_path)))

    brief_path = root / "planning" / "delivery_brief.md"
    actions.append((write_if_missing(brief_path, DELIVERY_BRIEF, args.dry_run), str(brief_path)))

    lane_path = root / "planning" / "workflow_lane.md"
    actions.append((write_if_missing(lane_path, WORKFLOW_LANE, args.dry_run), str(lane_path)))

    reference_route_path = root / "planning" / "reference_route.md"
    actions.append((write_if_missing(reference_route_path, REFERENCE_ROUTE, args.dry_run), str(reference_route_path)))

    mira_state_path = root / "planning" / "mira_state.json"
    state_payload = {**MIRA_STATE, "root": str(root)}
    actions.append((write_if_missing(mira_state_path, json.dumps(state_payload, ensure_ascii=False, indent=2) + "\n", args.dry_run), str(mira_state_path)))

    mira_state_md_path = root / "planning" / "mira_state.md"
    actions.append((write_if_missing(mira_state_md_path, MIRA_STATE_MD, args.dry_run), str(mira_state_md_path)))

    manifest_path = root / "planning" / "delivery_manifest.json"
    manifest_content = json.dumps(new_manifest(root), ensure_ascii=False, indent=2) + "\n"
    actions.append((write_if_missing(manifest_path, manifest_content, args.dry_run), str(manifest_path)))

    for template_name, target_name in (
        ("figure_evidence.json", "figure_evidence.json"),
        ("professional_modeling.json", "professional_modeling.json"),
        ("statistical_evidence.json", "statistical_evidence.json"),
        ("reference_authenticity.json", "reference_authenticity.json"),
        ("material_claim_anchors.json", "material_claim_anchors.json"),
        ("contest_evidence_chains.json", "contest_evidence_chains.json"),
        ("submission_requirements.json", "submission_requirements.json"),
    ):
        template_path = TEMPLATE_DIR / template_name
        target_path = root / "planning" / target_name
        actions.append((write_if_missing(target_path, template_path.read_text(encoding="utf-8"), args.dry_run), str(target_path)))

    queue_path = root / "revisions" / "iteration_queue.json"
    queue_content = json.dumps(ITERATION_QUEUE, ensure_ascii=False, indent=2) + "\n"
    actions.append((write_if_missing(queue_path, queue_content, args.dry_run), str(queue_path)))

    for status, path in actions:
        print(f"{status}: {path}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
