#!/usr/bin/env python3
"""Check evidence ownership of core claims for paper-intended visuals.

The gate absorbs the useful core of figure-table planning without reviving a
long sentinel workflow. Mira may draft a visual plan, but the load-bearing
claim of each main-paper visual must be concrete and traceable before a
contest-final delivery.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


MAIN_USE = "main"
SUPPORT_USE = "support"
DIAGNOSTIC_USE = "diagnostic"


@dataclass
class Visual:
    artifact: str
    source: str
    visual_type: str
    paper_use: str
    role: str
    mira_claim_draft: str
    source_artifact: str
    paper_section: str


@dataclass
class Finding:
    level: str
    artifact: str
    message: str


class FigureClaimOwnershipGate:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.output_level = args.output_level
        self.claims_path = self._resolve(args.claims or "planning/figure_claims.json")
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "checks" / "figure_claim_ownership_report.md"
        self.json_path = self._resolve(args.write_json) if args.write_json else None
        self.template_path = self._resolve(args.write_template) if args.write_template else None
        self.findings: list[Finding] = []
        self.visuals = collect_visuals(self.root)
        self.claims = self._load_claims()

    def run(self) -> int:
        self._check()
        if self.template_path:
            self._write_template()
        self._write_report()
        if self.json_path:
            self._write_json()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _check(self) -> None:
        if not self.visuals:
            self._add("INFO", "-", "no indexed visuals found; claim ownership cannot be assessed")
            return
        for visual in self.visuals:
            record = self.claims.get(normalize_artifact(visual.artifact), {})
            if not self._requires_claim(visual):
                if visual.paper_use == SUPPORT_USE and not record:
                    self._add("INFO", visual.artifact, "supporting visual has no claim record; this is acceptable unless it carries a main conclusion")
                continue
            if not record:
                level = "FAIL" if self.output_level == "contest_final" else "WARN"
                self._add(level, visual.artifact, "main-paper visual lacks a core-claim record in planning/figure_claims.json")
                continue
            self._check_record(visual, record)

    def _requires_claim(self, visual: Visual) -> bool:
        if visual.paper_use in {SUPPORT_USE, DIAGNOSTIC_USE}:
            return False
        return True

    def _check_record(self, visual: Visual, record: dict[str, Any]) -> None:
        claim = str(record.get("core_claim") or "").strip()
        section = str(record.get("paper_section") or visual.paper_section or "").strip()
        source = str(record.get("source_artifact") or visual.source_artifact or "").strip()
        if len(claim) < 8:
            self._add("FAIL", visual.artifact, "core_claim is missing or too short")
        if not section:
            self._add("WARN", visual.artifact, "paper_section is missing; the figure may drift away from its supporting paragraph")
        if not source:
            self._add("WARN", visual.artifact, "source_artifact is missing; the figure claim may not be traceable to data/results")

    def _load_claims(self) -> dict[str, dict[str, Any]]:
        data = load_json(self.claims_path, {"claims": []})
        records = data.get("claims", []) if isinstance(data, dict) else []
        out: dict[str, dict[str, Any]] = {}
        for record in records:
            if not isinstance(record, dict):
                continue
            artifact = normalize_artifact(str(record.get("artifact") or ""))
            if artifact:
                out[artifact] = record
        return out

    def _write_template(self) -> None:
        payload = {
            "version": 1,
            "generated_at": now(),
            "instructions": [
                "Copy resolved entries into planning/figure_claims.json.",
                "Give every main-paper visual a concrete core_claim, source artifact, and paper section.",
            ],
            "claims": [template_record(visual, self.claims.get(normalize_artifact(visual.artifact), {})) for visual in self.visuals],
        }
        self.template_path.parent.mkdir(parents=True, exist_ok=True)
        self.template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_report(self) -> None:
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(markdown(self.payload()), encoding="utf-8")

    def _write_json(self) -> None:
        assert self.json_path is not None
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.write_text(json.dumps(self.payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def payload(self) -> dict[str, Any]:
        main_visuals = [visual for visual in self.visuals if self._requires_claim(visual)]
        documented = 0
        for visual in main_visuals:
            record = self.claims.get(normalize_artifact(visual.artifact), {})
            if str(record.get("core_claim") or "").strip():
                documented += 1
        return {
            "generated_at": now(),
            "root": str(self.root),
            "output_level": self.output_level,
            "verdict": verdict(self.findings),
            "metrics": {
                "indexed_visuals": len(self.visuals),
                "main_visuals_requiring_claim": len(main_visuals),
                "documented_main_claims": documented,
                "warnings": sum(1 for item in self.findings if item.level == "WARN"),
                "failures": sum(1 for item in self.findings if item.level == "FAIL"),
            },
            "visuals": [asdict(visual) for visual in self.visuals],
            "findings": [asdict(item) for item in self.findings],
            "claims_path": rel(self.root, self.claims_path),
            "template_path": rel(self.root, self.template_path) if self.template_path else "",
        }

    def _emit(self) -> None:
        payload = self.payload()
        print_utf8(f"VERDICT: {payload['verdict']}")
        print_utf8("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
        for item in self.findings:
            print_utf8(f"{item.level}: {item.artifact}: {item.message}")
        if self.template_path:
            print_utf8(f"INFO: wrote {rel(self.root, self.template_path)}")
        print_utf8(f"INFO: wrote {rel(self.root, self.report_path)}")
        if self.json_path:
            print_utf8(f"INFO: wrote {rel(self.root, self.json_path)}")

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _add(self, level: str, artifact: str, message: str) -> None:
        self.findings.append(Finding(level, artifact, message))


def collect_visuals(root: Path) -> list[Visual]:
    rows: list[Visual] = []
    rows.extend(parse_index(root, "figures/figure_index.md", "figure_index"))
    rows.extend(parse_index(root, "diagrams/diagram_index.md", "diagram_index"))
    rows.extend(parse_storyboard(root))
    out: list[Visual] = []
    seen: set[str] = set()
    for row in rows:
        key = normalize_artifact(row.artifact)
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def parse_index(root: Path, rel_path: str, source: str) -> list[Visual]:
    text = read_text(root / rel_path)
    rows: list[Visual] = []
    for line in text.splitlines():
        if not line.strip().startswith("|") or "---" in line:
            continue
        cells = [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]
        if not cells or cells[0].strip().lower() in {"figure", "diagram", "artifact", "file", "图", "图片"}:
            continue
        while len(cells) < 5:
            cells.append("")
        artifact = cells[0]
        if not looks_like_visual(artifact):
            continue
        source_artifact = cells[1]
        claim = cells[3]
        location = cells[4]
        text_for_type = " ".join([artifact, source_artifact, claim, location])
        role = infer_role(text_for_type)
        visual_type, paper_use = infer_type_and_use(text_for_type, role, source)
        rows.append(
            Visual(
                artifact=artifact,
                source=source,
                visual_type=visual_type,
                paper_use=paper_use,
                role=role,
                mira_claim_draft=claim,
                source_artifact=source_artifact,
                paper_section=location,
            )
        )
    return rows


def parse_storyboard(root: Path) -> list[Visual]:
    path = root / "planning" / "figure_storyboard.json"
    if not path.exists():
        return []
    data = load_json(path, {})
    rows: list[Visual] = []
    for item in data.get("items", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        artifact = str(item.get("source_artifact") or "").strip()
        if not looks_like_visual(artifact):
            continue
        text = " ".join(str(item.get(key) or "") for key in ["role", "proposed_visual", "nearby_claim", "callout", "source_artifact"])
        role = infer_role(str(item.get("role") or text))
        visual_type, paper_use = infer_type_and_use(text, role, "figure_storyboard")
        rows.append(
            Visual(
                artifact=artifact,
                source="figure_storyboard",
                visual_type=visual_type,
                paper_use=paper_use,
                role=role,
                mira_claim_draft=str(item.get("nearby_claim") or ""),
                source_artifact=artifact,
                paper_section=str(item.get("question") or ""),
            )
        )
    return rows


def infer_role(text: str) -> str:
    lower = text.lower()
    for role in ["define", "derive", "operate", "result", "validate", "zoom", "compare"]:
        if re.search(rf"\b{role}\b", lower):
            return role
    if has_any(lower, ["diagnostic", "residual", "qq", "acf", "pacf", "correlation"]):
        return "validate"
    if has_any(lower, ["compare", "comparison", "baseline", "candidate", "scenario", "ablation", "before", "after"]):
        return "compare"
    if has_any(lower, ["flow", "algorithm", "solver", "process", "pipeline", "step"]):
        return "operate"
    if has_any(lower, ["geometry", "coordinate", "structure", "state", "mechanism"]):
        return "define"
    if has_any(lower, ["constraint", "formula", "relation", "derive"]):
        return "derive"
    if has_any(lower, ["zoom", "detail", "critical", "boundary", "local"]):
        return "zoom"
    return "result"


def infer_type_and_use(text: str, role: str, source: str) -> tuple[str, str]:
    lower = text.lower()
    # Existing indexes may still use appendix/supplement labels. Treat them as
    # external support input without creating an appendix output contract.
    if has_any(lower, ["appendix", "supplement", "附录"]):
        return "type4_support", SUPPORT_USE
    if has_any(lower, ["internal", "diagnostic only", "not for paper", "诊断"]):
        return "type1_diagnostic", DIAGNOSTIC_USE
    if role == "compare" or has_any(lower, ["compare", "comparison", "baseline", "candidate", "ablation"]):
        return "type2_comparison", MAIN_USE
    if source == "figure_storyboard" and has_any(lower, ["planned_gap", "tbd"]):
        return "type3_paper", MAIN_USE
    return "type3_paper", MAIN_USE


def template_record(visual: Visual, existing: dict[str, Any]) -> dict[str, Any]:
    return {
        "artifact": visual.artifact,
        "visual_type": existing.get("visual_type") or visual.visual_type,
        "paper_use": existing.get("paper_use") or visual.paper_use,
        "role": existing.get("role") or visual.role,
        "mira_claim_draft": existing.get("mira_claim_draft") or visual.mira_claim_draft,
        "core_claim": existing.get("core_claim") or "",
        "source_artifact": existing.get("source_artifact") or visual.source_artifact,
        "paper_section": existing.get("paper_section") or visual.paper_section,
        "evidence_note": existing.get("evidence_note") or "",
    }


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Figure Claim Ownership Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Output level: `{payload['output_level']}`",
        f"- Claims file: `{payload['claims_path']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Visuals", "", "| Artifact | Type | Use | Role | Draft Claim | Section | Source |", "|---|---|---|---|---|---|---|"])
    for item in payload["visuals"]:
        lines.append(
            f"| `{escape(item['artifact'])}` | `{item['visual_type']}` | `{item['paper_use']}` | `{item['role']}` | {escape(item['mira_claim_draft'])} | {escape(item['paper_section'])} | `{escape(item['source_artifact'])}` |"
        )
    lines.extend(["", "## Findings", "", "| Level | Artifact | Message |", "|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | `{escape(item['artifact'])}` | {escape(item['message'])} |")
    if not payload["findings"]:
        lines.append("| INFO | ALL | no figure-claim ownership findings |")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            "- Mira may recommend the chart type, caption direction, and draft claim.",
            "- For main-paper visuals, the final `core_claim` must be concrete and traceable to model, code, or result evidence.",
            "- Diagnostic and supporting visuals do not block contest-final delivery unless they carry a main conclusion.",
            "",
        ]
    )
    return "\n".join(lines)


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError:
        return default


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def looks_like_visual(value: str) -> bool:
    return bool(re.search(r"\.(?:png|jpg|jpeg|webp|svg|pdf)\b", value, flags=re.I))


def normalize_artifact(value: str) -> str:
    return value.strip().replace("\\", "/").lower()


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", "", value).lower()


def has_any(text: str, terms: list[str]) -> bool:
    return any(term.lower() in text for term in terms)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def rel(root: Path, path: Path | None) -> str:
    if path is None:
        return ""
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def print_utf8(text: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(text, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--output-level", default="reproducible_draft", choices=["quick_draft", "reproducible_draft", "contest_final"])
    parser.add_argument("--claims", help="Claim ledger path, default planning/figure_claims.json")
    parser.add_argument("--write-template", help="Write a fill-in template, e.g. planning/figure_claims_template.json")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return FigureClaimOwnershipGate(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
