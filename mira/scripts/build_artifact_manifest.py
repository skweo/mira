#!/usr/bin/env python3
"""Build an artifact manifest for a Mira math-modeling contest project."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


CODE_SUFFIXES = {".py", ".m", ".ipynb", ".r", ".jl"}
DATA_SUFFIXES = {".csv", ".xlsx", ".xls", ".json", ".md", ".txt", ".mat", ".pkl", ".parquet"}
FIGURE_SUFFIXES = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".webp"}
PAPER_SUFFIXES = {".tex", ".typ", ".md"}


@dataclass
class Finding:
    level: str
    message: str


class ManifestBuilder:
    def __init__(self, root: Path, strict: bool = False, write: bool = True) -> None:
        self.root = root.resolve()
        self.strict = strict
        self.write = write
        self.checks_dir = self.root / "checks"
        self.findings: list[Finding] = []

    def info(self, message: str) -> None:
        self.findings.append(Finding("INFO", message))

    def warn(self, message: str) -> None:
        self.findings.append(Finding("WARN", message))

    def fail(self, message: str) -> None:
        self.findings.append(Finding("FAIL", message))

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path)

    def run(self) -> int:
        manifest = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "root": str(self.root),
            "strict": self.strict,
            "directories": self._directories(),
            "code": self._code(),
            "results": self._results(),
            "figures": self._figures(),
            "diagrams": self._diagrams(),
            "paper": self._paper(),
        }
        self._cross_checks(manifest)
        manifest["findings"] = [finding.__dict__ for finding in self.findings]

        if self.write:
            self.checks_dir.mkdir(parents=True, exist_ok=True)
            (self.checks_dir / "artifact_manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            (self.checks_dir / "artifact_manifest.md").write_text(
                self._markdown(manifest),
                encoding="utf-8",
            )

        for finding in self.findings:
            print(f"{finding.level}: {finding.message}")
        if self.write:
            print(f"INFO: wrote {self.rel(self.checks_dir / 'artifact_manifest.json')}")
            print(f"INFO: wrote {self.rel(self.checks_dir / 'artifact_manifest.md')}")

        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _directories(self) -> dict[str, bool]:
        names = [
            "problem",
            "data_raw",
            "data_clean",
            "planning",
            "code",
            "results",
            "results/tables",
            "results/logs",
            "results/audits",
            "results/figures_data",
            "figures",
            "diagrams",
            "paper",
            "checks",
            "revisions",
        ]
        out = {name: (self.root / name).exists() for name in names}
        for name, exists in out.items():
            if not exists and name in {"planning", "code", "results", "paper"}:
                self.warn(f"missing canonical directory: {name}")
        return out

    def _code(self) -> dict[str, object]:
        code_dir = self.root / "code"
        files = self._files(code_dir, CODE_SUFFIXES)
        notebooks = [item for item in files if item["suffix"] == ".ipynb"]
        if not files:
            self.warn("no code files found under code/")
        return {
            "files": files,
            "notebooks": notebooks,
            "count": len(files),
        }

    def _results(self) -> dict[str, object]:
        result_report = self.root / "results" / "result_report.md"
        frozen_numbers = self.root / "results" / "frozen_numbers.json"
        logs = self._files(self.root / "results" / "logs", DATA_SUFFIXES)
        tables = self._files(self.root / "results" / "tables", DATA_SUFFIXES)
        audits = self._files(self.root / "results" / "audits", DATA_SUFFIXES)
        figure_data = self._files(self.root / "results" / "figures_data", DATA_SUFFIXES)

        if not result_report.exists():
            self._gap("missing results/result_report.md")
        if not logs:
            self.warn("no run logs found under results/logs/")

        return {
            "result_report": self._file_info(result_report) if result_report.exists() else None,
            "frozen_numbers": self._file_info(frozen_numbers) if frozen_numbers.exists() else None,
            "logs": logs,
            "tables": tables,
            "audits": audits,
            "figure_data": figure_data,
        }

    def _figures(self) -> dict[str, object]:
        figures_dir = self.root / "figures"
        index = figures_dir / "figure_index.md"
        files = self._files(figures_dir, FIGURE_SUFFIXES, recursive=False)
        index_text = self._read(index) if index.exists() else ""
        indexed_names = self._names_in_text(index_text)

        if files and not index.exists():
            self._gap("figures exist but figures/figure_index.md is missing")
        if index.exists() and not self._has_trace_terms(index_text):
            self.warn("figure_index.md may not record source data, feature summary, and supported claim")
        for item in files:
            if index.exists() and item["name"] not in indexed_names:
                self.warn(f"figure not listed in figure_index.md: {item['name']}")

        return {
            "index": self._file_info(index) if index.exists() else None,
            "files": files,
            "count": len(files),
        }

    def _diagrams(self) -> dict[str, object]:
        diagrams_dir = self.root / "diagrams"
        index = diagrams_dir / "diagram_index.md"
        files = self._files(
            diagrams_dir,
            FIGURE_SUFFIXES | {".drawio", ".mmd", ".tex", ".typ"},
            recursive=False,
        )
        if files and not index.exists():
            self.warn("diagrams exist but diagrams/diagram_index.md is missing")
        return {
            "index": self._file_info(index) if index.exists() else None,
            "files": files,
            "count": len(files),
        }

    def _paper(self) -> dict[str, object]:
        paper_dir = self.root / "paper"
        entries = [
            path
            for path in [paper_dir / "main.tex", paper_dir / "main.typ", paper_dir / "main.md"]
            if path.exists()
        ]
        sections = self._files(paper_dir / "sections", PAPER_SUFFIXES)
        refs = [
            path
            for path in [paper_dir / "references.tex", paper_dir / "references.typ", paper_dir / "references.bib"]
            if path.exists()
        ]

        body_text_parts: list[tuple[Path, str]] = []
        text_parts: list[tuple[Path, str]] = []
        for path in entries:
            body_text_parts.append((path, self._read(path)))
        for item in sections:
            path = self.root / str(item["path"])
            body_text_parts.append((path, self._read(path)))
        text_parts.extend(body_text_parts)
        for path in refs:
            text_parts.append((path, self._read(path)))

        image_refs = self._image_refs(text_parts)
        citations = self._citation_count("\n".join(text for _, text in body_text_parts))

        if not entries:
            self.warn("no paper entry file found under paper/")
        if citations and not refs:
            self._gap("paper has citation markers but no references file")

        return {
            "entries": [self._file_info(path) for path in entries],
            "sections": sections,
            "references": [self._file_info(path) for path in refs],
            "image_refs": image_refs,
            "citation_markers": citations,
        }

    def _cross_checks(self, manifest: dict[str, object]) -> None:
        code = manifest["code"]  # type: ignore[assignment]
        results = manifest["results"]  # type: ignore[assignment]
        paper = manifest["paper"]  # type: ignore[assignment]

        if code["count"] and not results["logs"]:  # type: ignore[index]
            self._gap("code files exist but no run logs were found")

        for ref in paper["image_refs"]:  # type: ignore[index]
            source = Path(ref["from"])
            target = (source.parent / ref["ref"]).resolve()
            if not target.exists():
                self.fail(f"paper references missing image: {ref['ref']} from {self.rel(source)}")

        figure_files = {item["name"] for item in manifest["figures"]["files"]}  # type: ignore[index]
        if paper["image_refs"] and figure_files:  # type: ignore[index]
            for ref in paper["image_refs"]:  # type: ignore[index]
                name = Path(ref["ref"]).name
                source = Path(ref["from"])
                if name not in figure_files and not (source.parent / ref["ref"]).exists():
                    self.warn(f"paper image is not in figures/ and was not resolved: {name}")

    def _gap(self, message: str) -> None:
        if self.strict:
            self.fail(message)
        else:
            self.warn(message)

    def _files(self, directory: Path, suffixes: set[str], recursive: bool = True) -> list[dict[str, object]]:
        if not directory.exists():
            return []
        iterator: Iterable[Path] = directory.rglob("*") if recursive else directory.glob("*")
        out = [
            self._file_info(path)
            for path in iterator
            if path.is_file() and path.suffix.lower() in suffixes and "__pycache__" not in path.parts
        ]
        return sorted(out, key=lambda item: str(item["path"]))

    def _file_info(self, path: Path) -> dict[str, object]:
        stat = path.stat()
        return {
            "path": self.rel(path),
            "name": path.name,
            "suffix": path.suffix.lower(),
            "size": stat.st_size,
            "mtime": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
        }

    def _read(self, path: Path) -> str:
        if not path.exists():
            return ""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return path.read_text(encoding="utf-8", errors="ignore")

    def _names_in_text(self, text: str) -> set[str]:
        return {
            match.group(0)
            for match in re.finditer(r"[\w.-]+\.(?:pdf|png|jpg|jpeg|svg|webp|csv|xlsx|json)", text, re.I)
        }

    def _has_trace_terms(self, text: str) -> bool:
        lower = text.lower()
        terms = ["source", "data", "script", "claim", "summary", "feature", "figures_data", "supported"]
        return any(term in lower for term in terms)

    def _image_refs(self, text_parts: list[tuple[Path, str]]) -> list[dict[str, str]]:
        refs: list[dict[str, str]] = []
        patterns = [
            re.compile(r"\\includegraphics\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}"),
            re.compile(r'image\(\s*"([^"]+)"'),
            re.compile(r"!\[[^\]]*\]\(([^)]+\.(?:pdf|png|jpg|jpeg|svg|webp))\)", re.I),
        ]
        for path, text in text_parts:
            for pattern in patterns:
                for match in pattern.finditer(text):
                    refs.append({"from": str(path), "ref": match.group(1)})
        return refs

    def _citation_count(self, text: str) -> int:
        latex = re.findall(r"\\cite\w*\{[^}]+\}", text)
        typst = re.findall(r"#cite\(|@\w[\w:-]*", text)
        return len(latex) + len(typst)

    def _markdown(self, manifest: dict[str, object]) -> str:
        findings = manifest["findings"]  # type: ignore[index]
        lines = [
            "# Artifact Manifest",
            "",
            f"- Root: `{manifest['root']}`",
            f"- Generated: `{manifest['generated_at']}`",
            f"- Strict: `{manifest['strict']}`",
            "",
            "## Counts",
            "",
            f"- Code files: {manifest['code']['count']}",  # type: ignore[index]
            f"- Figures: {manifest['figures']['count']}",  # type: ignore[index]
            f"- Diagrams: {manifest['diagrams']['count']}",  # type: ignore[index]
            f"- Paper entries: {len(manifest['paper']['entries'])}",  # type: ignore[index]
            f"- Paper image refs: {len(manifest['paper']['image_refs'])}",  # type: ignore[index]
            f"- Citation markers: {manifest['paper']['citation_markers']}",  # type: ignore[index]
            "",
            "## Findings",
            "",
        ]
        if not findings:
            lines.append("- PASS: no findings")
        else:
            for item in findings:
                lines.append(f"- {item['level']}: {item['message']}")
        lines.extend(["", "## Key Files", ""])
        for group, label in [
            ("code", "Code"),
            ("figures", "Figures"),
            ("diagrams", "Diagrams"),
        ]:
            files = manifest[group]["files"]  # type: ignore[index]
            lines.append(f"### {label}")
            if files:
                for item in files[:100]:
                    lines.append(f"- `{item['path']}`")
                if len(files) > 100:
                    lines.append(f"- ... {len(files) - 100} more")
            else:
                lines.append("- none")
            lines.append("")
        return "\n".join(lines) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--strict", action="store_true", help="Treat missing handoff artifacts as failures")
    parser.add_argument("--no-write", action="store_true", help="Print findings without writing manifest files")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    return ManifestBuilder(Path(args.root), strict=args.strict, write=not args.no_write).run()


if __name__ == "__main__":
    raise SystemExit(main())
