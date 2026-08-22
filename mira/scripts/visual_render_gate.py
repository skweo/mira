#!/usr/bin/env python3
"""Validate that paper figures are rendered, nonblank, indexed, and traceable."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from PIL import Image


@dataclass
class Finding:
    level: str
    file: str
    message: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--write-report", default="checks/visual_render_report.md")
    parser.add_argument("--write-json", default="checks/visual_render_report.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    findings: list[Finding] = []
    metrics: list[dict] = []
    index = read(root / "figures" / "figure_index.md").lower()
    pngs = sorted((root / "figures").glob("*.png")) if (root / "figures").exists() else []
    for path in pngs:
        inspect_render(root, path, index, findings, metrics)
    if not pngs:
        findings.append(Finding("FAIL", "figures", "no PNG render found"))

    verdict = "FAIL" if any(x.level == "FAIL" for x in findings) else ("PASS_WITH_WARNINGS" if findings else "PASS")
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "verdict": verdict,
        "metrics": {
            "renders": metrics,
            "warnings": sum(x.level == "WARN" for x in findings),
            "failures": sum(x.level == "FAIL" for x in findings),
        },
        "findings": [asdict(x) for x in findings],
    }
    write(root, args.write_json, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")
    lines = [
        "# Visual Render Report",
        "",
        f"Verdict: **{verdict}**",
        "",
        f"Rendered PNG files: {len(pngs)}",
        "",
        "## Findings",
        "",
    ] + [f"- {x.level}: `{x.file}` - {x.message}" for x in findings]
    write(root, args.write_report, "\n".join(lines) + "\n")
    print(f"VERDICT: {verdict}")
    return 1 if verdict == "FAIL" else 0


def inspect_render(
    root: Path,
    path: Path,
    index: str,
    findings: list[Finding],
    metrics: list[dict],
) -> None:
    relative = rel(root, path)
    try:
        with Image.open(path) as image:
            rgb = image.convert("RGB")
            extrema = rgb.getextrema()
            span = max(high - low for low, high in extrema)
            width, height = rgb.size
            metrics.append(
                {"file": relative, "width": width, "height": height, "channel_span": span, "bytes": path.stat().st_size}
            )
            if width < 1200 or height < 750:
                findings.append(Finding("WARN", relative, f"render is only {width}x{height}"))
            if span < 12 or path.stat().st_size < 8000:
                findings.append(Finding("FAIL", relative, "render is blank or near-blank"))
    except Exception as exc:
        findings.append(Finding("FAIL", relative, f"cannot decode raster: {exc}"))
        return

    pdf = path.with_suffix(".pdf")
    if not pdf.exists() or pdf.stat().st_size < 1000:
        findings.append(Finding("FAIL", relative, "vector PDF companion is missing or empty"))
    if path.name.lower() not in index and pdf.name.lower() not in index:
        findings.append(Finding("WARN", relative, "figure is not indexed"))
    validate_summary(root, path, findings)


def validate_summary(root: Path, path: Path, findings: list[Finding]) -> None:
    relative = rel(root, path)
    summary_path = root / "results" / "figures_data" / (path.stem + "_summary.json")
    if not summary_path.exists():
        findings.append(Finding("WARN", relative, "claim/source-data summary is missing"))
        return
    try:
        payload = json.loads(summary_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        findings.append(Finding("FAIL", relative, f"summary JSON is invalid: {exc}"))
        return
    for key in ("claim_id", "backend", "supported_claim", "source_data"):
        if not str(payload.get(key) or "").strip():
            findings.append(Finding("FAIL", relative, f"summary field {key} is missing"))
    source = payload.get("source_data")
    if source and not (root / str(source)).is_file():
        findings.append(Finding("FAIL", relative, f"source data does not exist: {source}"))


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore") if path.exists() else ""


def rel(root: Path, path: Path) -> str:
    return str(path.relative_to(root)).replace("\\", "/")


def write(root: Path, value: str, content: str) -> None:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
