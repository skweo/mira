#!/usr/bin/env python3
"""Audit figure and diagram assets for Mira contest-final visual quality."""

from __future__ import annotations

import argparse
import json
import re
import struct
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".svg", ".pdf"}
RASTER_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp"}
MIN_WIDTH = 900
MIN_HEIGHT = 650
MIN_BYTES = 8_000
MAX_BYTES = 8_000_000
GRID_STYLE_RE = re.compile(
    r"\.grid\s*\(\s*True\b|"
    r"rcParams\s*\[\s*['\"]axes\.grid['\"]\s*\]\s*=\s*True|"
    r"['\"]axes\.grid['\"]\s*:\s*True|"
    r"(?:set_style|style\.use)\s*\(\s*['\"][^'\"]*(?:whitegrid|darkgrid)[^'\"]*['\"]",
    re.I,
)
GRID_ALLOW_RE = re.compile(r"mira-allow-grid|structural grid|结构线|极坐标|雷达|Taylor|泰勒|heatmap|contour|等值线|网格数据", re.I)
BAD_PALETTE_RE = re.compile(
    r"\b(?:cmap|palette)\s*=\s*['\"](?:jet|rainbow|nipy_spectral|gist_rainbow)['\"]|"
    r"(?:color_palette|get_cmap)\s*\(\s*['\"](?:jet|rainbow|nipy_spectral|gist_rainbow)['\"]|"
    r"['\"](?:RdYlGn|PiYG|PRGn)['\"]",
    re.I,
)
BAD_PALETTE_ALLOW_RE = re.compile(r"mira-allow-palette|palette waiver|配色豁免|legacy palette", re.I)
GENERATED_IMAGE_RE = re.compile(
    r"AI image|image generation|generated image|imagegen|DALL[- ]?E|Midjourney|Stable Diffusion|GPT[- ]?Image|"
    r"AI生图|AI 生图|大模型生图|生图|生成式图像|生成图片|生成图像|AI辅助生成|AI 辅助生成",
    re.I,
)
GENERATED_IMAGE_PROVENANCE_RE = re.compile(
    r"prompt|提示词|tool|工具|model|模型|version|版本|developer|开发|date|日期|human edit|人工修改|人工后处理|采纳|adoption",
    re.I,
)


@dataclass
class Finding:
    level: str
    file: str
    message: str


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--figures-dir", default="figures")
    parser.add_argument("--diagrams-dir", default="diagrams")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    figure_dir = resolve_path(root, args.figures_dir)
    diagram_dir = resolve_path(root, args.diagrams_dir)
    findings, metrics = audit(root, figure_dir, diagram_dir)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "root": str(root),
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve_path(root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve_path(root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERDICT: {payload['verdict']}")
    print("metrics: " + json.dumps(metrics, ensure_ascii=False, sort_keys=True))
    for item in findings:
        print(f"{item.level}: {item.file}: {item.message}")
    return 1 if payload["verdict"] == "FAIL" else 0


def audit(root: Path, figure_dir: Path, diagram_dir: Path) -> tuple[list[Finding], dict[str, Any]]:
    findings: list[Finding] = []
    assets = sorted(
        [path for base in [figure_dir, diagram_dir] if base.exists() for path in base.rglob("*") if path.suffix.lower() in IMAGE_SUFFIXES],
        key=lambda path: str(path).lower(),
    )
    indexed = indexed_assets(root, figure_dir / "figure_index.md") | indexed_assets(root, diagram_dir / "diagram_index.md")
    raster_count = 0
    vector_count = 0
    indexed_count = 0
    dimensioned = 0
    grid_code_warnings = 0
    palette_code_warnings = 0

    for asset in assets:
        rel_path = rel(root, asset)
        if asset.suffix.lower() in RASTER_SUFFIXES:
            raster_count += 1
            width, height = image_size(asset)
            if width and height:
                dimensioned += 1
                if width < MIN_WIDTH or height < MIN_HEIGHT:
                    findings.append(Finding("WARN", rel_path, f"image is small ({width}x{height}); labels may be unreadable in PDF"))
                aspect = width / max(height, 1)
                if aspect > 3.2 or aspect < 0.35:
                    findings.append(Finding("WARN", rel_path, f"unusual aspect ratio ({aspect:.2f}); verify it fits the paper column"))
            else:
                findings.append(Finding("WARN", rel_path, "could not read raster dimensions; verify rendering manually"))
        else:
            vector_count += 1

        size = asset.stat().st_size
        if size < MIN_BYTES:
            findings.append(Finding("WARN", rel_path, "file is very small; check for blank or placeholder figure"))
        if size > MAX_BYTES:
            findings.append(Finding("WARN", rel_path, "file is very large; consider vector/PDF or compressed PNG for final paper"))
        if placeholder_name(asset):
            findings.append(Finding("WARN", rel_path, "filename looks temporary or generic; use stable claim-oriented names"))
        if rel_path.lower() in indexed or asset.name.lower() in indexed:
            indexed_count += 1
        else:
            findings.append(Finding("WARN", rel_path, "asset is not referenced in figure_index.md or diagram_index.md"))

    style_findings = grid_style_findings(root)
    grid_code_warnings = len(style_findings)
    findings.extend(style_findings)
    palette_findings = palette_style_findings(root)
    palette_code_warnings = len(palette_findings)
    findings.extend(palette_findings)
    generated_image_findings, generated_image_metrics = generated_image_provenance_findings(root)
    findings.extend(generated_image_findings)

    if not assets:
        findings.append(Finding("FAIL", "-", "no visual assets found under figures/ or diagrams/"))
    elif indexed_count == 0:
        findings.append(Finding("FAIL", "-", "visual assets exist but none are indexed; create figure_index.md/diagram_index.md rows with supported claims"))

    metrics = {
        "assets": len(assets),
        "raster_assets": raster_count,
        "vector_assets": vector_count,
        "dimensioned_rasters": dimensioned,
        "indexed_assets": indexed_count,
        "grid_style_code_warnings": grid_code_warnings,
        "palette_code_warnings": palette_code_warnings,
        "ai_generated_visual_mentions": generated_image_metrics["mentions"],
        "ai_generated_visual_ledger_records": generated_image_metrics["ledger_records"],
        "ai_generated_visual_provenance_markers": generated_image_metrics["provenance_markers"],
        "warnings": sum(1 for item in findings if item.level == "WARN"),
        "failures": sum(1 for item in findings if item.level == "FAIL"),
    }
    return findings, metrics


def grid_style_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    scan_dirs = [root / "code", root / "figures", root / "diagrams"]
    for base in scan_dirs:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                if not GRID_STYLE_RE.search(line):
                    continue
                if GRID_ALLOW_RE.search(line):
                    continue
                findings.append(
                    Finding(
                        "WARN",
                        f"{rel(root, path)}:{line_no}",
                        "plotting code enables a grid backdrop; use clean white backgrounds and replace grids with threshold lines, annotations, or documented structural guides",
                    )
                )
    return findings


def palette_style_findings(root: Path) -> list[Finding]:
    findings: list[Finding] = []
    scan_dirs = [root / "code", root / "figures", root / "diagrams"]
    for base in scan_dirs:
        if not base.exists():
            continue
        for path in sorted(base.rglob("*.py")):
            if "__pycache__" in path.parts:
                continue
            try:
                lines = path.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
            except OSError:
                continue
            for line_no, line in enumerate(lines, start=1):
                if not BAD_PALETTE_RE.search(line):
                    continue
                if BAD_PALETTE_ALLOW_RE.search(line):
                    continue
                findings.append(
                    Finding(
                        "WARN",
                        f"{rel(root, path)}:{line_no}",
                        "plotting code uses a risky rainbow/red-green palette; use semantic palettes from color_palette_router.py or visual_style.py unless a waiver explains the choice",
                    )
                )
    return findings


def generated_image_provenance_findings(root: Path) -> tuple[list[Finding], dict[str, int]]:
    findings: list[Finding] = []
    source_paths = [
        root / "figures" / "figure_index.md",
        root / "diagrams" / "diagram_index.md",
        root / "planning" / "figure_storyboard.md",
        root / "planning" / "figure_storyboard.json",
        root / "planning" / "generated_image_route.md",
        root / "planning" / "generated_image_route.json",
    ]
    source_text = "\n".join(read_text(path) for path in source_paths if path.exists())
    mentions = len(GENERATED_IMAGE_RE.findall(source_text))
    provenance_markers = len(GENERATED_IMAGE_PROVENANCE_RE.findall(source_text))
    if mentions:
        if provenance_markers < 4:
            findings.append(
                Finding(
                    "WARN",
                    "figures/figure_index.md",
                    "AI-generated visual is mentioned but prompt/tool/model/date/human-edit provenance is thin; update the visual index or generated_image_route",
                )
            )
    return findings, {
        "mentions": mentions,
        "ledger_records": provenance_markers,
        "route_records": provenance_markers,
        "provenance_markers": provenance_markers,
    }


def indexed_assets(root: Path, index_path: Path) -> set[str]:
    if not index_path.exists():
        return set()
    text = read_text(index_path).lower()
    out: set[str] = set()
    for match in re.findall(r"[\w./\\-]+\.(?:png|jpg|jpeg|webp|svg|pdf)", text, flags=re.I):
        normalized = match.replace("\\", "/").lower()
        out.add(normalized)
        out.add(Path(normalized).name)
    return out


def image_size(path: Path) -> tuple[int | None, int | None]:
    suffix = path.suffix.lower()
    try:
        data = path.read_bytes()
    except OSError:
        return None, None
    if suffix == ".png" and data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return struct.unpack(">II", data[16:24])
    if suffix in {".jpg", ".jpeg"}:
        return jpeg_size(data)
    if suffix == ".webp" and len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return webp_size(data)
    return None, None


def jpeg_size(data: bytes) -> tuple[int | None, int | None]:
    idx = 2
    while idx + 9 < len(data):
        if data[idx] != 0xFF:
            idx += 1
            continue
        marker = data[idx + 1]
        idx += 2
        if marker in {0xD8, 0xD9}:
            continue
        if idx + 2 > len(data):
            break
        length = int.from_bytes(data[idx : idx + 2], "big")
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            if idx + 7 <= len(data):
                height = int.from_bytes(data[idx + 3 : idx + 5], "big")
                width = int.from_bytes(data[idx + 5 : idx + 7], "big")
                return width, height
        idx += max(length, 2)
    return None, None


def webp_size(data: bytes) -> tuple[int | None, int | None]:
    chunk = data[12:16]
    if chunk == b"VP8X" and len(data) >= 30:
        width = 1 + int.from_bytes(data[24:27], "little")
        height = 1 + int.from_bytes(data[27:30], "little")
        return width, height
    return None, None


def placeholder_name(path: Path) -> bool:
    name = path.stem.lower()
    return bool(re.search(r"(test|tmp|temp|new|untitled|figure\d*$|fig\d*$|image\d*$|plot\d*$)", name))


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Visual Asset Audit",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Root: `{payload['root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---:|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(["", "## Findings", "", "| Level | File | Message |", "|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | `{item['file']}` | {escape(item['message'])} |")
    lines.append("")
    return "\n".join(lines)


def resolve_path(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


if __name__ == "__main__":
    raise SystemExit(main())
