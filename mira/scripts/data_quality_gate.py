#!/usr/bin/env python3
"""Audit contest data quality before modeling or final delivery.

This gate sits after the attachment-mapping P0 guard. It does not clean data by
itself and never edits raw files. It inventories tabular data, checks field
quality, units, missing values, duplicates, and readiness evidence so
Mira does not build a polished paper on silently wrong data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import re
import sys
import zipfile
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET


DATA_DIRS = ["data_raw", "data/raw", "workspace/data/data_raw", "workspace/data_raw"]
CLEAN_DIRS = ["data_clean", "data/clean", "workspace/data/data_clean", "workspace/data_clean"]
DATA_EXTS = {".csv", ".tsv", ".txt", ".dat", ".json", ".xlsx", ".xls"}
EMPTY_VALUES = {"", "na", "n/a", "nan", "null", "none", "-", "--", "/"}
UNIT_PATTERN = re.compile(r"[\(\（\[]\s*([^\)\）\]]{1,32})\s*[\)\）\]]|_(kg|g|t|m|km|cm|mm|s|min|h|day|d|yuan|rmb|usd|%|deg|rad|m2|m3)\b", re.I)
PHYSICAL_TERMS = [
    "time", "date", "distance", "length", "width", "height", "area", "volume",
    "weight", "mass", "speed", "velocity", "cost", "price", "demand", "supply",
    "capacity", "load", "flow", "force", "angle", "temperature", "pressure",
    "duration", "frequency", "rate",
    "时间", "日期", "距离", "长度", "宽度", "高度", "面积", "体积", "重量", "质量",
    "速度", "费用", "成本", "价格", "需求", "供给", "容量", "载荷", "流量", "力",
    "角度", "温度", "压力", "时长", "频率", "比例", "数量", "人数", "金额",
]
NONNEGATIVE_TERMS = [
    "distance", "length", "width", "height", "area", "volume", "weight", "mass",
    "cost", "price", "demand", "supply", "capacity", "load", "flow", "duration",
    "count", "number", "amount", "距离", "长度", "宽度", "高度", "面积", "体积",
    "重量", "质量", "费用", "成本", "价格", "需求", "供给", "容量", "流量", "时长",
    "数量", "人数", "金额",
]
ID_TERMS = ["id", "编号", "序号", "代码", "编码", "name", "名称", "城市", "节点", "类别"]


@dataclass
class Finding:
    level: str
    axis: str
    artifact: str
    message: str
    return_phase: str = "analysis"


@dataclass
class FieldAudit:
    artifact: str
    sheet: str
    field: str
    dtype: str
    unit: str
    unit_source: str
    missing_count: int
    missing_ratio: float
    unique_count: int
    min_value: float | None = None
    max_value: float | None = None
    negative_count: int = 0
    needs_unit_confirmation: bool = False
    notes: list[str] = field(default_factory=list)


@dataclass
class DatasetAudit:
    artifact: str
    format: str
    status: str
    size_bytes: int
    mapped_to: list[str]
    readiness: str
    rows: int = 0
    columns: int = 0
    sheets: list[str] = field(default_factory=list)
    duplicate_rows: int = 0
    clean_artifact: str = ""
    cleaning_recorded: bool = False
    notes: list[str] = field(default_factory=list)


class DataQualityGate:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.output_level = args.output_level
        self.report_path = self._resolve(args.write_report) if args.write_report else self.root / "checks" / "data_quality_report.md"
        self.json_path = self._resolve(args.write_json) if args.write_json else self.root / "checks" / "data_quality_report.json"
        self.template_path = self._resolve(args.write_template) if args.write_template else self.root / "planning" / "data_quality_template.json"
        self.overrides_path = self._resolve(args.overrides or "planning/data_quality_overrides.json")
        self.findings: list[Finding] = []
        self.overrides = load_json(self.overrides_path, {"datasets": [], "field_units": {}, "field_meanings": {}, "waivers": [], "cleaning_actions": []})
        self.attachment_mapping = load_json(self.root / "planning" / "attachment_mapping.json", {})
        self.cleaning_log = load_json(self.root / "planning" / "data_cleaning_log.json", {})
        self.data_files = discover_data_files(self.root, args.data_dir or [], self.attachment_mapping)
        self.datasets: list[DatasetAudit] = []
        self.fields: list[FieldAudit] = []

    def run(self) -> int:
        self._audit()
        self._write_template()
        self._write_outputs()
        self._emit()
        return 1 if any(item.level == "FAIL" for item in self.findings) else 0

    def _audit(self) -> None:
        if not self.data_files:
            self._handle_no_data()
            return
        for path in self.data_files:
            dataset, fields = audit_dataset(self.root, path, self.attachment_mapping, self.overrides, self.cleaning_log)
            self.datasets.append(dataset)
            self.fields.extend(fields)
            self._check_dataset(dataset)
            for field_audit in fields:
                self._check_field(field_audit)
        self._check_cleaning_records()

    def _handle_no_data(self) -> None:
        context = "\n".join(read_text(self.root / rel) for rel in [
            "planning/problem_analysis.md",
            "planning/problem_brief.md",
            "planning/modeling_plan.md",
            "planning/delivery_brief.md",
        ])
        mapping_attachments = self.attachment_mapping.get("attachments", []) if isinstance(self.attachment_mapping, dict) else []
        waiver = self._no_external_data_waiver()
        if waiver:
            note = str(waiver.get("reason") or waiver.get("notes") or "no external raw data files are required")
            if note.strip():
                self._add("INFO", "inventory", "-", f"no raw data files found; accepted by documented no-external-data waiver: {note}")
                return
            self._add("WARN", "inventory", "-", "no-external-data waiver exists but has no technical reason")
        if mapping_attachments or re.search(r"attachment|appendix|dataset|data file|附件|数据|表格|xlsx|csv", context, re.I):
            level = "FAIL" if self.output_level == "contest_final" else "WARN"
            self._add(level, "inventory", "-", "problem/modeling context references data, but no raw data files were found in canonical data_raw directories")
        else:
            self._add("INFO", "inventory", "-", "no raw data files found; this is acceptable for data-free theoretical problems")

    def _no_external_data_waiver(self) -> dict[str, Any]:
        waivers = self.overrides.get("waivers", []) if isinstance(self.overrides, dict) else []
        for item in waivers:
            if not isinstance(item, dict):
                continue
            waiver_type = str(item.get("type") or item.get("issue") or item.get("axis") or "").lower()
            if waiver_type in {"no_external_data", "embedded_problem_constants", "data_free_problem"}:
                return item
        return {}

    def _check_dataset(self, dataset: DatasetAudit) -> None:
        if dataset.status != "readable":
            level = "FAIL" if self._blocks_final(dataset) else "WARN"
            self._add(level, "readability", dataset.artifact, f"dataset is not fully readable: {dataset.status}")
        if not dataset.mapped_to and not is_unused_dataset(dataset):
            level = "FAIL" if self.output_level == "contest_final" else "WARN"
            self._add(level, "attachment_mapping", dataset.artifact, "dataset has no Qx/SHARED attachment mapping")
        readiness = dataset.readiness.strip().lower()
        if readiness == "blocked":
            self._add("FAIL", "data_readiness", dataset.artifact, "dataset readiness is blocked; resolve the stated issue before downstream use")
        elif readiness and readiness not in {"accepted", "accepted_with_warnings", "unused"}:
            self._add("WARN", "data_readiness", dataset.artifact, f"unrecognized readiness status `{dataset.readiness}`")
        if dataset.rows == 0 and dataset.status == "readable":
            self._add("FAIL" if self._blocks_final(dataset) else "WARN", "shape", dataset.artifact, "dataset has zero data rows")
        if dataset.columns == 0 and dataset.status == "readable":
            self._add("FAIL" if self._blocks_final(dataset) else "WARN", "shape", dataset.artifact, "dataset has zero columns")
        if dataset.duplicate_rows > 0:
            level = "WARN"
            if dataset.duplicate_rows / max(dataset.rows, 1) > 0.2 and self.output_level == "contest_final":
                level = "FAIL"
            self._add(level, "duplicates", dataset.artifact, f"duplicate row count is {dataset.duplicate_rows}")

    def _check_field(self, field_audit: FieldAudit) -> None:
        resolved_action = self._has_resolved_action_or_waiver(field_audit.artifact, field_audit.field)
        if field_audit.missing_ratio >= 0.5:
            level = "WARN" if resolved_action else ("FAIL" if self.output_level == "contest_final" else "WARN")
            self._add(level, "missing_values", field_audit.artifact, f"{field_audit.field} has {field_audit.missing_ratio:.1%} missing values")
        elif field_audit.missing_ratio >= 0.2:
            self._add("WARN", "missing_values", field_audit.artifact, f"{field_audit.field} has {field_audit.missing_ratio:.1%} missing values")
        if field_audit.needs_unit_confirmation:
            level = "FAIL" if self.output_level == "contest_final" else "WARN"
            self._add(level, "unit", field_audit.artifact, f"{field_audit.field} looks quantitative/physical but has no confirmed unit")
        if field_audit.negative_count > 0 and looks_nonnegative(field_audit.field):
            level = "WARN" if resolved_action else ("FAIL" if self.output_level == "contest_final" else "WARN")
            self._add(level, "range", field_audit.artifact, f"{field_audit.field} has {field_audit.negative_count} negative values although it appears nonnegative")

    def _check_cleaning_records(self) -> None:
        used = [item for item in self.datasets if item.mapped_to and not is_unused_dataset(item)]
        if not used:
            return
        for dataset in used:
            if dataset.clean_artifact and not dataset.cleaning_recorded:
                self._add("WARN", "cleaning", dataset.artifact, "a likely cleaned artifact exists but planning/data_cleaning_log.json does not record row/column changes")
            if (
                self.output_level == "contest_final"
                and has_quality_risk(dataset, self.fields)
                and not self._has_resolved_cleaning_record(dataset.artifact)
            ):
                self._add("FAIL", "cleaning", dataset.artifact, "data quality risks exist but no documented cleaning action or technical waiver is recorded")

    def _has_resolved_cleaning_record(self, artifact: str) -> bool:
        normalized = normalize_path(artifact)
        for collection_name in ["cleaning_actions", "waivers"]:
            records = self.overrides.get(collection_name, []) if isinstance(self.overrides, dict) else []
            for item in records:
                if not isinstance(item, dict):
                    continue
                item_artifact = normalize_path(str(item.get("artifact") or ""))
                if item_artifact and item_artifact != normalized:
                    continue
                action = str(item.get("action") or item.get("resolution") or "").strip()
                reason = str(item.get("reason") or item.get("notes") or item.get("waiver_reason") or "").strip()
                if action and reason:
                    return True
        return False

    def _blocks_final(self, dataset: DatasetAudit) -> bool:
        return self.output_level == "contest_final" and bool(dataset.mapped_to) and not is_unused_dataset(dataset)

    def _has_resolved_action_or_waiver(self, artifact: str, field: str) -> bool:
        for collection_name in ["cleaning_actions", "waivers"]:
            records = self.overrides.get(collection_name, []) if isinstance(self.overrides, dict) else []
            for item in records:
                if not isinstance(item, dict):
                    continue
                if normalize_path(str(item.get("artifact") or "")) != normalize_path(artifact):
                    continue
                target = str(item.get("target") or item.get("field") or item.get("issue") or "").lower()
                if target and field.lower() not in target and "all" not in target and "全部" not in target:
                    continue
                action = str(item.get("action") or item.get("resolution") or "").strip()
                reason = str(item.get("reason") or item.get("notes") or item.get("waiver_reason") or "").strip()
                if action and reason:
                    return True
        return False

    def _write_template(self) -> None:
        payload = {
            "version": 1,
            "generated_at": now(),
            "instructions": [
                "Copy resolved entries into planning/data_quality_overrides.json.",
                "Raw files must stay unchanged; cleaned files belong under data_clean/ and cleaning actions belong in planning/data_cleaning_log.json.",
                "Use explicit readiness states and document the technical reason for each cleaning action or waiver.",
            ],
            "datasets": [dataset_template(item) for item in self.datasets],
            "field_units": {
                field_key(item): (item.unit if item.unit_source == "confirmed" else "")
                for item in self.fields
                if item.needs_unit_confirmation or item.unit_source == "confirmed"
            },
            "field_meanings": {
                field_key(item): ""
                for item in self.fields
                if item.dtype in {"mixed", "text"} or item.needs_unit_confirmation
            },
            "cleaning_actions": [
                {
                    "artifact": item.artifact,
                    "action": "",
                    "target": "",
                    "reason": "",
                    "risk": "low|medium|high",
                    "evidence": "",
                }
                for item in self.datasets
                if has_quality_risk(item, self.fields)
            ],
            "waivers": [
                {
                    "type": "no_external_data",
                    "reason": "",
                    "action": "accept no external data",
                }
            ] if not self.data_files else [],
        }
        self.template_path.parent.mkdir(parents=True, exist_ok=True)
        self.template_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def _write_outputs(self) -> None:
        payload = self.payload()
        self.report_path.parent.mkdir(parents=True, exist_ok=True)
        self.json_path.parent.mkdir(parents=True, exist_ok=True)
        self.report_path.write_text(markdown(payload), encoding="utf-8")
        self.json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def payload(self) -> dict[str, Any]:
        return {
            "generated_at": now(),
            "root": str(self.root),
            "output_level": self.output_level,
            "verdict": verdict(self.findings),
            "metrics": {
                "datasets": len(self.datasets),
                "fields": len(self.fields),
                "readable_datasets": sum(1 for item in self.datasets if item.status == "readable"),
                "mapped_datasets": sum(1 for item in self.datasets if item.mapped_to),
                "readiness_recorded": sum(1 for item in self.datasets if item.readiness),
                "unit_confirmation_needed": sum(1 for item in self.fields if item.needs_unit_confirmation),
                "warnings": sum(1 for item in self.findings if item.level == "WARN"),
                "failures": sum(1 for item in self.findings if item.level == "FAIL"),
            },
            "datasets": [asdict(item) for item in self.datasets],
            "fields": [asdict(item) for item in self.fields],
            "findings": [asdict(item) for item in self.findings],
            "template_path": rel(self.root, self.template_path),
            "overrides_path": rel(self.root, self.overrides_path),
        }

    def _emit(self) -> None:
        payload = self.payload()
        print_utf8(f"VERDICT: {payload['verdict']}")
        print_utf8("metrics: " + json.dumps(payload["metrics"], ensure_ascii=False, sort_keys=True))
        for item in self.findings:
            print_utf8(f"{item.level}: {item.axis}: {item.artifact}: {item.message}")
        print_utf8(f"INFO: wrote {rel(self.root, self.template_path)}")
        print_utf8(f"INFO: wrote {rel(self.root, self.report_path)}")
        print_utf8(f"INFO: wrote {rel(self.root, self.json_path)}")

    def _resolve(self, value: str | Path) -> Path:
        path = Path(value)
        return path if path.is_absolute() else self.root / path

    def _add(self, level: str, axis: str, artifact: str, message: str) -> None:
        self.findings.append(Finding(level, axis, artifact, message))


def discover_data_files(root: Path, data_dirs: list[str], attachment_mapping: Any) -> list[Path]:
    files: list[Path] = []
    roots: list[Path] = []
    for value in data_dirs:
        path = Path(value)
        roots.append(path if path.is_absolute() else root / path)
    roots.extend(root / rel for rel in DATA_DIRS)
    for folder in roots:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in DATA_EXTS and not is_in_clean_or_output(root, path):
                files.append(path.resolve())
    if isinstance(attachment_mapping, dict):
        for item in attachment_mapping.get("attachments", []):
            if not isinstance(item, dict):
                continue
            rel_path = str(item.get("rel_path") or "")
            if not rel_path:
                continue
            path = root / rel_path
            if path.exists() and path.is_file() and path.suffix.lower() in DATA_EXTS:
                files.append(path.resolve())
    return sorted(set(files), key=lambda item: rel(root, item).lower())


def audit_dataset(root: Path, path: Path, attachment_mapping: Any, overrides: dict[str, Any], cleaning_log: Any) -> tuple[DatasetAudit, list[FieldAudit]]:
    rel_path = rel(root, path)
    mapping = lookup_mapping(rel_path, attachment_mapping)
    mapped_to = mapping_qids(mapping)
    readiness_record = lookup_dataset_override(rel_path, overrides)
    clean_artifact = find_clean_artifact(root, path, cleaning_log)
    cleaning_recorded = bool(lookup_cleaning_record(rel_path, cleaning_log))
    dataset = DatasetAudit(
        artifact=rel_path,
        format=path.suffix.lower().lstrip(".") or "unknown",
        status="unreadable",
        size_bytes=path.stat().st_size,
        mapped_to=mapped_to,
        readiness=str(readiness_record.get("readiness") or ""),
        clean_artifact=clean_artifact,
        cleaning_recorded=cleaning_recorded,
    )
    try:
        sheets = read_tabular(path)
    except Exception as exc:
        dataset.status = f"unreadable: {exc.__class__.__name__}: {exc}"
        return dataset, []
    fields: list[FieldAudit] = []
    dataset.status = "readable"
    dataset.sheets = [sheet["name"] for sheet in sheets]
    dataset.rows = sum(int(sheet["rows"]) for sheet in sheets)
    dataset.columns = max([int(sheet["columns"]) for sheet in sheets] or [0])
    dataset.duplicate_rows = sum(int(sheet.get("duplicate_rows", 0)) for sheet in sheets)
    for sheet in sheets:
        for field in audit_fields(rel_path, sheet, overrides):
            fields.append(field)
    return dataset, fields


def read_tabular(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix in {".csv", ".tsv", ".txt", ".dat"}:
        return [read_csv_like(path)]
    if suffix == ".json":
        return [read_json_table(path)]
    if suffix == ".xlsx":
        return read_xlsx(path)
    if suffix == ".xls":
        raise ValueError("legacy .xls is not safely readable without conversion; save as .xlsx or CSV")
    raise ValueError(f"unsupported data format: {suffix}")


def read_csv_like(path: Path) -> dict[str, Any]:
    raw = read_text_with_fallback(path)
    sample = raw[:4096]
    delimiter = "\t" if path.suffix.lower() == ".tsv" else ","
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;|")
        delimiter = dialect.delimiter
    except csv.Error:
        pass
    rows = list(csv.reader(raw.splitlines(), delimiter=delimiter))
    return rows_to_sheet(path.stem, rows)


def read_text_with_fallback(path: Path) -> str:
    last = ""
    for encoding in ["utf-8-sig", "utf-8", "gb18030", "gbk"]:
        try:
            return path.read_text(encoding=encoding)
        except UnicodeDecodeError as exc:
            last = str(exc)
    return path.read_text(encoding="utf-8-sig", errors="replace") + (f"\n# decode warning: {last}" if last else "")


def read_json_table(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if isinstance(data, list):
        if all(isinstance(item, dict) for item in data):
            columns = sorted({str(key) for item in data for key in item.keys()})
            rows = [columns] + [[stringify(item.get(col, "")) for col in columns] for item in data]
            return rows_to_sheet(path.stem, rows)
        return rows_to_sheet(path.stem, [["value"]] + [[stringify(item)] for item in data])
    if isinstance(data, dict):
        if all(isinstance(value, (str, int, float, bool, type(None))) for value in data.values()):
            return rows_to_sheet(path.stem, [list(data.keys()), [stringify(value) for value in data.values()]])
        rows = [["key", "value"]] + [[stringify(key), stringify(value)] for key, value in data.items()]
        return rows_to_sheet(path.stem, rows)
    return rows_to_sheet(path.stem, [["value"], [stringify(data)]])


def read_xlsx(path: Path) -> list[dict[str, Any]]:
    with zipfile.ZipFile(path) as zf:
        shared = read_shared_strings(zf)
        workbook = ET.fromstring(zf.read("xl/workbook.xml"))
        ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main", "rel": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
        sheets = []
        for idx, sheet in enumerate(workbook.findall(".//main:sheet", ns), start=1):
            name = sheet.attrib.get("name", f"Sheet{idx}")
            rid = sheet.attrib.get("{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id")
            sheet_path = worksheet_path(zf, rid, idx)
            if sheet_path:
                rows = parse_xlsx_sheet(zf, sheet_path, shared)
                sheets.append(rows_to_sheet(name, rows))
        return sheets or [rows_to_sheet("Sheet1", [])]


def read_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    out = []
    for si in root.findall(".//main:si", ns):
        texts = [node.text or "" for node in si.findall(".//main:t", ns)]
        out.append("".join(texts))
    return out


def worksheet_path(zf: zipfile.ZipFile, rid: str | None, idx: int) -> str:
    if rid and "xl/_rels/workbook.xml.rels" in zf.namelist():
        rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
        for rel_node in rels:
            if rel_node.attrib.get("Id") == rid:
                target = rel_node.attrib.get("Target", "")
                if target.startswith("/"):
                    target = target.lstrip("/")
                elif not target.startswith("xl/"):
                    target = "xl/" + target
                return target
    fallback = f"xl/worksheets/sheet{idx}.xml"
    return fallback if fallback in zf.namelist() else ""


def parse_xlsx_sheet(zf: zipfile.ZipFile, sheet_path: str, shared: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(sheet_path))
    ns = {"main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rows: list[list[str]] = []
    for row in root.findall(".//main:row", ns):
        values: dict[int, str] = {}
        for cell in row.findall("main:c", ns):
            ref = cell.attrib.get("r", "")
            col_index = column_index(ref)
            value = cell_value(cell, shared, ns)
            values[col_index] = value
        if values:
            max_col = max(values)
            rows.append([values.get(index, "") for index in range(1, max_col + 1)])
    return rows


def cell_value(cell: ET.Element, shared: list[str], ns: dict[str, str]) -> str:
    cell_type = cell.attrib.get("t", "")
    value_node = cell.find("main:v", ns)
    if value_node is None:
        inline = cell.find(".//main:t", ns)
        return inline.text if inline is not None and inline.text else ""
    raw = value_node.text or ""
    if cell_type == "s":
        try:
            return shared[int(raw)]
        except (ValueError, IndexError):
            return raw
    return raw


def rows_to_sheet(name: str, rows: list[list[str]]) -> dict[str, Any]:
    if not rows:
        return {"name": name, "rows": 0, "columns": 0, "columns_names": [], "data": [], "duplicate_rows": 0}
    width = max(len(row) for row in rows)
    normalized = [row + [""] * (width - len(row)) for row in rows]
    header = [clean_header(value, index) for index, value in enumerate(normalized[0], start=1)]
    data = normalized[1:]
    row_counter = Counter(tuple(row) for row in data)
    duplicate_rows = sum(count - 1 for count in row_counter.values() if count > 1)
    return {"name": name, "rows": len(data), "columns": len(header), "columns_names": header, "data": data, "duplicate_rows": duplicate_rows}


def audit_fields(artifact: str, sheet: dict[str, Any], overrides: dict[str, Any]) -> list[FieldAudit]:
    out: list[FieldAudit] = []
    headers = list(sheet.get("columns_names", []))
    data = list(sheet.get("data", []))
    for idx, header in enumerate(headers):
        values = [row[idx] if idx < len(row) else "" for row in data]
        out.append(audit_field(artifact, str(sheet.get("name", "")), header, values, overrides))
    return out


def audit_field(artifact: str, sheet: str, field: str, values: list[str], overrides: dict[str, Any]) -> FieldAudit:
    key = f"{artifact}::{sheet}::{field}"
    unit_overrides = overrides.get("field_units", {}) if isinstance(overrides, dict) else {}
    confirmed_unit = ""
    if isinstance(unit_overrides, dict):
        confirmed_unit = str(unit_overrides.get(key) or unit_overrides.get(f"{artifact}::{field}") or unit_overrides.get(field) or "")
    unit, source = infer_unit(field, confirmed_unit)
    nonempty = [value for value in values if not is_empty(value)]
    missing_count = len(values) - len(nonempty)
    numbers = [parse_number(value) for value in nonempty]
    numeric_values = [value for value in numbers if value is not None and math.isfinite(value)]
    dtype = infer_dtype(nonempty, numeric_values)
    missing_ratio = round(missing_count / max(len(values), 1), 4)
    unique_count = len(set(nonempty))
    min_value = min(numeric_values) if numeric_values and dtype == "numeric" else None
    max_value = max(numeric_values) if numeric_values and dtype == "numeric" else None
    negative_count = sum(1 for value in numeric_values if value < 0) if dtype == "numeric" else 0
    needs_unit = dtype == "numeric" and looks_physical(field) and not unit and not looks_identifier(field)
    notes = []
    if dtype == "mixed":
        notes.append("mixed data formats detected")
    if unique_count <= 1 and len(nonempty) > 1:
        notes.append("constant or near-constant field")
    return FieldAudit(
        artifact=artifact,
        sheet=sheet,
        field=field,
        dtype=dtype,
        unit=unit,
        unit_source=source,
        missing_count=missing_count,
        missing_ratio=missing_ratio,
        unique_count=unique_count,
        min_value=min_value,
        max_value=max_value,
        negative_count=negative_count,
        needs_unit_confirmation=needs_unit,
        notes=notes,
    )


def infer_dtype(nonempty: list[str], numeric_values: list[float]) -> str:
    if not nonempty:
        return "empty"
    if len(numeric_values) / max(len(nonempty), 1) >= 0.85:
        return "numeric"
    date_count = sum(1 for value in nonempty if looks_like_date(value))
    if date_count / max(len(nonempty), 1) >= 0.7:
        return "date"
    unique_count = len(set(nonempty))
    if unique_count <= max(20, int(len(nonempty) * 0.2)):
        return "categorical"
    numeric_like = sum(1 for value in nonempty if parse_number(value) is not None)
    if numeric_like > 0:
        return "mixed"
    return "text"


def infer_unit(field: str, confirmed_unit: str) -> tuple[str, str]:
    if confirmed_unit.strip():
        return confirmed_unit.strip(), "confirmed"
    match = UNIT_PATTERN.search(field)
    if not match:
        return "", ""
    return (match.group(1) or match.group(2) or "").strip(), "header"


def lookup_mapping(rel_path: str, attachment_mapping: Any) -> dict[str, Any]:
    if not isinstance(attachment_mapping, dict):
        return {}
    normalized = normalize_path(rel_path)
    for item in attachment_mapping.get("attachments", []):
        if isinstance(item, dict) and normalize_path(str(item.get("rel_path") or "")) == normalized:
            return item
    return {}


def mapping_qids(mapping: dict[str, Any]) -> list[str]:
    values = mapping.get("candidate_subquestions", []) if isinstance(mapping, dict) else []
    if not isinstance(values, list):
        return []
    return [str(value) for value in values if str(value).strip()]


def lookup_dataset_override(rel_path: str, overrides: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_path(rel_path)
    for item in overrides.get("datasets", []) if isinstance(overrides, dict) else []:
        if isinstance(item, dict) and normalize_path(str(item.get("artifact") or "")) == normalized:
            return item
    return {}


def lookup_cleaning_record(rel_path: str, cleaning_log: Any) -> dict[str, Any]:
    normalized = normalize_path(rel_path)
    records = cleaning_log.get("records", []) if isinstance(cleaning_log, dict) else []
    for item in records:
        if isinstance(item, dict) and normalize_path(str(item.get("raw_artifact") or "")) == normalized:
            return item
    return {}


def find_clean_artifact(root: Path, raw_path: Path, cleaning_log: Any) -> str:
    record = lookup_cleaning_record(rel(root, raw_path), cleaning_log)
    if record.get("clean_artifact"):
        return str(record["clean_artifact"])
    stem = raw_path.stem.lower()
    for rel_dir in CLEAN_DIRS:
        folder = root / rel_dir
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in DATA_EXTS and stem in path.stem.lower():
                return rel(root, path)
    return ""


def dataset_template(dataset: DatasetAudit) -> dict[str, Any]:
    return {
        "artifact": dataset.artifact,
        "mapped_to": dataset.mapped_to,
        "readiness": dataset.readiness or "accepted|accepted_with_warnings|blocked|unused",
        "evidence": "",
        "notes": "",
        "required_cleaning": has_quality_risk(dataset, []),
    }


def has_quality_risk(dataset: DatasetAudit, fields: list[FieldAudit]) -> bool:
    if dataset.duplicate_rows > 0:
        return True
    for field in fields:
        if field.artifact == dataset.artifact and (field.missing_ratio >= 0.2 or field.needs_unit_confirmation or field.negative_count > 0):
            return True
    return False


def is_unused_dataset(dataset: DatasetAudit) -> bool:
    return dataset.readiness == "unused" or dataset.mapped_to == ["UNUSED"]


def field_key(field: FieldAudit) -> str:
    return f"{field.artifact}::{field.sheet}::{field.field}"


def looks_physical(field: str) -> bool:
    lower = field.lower()
    return any(term.lower() in lower for term in PHYSICAL_TERMS)


def looks_nonnegative(field: str) -> bool:
    lower = field.lower()
    return any(term.lower() in lower for term in NONNEGATIVE_TERMS)


def looks_identifier(field: str) -> bool:
    lower = field.lower()
    return any(term.lower() in lower for term in ID_TERMS)


def is_empty(value: Any) -> bool:
    return str(value).strip().lower() in EMPTY_VALUES


def parse_number(value: Any) -> float | None:
    text = str(value).strip().replace(",", "")
    if text.endswith("%"):
        text = text[:-1]
    try:
        return float(text)
    except ValueError:
        return None


def looks_like_date(value: str) -> bool:
    text = str(value).strip()
    return bool(re.match(r"^\d{4}[-/]\d{1,2}[-/]\d{1,2}$|^\d{4}[-/]\d{1,2}$", text))


def clean_header(value: Any, index: int) -> str:
    text = str(value or "").strip()
    return text if text else f"unnamed_{index}"


def column_index(ref: str) -> int:
    letters = re.match(r"([A-Z]+)", ref.upper())
    if not letters:
        return 1
    total = 0
    for char in letters.group(1):
        total = total * 26 + ord(char) - ord("A") + 1
    return total


def is_in_clean_or_output(root: Path, path: Path) -> bool:
    try:
        parts = path.resolve().relative_to(root.resolve()).parts
    except ValueError:
        return False
    return any(part in {"data_clean", "results", "figures", "diagrams", "paper", "checks", "revisions"} for part in parts)


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


def stringify(value: Any) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def normalize_path(value: str) -> str:
    return value.strip().replace("\\", "/").lower()


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve())).replace("\\", "/")
    except ValueError:
        return str(path).replace("\\", "/")


def verdict(findings: list[Finding]) -> str:
    if any(item.level == "FAIL" for item in findings):
        return "FAIL"
    if any(item.level == "WARN" for item in findings):
        return "PASS_WITH_WARNINGS"
    return "PASS"


def markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Data Quality Gate",
        "",
        f"- Generated: {payload['generated_at']}",
        f"- Verdict: **{payload['verdict']}**",
        f"- Output level: `{payload['output_level']}`",
        f"- Overrides: `{payload['overrides_path']}`",
        f"- Fill-in template: `{payload['template_path']}`",
        "",
        "## Metrics",
        "",
        "| Metric | Value |",
        "|---|---|",
    ]
    for key, value in payload["metrics"].items():
        lines.append(f"| {key} | {escape(json.dumps(value, ensure_ascii=False))} |")
    lines.extend(["", "## Datasets", "", "| Artifact | Status | Rows | Columns | Mapping | Readiness | Duplicates | Clean Artifact |", "|---|---|---:|---:|---|---|---:|---|"])
    for item in payload["datasets"]:
        lines.append(
            f"| `{escape(item['artifact'])}` | {escape(item['status'])} | {item['rows']} | {item['columns']} | {escape(', '.join(item['mapped_to']))} | {escape(item['readiness'] or 'inferred from audit')} | {item['duplicate_rows']} | `{escape(item['clean_artifact'])}` |"
        )
    lines.extend(["", "## Field Audit", "", "| Artifact | Sheet | Field | Type | Unit | Missing | Unique | Range | Notes |", "|---|---|---|---|---|---:|---:|---|---|"])
    for item in payload["fields"][:200]:
        range_text = ""
        if item["min_value"] is not None or item["max_value"] is not None:
            range_text = f"{item['min_value']} - {item['max_value']}"
        unit = item["unit"] or ("NEEDS_CONFIRMATION" if item["needs_unit_confirmation"] else "")
        lines.append(
            f"| `{escape(item['artifact'])}` | {escape(item['sheet'])} | {escape(item['field'])} | `{item['dtype']}` | {escape(unit)} | {item['missing_count']} ({item['missing_ratio']:.1%}) | {item['unique_count']} | {escape(range_text)} | {escape('; '.join(item['notes']))} |"
        )
    if len(payload["fields"]) > 200:
        lines.append(f"| ... | ... | ... | ... | ... | ... | ... | ... | truncated {len(payload['fields']) - 200} fields in markdown; see JSON |")
    lines.extend(["", "## Findings", "", "| Level | Axis | Artifact | Return To | Message |", "|---|---|---|---|---|"])
    for item in payload["findings"]:
        lines.append(f"| {item['level']} | {item['axis']} | `{escape(item['artifact'])}` | {item['return_phase']} | {escape(item['message'])} |")
    if not payload["findings"]:
        lines.append("| INFO | all | - | - | no data-quality findings |")
    lines.extend(
        [
            "",
            "## Rule",
            "",
            "- Raw data is read-only.",
            "- Cleaned data must be saved under `data_clean/` and cleaning row/column changes should be recorded in `planning/data_cleaning_log.json`.",
            "- For `contest_final`, blocked readiness and unresolved data-quality risks fail; quantitative physical fields need declared units.",
            "",
        ]
    )
    return "\n".join(lines)


def escape(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


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
    parser.add_argument("--data-dir", action="append", help="Additional raw data directory")
    parser.add_argument("--overrides", help="Data-readiness/unit evidence file, default planning/data_quality_overrides.json")
    parser.add_argument("--write-template", help="Write fill-in template, default planning/data_quality_template.json")
    parser.add_argument("--write-report", help="Write markdown report")
    parser.add_argument("--write-json", help="Write JSON report")
    return parser.parse_args()


def main() -> int:
    return DataQualityGate(parse_args()).run()


if __name__ == "__main__":
    raise SystemExit(main())
