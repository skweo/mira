#!/usr/bin/env python3
"""Canonical contest-final delivery contract for Mira projects.

The manifest is the single source of truth for the source, PDF, build batch,
and release status.  Other final-delivery tools must resolve artifacts through
this module instead of searching the project tree.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


PROFILE = "contest_final"
CANONICAL_SOURCE = "paper/main.tex"
CANONICAL_PDF = "output/contest_final/paper.pdf"
MANIFEST_PATH = "planning/delivery_manifest.json"
EVIDENCE_DECLARATION = "planning/delivery_evidence.json"
BUILD_ENGINE = "xelatex"
STATUSES = {"DRAFT", "BUILT", "AUDIT_FAILED", "READY"}
FINAL_STATUSES = {"AUDIT_FAILED", "READY"}
SOURCE_SUFFIXES = {".tex", ".bib", ".cls", ".sty"}


class DeliveryContractError(RuntimeError):
    """Raised when a project violates the contest-final artifact contract."""


def now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def canonical_source(root: Path | str) -> Path:
    return Path(root).resolve() / CANONICAL_SOURCE


def canonical_pdf(root: Path | str) -> Path:
    return Path(root).resolve() / CANONICAL_PDF


def manifest_path(root: Path | str) -> Path:
    return Path(root).resolve() / MANIFEST_PATH


def relative(root: Path | str, path: Path | str) -> str:
    root_path = Path(root).resolve()
    target = Path(path).resolve()
    try:
        return target.relative_to(root_path).as_posix()
    except ValueError:
        return str(target)


def sha256_file(path: Path | str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def collect_source_files(root: Path | str, entry: Path | str | None = None) -> list[Path]:
    """Collect the transitive LaTeX source set used by the canonical entry."""
    root_path = Path(root).resolve()
    entry_path = Path(entry).resolve() if entry else canonical_source(root_path)
    if not entry_path.is_file():
        return []

    found: list[Path] = []
    visited: set[Path] = set()

    def visit(path: Path) -> None:
        resolved = path.resolve()
        if resolved in visited or not resolved.is_file():
            return
        try:
            resolved.relative_to(root_path)
        except ValueError as exc:
            raise DeliveryContractError(f"source include escapes project root: {resolved}") from exc
        visited.add(resolved)
        found.append(resolved)
        if resolved.suffix.lower() not in {".tex", ".cls", ".sty"}:
            return
        text = read_text(resolved)
        targets: list[tuple[str, str]] = []
        targets.extend((item, ".tex") for item in re.findall(r"\\(?:input|include)\s*\{([^}]+)\}", text))
        targets.extend((item, ".bib") for item in re.findall(r"\\addbibresource(?:\[[^\]]*\])?\s*\{([^}]+)\}", text))
        for group in re.findall(r"\\bibliography\s*\{([^}]+)\}", text):
            targets.extend((item.strip(), ".bib") for item in group.split(",") if item.strip())
        for raw, suffix in targets:
            candidate = Path(raw.strip())
            if not candidate.suffix:
                candidate = candidate.with_suffix(suffix)
            visit(resolved.parent / candidate)

    visit(entry_path)
    return sorted(found, key=lambda item: relative(root_path, item).lower())


def aggregate_source_hash(root: Path | str, files: Iterable[Path] | None = None) -> str:
    root_path = Path(root).resolve()
    source_files = list(files) if files is not None else collect_source_files(root_path)
    if not source_files:
        return ""
    digest = hashlib.sha256()
    for path in sorted(source_files, key=lambda item: relative(root_path, item).lower()):
        rel = relative(root_path, path).encode("utf-8")
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
    return digest.hexdigest()


def source_fingerprint(root: Path | str, entry: Path | str | None = None) -> dict[str, Any]:
    """Describe the current transitive source set for a paper entry."""

    root_path = Path(root).resolve()
    entry_path = Path(entry).resolve() if entry else canonical_source(root_path)
    files = collect_source_files(root_path, entry_path)
    return {
        "canonical_source": relative(root_path, entry_path),
        "source_files": [relative(root_path, path) for path in files],
        "source_sha256": aggregate_source_hash(root_path, files),
    }


def load_current_source_report(root: Path | str, path: Path | str) -> dict[str, Any]:
    """Load a JSON report only when its source fingerprint is still current."""

    root_path = Path(root).resolve()
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = root_path / report_path
    if not report_path.is_file():
        return {}
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    if not isinstance(payload, dict):
        return {}

    canonical = str(payload.get("canonical_source") or "").strip()
    recorded_files = payload.get("source_files")
    recorded_hash = str(payload.get("source_sha256") or "").strip()
    if not canonical or not isinstance(recorded_files, list) or not recorded_hash:
        return {}

    entry_path = Path(canonical)
    if not entry_path.is_absolute():
        entry_path = root_path / entry_path
    try:
        current = source_fingerprint(root_path, entry_path)
    except (OSError, DeliveryContractError):
        return {}
    if current["source_files"] != recorded_files or current["source_sha256"] != recorded_hash:
        return {}
    return payload


def source_report_status(root: Path | str, path: Path | str) -> str:
    """Return MISSING, CURRENT, or STALE for a source-bound JSON report."""

    root_path = Path(root).resolve()
    report_path = Path(path)
    if not report_path.is_absolute():
        report_path = root_path / report_path
    if not report_path.is_file():
        return "MISSING"
    return "CURRENT" if load_current_source_report(root_path, report_path) else "STALE"


def new_manifest(root: Path | str, batch_id: str | None = None) -> dict[str, Any]:
    root_path = Path(root).resolve()
    timestamp = now()
    return {
        "schema_version": 1,
        "profile": PROFILE,
        "project_root": str(root_path),
        "canonical_source": CANONICAL_SOURCE,
        "canonical_pdf": CANONICAL_PDF,
        "build_engine": BUILD_ENGINE,
        "status": "DRAFT",
        "batch_id": batch_id or create_batch_id(),
        "started_at": timestamp,
        "updated_at": timestamp,
        "source": {"files": [], "sha256": ""},
        "pdf": {"sha256": "", "page_count": None},
        "supplemental_evidence": {
            "declaration": EVIDENCE_DECLARATION,
            "files": [],
            "sha256": "",
        },
        "build": {"status": "NOT_RUN", "command": [], "returncode": None, "log": ""},
        "audit": {"batch_id": "", "status": "NOT_RUN", "report": "", "blockers": []},
    }


def create_batch_id() -> str:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    return f"{stamp}-{uuid.uuid4().hex[:8]}"


def begin_batch(root: Path | str) -> dict[str, Any]:
    manifest = new_manifest(root)
    write_manifest(root, manifest)
    return manifest


def load_manifest(root: Path | str, *, required: bool = True, validate: bool = True) -> dict[str, Any]:
    path = manifest_path(root)
    if not path.is_file():
        if required:
            raise DeliveryContractError(f"delivery manifest not found: {path}")
        return new_manifest(root)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryContractError(f"invalid delivery manifest: {path}") from exc
    if not isinstance(payload, dict):
        raise DeliveryContractError("delivery manifest root must be a JSON object")
    if validate:
        validate_manifest(root, payload)
    return payload


def validate_manifest(root: Path | str, manifest: dict[str, Any]) -> None:
    expected = {
        "profile": PROFILE,
        "canonical_source": CANONICAL_SOURCE,
        "canonical_pdf": CANONICAL_PDF,
        "build_engine": BUILD_ENGINE,
    }
    for key, value in expected.items():
        if manifest.get(key) != value:
            raise DeliveryContractError(f"manifest {key} must be {value!r}, got {manifest.get(key)!r}")
    status = manifest.get("status")
    if status not in STATUSES:
        raise DeliveryContractError(f"invalid delivery status: {status!r}")
    if not str(manifest.get("batch_id") or "").strip():
        raise DeliveryContractError("manifest batch_id is required")
    declared_root = Path(str(manifest.get("project_root") or "")).resolve()
    if declared_root != Path(root).resolve():
        raise DeliveryContractError(f"manifest project_root mismatch: {declared_root}")


def write_manifest(root: Path | str, manifest: dict[str, Any]) -> Path:
    validate_manifest(root, manifest)
    path = manifest_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest["updated_at"] = now()
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path


def record_build(
    root: Path | str,
    manifest: dict[str, Any],
    *,
    command: list[str],
    returncode: int,
    log: str,
    log_path: str,
    toolchain: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if manifest.get("status") != "DRAFT":
        raise DeliveryContractError("a build can only be recorded from DRAFT")
    source_files = collect_source_files(root)
    manifest["source"] = {
        "files": [relative(root, path) for path in source_files],
        "sha256": aggregate_source_hash(root, source_files),
    }
    manifest["build"] = {
        "status": "PASS" if returncode == 0 else "FAIL",
        "command": command,
        "returncode": returncode,
        "log": log_path,
        "log_tail": log[-4000:],
        "toolchain": toolchain or {},
    }
    if returncode == 0:
        manifest["status"] = "BUILT"
    return manifest


def record_pdf(root: Path | str, manifest: dict[str, Any], *, page_count: int | None = None) -> dict[str, Any]:
    path = canonical_pdf(root)
    if not path.is_file():
        raise DeliveryContractError(f"canonical PDF not found: {path}")
    manifest["pdf"] = {"sha256": sha256_file(path), "page_count": page_count}
    return manifest


def declared_evidence_files(root: Path | str) -> list[Path]:
    """Resolve the optional, explicit list of evidence that belongs to a build batch."""
    root_path = Path(root).resolve()
    declaration = root_path / EVIDENCE_DECLARATION
    if not declaration.is_file():
        return []
    try:
        payload = json.loads(declaration.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeliveryContractError(f"invalid evidence declaration: {declaration}") from exc
    if not isinstance(payload, dict) or payload.get("schema_version") != 1:
        raise DeliveryContractError("evidence declaration must be a version 1 JSON object")
    records = payload.get("files")
    if not isinstance(records, list):
        raise DeliveryContractError("evidence declaration files must be a list")

    paths: list[Path] = []
    seen: set[str] = set()
    for record in records:
        value = record.get("path") if isinstance(record, dict) else record
        if not isinstance(value, str) or not value.strip():
            raise DeliveryContractError("each evidence record requires a path")
        path = (root_path / value).resolve()
        try:
            path.relative_to(root_path)
        except ValueError as exc:
            raise DeliveryContractError(f"evidence path escapes project root: {path}") from exc
        rel = relative(root_path, path)
        if rel in seen:
            raise DeliveryContractError(f"duplicate evidence path: {rel}")
        if not path.is_file():
            raise DeliveryContractError(f"declared evidence is missing: {rel}")
        seen.add(rel)
        paths.append(path)
    return sorted(paths, key=lambda item: relative(root_path, item).lower())


def aggregate_file_hash(root: Path | str, files: Iterable[Path]) -> str:
    root_path = Path(root).resolve()
    digest = hashlib.sha256()
    count = 0
    for path in sorted(files, key=lambda item: relative(root_path, item).lower()):
        rel = relative(root_path, path).encode("utf-8")
        data = path.read_bytes()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        count += 1
    return digest.hexdigest() if count else ""


def record_supplemental_evidence(root: Path | str, manifest: dict[str, Any]) -> dict[str, Any]:
    root_path = Path(root).resolve()
    files = declared_evidence_files(root_path)
    manifest["supplemental_evidence"] = {
        "declaration": EVIDENCE_DECLARATION,
        "files": [
            {
                "path": relative(root_path, path),
                "sha256": sha256_file(path),
                "size_bytes": path.stat().st_size,
            }
            for path in files
        ],
        "sha256": aggregate_file_hash(root_path, files),
    }
    return manifest


def record_audit(
    root: Path | str,
    manifest: dict[str, Any],
    *,
    verdict: str,
    report: str,
    blockers: list[dict[str, Any]],
) -> dict[str, Any]:
    if manifest.get("status") != "BUILT":
        raise DeliveryContractError("an audit can only close a BUILT batch")
    if verdict not in {"PASS", "FAIL"}:
        raise DeliveryContractError(f"invalid audit verdict: {verdict}")
    normalized: list[dict[str, Any]] = []
    for blocker in blockers:
        item = dict(blocker)
        if not item.get("owner_phase") or not item.get("return_to"):
            raise DeliveryContractError("every audit blocker requires owner_phase and return_to")
        normalized.append(item)
    if verdict == "PASS" and normalized:
        raise DeliveryContractError("PASS cannot be recorded with blockers")
    manifest["audit"] = {
        "batch_id": manifest["batch_id"],
        "status": verdict,
        "report": report,
        "blockers": normalized,
        "completed_at": now(),
    }
    manifest["status"] = "READY" if verdict == "PASS" else "AUDIT_FAILED"
    write_manifest(root, manifest)
    return manifest


def manifest_source(root: Path | str, *, require_ready: bool = False) -> Path:
    manifest = load_manifest(root)
    if require_ready and manifest.get("status") != "READY":
        raise DeliveryContractError(f"delivery status is {manifest.get('status')}, not READY")
    return canonical_source(root)


def manifest_pdf(root: Path | str, *, require_ready: bool = False) -> Path:
    manifest = load_manifest(root)
    if require_ready and manifest.get("status") != "READY":
        raise DeliveryContractError(f"delivery status is {manifest.get('status')}, not READY")
    return canonical_pdf(root)


def verify_hashes(root: Path | str, manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    source = canonical_source(root)
    pdf = canonical_pdf(root)
    if not source.is_file():
        errors.append(f"canonical source missing: {CANONICAL_SOURCE}")
    else:
        actual = aggregate_source_hash(root)
        recorded = str(manifest.get("source", {}).get("sha256") or "")
        if not recorded:
            errors.append("source hash missing from manifest")
        elif actual != recorded:
            errors.append("source hash does not match the built batch")
    if not pdf.is_file():
        errors.append(f"canonical PDF missing: {CANONICAL_PDF}")
    else:
        actual = sha256_file(pdf)
        recorded = str(manifest.get("pdf", {}).get("sha256") or "")
        if not recorded:
            errors.append("PDF hash missing from manifest")
        elif actual != recorded:
            errors.append("PDF hash does not match the audited artifact")
    declaration = Path(root).resolve() / EVIDENCE_DECLARATION
    recorded_evidence = manifest.get("supplemental_evidence", {})
    if declaration.is_file() or recorded_evidence.get("files"):
        try:
            declared = declared_evidence_files(root)
        except DeliveryContractError as exc:
            errors.append(str(exc))
        else:
            expected_paths = [relative(root, path) for path in declared]
            records = recorded_evidence.get("files")
            recorded_paths = [str(item.get("path") or "") for item in records] if isinstance(records, list) else []
            if expected_paths != recorded_paths:
                errors.append("supplemental evidence files do not match the declaration")
            else:
                for path, record in zip(declared, records):
                    if sha256_file(path) != str(record.get("sha256") or ""):
                        errors.append(f"supplemental evidence hash is stale: {relative(root, path)}")
                aggregate = aggregate_file_hash(root, declared)
                if aggregate != str(recorded_evidence.get("sha256") or ""):
                    errors.append("supplemental evidence aggregate hash is stale")
    return errors


def read_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gb18030"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="ignore")
