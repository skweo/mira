#!/usr/bin/env python3
"""Build a per-file before/after hash manifest for a Mira release candidate."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_baseline(path: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, list):
        raise ValueError("baseline manifest must be a JSON list")
    rows: dict[str, dict[str, Any]] = {}
    for item in payload:
        if not isinstance(item, dict):
            raise ValueError("baseline manifest rows must be JSON objects")
        relative = str(item.get("path") or "").replace("\\", "/").strip("/")
        digest = str(item.get("sha256") or "").upper()
        if not relative or len(digest) != 64 or relative in rows:
            raise ValueError(f"invalid or duplicate baseline row: {relative or '<missing>'}")
        rows[relative] = {
            "size": int(item.get("size") or 0),
            "sha256": digest,
        }
    return rows


def inventory(root: Path, excluded: set[Path]) -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in sorted((item for item in root.rglob("*") if item.is_file()), key=lambda item: item.as_posix().lower()):
        resolved = path.resolve()
        if resolved in excluded:
            continue
        relative = path.relative_to(root).as_posix()
        rows[relative] = {"size": path.stat().st_size, "sha256": sha256(path)}
    return rows


def aggregate(rows: dict[str, dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(rows):
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(rows[relative]["sha256"].encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest().upper()


def build_manifest(
    baseline_path: Path,
    current_root: Path,
    excluded: set[Path] | None = None,
    excluded_current_files: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    before = load_baseline(baseline_path)
    control_exclusions = excluded_current_files or []
    excluded_relatives = {str(item["path"]) for item in control_exclusions}
    before = {relative: row for relative, row in before.items() if relative not in excluded_relatives}
    excluded_paths = set(excluded or set())
    excluded_paths.update((current_root / relative).resolve() for relative in excluded_relatives)
    after = inventory(current_root, excluded_paths)
    files: list[dict[str, Any]] = []
    for relative in sorted(set(before) | set(after)):
        prior = before.get(relative)
        current = after.get(relative)
        if prior is None:
            status = "ADDED"
        elif current is None:
            status = "REMOVED"
        elif prior == current:
            status = "UNCHANGED"
        else:
            status = "MODIFIED"
        files.append({"path": relative, "status": status, "before": prior, "after": current})
    counts = Counter(item["status"] for item in files)
    return {
        "schema_version": 1,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "baseline_manifest": str(baseline_path.resolve()),
        "baseline_manifest_sha256": sha256(baseline_path),
        "current_root": str(current_root.resolve()),
        "status": "PASS",
        "counts": {
            "baseline": len(before),
            "current": len(after),
            "added": counts["ADDED"],
            "modified": counts["MODIFIED"],
            "removed": counts["REMOVED"],
            "unchanged": counts["UNCHANGED"],
        },
        "baseline_aggregate_sha256": aggregate(before),
        "current_aggregate_sha256": aggregate(after),
        "excluded_current_files": control_exclusions,
        "files": files,
    }


def parse_control_exclusions(current_root: Path, values: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for value in values:
        relative_text, separator, reason = value.partition("=")
        relative = relative_text.replace("\\", "/").strip().strip("/")
        reason = reason.strip()
        if not separator or not relative or not reason:
            raise ValueError("--exclude-current must be RELATIVE_PATH=REASON")
        path = (current_root / relative).resolve()
        try:
            normalized = path.relative_to(current_root).as_posix()
        except ValueError as exc:
            raise ValueError(f"excluded path is outside current root: {relative}") from exc
        if normalized in seen:
            raise ValueError(f"duplicate excluded path: {normalized}")
        if not path.is_file():
            raise ValueError(f"excluded current file does not exist: {normalized}")
        seen.add(normalized)
        rows.append(
            {
                "path": normalized,
                "reason": reason,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )
    return sorted(rows, key=lambda item: str(item["path"]).lower())


def render_markdown(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        "# Mira Release Change Manifest",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Status: **{payload['status']}**",
        f"- Baseline files: {counts['baseline']}",
        f"- Current files: {counts['current']}",
        f"- Added: {counts['added']}",
        f"- Modified: {counts['modified']}",
        f"- Removed: {counts['removed']}",
        f"- Unchanged: {counts['unchanged']}",
        f"- Baseline aggregate SHA256: `{payload['baseline_aggregate_sha256']}`",
        f"- Current aggregate SHA256: `{payload['current_aggregate_sha256']}`",
        "",
        "## Explicit Control-Metadata Exclusions",
        "",
        "| Path | Reason | SHA256 |",
        "|---|---|---|",
    ]
    for item in payload.get("excluded_current_files", []):
        lines.append(f"| `{item['path']}` | {item['reason']} | `{item['sha256']}` |")
    if not payload.get("excluded_current_files"):
        lines.append("| - | None | - |")
    lines.extend(
        [
            "",
        "## Changed Files",
        "",
        "| Status | Path | Before SHA256 | After SHA256 |",
        "|---|---|---|---|",
        ]
    )
    for item in payload["files"]:
        if item["status"] == "UNCHANGED":
            continue
        before = item["before"]["sha256"] if item["before"] else "-"
        after = item["after"]["sha256"] if item["after"] else "-"
        lines.append(f"| {item['status']} | `{item['path']}` | `{before}` | `{after}` |")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", required=True)
    parser.add_argument("--current-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--write-json", required=True)
    parser.add_argument("--write-report")
    parser.add_argument(
        "--exclude-current",
        action="append",
        default=[],
        metavar="RELATIVE_PATH=REASON",
        help="exclude self-referential release control metadata while recording its hash and reason",
    )
    args = parser.parse_args()

    baseline_path = Path(args.baseline_manifest).resolve()
    current_root = Path(args.current_root).resolve()
    json_path = Path(args.write_json).resolve()
    report_path = Path(args.write_report).resolve() if args.write_report else None
    excluded = {json_path}
    if report_path:
        excluded.add(report_path)
    try:
        control_exclusions = parse_control_exclusions(current_root, args.exclude_current)
    except ValueError as exc:
        parser.error(str(exc))
    payload = build_manifest(baseline_path, current_root, excluded, control_exclusions)

    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if report_path:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(render_markdown(payload), encoding="utf-8")
    print(f"VERDICT: {payload['status']}")
    print(f"CURRENT_AGGREGATE_SHA256: {payload['current_aggregate_sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
