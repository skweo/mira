#!/usr/bin/env python3
"""Guard the attachment-to-subquestion mapping before data use.

The gate is intentionally narrow: inventory official/data attachments, preview
only headers plus the first three rows, and require a credible Qx or SHARED
mapping before modeling or cleaning code consumes the files.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


TABULAR_EXTS = {".csv", ".tsv", ".xlsx", ".xls", ".txt", ".dat", ".json"}
MEDIA_EXTS = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".gif", ".mp4", ".avi", ".mov"}
DATA_EXTS = TABULAR_EXTS | MEDIA_EXTS | {".mat", ".npy", ".npz"}
DEFAULT_DATA_DIRS = [
    "data_raw",
    "data/raw",
    "workspace/data/data_raw",
    "workspace/data_raw",
]
PROBLEM_TEXT_FILES = [
    "planning/problem_analysis.md",
    "planning/problem_brief.md",
    "planning/modeling_plan.md",
    "planning/delivery_brief.md",
]
QID_PATTERN = re.compile(
    r"(?:\bQ\s*([1-9])\b|问题\s*([一二三四五六七八九1-9])|第\s*([一二三四五六七八九1-9])\s*[问题])",
    re.I,
)
ATTACHMENT_REF_PATTERN = re.compile(
    r"(附件\s*[0-9一二三四五六七八九十]+|attachment(?:\s+|-)?(?:[0-9]+|[A-Z]\b)|appendix(?:\s+|-)?(?:[0-9]+|[A-Z]\b))"
)
APPENDIX_ALIAS_PATTERN = re.compile(
    r"^[ \t\f]*((?:附件|附录)\s*[0-9一二三四五六七八九十]+|(?:attachment|appendix)(?:\s+|-)?(?:[0-9]+|[A-Z]\b))\s*(?:[:：][^\r\n]*)?$",
    re.I | re.M,
)
CN_NUMBERS = {
    "一": "1",
    "二": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
    "十": "10",
}


@dataclass
class Finding:
    level: str
    item: str
    message: str
    return_phase: str = "analysis"


@dataclass
class Preview:
    status: str
    format: str
    sheets: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    sample_rows: list[list[str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


@dataclass
class AttachmentMapping:
    rel_path: str
    name: str
    size_bytes: int
    extension: str
    preview: Preview
    candidate_subquestions: list[str]
    status: str
    confidence: str
    evidence: list[str]
    requires_user_decision: bool = False
    notes: list[str] = field(default_factory=list)


class AttachmentMappingGuard:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.mapping_json = self._resolve(args.write_json) if args.write_json else self.root / "planning" / "attachment_mapping.json"
        self.mapping_md = self._resolve(args.write_md) if args.write_md else self.root / "planning" / "attachment_mapping.md"
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "checks" / "attachment_mapping_report.md"
        self.output_level = self._detect_output_level()
        self.previous = self._load_json(self.mapping_json, {})
        self.findings: list[Finding] = []
        self.attachments: list[AttachmentMapping] = []
        self.referenced_attachments: list[str] = []
        self.data_roots: list[str] = []
        self.problem_text = self._collect_problem_text()

    def run(self) -> int:
        self.attachments = self._build_mappings()
        self._apply_manual_sets()
        self._check_referenced_missing()
        self._check_mappings()
        self._write_outputs()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _build_mappings(self) -> list[AttachmentMapping]:
        attachments = self._discover_attachments()
        previous_by_path = {
            str(item.get("rel_path", "")).replace("\\", "/"): item
            for item in self.previous.get("attachments", [])
            if isinstance(item, dict)
        }
        out: list[AttachmentMapping] = []
        for path in attachments:
            rel_path = self.rel(path)
            previous = previous_by_path.get(rel_path, {})
            preview = self._preview(path)
            inferred_qids, evidence, confidence, status, _ = self._infer_mapping(path, preview)
            if previous:
                prev_qids = _normalize_qids(previous.get("candidate_subquestions", []))
                previous_status = str(previous.get("status") or "")
                if prev_qids or previous_status == "unused":
                    inferred_qids = prev_qids
                    status = previous_status or _status_for_qids(inferred_qids)
                    confidence = "recorded"
                    evidence.append("previous saved mapping")
            mapping = AttachmentMapping(
                rel_path=rel_path,
                name=path.name,
                size_bytes=path.stat().st_size,
                extension=path.suffix.lower(),
                preview=preview,
                candidate_subquestions=inferred_qids,
                status=status,
                confidence=confidence,
                evidence=_dedupe(evidence),
                requires_user_decision=status == "ambiguous",
                notes=list(previous.get("notes", [])) if isinstance(previous.get("notes"), list) else [],
            )
            out.append(mapping)
        return out

    def _discover_attachments(self) -> list[Path]:
        roots: list[Path] = []
        for value in self.args.data_dir or []:
            path = self._resolve(value)
            if path.exists():
                roots.append(path)
        for rel in DEFAULT_DATA_DIRS:
            path = self.root / rel
            if path.exists():
                roots.append(path)
        if self.args.include_root_files:
            roots.append(self.root)

        seen_roots: set[Path] = set()
        files: list[Path] = []
        for folder in roots:
            folder = folder.resolve()
            if folder in seen_roots:
                continue
            seen_roots.add(folder)
            self.data_roots.append(self.rel(folder) if folder != self.root else ".")
            if folder == self.root:
                candidates = [path for path in folder.iterdir() if path.is_file()]
            else:
                candidates = [path for path in folder.rglob("*") if path.is_file()]
            for path in candidates:
                if path.name.startswith(".") or path.name == ".gitkeep":
                    continue
                rel_parts = path.relative_to(self.root).parts if _is_relative_to(path, self.root) else ()
                if any(part in {"data_clean", "results", "figures", "diagrams", "paper", "checks", "revisions"} for part in rel_parts):
                    continue
                if path.suffix.lower() in DATA_EXTS:
                    files.append(path.resolve())

        return sorted(set(files), key=lambda item: self.rel(item).lower())

    def _infer_mapping(self, path: Path, preview: Preview) -> tuple[list[str], list[str], str, str, bool]:
        qid_scores: dict[str, int] = {}
        evidence: list[str] = []

        official_aliases = self._problem_attachment_aliases(path)
        if official_aliases:
            evidence.append(
                "problem statement associates the supplied file with "
                + ", ".join(official_aliases)
            )

        for qid in _qids_from_text(path.stem, allow_attachment_number=False):
            qid_scores[qid] = qid_scores.get(qid, 0) + 3
            evidence.append(f"file name explicitly mentions {qid}")

        context_hits = self._attachment_contexts(path)
        for context in context_hits:
            qids = _qids_from_text(context, allow_attachment_number=False)
            if qids:
                for qid in qids:
                    qid_scores[qid] = qid_scores.get(qid, 0) + 4
                evidence.append(f"problem/planning context near attachment mentions {','.join(qids)}")
            if re.search(r"共享|共用|所有问题|全部问题|shared|common", context, re.I):
                evidence.append("context suggests shared attachment")

        for qid in _qids_from_text(" ".join(preview.columns), allow_attachment_number=False):
            qid_scores[qid] = qid_scores.get(qid, 0) + 1
            evidence.append(f"column header mentions {qid}")

        qids = sorted(qid_scores, key=lambda qid: (int(qid[1:]) if qid[1:].isdigit() else 99))
        strong_qids = [qid for qid in qids if qid_scores[qid] >= 4]
        if strong_qids:
            qids = strong_qids

        if not qids:
            return [], evidence or ["no Qx evidence found from file name, preview, or problem context"], "none", "ambiguous", True
        if len(qids) == 1:
            confidence = "high" if qid_scores[qids[0]] >= 4 else "weak"
            return qids, evidence, confidence, "mapped", confidence != "high"

        if any("shared" in item.lower() or "共享" in item or "共用" in item for item in evidence):
            return qids, evidence, "medium", "shared", True
        return qids, evidence, "conflict", "ambiguous", True

    def _attachment_contexts(self, path: Path) -> list[str]:
        if not self.problem_text:
            return []
        tokens = _attachment_tokens(path)
        contexts: list[str] = []
        lowered = self.problem_text.lower()
        for token in tokens:
            if not token:
                continue
            start = 0
            token_lower = token.lower()
            while True:
                idx = lowered.find(token_lower, start)
                if idx < 0:
                    break
                contexts.append(self.problem_text[max(0, idx - 240) : idx + len(token) + 240])
                start = idx + len(token)
        return contexts[:6]

    def _apply_manual_sets(self) -> None:
        for raw in self.args.set or []:
            if "=" not in raw:
                self._add("FAIL", "manual_set", f"invalid --set value `{raw}`; use path=Q1 or path=SHARED:Q1,Q3")
                continue
            left, right = raw.split("=", 1)
            target = _norm_token(left)
            matches = [item for item in self.attachments if target in {_norm_token(item.rel_path), _norm_token(item.name), _norm_token(Path(item.rel_path).stem)}]
            if not matches:
                self._add("FAIL", left, f"--set target does not match any discovered attachment: {left}")
                continue
            if len(matches) > 1:
                self._add("FAIL", left, f"--set target is ambiguous: {left} matches {', '.join(item.rel_path for item in matches)}")
                continue
            item = matches[0]
            value = right.strip()
            if value.lower() in {"unused", "ignore", "ignored", "不用", "忽略"}:
                item.candidate_subquestions = []
                item.status = "unused"
            else:
                qids = _normalize_qids(_qids_from_text(value, allow_attachment_number=False))
                if not qids:
                    self._add("FAIL", item.rel_path, f"--set value has no valid Qx mapping: {right}")
                    continue
                item.candidate_subquestions = qids
                item.status = "shared" if len(qids) > 1 or value.lower().startswith("shared") else "mapped"
            item.confidence = "recorded"
            item.requires_user_decision = False
            item.evidence = _dedupe(item.evidence + [f"manual mapping set: {right}"])

    def _check_referenced_missing(self) -> None:
        refs = _dedupe(ATTACHMENT_REF_PATTERN.findall(self.problem_text))
        self.referenced_attachments = refs
        existing_tokens: set[str] = set()
        existing_ref_keys: set[str] = set()
        for item in self.attachments:
            tokens = _attachment_tokens(Path(item.rel_path)) + self._problem_attachment_aliases(Path(item.rel_path))
            existing_tokens.update(_norm_token(token) for token in tokens)
            existing_ref_keys.update(key for token in tokens if (key := _attachment_ref_key(token)))
        for ref in refs:
            norm_ref = _norm_token(ref)
            ref_key = _attachment_ref_key(ref)
            matched = bool(ref_key and ref_key in existing_ref_keys)
            matched = matched or bool(
                norm_ref
                and any(norm_ref in token or token in norm_ref for token in existing_tokens)
            )
            if norm_ref and not matched:
                self._add("FAIL", ref, f"problem/planning text references `{ref}`, but no matching attachment was found in data_raw")

    def _problem_attachment_aliases(self, path: Path) -> list[str]:
        """Return official appendix/attachment labels that introduce a named file."""
        aliases: list[str] = []
        lowered = self.problem_text.lower()
        for token in _dedupe([path.name, path.stem]):
            token_lower = token.lower()
            start = 0
            while token_lower:
                idx = lowered.find(token_lower, start)
                if idx < 0:
                    break
                prefix = self.problem_text[max(0, idx - 400) : idx]
                matches = list(APPENDIX_ALIAS_PATTERN.finditer(prefix))
                if matches:
                    nearest = matches[-1]
                    if len(prefix) - nearest.end() <= 240:
                        aliases.append(nearest.group(1))
                start = idx + len(token_lower)
        return _dedupe(aliases)

    def _check_mappings(self) -> None:
        if not self.attachments:
            self._add("INFO", "attachments", "no data attachments found under data_raw/search paths")
            return
        for item in self.attachments:
            if item.preview.status == "unreadable":
                self._add("WARN", item.rel_path, f"preview could not be read: {'; '.join(item.preview.notes)}")
            if item.status == "ambiguous":
                self._add("FAIL", item.rel_path, "attachment-to-subquestion mapping is ambiguous; record requires_user_decision in analysis before data cleaning/modeling")
            elif item.status == "missing":
                self._add("FAIL", item.rel_path, "referenced attachment is missing")
            elif item.status in {"mapped", "shared", "unused"}:
                self._add("INFO", item.rel_path, f"{item.status} mapping recorded")
            else:
                self._add("WARN", item.rel_path, f"unrecognized mapping status `{item.status}`")

    def _preview(self, path: Path) -> Preview:
        ext = path.suffix.lower()
        if ext in {".csv", ".tsv", ".txt", ".dat"}:
            return self._preview_delimited(path, "\t" if ext == ".tsv" else None)
        if ext == ".xlsx":
            return self._preview_xlsx(path)
        if ext == ".json":
            return self._preview_json(path)
        if ext in MEDIA_EXTS:
            return Preview(status="metadata_only", format=ext.lstrip("."), notes=["media attachment; table preview not applicable"])
        return Preview(status="metadata_only", format=ext.lstrip(".") or "unknown", notes=["preview unsupported; file is still inventoried"])

    def _preview_delimited(self, path: Path, delimiter: str | None) -> Preview:
        for encoding in ("utf-8-sig", "gb18030", "utf-16", "latin-1"):
            try:
                text = path.read_text(encoding=encoding, errors="strict")
                lines = text.splitlines()[:8]
                if not lines:
                    return Preview(status="empty", format=path.suffix.lower().lstrip("."), notes=[f"decoded as {encoding}"])
                sample_text = "\n".join(lines)
                dialect = csv.excel_tab if delimiter == "\t" else csv.Sniffer().sniff(sample_text, delimiters=",;\t|")
                rows = list(csv.reader(lines, dialect=dialect))[:4]
                header = [_clean_cell(cell) for cell in rows[0]] if rows else []
                samples = [[_clean_cell(cell) for cell in row] for row in rows[1:4]]
                return Preview(
                    status="readable",
                    format=path.suffix.lower().lstrip("."),
                    columns=header,
                    sample_rows=samples,
                    notes=[f"decoded as {encoding}", "preview limited to header + first 3 rows"],
                )
            except Exception:
                continue
        return Preview(status="unreadable", format=path.suffix.lower().lstrip("."), notes=["cannot decode delimited text preview"])

    def _preview_json(self, path: Path) -> Preview:
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            return Preview(status="unreadable", format="json", notes=[str(exc)])
        if isinstance(data, dict):
            columns = list(data)[:12]
            sample = [[_short(data[key]) for key in columns[:6]]]
        elif isinstance(data, list) and data and isinstance(data[0], dict):
            columns = list(data[0])[:12]
            sample = [[_short(row.get(key, "")) for key in columns[:6]] for row in data[:3] if isinstance(row, dict)]
        else:
            columns = [type(data).__name__]
            sample = [[_short(data)]]
        return Preview(status="readable", format="json", columns=columns, sample_rows=sample, notes=["preview limited to top-level keys/items"])

    def _preview_xlsx(self, path: Path) -> Preview:
        try:
            import openpyxl  # type: ignore

            wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
            sheet_names = list(wb.sheetnames)
            sheet = wb[sheet_names[0]]
            rows: list[list[str]] = []
            for idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
                rows.append([_clean_cell(cell) for cell in row])
                if idx >= 4:
                    break
            wb.close()
            return Preview(
                status="readable",
                format="xlsx",
                sheets=sheet_names,
                columns=rows[0] if rows else [],
                sample_rows=rows[1:4],
                notes=["preview limited to first sheet header + first 3 rows"],
            )
        except Exception:
            return self._preview_xlsx_zip(path)

    def _preview_xlsx_zip(self, path: Path) -> Preview:
        try:
            with zipfile.ZipFile(path) as zf:
                shared = _read_shared_strings(zf)
                sheet_names, sheet_paths = _read_workbook_sheets(zf)
                if not sheet_paths:
                    return Preview(status="unreadable", format="xlsx", sheets=sheet_names, notes=["no worksheet xml found"])
                rows = _read_sheet_rows(zf, sheet_paths[0], shared, limit=4)
                return Preview(
                    status="readable",
                    format="xlsx",
                    sheets=sheet_names,
                    columns=rows[0] if rows else [],
                    sample_rows=rows[1:4],
                    notes=["stdlib xlsx preview; first sheet header + first 3 rows only"],
                )
        except Exception as exc:
            return Preview(status="unreadable", format="xlsx", notes=[str(exc)])

    def _collect_problem_text(self) -> str:
        parts: list[str] = []
        if self.args.problem_text:
            path = self._resolve(self.args.problem_text)
            if path.exists():
                parts.append(path.read_text(encoding="utf-8-sig", errors="ignore"))
        for rel in PROBLEM_TEXT_FILES:
            path = self.root / rel
            if path.exists():
                parts.append(path.read_text(encoding="utf-8-sig", errors="ignore"))
        problem_dir = self.root / "problem"
        if problem_dir.exists():
            for path in sorted(problem_dir.rglob("*")):
                if path.is_file() and path.suffix.lower() in {".txt", ".md"}:
                    parts.append(path.read_text(encoding="utf-8-sig", errors="ignore")[:20000])
        return "\n".join(parts)

    def _write_outputs(self) -> None:
        payload = self._payload()
        self.mapping_json.parent.mkdir(parents=True, exist_ok=True)
        self.mapping_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        self.mapping_md.parent.mkdir(parents=True, exist_ok=True)
        self.mapping_md.write_text(self._mapping_markdown(payload), encoding="utf-8")
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(self._report_markdown(payload), encoding="utf-8")

    def _payload(self) -> dict[str, Any]:
        verdict = self._verdict()
        return {
            "version": 1,
            "generated_at": _now(),
            "root": str(self.root),
            "output_level": self.output_level,
            "data_roots": self.data_roots,
            "referenced_attachments": self.referenced_attachments,
            "verdict": verdict,
            "blocks_downstream": verdict == "FAIL",
            "attachments": [asdict(item) for item in self.attachments],
            "findings": [asdict(item) for item in self.findings],
        }

    def _mapping_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# Attachment Mapping",
            "",
            f"- Generated: {payload['generated_at']}",
            f"- Verdict: **{payload['verdict']}**",
            f"- Output level: `{self.output_level}`",
            "",
            "## Mapping Table",
            "",
            "| Attachment | Columns / sample | -> Subquestion | Status | User decision |",
            "|---|---|---|---|---|",
        ]
        for item in self.attachments:
            columns = ", ".join(item.preview.columns[:8]) if item.preview.columns else "; ".join(item.preview.notes[:2])
            if len(item.preview.columns) > 8:
                columns += f", ... ({len(item.preview.columns)} cols)"
            qids = _format_qids(item.candidate_subquestions, item.status)
            decision = "required" if item.requires_user_decision else "not required"
            lines.append(f"| `{item.rel_path}` | {_escape_table(columns)} | **{qids}** | `{item.status}` | {decision} |")
        if not self.attachments:
            lines.append("| - | No data attachments discovered | - | `none` | - |")
        lines.extend(
            [
                "",
                "## Evidence",
                "",
            ]
        )
        for item in self.attachments:
            lines.append(f"### `{item.rel_path}`")
            for evidence in item.evidence:
                lines.append(f"- {evidence}")
            if item.preview.sheets:
                lines.append(f"- sheets: {', '.join(item.preview.sheets[:8])}")
            lines.append("")
        return "\n".join(lines)

    def _report_markdown(self, payload: dict[str, Any]) -> str:
        lines = [
            "# Attachment Mapping Guard Report",
            "",
            f"- Generated: {payload['generated_at']}",
            f"- Verdict: **{payload['verdict']}**",
            f"- Mapping JSON: `{self.rel(self.mapping_json)}`",
            f"- Mapping table: `{self.rel(self.mapping_md)}`",
            "",
            "## Findings",
            "",
            "| Level | Item | Return to | Finding |",
            "|---|---|---|---|",
        ]
        for item in self.findings:
            lines.append(f"| {item.level} | `{_escape_table(item.item)}` | {item.return_phase} | {_escape_table(item.message)} |")
        lines.extend(
            [
                "",
                "## Gate Rule",
                "",
                "- Run this before data cleaning, modeling code, and final verification when attachments exist.",
                "- The gate reads only file metadata, headers, and the first three rows.",
                "- Ambiguous, missing, or weak contest-final mappings block downstream use until the human confirms or fixes `planning/attachment_mapping.json`.",
                "- Do not infer `附件1 -> Q1` from file order alone.",
                "",
            ]
        )
        return "\n".join(lines)

    def _verdict(self) -> str:
        if any(item.level == "FAIL" for item in self.findings):
            return "FAIL"
        if any(item.level == "WARN" for item in self.findings):
            return "PASS_WITH_WARNINGS"
        return "PASS"

    def _emit(self) -> None:
        for item in self.findings:
            _print(f"{item.level}: [{item.item}] {item.message}")
        _print(f"VERDICT: {self._verdict()}")
        _print(f"INFO: wrote {self.rel(self.mapping_json)}")
        _print(f"INFO: wrote {self.rel(self.mapping_md)}")
        _print(f"INFO: wrote {self.rel(self.report_path)}")

    def _detect_output_level(self) -> str:
        if self.args.output_level:
            return self.args.output_level
        text = (self.root / "planning" / "delivery_brief.md").read_text(encoding="utf-8-sig", errors="ignore") if (self.root / "planning" / "delivery_brief.md").exists() else ""
        match = re.search(r"Output level\s*\|\s*([^|\n]+)", text, re.I)
        if match and match.group(1).strip() in {"quick_draft", "reproducible_draft", "contest_final"}:
            return match.group(1).strip()
        return "reproducible_draft"

    def _load_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        try:
            return json.loads(path.read_text(encoding="utf-8-sig"))
        except json.JSONDecodeError as exc:
            self._add("FAIL", self.rel(path), f"invalid attachment mapping JSON: {exc}")
            return default

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def rel(self, path: Path) -> str:
        try:
            return str(path.resolve().relative_to(self.root)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")

    def _add(self, level: str, item: str, message: str, return_phase: str = "analysis") -> None:
        self.findings.append(Finding(level, item, message, return_phase))


def _read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    ns = _ns(root)
    strings: list[str] = []
    for si in root.findall(f".//{ns}si"):
        parts = [node.text or "" for node in si.findall(f".//{ns}t")]
        strings.append("".join(parts))
    return strings


def _read_workbook_sheets(zf: zipfile.ZipFile) -> tuple[list[str], list[str]]:
    try:
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    except KeyError:
        return [], []
    ns = _ns(workbook)
    rel_map = {rel.attrib.get("Id", ""): rel.attrib.get("Target", "") for rel in rels}
    names: list[str] = []
    paths: list[str] = []
    for sheet in workbook.findall(f".//{ns}sheet"):
        names.append(sheet.attrib.get("name", "sheet"))
        rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id", "")
        target = rel_map.get(rid, "")
        if target:
            paths.append("xl/" + target.lstrip("/").replace("\\", "/"))
    return names, paths


def _read_sheet_rows(zf: zipfile.ZipFile, sheet_path: str, shared: list[str], limit: int) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    ns = _ns(root)
    rows: list[list[str]] = []
    for row in root.findall(f".//{ns}row"):
        values: list[str] = []
        for cell in row.findall(f"{ns}c"):
            value = ""
            cell_type = cell.attrib.get("t", "")
            if cell_type == "inlineStr":
                value = "".join(node.text or "" for node in cell.findall(f".//{ns}t"))
            else:
                raw = cell.find(f"{ns}v")
                if raw is not None and raw.text is not None:
                    value = raw.text
                    if cell_type == "s":
                        try:
                            value = shared[int(value)]
                        except Exception:
                            pass
            values.append(_clean_cell(value))
        if any(values):
            rows.append(values)
        if len(rows) >= limit:
            break
    return rows


def _ns(root: ET.Element) -> str:
    if root.tag.startswith("{"):
        return root.tag.split("}", 1)[0] + "}"
    return ""


def _qids_from_text(text: str, allow_attachment_number: bool) -> list[str]:
    out: list[str] = []
    for match in QID_PATTERN.finditer(text or ""):
        value = next(group for group in match.groups() if group)
        out.append("Q" + CN_NUMBERS.get(value, value))
    if allow_attachment_number:
        for value in re.findall(r"附件\s*([0-9一二三四五六七八九])", text or ""):
            out.append("Q" + CN_NUMBERS.get(value, value))
    return _normalize_qids(out)


def _normalize_qids(values: Any) -> list[str]:
    if isinstance(values, str):
        values = re.split(r"[,;，、\s]+", values)
    if not isinstance(values, list):
        return []
    out: list[str] = []
    for value in values:
        text = str(value).strip().upper()
        if not text:
            continue
        if text in {"SHARED", "UNUSED"}:
            continue
        if text.startswith("Q") and text[1:].isdigit():
            out.append(text)
        elif text.isdigit():
            out.append("Q" + text)
        elif text in CN_NUMBERS:
            out.append("Q" + CN_NUMBERS[text])
    return _dedupe(out)


def _status_for_qids(qids: list[str]) -> str:
    if len(qids) > 1:
        return "shared"
    if len(qids) == 1:
        return "mapped"
    return "ambiguous"


def _attachment_tokens(path: Path) -> list[str]:
    name = path.name
    stem = path.stem
    tokens = [name, stem]
    match = re.search(r"(附件\s*[0-9一二三四五六七八九十]+)", stem)
    if match:
        tokens.append(match.group(1))
    match = re.search(r"(attachment[\s_-]*[A-Za-z0-9]+)", stem, re.I)
    if match:
        tokens.append(match.group(1))
    return _dedupe(tokens)


def _attachment_ref_key(value: str) -> str:
    match = re.search(
        r"(?:附件|附录)\s*([0-9一二三四五六七八九十]+)", value, re.I
    )
    if match:
        raw = match.group(1)
        return "number:" + CN_NUMBERS.get(raw, raw)
    match = re.search(
        r"(?:attachment|appendix)(?:\s+|-)?([0-9]+|[A-Z]\b)", value, re.I
    )
    if match:
        return "number:" + match.group(1).upper()
    return ""


def _norm_token(value: str) -> str:
    return re.sub(r"[\s_\-./\\（）()]+", "", str(value).lower())


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _format_qids(qids: list[str], status: str) -> str:
    if status == "unused":
        return "UNUSED"
    if status == "shared":
        return "[SHARED: " + ",".join(qids) + "]"
    return ",".join(qids) if qids else "UNMAPPED"


def _clean_cell(value: Any) -> str:
    return _short("" if value is None else str(value).strip())


def _short(value: Any, limit: int = 80) -> str:
    text = str(value).replace("\n", " ").replace("\r", " ").strip()
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _dedupe(values: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        if value and value not in seen:
            out.append(value)
            seen.add(value)
    return out


def _escape_table(text: Any) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def _now() -> str:
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
    parser.add_argument("--data-dir", action="append", help="Extra raw-data directory to scan")
    parser.add_argument("--problem-text", help="Optional problem text/markdown file for attachment context")
    parser.add_argument("--output-level", choices=["quick_draft", "reproducible_draft", "contest_final"], help="Override output level")
    parser.add_argument("--include-root-files", action="store_true", help="Also scan direct files under the project root")
    parser.add_argument("--set", action="append", help="Explicit mapping, e.g. attachment1.xlsx=Q1 or file.csv=SHARED:Q1,Q3")
    parser.add_argument("--write-report", help="Write checks/attachment_mapping_report.md")
    parser.add_argument("--write-json", help="Write planning/attachment_mapping.json")
    parser.add_argument("--write-md", help="Write planning/attachment_mapping.md")
    return parser.parse_args()


def main() -> int:
    return AttachmentMappingGuard(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
