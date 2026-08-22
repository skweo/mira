#!/usr/bin/env python3
"""Freeze one Mira 0.11 release verification as hashed, machine-readable evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from matlab_execution_record import validate_execution_record


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest().upper()


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return payload


def relative(workspace_root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def file_record(workspace_root: Path, path: Path) -> dict[str, Any]:
    return {
        "path": relative(workspace_root, path),
        "size": path.stat().st_size,
        "sha256": sha256(path),
    }


def resolve_project_path(project_root: Path, value: Any) -> Path:
    text = str(value or "").strip()
    if not text:
        raise ValueError("artifact path is empty")
    candidate = (project_root / text).resolve()
    try:
        candidate.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ValueError(f"artifact is outside project root: {text}") from exc
    return candidate


def aggregate_project_files(project_root: Path, paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        paths, key=lambda item: item.resolve().relative_to(project_root.resolve()).as_posix().lower()
    ):
        rel = path.resolve().relative_to(project_root.resolve()).as_posix().encode("utf-8")
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest() if paths else ""


def verify_python_render(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    gate_path = project_root / "checks" / "figure_evidence_report.json"
    manifest_path = project_root / "planning" / "figure_evidence.json"

    try:
        gate = load_json(gate_path)
        manifest = load_json(manifest_path)
        sources = [
            file_record(workspace_root, gate_path),
            file_record(workspace_root, manifest_path),
        ]
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append({"code": "source_report", "message": str(exc)})
        gate = {}
        manifest = {}

    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    if gate.get("verdict") != "PASS" or metrics.get("failures") != 0:
        findings.append(
            {
                "code": "figure_evidence_gate",
                "message": "figure evidence gate must be PASS with zero failures",
            }
        )

    rows = manifest.get("figures") if isinstance(manifest.get("figures"), list) else []
    python_rows = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("backend") or "").lower().startswith("python")
    ]
    if not python_rows or metrics.get("python_figures") != len(python_rows):
        findings.append(
            {
                "code": "python_figure_count",
                "message": "at least one Python figure is required and gate/manifest counts must agree",
            }
        )

    minimum_dpi = min((int(row.get("png_dpi") or 0) for row in python_rows), default=0)
    seen: set[Path] = set()
    required_text = (
        "figure_id",
        "claim_id",
        "reader_question",
        "expected_inference",
        "backend_reason",
        "prelude",
        "conclusion",
    )
    artifact_fields = ("source_file", "log_file", "data_source", "vector_file", "png_file")
    for index, row in enumerate(python_rows):
        missing_text = [key for key in required_text if not str(row.get(key) or "").strip()]
        if missing_text:
            findings.append(
                {
                    "code": "figure_claim_binding",
                    "message": f"Python figure {index} lacks fields: {missing_text}",
                }
            )
        if int(row.get("png_dpi") or 0) < 300:
            findings.append(
                {
                    "code": "png_dpi",
                    "message": f"Python figure {index} declares less than 300 DPI",
                }
            )
        for field in artifact_fields:
            try:
                path = resolve_project_path(project_root, row.get(field))
            except ValueError as exc:
                findings.append({"code": "artifact_path", "message": str(exc)})
                continue
            if not path.is_file() or path.stat().st_size == 0:
                findings.append(
                    {
                        "code": "artifact_missing",
                        "message": f"missing or empty {field}: {relative(workspace_root, path)}",
                    }
                )
            elif path not in seen:
                artifacts.append(file_record(workspace_root, path))
                seen.add(path)

    status = "FAIL" if findings else "PASS"
    return {
        "schema_version": 1,
        "verification_id": "python_render",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"]).lower()),
        "summary": {
            "gate_verdict": gate.get("verdict", "MISSING"),
            "python_figure_count": len(python_rows),
            "minimum_png_dpi": minimum_dpi,
        },
        "findings": findings,
    }


def verify_matlab_render(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    gate_path = project_root / "checks" / "figure_evidence_report.json"
    manifest_path = project_root / "planning" / "figure_evidence.json"
    capability_path = project_root / "results" / "logs" / "matlab_visual_capability.json"
    summary_path = project_root / "results" / "figures_data" / "matlab_figures_summary.json"

    loaded: dict[str, dict[str, Any]] = {}
    for name, path in (
        ("gate", gate_path),
        ("manifest", manifest_path),
        ("capability", capability_path),
        ("matlab_summary", summary_path),
    ):
        try:
            loaded[name] = load_json(path)
            sources.append(file_record(workspace_root, path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            loaded[name] = {}
            findings.append({"code": "source_report", "message": str(exc)})

    gate = loaded["gate"]
    manifest = loaded["manifest"]
    capability = loaded["capability"]
    matlab_summary = loaded["matlab_summary"]
    metrics = gate.get("metrics") if isinstance(gate.get("metrics"), dict) else {}
    if gate.get("verdict") != "PASS" or metrics.get("failures") != 0:
        findings.append(
            {
                "code": "figure_evidence_gate",
                "message": "figure evidence gate must be PASS with zero failures",
            }
        )

    version = str(capability.get("matlab_version") or "").strip()
    execution_errors = validate_execution_record(
        project_root, capability, require_success=True
    )
    if execution_errors:
        findings.append(
            {
                "code": "matlab_execution",
                "message": "invalid MATLAB execution record: " + "; ".join(execution_errors),
            }
        )

    validation = (
        matlab_summary.get("validation")
        if isinstance(matlab_summary.get("validation"), dict)
        else {}
    )
    validation_keys = [key for key in validation if str(key).lower().endswith("_pass")]
    if (
        validation.get("status") != "PASS"
        or not validation_keys
        or any(validation.get(key) is not True for key in validation_keys)
    ):
        findings.append(
            {
                "code": "matlab_validation",
                "message": "all MATLAB figure validations must pass",
            }
        )

    rows = manifest.get("figures") if isinstance(manifest.get("figures"), list) else []
    matlab_rows = [
        row
        for row in rows
        if isinstance(row, dict) and str(row.get("backend") or "").lower().startswith("matlab")
    ]
    summary_rows = matlab_summary.get("figures") if isinstance(matlab_summary.get("figures"), list) else []
    if (
        not matlab_rows
        or metrics.get("matlab_figures") != len(matlab_rows)
        or len(summary_rows) != len(matlab_rows)
    ):
        findings.append(
            {
                "code": "matlab_figure_count",
                "message": "at least one MATLAB figure is required and gate/manifest/summary counts must agree",
            }
        )

    minimum_dpi = min((int(row.get("png_dpi") or 0) for row in matlab_rows), default=0)
    seen: set[Path] = set()

    def add_artifact(value: Any, label: str) -> None:
        try:
            path = resolve_project_path(project_root, value)
        except ValueError as exc:
            findings.append({"code": "artifact_path", "message": str(exc)})
            return
        if not path.is_file() or path.stat().st_size == 0:
            findings.append(
                {
                    "code": "artifact_missing",
                    "message": f"missing or empty {label}: {relative(workspace_root, path)}",
                }
            )
        elif path not in seen:
            artifacts.append(file_record(workspace_root, path))
            seen.add(path)

    required_text = (
        "figure_id",
        "claim_id",
        "reader_question",
        "expected_inference",
        "backend_reason",
        "prelude",
        "conclusion",
    )
    artifact_fields = ("source_file", "log_file", "data_source", "vector_file", "png_file")
    for index, row in enumerate(matlab_rows):
        missing_text = [key for key in required_text if not str(row.get(key) or "").strip()]
        if missing_text:
            findings.append(
                {
                    "code": "figure_claim_binding",
                    "message": f"MATLAB figure {index} lacks fields: {missing_text}",
                }
            )
        if int(row.get("png_dpi") or 0) < 300:
            findings.append(
                {
                    "code": "png_dpi",
                    "message": f"MATLAB figure {index} declares less than 300 DPI",
                }
            )
        for field in artifact_fields:
            add_artifact(row.get(field), field)

    if capability.get("source"):
        add_artifact(capability.get("source"), "MATLAB source")
    for field in ("log_files", "evidence", "outputs"):
        values = capability.get(field) if isinstance(capability.get(field), list) else []
        for value in values:
            add_artifact(value, f"capability {field}")

    status = "FAIL" if findings else "PASS"
    return {
        "schema_version": 1,
        "verification_id": "matlab_render",
        "status": status,
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"]).lower()),
        "summary": {
            "gate_verdict": gate.get("verdict", "MISSING"),
            "installed": capability.get("installed") is True,
            "executed": capability.get("executed") is True,
            "transport": capability.get("transport", ""),
            "execution_context": capability.get("execution_context", ""),
            "matlab_version": version,
            "matlab_figure_count": len(matlab_rows),
            "minimum_png_dpi": minimum_dpi,
            "validation_status": validation.get("status", "MISSING"),
        },
        "findings": findings,
    }


def verify_latex_build(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    manifest_path = project_root / "planning" / "delivery_manifest.json"

    try:
        manifest = load_json(manifest_path)
        sources.append(file_record(workspace_root, manifest_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        manifest = {}
        findings.append({"code": "delivery_manifest", "message": str(exc)})

    expected_contract = {
        "profile": "contest_final",
        "canonical_source": "paper/main.tex",
        "canonical_pdf": "output/contest_final/paper.pdf",
        "build_engine": "xelatex",
        "status": "READY",
    }
    for key, expected in expected_contract.items():
        if manifest.get(key) != expected:
            findings.append(
                {
                    "code": "delivery_contract",
                    "message": f"manifest {key} must be {expected!r}",
                }
            )
    declared_root = str(manifest.get("project_root") or "").strip()
    if not declared_root or Path(declared_root).resolve() != project_root.resolve():
        findings.append(
            {"code": "project_root", "message": "manifest project_root does not match the project"}
        )

    build = manifest.get("build") if isinstance(manifest.get("build"), dict) else {}
    command = build.get("command") if isinstance(build.get("command"), list) else []
    command_text = [str(item) for item in command]
    has_latexmk = bool(command_text) and "latexmk" in Path(command_text[0]).name.lower()
    has_xelatex_flag = any(item.lower() == "-xelatex" for item in command_text)
    if (
        build.get("status") != "PASS"
        or build.get("returncode") != 0
        or not has_latexmk
        or not has_xelatex_flag
    ):
        findings.append(
            {
                "code": "latex_build",
                "message": "build must be a successful latexmk -xelatex invocation",
            }
        )

    tools = (
        build.get("toolchain", {}).get("tools", {})
        if isinstance(build.get("toolchain"), dict)
        else {}
    )
    xelatex = tools.get("xelatex") if isinstance(tools.get("xelatex"), dict) else {}
    if xelatex.get("returncode") != 0 or not str(xelatex.get("version") or "").strip():
        findings.append(
            {"code": "xelatex_toolchain", "message": "XeLaTeX toolchain evidence is incomplete"}
        )

    declared_source = manifest.get("source") if isinstance(manifest.get("source"), dict) else {}
    source_values = declared_source.get("files") if isinstance(declared_source.get("files"), list) else []
    source_paths: list[Path] = []
    for value in source_values:
        try:
            path = resolve_project_path(project_root, value)
        except ValueError as exc:
            findings.append({"code": "source_path", "message": str(exc)})
            continue
        if not path.is_file() or path.stat().st_size == 0:
            findings.append(
                {"code": "source_missing", "message": f"missing or empty source: {value}"}
            )
        else:
            source_paths.append(path)
            artifacts.append(file_record(workspace_root, path))
    if not source_paths or "paper/main.tex" not in [str(item).replace("\\", "/") for item in source_values]:
        findings.append(
            {"code": "source_set", "message": "source set must be nonempty and include paper/main.tex"}
        )
    else:
        actual_source_hash = aggregate_project_files(project_root, source_paths)
        if actual_source_hash.lower() != str(declared_source.get("sha256") or "").lower():
            findings.append(
                {"code": "source_hash", "message": "aggregate source hash does not match the built batch"}
            )

    pdf_path = project_root / "output" / "contest_final" / "paper.pdf"
    declared_pdf = manifest.get("pdf") if isinstance(manifest.get("pdf"), dict) else {}
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        findings.append({"code": "pdf_missing", "message": "canonical PDF is missing or empty"})
    else:
        artifacts.append(file_record(workspace_root, pdf_path))
        if sha256(pdf_path).lower() != str(declared_pdf.get("sha256") or "").lower():
            findings.append({"code": "pdf_hash", "message": "canonical PDF hash is stale"})

    try:
        build_log_path = resolve_project_path(project_root, build.get("log"))
    except ValueError as exc:
        build_log_path = project_root / "__missing_build_log__"
        findings.append({"code": "build_log", "message": str(exc)})
    if not build_log_path.is_file() or build_log_path.stat().st_size == 0:
        findings.append({"code": "build_log", "message": "build log is missing or empty"})
    else:
        artifacts.append(file_record(workspace_root, build_log_path))

    audit = manifest.get("audit") if isinstance(manifest.get("audit"), dict) else {}
    report: dict[str, Any] = {}
    try:
        report_path = resolve_project_path(project_root, audit.get("report"))
        report = load_json(report_path)
        sources.append(file_record(workspace_root, report_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        findings.append({"code": "audit_report", "message": str(exc)})
    batch_id = str(manifest.get("batch_id") or "")
    if (
        audit.get("batch_id") != batch_id
        or audit.get("status") != "PASS"
        or audit.get("blockers") not in ([], None)
        or report.get("batch_id") != batch_id
        or report.get("verdict") != "PASS"
        or report.get("source") != "paper/main.tex"
        or report.get("pdf") != "output/contest_final/paper.pdf"
        or report.get("findings") not in ([], None)
        or report.get("blockers") not in ([], None)
    ):
        findings.append(
            {"code": "audit_batch", "message": "build and final audit must close the same PASS batch"}
        )

    return {
        "schema_version": 1,
        "verification_id": "latex_build",
        "status": "FAIL" if findings else "PASS",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"]).lower()),
        "summary": {
            "batch_id": batch_id,
            "manifest_status": manifest.get("status", "MISSING"),
            "build_engine": manifest.get("build_engine", "MISSING"),
            "source_file_count": len(source_paths),
            "pdf_page_count": declared_pdf.get("page_count"),
            "audit_status": audit.get("status", "MISSING"),
        },
        "findings": findings,
    }


def verify_page_audit(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    manifest_path = project_root / "planning" / "delivery_manifest.json"
    report_path = project_root / "checks" / "final_delivery_report.json"

    loaded: dict[str, dict[str, Any]] = {}
    for name, path in (("manifest", manifest_path), ("report", report_path)):
        try:
            loaded[name] = load_json(path)
            sources.append(file_record(workspace_root, path))
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            loaded[name] = {}
            findings.append({"code": name, "message": str(exc)})
    manifest = loaded["manifest"]
    report = loaded["report"]
    batch_id = str(manifest.get("batch_id") or "")

    if (
        manifest.get("profile") != "contest_final"
        or manifest.get("status") != "READY"
        or manifest.get("canonical_source") != "paper/main.tex"
        or manifest.get("canonical_pdf") != "output/contest_final/paper.pdf"
        or manifest.get("build_engine") != "xelatex"
    ):
        findings.append(
            {"code": "delivery_contract", "message": "page audit requires a READY contest_final XeLaTeX manifest"}
        )

    audit = manifest.get("audit") if isinstance(manifest.get("audit"), dict) else {}
    if (
        not batch_id
        or audit.get("batch_id") != batch_id
        or audit.get("status") != "PASS"
        or audit.get("report") != "checks/final_delivery_report.json"
        or audit.get("blockers") not in ([], None)
        or report.get("batch_id") != batch_id
        or report.get("profile") != "contest_final"
        or report.get("source") != "paper/main.tex"
        or report.get("pdf") != "output/contest_final/paper.pdf"
        or report.get("verdict") != "PASS"
        or report.get("findings") not in ([], None)
        or report.get("blockers") not in ([], None)
    ):
        findings.append(
            {"code": "audit_batch", "message": "manifest and final report must identify the same blocker-free PASS batch"}
        )

    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    pdf_pages = int(metrics.get("pdf_page_count") or 0)
    rendered_count = int(metrics.get("rendered_page_count") or 0)
    effective_pages = int(metrics.get("effective_body_pages") or 0)
    if pdf_pages <= 0 or rendered_count != pdf_pages:
        findings.append(
            {"code": "page_count", "message": "PDF and rendered page counts must be positive and equal"}
        )
    manifest_page_count = (
        manifest.get("pdf", {}).get("page_count")
        if isinstance(manifest.get("pdf"), dict)
        else None
    )
    if manifest_page_count is not None and manifest_page_count != pdf_pages:
        findings.append(
            {"code": "page_count", "message": "manifest and final report page counts disagree"}
        )
    if not 23 <= effective_pages <= 30:
        findings.append(
            {"code": "effective_body_pages", "message": "effective body pages must be between 23 and 30"}
        )
    if metrics.get("abstract_pages") != [1]:
        findings.append({"code": "abstract_page", "message": "abstract must occupy page 1 only"})
    if metrics.get("toc_pages") != [2]:
        findings.append({"code": "toc_page", "message": "table of contents must occupy page 2 only"})
    if metrics.get("body_start_page") != 3:
        findings.append({"code": "body_start_page", "message": "body must start on page 3"})

    empty_metrics = (
        "low_information_body_pages",
        "blank_rendered_pages",
        "edge_clipping_pages",
        "colored_heading_page_signals",
        "colored_title_heading_signals",
        "unresolved_citations",
        "orphan_references",
        "unbound_citation_keys",
        "citation_binding_errors",
    )
    nonempty = [key for key in empty_metrics if metrics.get(key) not in ([], None)]
    if nonempty:
        findings.append(
            {"code": "page_or_citation_findings", "message": f"nonempty blocking metrics: {nonempty}"}
        )
    if (
        metrics.get("uses_booktabs") is not True
        or int(metrics.get("markdown_table_rows") or 0) != 0
        or int(metrics.get("naked_math_token_count") or 0) != 0
    ):
        findings.append(
            {"code": "typesetting_contract", "message": "booktabs is required and Markdown tables/naked math are forbidden"}
        )

    pdf_path = project_root / "output" / "contest_final" / "paper.pdf"
    declared_pdf = manifest.get("pdf") if isinstance(manifest.get("pdf"), dict) else {}
    if not pdf_path.is_file() or pdf_path.stat().st_size == 0:
        findings.append({"code": "pdf_missing", "message": "canonical PDF is missing or empty"})
    else:
        artifacts.append(file_record(workspace_root, pdf_path))
        if sha256(pdf_path).lower() != str(declared_pdf.get("sha256") or "").lower():
            findings.append({"code": "pdf_hash", "message": "canonical PDF hash is stale"})

    render_dir = project_root / "output" / "contest_final" / "rendered"
    rendered_paths = sorted(render_dir.glob("page-*.png")) if render_dir.is_dir() else []
    expected_names = [f"page-{index:02d}.png" for index in range(1, pdf_pages + 1)]
    if len(rendered_paths) != rendered_count or [path.name for path in rendered_paths] != expected_names:
        findings.append(
            {"code": "rendered_pages", "message": "rendered page files must be complete, contiguous, and match the report"}
        )
    for path in rendered_paths:
        if path.stat().st_size == 0:
            findings.append({"code": "rendered_page_empty", "message": f"empty rendered page: {path.name}"})
        else:
            artifacts.append(file_record(workspace_root, path))

    component_gates = report.get("component_gates") if isinstance(report.get("component_gates"), list) else []
    if not component_gates:
        findings.append({"code": "component_gates", "message": "final audit must record component gates"})
    for index, gate in enumerate(component_gates):
        if not isinstance(gate, dict) or gate.get("returncode") != 0:
            findings.append(
                {"code": "component_gate", "message": f"component gate {index} did not pass"}
            )
            continue
        try:
            log_path = resolve_project_path(project_root, gate.get("log"))
        except ValueError as exc:
            findings.append({"code": "component_log", "message": str(exc)})
            continue
        if not log_path.is_file() or log_path.stat().st_size == 0:
            findings.append(
                {"code": "component_log", "message": f"missing or empty component log {index}"}
            )
        else:
            artifacts.append(file_record(workspace_root, log_path))

    return {
        "schema_version": 1,
        "verification_id": "page_audit",
        "status": "FAIL" if findings else "PASS",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"]).lower()),
        "summary": {
            "batch_id": batch_id,
            "pdf_page_count": pdf_pages,
            "rendered_page_count": len(rendered_paths),
            "effective_body_pages": effective_pages,
            "component_gate_count": len(component_gates),
        },
        "findings": findings,
    }


def verify_compaction_audit(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    report_path = project_root / "checks" / "mira_skill_compaction_pre_release.json"
    skill_path = project_root / "SKILL.md"
    rules_path = project_root / "references" / "skill-compaction-control-rules.md"

    try:
        report = load_json(report_path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        report = {}
        findings.append({"code": "compaction_report", "message": str(exc)})

    for path in (report_path, skill_path, rules_path):
        if not path.is_file() or path.stat().st_size == 0:
            findings.append(
                {
                    "code": "control_file",
                    "message": f"missing or empty compaction control file: {relative(workspace_root, path)}",
                }
            )
        else:
            sources.append(file_record(workspace_root, path))

    declared_root = str(report.get("skill_root") or "").strip()
    if not declared_root or Path(declared_root).resolve() != project_root.resolve():
        findings.append(
            {"code": "skill_root", "message": "compaction report skill_root does not match the audited skill"}
        )

    report_findings = report.get("findings") if isinstance(report.get("findings"), list) else []
    fail_findings = [
        item
        for item in report_findings
        if isinstance(item, dict) and str(item.get("level") or "").upper() == "FAIL"
    ]
    if report.get("verdict") not in {"PASS", "PASS_WITH_WARNINGS"} or fail_findings:
        findings.append(
            {"code": "compaction_verdict", "message": "compaction audit must have no FAIL finding"}
        )

    metrics = report.get("metrics") if isinstance(report.get("metrics"), dict) else {}
    declared_skill_lines = int(metrics.get("skill_lines") or 0)
    actual_skill_lines = (
        len(skill_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines())
        if skill_path.is_file()
        else 0
    )
    if declared_skill_lines != actual_skill_lines:
        findings.append(
            {
                "code": "skill_line_mismatch",
                "message": "reported SKILL.md line count does not match the current file",
            }
        )
    if (
        metrics.get("skill_md_exists") is not True
        or actual_skill_lines <= 0
        or actual_skill_lines > 500
    ):
        findings.append(
            {"code": "skill_size", "message": "SKILL.md must exist and remain at or below the 500-line hard limit"}
        )
    if metrics.get("unmentioned_scripts") not in ([], None):
        findings.append(
            {"code": "unmentioned_scripts", "message": "all active scripts must be mentioned or imported"}
        )
    if metrics.get("stale_version_route_hits") not in ([], None):
        findings.append(
            {"code": "stale_version_route", "message": "active routing must not reference stale version notes"}
        )
    if metrics.get("has_skill_compaction_rules") is not True:
        findings.append(
            {"code": "compaction_rules", "message": "skill compaction control rules must be present"}
        )

    audit_inputs = [skill_path]
    for folder, pattern in (("references", "*.md"), ("scripts", "*.py"), ("tests", "*.py")):
        directory = project_root / folder
        if directory.is_dir():
            audit_inputs.extend(path for path in directory.rglob(pattern) if path.is_file())
    if report_path.is_file() and any(path.stat().st_mtime > report_path.stat().st_mtime for path in audit_inputs):
        findings.append(
            {
                "code": "stale_compaction_report",
                "message": "compaction audit predates an active skill, reference, script, or test input",
            }
        )

    warning_count = sum(
        1
        for item in report_findings
        if isinstance(item, dict) and str(item.get("level") or "").upper() == "WARN"
    )
    return {
        "schema_version": 1,
        "verification_id": "compaction_audit",
        "status": "FAIL" if findings else "PASS",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": [],
        "summary": {
            "audit_generated_at": report.get("generated_at", ""),
            "audit_verdict": report.get("verdict", "MISSING"),
            "skill_lines": actual_skill_lines,
            "warning_count": warning_count,
            "unmentioned_script_count": len(metrics.get("unmentioned_scripts") or []),
            "stale_version_route_count": len(metrics.get("stale_version_route_hits") or []),
        },
        "findings": findings,
    }


def verify_historical_registry(workspace_root: Path, project_root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    sources: list[dict[str, Any]] = []
    artifacts: list[dict[str, Any]] = []
    registry_path = project_root / "benchmarks" / "registry.json"

    try:
        registry = load_json(registry_path)
        sources.append(file_record(workspace_root, registry_path))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        registry = {}
        findings.append({"code": "registry_source", "message": str(exc)})

    if registry.get("schema_version") != 2:
        findings.append({"code": "registry_schema", "message": "historical registry schema_version must be 2"})
    candidate_release_status = registry.get("candidate_release_status")
    allowed_release_statuses = {"BLOCKED", "RELEASED"}
    if candidate_release_status not in allowed_release_statuses:
        findings.append(
            {
                "code": "candidate_release_status",
                "message": (
                    "candidate_release_status must be BLOCKED or RELEASED"
                ),
            }
        )

    archive_root_text = str(registry.get("archive_root") or "").strip()
    archive_root = (workspace_root / archive_root_text).resolve()
    try:
        archive_root.relative_to(workspace_root.resolve())
    except ValueError:
        findings.append({"code": "archive_root", "message": "archive_root escapes the workspace"})

    projects = registry.get("projects") if isinstance(registry.get("projects"), list) else []
    comparisons = (
        registry.get("comparisons") if isinstance(registry.get("comparisons"), list) else []
    )
    if not projects:
        findings.append({"code": "projects", "message": "historical registry must contain projects"})

    seen_ids: set[str] = set()
    seen_artifacts: set[Path] = set()
    not_available_count = 0
    allowed_statuses = {"PRESERVED", "PARTIAL", "NOT_AVAILABLE"}
    section_names = ("canonical_summary", "run_manifest", "key_results", "final_decision")

    def add_artifact(path: Path) -> None:
        if path not in seen_artifacts:
            artifacts.append(file_record(workspace_root, path))
            seen_artifacts.add(path)

    for index, row in enumerate(projects):
        if not isinstance(row, dict):
            findings.append({"code": "project_record", "message": f"project {index} is not an object"})
            continue
        project_id = str(row.get("id") or "").strip()
        if not project_id or project_id in seen_ids:
            findings.append({"code": "project_id", "message": f"project {index} has a missing or duplicate id"})
        seen_ids.add(project_id)

        archive_path_text = str(row.get("archive_path") or "").strip()
        project_archive = (workspace_root / archive_path_text).resolve()
        try:
            project_archive.relative_to(archive_root)
        except ValueError:
            findings.append(
                {"code": "project_archive", "message": f"{project_id}: archive_path is outside archive_root"}
            )
            continue
        if not project_archive.is_dir():
            findings.append(
                {"code": "project_archive", "message": f"{project_id}: archive directory is missing"}
            )
            continue

        final_text = str(row.get("final_artifact") or "").strip()
        final_path = (project_archive / final_text).resolve()
        try:
            final_path.relative_to(project_archive)
        except ValueError:
            findings.append(
                {"code": "final_artifact_path", "message": f"{project_id}: final artifact escapes its archive"}
            )
        else:
            if not final_path.is_file() or final_path.stat().st_size == 0:
                findings.append(
                    {"code": "final_artifact", "message": f"{project_id}: final artifact is missing or empty"}
                )
            else:
                add_artifact(final_path)

        for section_name in section_names:
            section = row.get(section_name) if isinstance(row.get(section_name), dict) else {}
            status = str(section.get("status") or "").strip().upper()
            if status not in allowed_statuses:
                findings.append(
                    {"code": "section_status", "message": f"{project_id}.{section_name} has an invalid status"}
                )
                continue
            if status == "NOT_AVAILABLE":
                not_available_count += 1
            evidence = section.get("evidence") if isinstance(section.get("evidence"), list) else []
            if status != "NOT_AVAILABLE" and not evidence:
                findings.append(
                    {"code": "section_evidence", "message": f"{project_id}.{section_name} lacks evidence"}
                )
            for evidence_index, value in enumerate(evidence):
                evidence_text = str(value or "").strip()
                evidence_path = (project_archive / evidence_text).resolve()
                try:
                    evidence_path.relative_to(project_archive)
                except ValueError:
                    findings.append(
                        {
                            "code": "evidence_path",
                            "message": f"{project_id}.{section_name}[{evidence_index}] escapes its archive",
                        }
                    )
                    continue
                if not evidence_path.is_file() or evidence_path.stat().st_size == 0:
                    findings.append(
                        {
                            "code": "evidence_missing",
                            "message": f"{project_id}.{section_name}[{evidence_index}] is missing or empty",
                        }
                    )
                else:
                    add_artifact(evidence_path)

        summary = row.get("canonical_summary") if isinstance(row.get("canonical_summary"), dict) else {}
        if not str(summary.get("text") or "").strip():
            findings.append({"code": "summary_text", "message": f"{project_id}: canonical summary text is empty"})
        key_results = row.get("key_results") if isinstance(row.get("key_results"), dict) else {}
        items = key_results.get("items") if isinstance(key_results.get("items"), list) else []
        if key_results.get("status") != "NOT_AVAILABLE" and not any(str(item).strip() for item in items):
            findings.append({"code": "key_results", "message": f"{project_id}: key result items are empty"})
        decision = row.get("final_decision") if isinstance(row.get("final_decision"), dict) else {}
        if decision.get("verdict") != row.get("verdict"):
            findings.append(
                {"code": "decision_verdict", "message": f"{project_id}: final decision differs from historical verdict"}
            )
        if not str(decision.get("basis") or "").strip():
            findings.append({"code": "decision_basis", "message": f"{project_id}: final decision basis is empty"})

    return {
        "schema_version": 1,
        "verification_id": "historical_registry",
        "status": "FAIL" if findings else "PASS",
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "workspace_root": str(workspace_root),
        "project_root": relative(workspace_root, project_root),
        "sources": sources,
        "artifacts": sorted(artifacts, key=lambda item: str(item["path"]).lower()),
        "summary": {
            "project_count": len(projects),
            "comparison_count": len(comparisons),
            "not_available_section_count": not_available_count,
            "archived_evidence_file_count": len(artifacts),
        },
        "findings": findings,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--verification-id",
        required=True,
        choices=(
            "python_render",
            "matlab_render",
            "latex_build",
            "page_audit",
            "compaction_audit",
            "historical_registry",
        ),
    )
    parser.add_argument("--workspace-root", required=True)
    parser.add_argument("--project-root", required=True)
    parser.add_argument("--write-json", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace_root = Path(args.workspace_root).resolve()
    project_root = Path(args.project_root).resolve()
    verifiers = {
        "python_render": verify_python_render,
        "matlab_render": verify_matlab_render,
        "latex_build": verify_latex_build,
        "page_audit": verify_page_audit,
        "compaction_audit": verify_compaction_audit,
        "historical_registry": verify_historical_registry,
    }
    payload = verifiers[args.verification_id](workspace_root, project_root)
    output = Path(args.write_json).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"VERIFICATION: {payload['verification_id']}")
    print(f"STATUS: {payload['status']}")
    print(f"EVIDENCE_SHA256: {sha256(output)}")
    return 0 if payload["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
