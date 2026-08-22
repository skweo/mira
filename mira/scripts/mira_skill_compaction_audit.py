#!/usr/bin/env python3
"""Audit Mira skill size, routing coverage, and compaction risks."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from reference_registry_audit import audit_registry


@dataclass
class Finding:
    level: str
    axis: str
    message: str


def main() -> int:
    args = parse_args()
    skill_root = Path(args.skill_root).resolve()
    metrics = collect_metrics(skill_root)
    findings = review(metrics)
    payload = {
        "generated_at": now(),
        "skill_root": str(skill_root),
        "verdict": verdict(findings),
        "metrics": metrics,
        "findings": [asdict(item) for item in findings],
    }
    if args.write_report:
        path = resolve(skill_root, args.write_report)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(markdown(payload), encoding="utf-8")
    if args.write_json:
        path = resolve(skill_root, args.write_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _print(f"VERDICT: {payload['verdict']}")
    for key, value in metrics.items():
        _print(f"METRIC: {key}={value}")
    for finding in findings:
        _print(f"{finding.level}: [{finding.axis}] {finding.message}")
    if args.write_report:
        _print(f"wrote: {resolve(skill_root, args.write_report)}")
    if args.write_json:
        _print(f"wrote: {resolve(skill_root, args.write_json)}")
    return 1 if payload["verdict"] == "FAIL" else 0


def collect_metrics(skill_root: Path) -> dict[str, Any]:
    skill_md = skill_root / "SKILL.md"
    skill_text = read_text(skill_md)
    references = sorted((skill_root / "references").glob("*.md")) if (skill_root / "references").exists() else []
    scripts = sorted((skill_root / "scripts").glob("*.py")) if (skill_root / "scripts").exists() else []
    route_text = read_text(skill_root / "scripts" / "route_references.py")
    registry_audit = audit_registry(skill_root)
    all_text = collect_all_text(skill_root)
    active_version = active_version_from(skill_text)
    routed_refs = sorted(set(re.findall(r"references/[A-Za-z0-9_.\-/]+\.md", route_text + "\n" + skill_text)))
    script_names = [path.name for path in scripts]
    mentioned_scripts = mentioned_script_names(all_text, script_names)
    version_files = [path for path in references if re.match(r"mira-version-", path.name)]
    command_names = re.findall(r"scripts\\([A-Za-z0-9_]+\.py)|scripts/([A-Za-z0-9_]+\.py)", route_text + "\n" + skill_text)
    flat_commands = [left or right for left, right in command_names]
    return {
        "skill_md_exists": skill_md.exists(),
        "skill_lines": len(skill_text.splitlines()),
        "skill_words": len(re.findall(r"\S+", skill_text)),
        "skill_chars": len(skill_text),
        "active_version": active_version,
        "version_paragraph_count": len(re.findall(r"^Mira 0\.", skill_text, flags=re.M)),
        "reference_count": len(references),
        "reference_registry_verdict": registry_audit["verdict"],
        "registered_reference_count": registry_audit["metrics"]["registered_references"],
        "reference_status_counts": registry_audit["metrics"]["status_counts"],
        "reference_cleanup_queue": registry_audit["metrics"]["cleanup_queue"],
        "script_count": len(scripts),
        "version_file_count": len(version_files),
        "largest_references": top_sizes(skill_root, references, 10),
        "long_reference_count": sum(1 for path in references if path.stat().st_size > 10_000 or line_count(path) > 160),
        "routed_reference_count": len(routed_refs),
        "unrouted_references": [rel(skill_root, path) for path in references if rel(skill_root, path) not in routed_refs],
        "mentioned_script_count": len(mentioned_scripts),
        "unmentioned_scripts": [f"scripts/{name}" for name in script_names if name not in mentioned_scripts and name != "mira_skill_compaction_audit.py"],
        "duplicate_command_entries": duplicate_counts(flat_commands),
        "stale_version_route_hits": stale_version_hits(route_text + "\n" + skill_text, active_version),
        "has_skill_compaction_rules": (skill_root / "references" / "skill-compaction-control-rules.md").exists(),
    }


def review(metrics: dict[str, Any]) -> list[Finding]:
    findings: list[Finding] = []
    if not metrics["skill_md_exists"]:
        return [Finding("FAIL", "skill_root", "SKILL.md was not found")]
    if metrics["skill_lines"] > 500:
        findings.append(Finding("FAIL", "skill_size", "SKILL.md exceeds the hard refactor zone of 500 lines"))
    elif metrics["skill_lines"] > 300:
        findings.append(Finding("WARN", "skill_size", "SKILL.md is above the 300-line warning zone"))
    elif metrics["skill_lines"] > 250:
        findings.append(Finding("WARN", "skill_size", "SKILL.md is above the 250-line target; move history/details to references when convenient"))
    if metrics["skill_chars"] > 50_000:
        findings.append(Finding("WARN", "skill_size", "SKILL.md is over 50k characters; keep only control-plane instructions in the main file"))
    if metrics["version_paragraph_count"] > 12:
        findings.append(Finding("WARN", "version_history", "many version paragraphs remain in SKILL.md; consider a compact version index"))
    if metrics["version_file_count"] > 16:
        findings.append(Finding("WARN", "version_files", "many one-version files are active; consider archiving old version notes"))
    if metrics["reference_count"] > 70:
        findings.append(Finding("WARN", "reference_count", "reference count is high; keep the registry and bounded routes authoritative"))
    if metrics["long_reference_count"] > 8:
        findings.append(Finding("WARN", "long_references", "many long references exist; ensure they are phase/risk routed, not loaded by default"))
    if metrics["reference_registry_verdict"] != "PASS":
        findings.append(Finding("FAIL", "reference_registry", "top-level reference registry audit failed"))
    elif len(metrics["unrouted_references"]) > 12 and metrics["registered_reference_count"] != metrics["reference_count"]:
        findings.append(Finding("WARN", "reference_routing", "many references are not visible in SKILL.md or route_references.py; classify before deleting"))
    if len(metrics["unmentioned_scripts"]) > 8:
        findings.append(Finding("WARN", "script_routing", "many scripts are not visibly mentioned; check imports or archive candidates before deleting"))
    if metrics["stale_version_route_hits"]:
        findings.append(Finding("WARN", "active_version", "older mira-version references still appear in active routing or SKILL text"))
    if len(metrics["duplicate_command_entries"]) > 6:
        findings.append(Finding("WARN", "command_duplication", "many duplicate command entries exist; consider command profiles or a runner script"))
    if not metrics["has_skill_compaction_rules"]:
        findings.append(Finding("WARN", "compaction_rules", "skill compaction rules reference was not found"))
    return findings


def collect_all_text(root: Path) -> str:
    chunks: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix.lower() not in {".md", ".py", ".yaml", ".yml", ".json"}:
            continue
        if "__pycache__" in path.parts:
            continue
        chunks.append(read_text(path))
    return "\n".join(chunks)


def mentioned_script_names(text: str, available_scripts: list[str] | None = None) -> set[str]:
    """Return scripts named explicitly or referenced by a local Python import.

    The compaction audit previously understood only literal ``helper.py`` text.
    Production callers normally use ``from helper import ...`` or
    ``import helper``, so valid shared modules could be reported as cleanup
    candidates.  Import-derived names are accepted only when a matching Python
    file actually exists in the audited ``scripts/`` directory.
    """
    names = set(re.findall(r"([A-Za-z0-9_]+\.py)", text))
    names.update(re.findall(r"scripts[/\\]([A-Za-z0-9_]+\.py)", text))
    available = {Path(name).stem: name for name in (available_scripts or [])}
    if not available:
        return names

    imported_modules: set[str] = set()
    imported_modules.update(
        module.lstrip(".").split(".")[-1]
        for module in re.findall(
            r"(?m)^\s*from\s+([.A-Za-z_][A-Za-z0-9_.]*)\s+import\s+",
            text,
        )
    )
    for clause in re.findall(r"(?m)^\s*import\s+([^#\n]+)", text):
        for item in clause.split(","):
            module = re.split(r"\s+as\s+", item.strip(), maxsplit=1)[0]
            if module:
                imported_modules.add(module.lstrip(".").split(".")[-1])

    names.update(available[module] for module in imported_modules if module in available)
    return names


def active_version_from(text: str) -> str:
    match = re.search(r"Current baseline:\s*\*\*Mira ([0-9.]+)\*\*", text)
    return match.group(1) if match else ""


def stale_version_hits(text: str, active_version: str) -> list[str]:
    hits = sorted(set(re.findall(r"mira-version-([0-9.]+)\.md", text)))
    return [version for version in hits if version != active_version]


def duplicate_counts(values: list[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return {key: value for key, value in sorted(counts.items()) if value > 1}


def top_sizes(root: Path, paths: list[Path], limit: int) -> list[dict[str, Any]]:
    rows = [{"path": rel(root, path), "bytes": path.stat().st_size, "lines": line_count(path)} for path in paths]
    return sorted(rows, key=lambda item: item["bytes"], reverse=True)[:limit]


def line_count(path: Path) -> int:
    return len(read_text(path).splitlines())


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Mira Skill Compaction Audit",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Skill root: `{payload['skill_root']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(value)} |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Message |", "|---|---|---|"])
    if payload["findings"]:
        for item in payload["findings"]:
            lines.append(f"| {item['level']} | {item['axis']} | {escape(item['message'])} |")
    else:
        lines.append("| INFO | skill_compaction | no findings |")
    lines.append("")
    return "\n".join(lines)


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve(root: Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _print(text: str) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(text, flush=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skill-root", default=".", help="Mira skill root")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


if __name__ == "__main__":
    raise SystemExit(main())
