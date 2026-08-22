#!/usr/bin/env python3
"""Run compact regression benchmarks against a Mira project."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_ROOT = SCRIPT_DIR.parent
BENCHMARK_DIR = SKILL_ROOT / "benchmarks"


class NoBenchmarkMatch(Exception):
    """Raised when automatic benchmark routing finds no safe known-case match."""


@dataclass
class Check:
    level: str
    axis: str
    name: str
    message: str


class BenchmarkRegression:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.benchmark: dict[str, Any] = {}
        self.benchmark_path: Path | None = None
        self.frozen: dict[str, Any] = {}
        self.checks: list[Check] = []

    def run(self) -> int:
        self._load()
        if self.benchmark:
            self._check_expected_values()
            self._check_required_evidence()
            self._check_required_cards()
            self._check_stale_artifacts()
        self._write_outputs()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.checks) else 0

    def _load(self) -> None:
        try:
            self.benchmark_path, self.benchmark = resolve_benchmark(self.root, self.args.benchmark)
        except NoBenchmarkMatch as exc:
            self.info("benchmark", "auto", str(exc))
            return
        except FileNotFoundError as exc:
            self.fail("benchmark", "benchmark", str(exc))
            return
        frozen_rel = self.benchmark.get("frozen_numbers_path", "results/frozen_numbers.json")
        frozen_path = resolve_path(self.root, frozen_rel)
        if not frozen_path.exists():
            self.fail("frozen_numbers", "frozen", f"missing frozen numbers: {rel(self.root, frozen_path)}")
            return
        try:
            self.frozen = json.loads(read_text(frozen_path))
        except json.JSONDecodeError as exc:
            self.fail("frozen_numbers", "frozen", f"cannot parse {rel(self.root, frozen_path)}: {exc}")

    def _check_expected_values(self) -> None:
        for item in self.benchmark.get("expected", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or item.get("path") or "expected")
            path = str(item.get("path", ""))
            expected = item.get("value")
            tol = float(item.get("abs_tol", 0.0))
            actual = dotted_get(self.frozen, path)
            if actual is None:
                self.fail("numeric", name, f"missing `{path}` in frozen numbers")
                continue
            if not is_number(actual) or not is_number(expected):
                if actual == expected:
                    self.pass_("numeric", name, f"`{path}` matched nonnumeric value `{actual}`")
                else:
                    self.fail("numeric", name, f"`{path}` expected `{expected}`, got `{actual}`")
                continue
            actual_f = float(actual)
            expected_f = float(expected)
            delta = abs(actual_f - expected_f)
            if delta <= tol:
                self.pass_("numeric", name, f"`{path}`={actual_f:g}, expected {expected_f:g}, delta {delta:g} <= {tol:g}")
            else:
                self.fail("numeric", name, f"`{path}`={actual_f:g}, expected {expected_f:g}, delta {delta:g} > {tol:g}")

    def _check_required_evidence(self) -> None:
        for item in self.benchmark.get("required_evidence", []):
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "evidence")
            paths = [str(path) for path in item.get("paths", [])]
            terms = [str(term) for term in item.get("terms", [])]
            existing_texts: list[str] = []
            missing_paths: list[str] = []
            for rel_path in paths:
                path = resolve_path(self.root, rel_path)
                if path.exists() and path.is_file():
                    existing_texts.append(read_text(path))
                else:
                    missing_paths.append(rel_path)
            if missing_paths:
                self.fail("evidence", name, "missing evidence files: " + ", ".join(f"`{path}`" for path in missing_paths))
                continue
            combined = "\n".join(existing_texts).lower()
            missing_terms = [term for term in terms if term.lower() not in combined]
            if missing_terms:
                self.fail("evidence", name, "evidence exists but lacks terms: " + ", ".join(missing_terms))
            else:
                self.pass_("evidence", name, "required evidence files and terms are present")

    def _check_required_cards(self) -> None:
        required = [item for item in self.benchmark.get("required_cards", []) if isinstance(item, dict)]
        if not required:
            return
        text = collect_card_trace_text(self.root)
        for item in required:
            name = str(item.get("name") or item.get("path_contains") or "card")
            needle = str(item.get("path_contains") or "").lower()
            if not needle:
                continue
            if needle in text.lower():
                self.pass_("knowledge_card", name, f"project traces selected card containing `{needle}`")
            else:
                self.fail("knowledge_card", name, f"project does not trace a required card containing `{needle}`")

    def _check_stale_artifacts(self) -> None:
        for item in self.benchmark.get("stale_artifact_checks", []):
            if not isinstance(item, dict):
                continue
            artifact = str(item.get("artifact", ""))
            values = [str(value) for value in item.get("forbidden_values", [])]
            message = str(item.get("message") or "stale forbidden value found")
            path = resolve_path(self.root, artifact)
            if not path.exists():
                self.warn("stale_artifact", artifact, f"artifact not found, stale scan skipped: `{artifact}`")
                continue
            text = read_text(path)
            found = [value for value in values if value and value in text]
            if found:
                self.fail("stale_artifact", artifact, f"{message}; found forbidden values: {', '.join(found)}")
            else:
                self.pass_("stale_artifact", artifact, "no forbidden stale values found")

    def _write_outputs(self) -> None:
        if self.args.write_report:
            path = resolve_path(self.root, self.args.write_report)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(self._markdown(), encoding="utf-8")
        if self.args.write_json:
            path = resolve_path(self.root, self.args.write_json)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self._payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _markdown(self) -> str:
        verdict = self.verdict()
        lines = [
            "# Mira Benchmark Regression",
            "",
            f"- Generated: {now()}",
            f"- Verdict: **{verdict}**",
            f"- Root: `{self.root}`",
            f"- Benchmark: `{self.benchmark.get('id', '-')}`",
            f"- Benchmark file: `{self.benchmark_path if self.benchmark_path else '-'}`",
            "",
            "## Checks",
            "",
            "| Level | Axis | Name | Message |",
            "|---|---|---|---|",
        ]
        for item in self.checks:
            lines.append(f"| {item.level} | {item.axis} | {escape(item.name)} | {escape(item.message)} |")
        if not self.checks:
            lines.append("| INFO | benchmark | - | no checks ran |")
        known = self.benchmark.get("known_failures", [])
        if known:
            lines.extend(["", "## Known Failure Modes", ""])
            for item in known:
                lines.append(f"- {item}")
        lines.append("")
        return "\n".join(lines)

    def _payload(self) -> dict[str, Any]:
        return {
            "generated_at": now(),
            "root": str(self.root),
            "benchmark": self.benchmark.get("id"),
            "benchmark_path": str(self.benchmark_path) if self.benchmark_path else None,
            "verdict": self.verdict(),
            "checks": [asdict(item) for item in self.checks],
        }

    def _emit(self) -> None:
        _print(f"BENCHMARK: {self.benchmark.get('id', '-')}")
        _print(f"VERDICT: {self.verdict()}")
        counts: dict[str, int] = {}
        for item in self.checks:
            counts[item.level] = counts.get(item.level, 0) + 1
            if item.level in {"FAIL", "WARN"}:
                _print(f"{item.level}: [{item.axis}] {item.name}: {item.message}")
        _print("counts: " + json.dumps(counts, ensure_ascii=False, sort_keys=True))
        if self.args.write_report:
            _print(f"wrote: {resolve_path(self.root, self.args.write_report)}")
        if self.args.write_json:
            _print(f"wrote: {resolve_path(self.root, self.args.write_json)}")

    def verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.checks):
            return "FAIL"
        if any(item.level == "WARN" for item in self.checks):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def pass_(self, axis: str, name: str, message: str) -> None:
        self.checks.append(Check("PASS", axis, name, message))

    def warn(self, axis: str, name: str, message: str) -> None:
        self.checks.append(Check("WARN", axis, name, message))

    def fail(self, axis: str, name: str, message: str) -> None:
        self.checks.append(Check("FAIL", axis, name, message))

    def info(self, axis: str, name: str, message: str) -> None:
        self.checks.append(Check("INFO", axis, name, message))


def resolve_benchmark(root: Path, spec: str) -> tuple[Path, dict[str, Any]]:
    if not spec or spec == "auto":
        candidates = sorted(BENCHMARK_DIR.glob("*.json"))
        if not candidates:
            raise NoBenchmarkMatch(f"no benchmark JSON files under {BENCHMARK_DIR}")
        context = (root.name + "\n" + read_text(root / "results" / "frozen_numbers.json")[:4000]).lower()
        scored: list[tuple[int, Path, dict[str, Any]]] = []
        for path in candidates:
            data = json.loads(read_text(path))
            hints = [str(item).lower() for item in data.get("project_hints", [])]
            score = sum(1 for hint in hints if hint and hint in context)
            scored.append((score, path, data))
        scored.sort(key=lambda item: (-item[0], item[1].name))
        if scored[0][0] <= 0:
            raise NoBenchmarkMatch("no known-case benchmark matched this project; pass --benchmark explicitly if this is intentional")
        return scored[0][1], scored[0][2]

    raw = Path(spec)
    candidates = [raw]
    if not raw.suffix:
        candidates.append(raw.with_suffix(".json"))
    candidates.extend([BENCHMARK_DIR / raw.name, BENCHMARK_DIR / (raw.name + ".json")])
    for path in candidates:
        if path.exists():
            data = json.loads(read_text(path))
            return path.resolve(), data
    raise FileNotFoundError(f"benchmark not found: {spec}")


def collect_card_trace_text(root: Path) -> str:
    parts: list[str] = []
    for pattern in [
        "planning/knowledge_injection*.json",
        "planning/knowledge_injection*.md",
        "planning/validation_plan*.json",
        "planning/validation_plan*.md",
        "planning/modeling_plan.md",
        "planning/method_route*.json",
        "planning/method_route*.md",
    ]:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                parts.append(read_text(path)[:100000])
    return "\n".join(parts)


def dotted_get(data: Any, path: str) -> Any:
    current = data
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return None
    return current


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(float(value))


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
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--benchmark", default="auto", help="Benchmark id/path, or auto")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return BenchmarkRegression(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
