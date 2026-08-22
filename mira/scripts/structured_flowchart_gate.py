#!/usr/bin/env python3
"""Portfolio gate for structured Python flowcharts in Mira contest papers."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from render_structured_flowchart import StructuredFlowchart, load_spec


@dataclass
class Finding:
    level: str
    diagram_id: str
    code: str
    message: str
    evidence: str = ""


class StructuredFlowchartGate:
    def __init__(self, root: Path, intent_path: Path, render: bool = False) -> None:
        self.root = root.resolve()
        self.intent_path = intent_path.resolve()
        self.render = render
        self.findings: list[Finding] = []
        self.diagrams: list[dict[str, Any]] = []

    def run(self) -> dict[str, Any]:
        intents = load_intents(self.intent_path)
        if not intents:
            self.fail("portfolio", "intent_pack", "no structural flowchart intent is recorded", str(self.intent_path))
        for intent in intents:
            self._check_intent(intent)
        failures = [item for item in self.findings if item.level == "FAIL"]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "root": str(self.root),
            "intent_pack": relative(self.root, self.intent_path),
            "verdict": "FAIL" if failures else "PASS",
            "metrics": {
                "intent_count": len(intents),
                "checked_diagrams": len(self.diagrams),
                "failures": len(failures),
            },
            "diagrams": self.diagrams,
            "findings": [asdict(item) for item in self.findings],
        }

    def fail(self, diagram_id: str, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("FAIL", diagram_id, code, message, evidence))

    def warn(self, diagram_id: str, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("WARN", diagram_id, code, message, evidence))

    def _check_intent(self, intent: dict[str, Any]) -> None:
        diagram_id = str(intent.get("diagram_id") or intent.get("id") or "unknown")
        route = str(intent.get("tool_route") or intent.get("route") or "").lower()
        if route in {"waived", "none"}:
            if len(str(intent.get("waiver_reason") or "")) < 12:
                self.fail(diagram_id, "waiver", "flowchart waiver needs a concrete evidence-based reason")
            return
        if route not in {"python_matplotlib", "python_structure"}:
            self.fail(diagram_id, "backend", "structured contest-paper flowcharts must use the Python renderer", route)
            return
        source_rel = str(intent.get("source_file") or "")
        if not source_rel:
            self.fail(diagram_id, "source", "source_file is required")
            return
        source = resolve(self.root, source_rel)
        if not source.is_file() or source.suffix.lower() != ".json":
            self.fail(diagram_id, "source", "source_file must be an existing JSON flowchart spec", source_rel)
            return
        try:
            spec = load_spec(source)
        except (OSError, json.JSONDecodeError, ValueError) as exc:
            self.fail(diagram_id, "source", str(exc), source_rel)
            return
        if str(spec.get("diagram_id")) != diagram_id:
            self.fail(diagram_id, "identity", "intent and source diagram_id differ", str(spec.get("diagram_id")))
        output_dir = resolve(self.root, str(Path(str(intent.get("export_file") or f"diagrams/{diagram_id}.pdf")).parent))
        report = StructuredFlowchart(spec, source, output_dir).run(audit_only=not self.render)
        self.diagrams.append(report)
        for item in report["findings"]:
            level = str(item.get("level"))
            finding = Finding(level, diagram_id, str(item.get("code")), str(item.get("message")), str(item.get("evidence") or ""))
            self.findings.append(finding)
        if report["verdict"] == "FAIL":
            return
        pdf = resolve(self.root, str(intent.get("export_file") or f"diagrams/{diagram_id}.pdf"))
        png = resolve(self.root, str(intent.get("png_file") or f"diagrams/{diagram_id}.png"))
        provenance = pdf.parent / f"{diagram_id}.provenance.json"
        for kind, path in (("PDF", pdf), ("300 DPI PNG", png), ("provenance", provenance)):
            if not path.is_file():
                self.fail(diagram_id, "exports", f"missing {kind} output", relative(self.root, path))
        if png.is_file():
            try:
                from PIL import Image

                with Image.open(png) as image:
                    dpi = image.info.get("dpi", (0, 0))
                    if min(float(dpi[0]), float(dpi[1])) < 295:
                        self.fail(diagram_id, "png_dpi", "PNG export is below 300 DPI", str(dpi))
            except Exception as exc:
                self.fail(diagram_id, "png_read", f"cannot inspect PNG: {exc}", relative(self.root, png))
        if provenance.is_file():
            try:
                data = json.loads(provenance.read_text(encoding="utf-8-sig"))
            except (OSError, json.JSONDecodeError) as exc:
                self.fail(diagram_id, "provenance", f"invalid provenance: {exc}", relative(self.root, provenance))
            else:
                if data.get("diagram_id") != diagram_id or data.get("exports", {}).get("png_dpi") != 300:
                    self.fail(diagram_id, "provenance", "provenance does not match diagram exports", relative(self.root, provenance))


def load_intents(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return []
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        rows = payload.get("intents") or payload.get("diagrams") or payload.get("items") or []
        return [item for item in rows if isinstance(item, dict)]
    return []


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Structured Flowchart Portfolio Gate",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Intent pack: `{payload['intent_pack']}`",
        "",
        "| Level | Diagram | Code | Message | Evidence |",
        "|---|---|---|---|---|",
    ]
    if payload["findings"]:
        for item in payload["findings"]:
            cells = [str(item.get(key, "")).replace("|", "\\|").replace("\n", " ") for key in ("level", "diagram_id", "code", "message", "evidence")]
            lines.append("| " + " | ".join(cells) + " |")
    else:
        lines.append("| INFO | - | complete | no findings | - |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--intent-pack", default="planning/diagram_intent_pack.json")
    parser.add_argument("--render", action="store_true", help="Render declared diagrams before auditing exports")
    parser.add_argument("--write-json", default="checks/structured_flowchart_gate.json")
    parser.add_argument("--write-report", default="checks/structured_flowchart_gate.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = StructuredFlowchartGate(root, resolve(root, args.intent_pack), args.render).run()
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(f"checked_diagrams: {payload['metrics']['checked_diagrams']}")
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())

