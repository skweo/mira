#!/usr/bin/env python3
"""Create and validate Mira MATLAB execution records."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SCHEMA_VERSION = 3
MCP_RECEIPT_SCHEMA_VERSION = 1
EXECUTION_POLICY = {
    "interactive": "mcp",
    "unattended": "batch",
}
SUCCESS_STATUSES = {"ok", "pass", "passed", "success"}
MCP_VISUAL_REQUEST_KIND = "mira_matlab_visual_mcp_request"
MCP_RUN_FILE_TOOL = "mcp__matlab__run_matlab_file"


def execution_transport(execution_context: str) -> str:
    """Return the only supported transport for an execution context."""
    context = str(execution_context or "").strip().lower()
    try:
        return EXECUTION_POLICY[context]
    except KeyError as exc:
        raise ValueError(
            "execution_context must be 'interactive' or 'unattended'"
        ) from exc


def build_execution_record(
    *,
    transport: str,
    execution_context: str,
    installed: bool,
    source: str,
    request: dict[str, Any],
    executed: bool = False,
    status: str = "not_run",
    matlab_version: str = "",
    command_or_tool: dict[str, Any] | None = None,
    started_at: str = "",
    finished_at: str = "",
    duration_seconds: float = 0.0,
    log_files: list[str] | None = None,
    evidence: list[str] | None = None,
    outputs: list[str] | None = None,
    executable: str = "",
    returncode: int | None = None,
) -> dict[str, Any]:
    """Build the canonical record without claiming that execution occurred."""
    normalized_transport = str(transport or "").strip().lower()
    record: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "backend": "matlab",
        "transport": normalized_transport,
        "execution_context": str(execution_context or "").strip().lower(),
        "installed": bool(installed),
        "executed": bool(executed),
        "status": str(status or "").strip().lower(),
        "matlab_version": str(matlab_version or "").strip(),
        "source": str(source or "").strip(),
        "request": dict(request),
        "command_or_tool": dict(command_or_tool or {}),
        "started_at": str(started_at or "").strip(),
        "finished_at": str(finished_at or "").strip(),
        "duration_seconds": max(float(duration_seconds), 0.0),
        "log_files": list(log_files or []),
        "evidence": list(evidence or []),
        "outputs": list(outputs or []),
    }
    if normalized_transport == "batch":
        record["executable"] = str(executable or "").strip()
        record["returncode"] = returncode
    return record


def validate_execution_record(
    root: Path,
    payload: Any,
    *,
    require_success: bool = True,
) -> list[str]:
    """Validate schema, policy, transport fields, and declared local evidence."""
    root = root.resolve()
    if not isinstance(payload, dict):
        return ["execution record must be a JSON object"]
    errors: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if str(payload.get("backend") or "").strip().lower() != "matlab":
        errors.append("backend must be matlab")

    transport = str(payload.get("transport") or "").strip().lower()
    context = str(payload.get("execution_context") or "").strip().lower()
    try:
        expected = execution_transport(context)
    except ValueError as exc:
        errors.append(str(exc))
        expected = ""
    if transport not in {"mcp", "batch"}:
        errors.append("transport must be mcp or batch")
    elif expected and transport != expected:
        errors.append(f"{context} execution must use {expected}, not {transport}")

    if not isinstance(payload.get("installed"), bool):
        errors.append("installed must be a boolean")
    if not isinstance(payload.get("executed"), bool):
        errors.append("executed must be a boolean")
    status = str(payload.get("status") or "").strip().lower()
    if not status:
        errors.append("status is required")
    if not isinstance(payload.get("request"), dict) or not payload.get("request"):
        errors.append("request must be a nonempty object")

    source = str(payload.get("source") or "").strip()
    if not source:
        errors.append("source is required")
    elif not declared_file(root, source):
        errors.append(f"source file is missing or outside project: {source}")

    command_or_tool = payload.get("command_or_tool")
    if not isinstance(command_or_tool, dict):
        errors.append("command_or_tool must be an object")
        command_or_tool = {}
    if transport == "batch":
        validate_batch_fields(payload, command_or_tool, errors, require_success)
    elif transport == "mcp":
        validate_mcp_fields(root, payload, command_or_tool, errors)

    started = parse_timestamp(payload.get("started_at"), "started_at", errors)
    finished = parse_timestamp(payload.get("finished_at"), "finished_at", errors)
    duration = payload.get("duration_seconds")
    if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
        errors.append("duration_seconds must be a nonnegative number")
    if started and finished and finished < started:
        errors.append("finished_at must not precede started_at")

    for field_name in ("log_files", "evidence", "outputs"):
        values = payload.get(field_name)
        if not isinstance(values, list):
            errors.append(f"{field_name} must be a list")
            continue
        if require_success and not values:
            errors.append(f"successful execution requires {field_name}")
        for value in values:
            text = str(value or "").strip()
            if not text or not declared_file(root, text):
                errors.append(f"missing or outside-project {field_name} path: {text or '<empty>'}")

    if require_success:
        if payload.get("installed") is not True:
            errors.append("successful execution must confirm MATLAB availability")
        if payload.get("executed") is not True:
            errors.append("record does not confirm successful execution")
        if status not in SUCCESS_STATUSES:
            errors.append("record status is not successful")
        if not str(payload.get("matlab_version") or "").strip():
            errors.append("successful execution requires matlab_version")
        if not started or not finished:
            errors.append("successful execution requires start and finish timestamps")
    return unique(errors)


def validate_batch_fields(
    payload: dict[str, Any],
    command_or_tool: dict[str, Any],
    errors: list[str],
    require_success: bool,
) -> None:
    if command_or_tool.get("kind") != "command":
        errors.append("batch command_or_tool.kind must be command")
    argv = command_or_tool.get("argv")
    if not isinstance(argv, list) or not argv or "-batch" not in argv:
        errors.append("batch command_or_tool.argv must contain -batch")
    if "returncode" not in payload:
        errors.append("batch record requires returncode")
    elif require_success and payload.get("returncode") != 0:
        errors.append("successful batch execution requires returncode 0")
    if "executable" not in payload or not str(payload.get("executable") or "").strip():
        errors.append("batch record requires executable")


def validate_mcp_fields(
    root: Path,
    payload: dict[str, Any],
    command_or_tool: dict[str, Any],
    errors: list[str],
) -> None:
    if command_or_tool.get("kind") != "mcp_tool":
        errors.append("MCP command_or_tool.kind must be mcp_tool")
    if str(command_or_tool.get("server") or "").strip().lower() != "matlab":
        errors.append("MCP tool server must be matlab")
    tool_name = str(command_or_tool.get("tool_name") or "").strip()
    if not tool_name or "matlab" not in tool_name.lower():
        errors.append("MCP tool_name must identify a MATLAB tool")
    if not str(command_or_tool.get("request_id") or "").strip():
        errors.append("MCP execution requires request_id")
    receipt = str(command_or_tool.get("receipt") or "").strip()
    if not receipt or not declared_file(root, receipt):
        errors.append("MCP execution requires an existing in-project receipt")
    elif receipt not in [str(value) for value in payload.get("evidence", [])]:
        errors.append("MCP receipt must be listed in evidence")
    else:
        receipt_path = resolve_project_path(root, receipt)
        try:
            receipt_payload = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"MCP receipt is not valid JSON: {exc}")
        else:
            if not isinstance(receipt_payload, dict):
                errors.append("MCP receipt must be a JSON object")
            else:
                errors.extend(validate_mcp_receipt(root, receipt_payload))
                if str(receipt_payload.get("request_id") or "") != str(
                    command_or_tool.get("request_id") or ""
                ):
                    errors.append("MCP record request_id does not match its receipt")
                if str(receipt_payload.get("tool_name") or "") != tool_name:
                    errors.append("MCP record tool_name does not match its receipt")
                if receipt_payload.get("request") != payload.get("request"):
                    errors.append("MCP record request does not match its receipt")
    if "returncode" in payload:
        errors.append("MCP record must not contain returncode")
    if "executable" in payload:
        errors.append("MCP record must not contain executable")


def register_mcp_execution(
    root: Path,
    receipt_path: Path,
    receipt: dict[str, Any],
) -> dict[str, Any]:
    """Normalize a saved MCP receipt; this function never invokes MATLAB."""
    root = root.resolve()
    receipt_path = receipt_path.resolve()
    receipt_rel = relative_project_path(root, receipt_path)
    errors = validate_mcp_receipt(root, receipt)
    if errors:
        raise ValueError("invalid MATLAB MCP receipt: " + "; ".join(errors))
    evidence = unique([receipt_rel, *[str(value) for value in receipt["evidence"]]])
    started = str(receipt["started_at"])
    finished = str(receipt["finished_at"])
    duration = (datetime.fromisoformat(finished) - datetime.fromisoformat(started)).total_seconds()
    return build_execution_record(
        transport="mcp",
        execution_context="interactive",
        installed=True,
        source=str(receipt["source"]),
        request=receipt["request"],
        executed=True,
        status="ok",
        matlab_version=str(receipt["matlab_version"]),
        command_or_tool={
            "kind": "mcp_tool",
            "server": "matlab",
            "tool_name": str(receipt["tool_name"]),
            "request_id": str(receipt["request_id"]),
            "receipt": receipt_rel,
        },
        started_at=started,
        finished_at=finished,
        duration_seconds=duration,
        log_files=[str(value) for value in receipt["log_files"]],
        evidence=evidence,
        outputs=[str(value) for value in receipt["outputs"]],
    )


def validate_mcp_receipt(root: Path, receipt: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if receipt.get("schema_version") != MCP_RECEIPT_SCHEMA_VERSION:
        errors.append(f"receipt schema_version must be {MCP_RECEIPT_SCHEMA_VERSION}")
    if str(receipt.get("backend") or "").strip().lower() != "matlab":
        errors.append("receipt backend must be matlab")
    if str(receipt.get("transport") or "").strip().lower() != "mcp":
        errors.append("receipt transport must be mcp")
    if str(receipt.get("server") or "").strip().lower() != "matlab":
        errors.append("receipt server must be matlab")
    tool_name = str(receipt.get("tool_name") or "").strip()
    if not tool_name or "matlab" not in tool_name.lower():
        errors.append("receipt tool_name must identify a MATLAB tool")
    if not str(receipt.get("request_id") or "").strip():
        errors.append("receipt request_id is required")
    if receipt.get("executed") is not True:
        errors.append("receipt must confirm executed=true")
    if str(receipt.get("status") or "").strip().lower() not in SUCCESS_STATUSES:
        errors.append("receipt status is not successful")
    if not str(receipt.get("matlab_version") or "").strip():
        errors.append("receipt matlab_version is required")
    if not isinstance(receipt.get("request"), dict) or not receipt.get("request"):
        errors.append("receipt request must be a nonempty object")
    if not str(receipt.get("response_summary") or "").strip():
        errors.append("receipt response_summary is required")
    source = str(receipt.get("source") or "").strip()
    if not source or not declared_file(root, source):
        errors.append("receipt source file is missing or outside project")
    started = parse_timestamp(receipt.get("started_at"), "receipt started_at", errors)
    finished = parse_timestamp(receipt.get("finished_at"), "receipt finished_at", errors)
    if started and finished and finished < started:
        errors.append("receipt finished_at must not precede started_at")
    for field_name in ("log_files", "evidence", "outputs"):
        values = receipt.get(field_name)
        if not isinstance(values, list) or not values:
            errors.append(f"receipt {field_name} must be a nonempty list")
            continue
        for value in values:
            if not declared_file(root, str(value or "")):
                errors.append(f"receipt {field_name} path is missing or outside project: {value}")
    request_file = str(receipt.get("request_file") or "").strip()
    response_file = str(receipt.get("response_file") or "").strip()
    request_payload = load_hashed_json(
        root,
        request_file,
        str(receipt.get("request_sha256") or ""),
        "receipt request",
        errors,
    )
    response_payload = load_hashed_json(
        root,
        response_file,
        str(receipt.get("response_sha256") or ""),
        "receipt response",
        errors,
    )
    if request_file and request_file not in [str(value) for value in receipt.get("evidence", [])]:
        errors.append("receipt request_file must be listed in evidence")
    if response_file and response_file not in [str(value) for value in receipt.get("evidence", [])]:
        errors.append("receipt response_file must be listed in evidence")
    if isinstance(request_payload, dict):
        errors.extend(validate_mcp_visual_request(root, request_payload, require_outputs=True))
        if receipt.get("request") != request_payload.get("request"):
            errors.append("receipt request does not match the saved MCP request")
        for field_name in ("request_id", "tool_name", "source"):
            if str(receipt.get(field_name) or "") != str(request_payload.get(field_name) or ""):
                errors.append(f"receipt {field_name} does not match the saved MCP request")
        if isinstance(response_payload, dict):
            errors.extend(validate_mcp_response_envelope(request_payload, response_payload))
    return unique(errors)


def validate_mcp_visual_request(
    root: Path,
    request: Any,
    *,
    require_outputs: bool = False,
) -> list[str]:
    """Validate a prepared visual request without claiming it was executed."""
    if not isinstance(request, dict):
        return ["MATLAB MCP visual request must be a JSON object"]
    errors: list[str] = []
    expected_scalars = {
        "schema_version": MCP_RECEIPT_SCHEMA_VERSION,
        "kind": MCP_VISUAL_REQUEST_KIND,
        "backend": "matlab",
        "transport": "mcp",
        "server": "matlab",
        "tool_name": MCP_RUN_FILE_TOOL,
    }
    for field_name, expected in expected_scalars.items():
        actual = request.get(field_name)
        if isinstance(expected, str):
            actual = str(actual or "").strip().lower()
            expected = expected.lower()
        if actual != expected:
            errors.append(f"MCP visual request {field_name} must be {expected}")
    if not str(request.get("request_id") or "").strip():
        errors.append("MCP visual request request_id is required")
    parse_timestamp(request.get("created_at"), "MCP visual request created_at", errors)
    if not isinstance(request.get("request"), dict) or not request.get("request"):
        errors.append("MCP visual request request must be a nonempty object")
    if not isinstance(request.get("visual_request"), dict) or not request.get("visual_request"):
        errors.append("MCP visual request visual_request must be a nonempty object")
    if not isinstance(request.get("route"), dict) or request.get("route", {}).get("backend") != "matlab":
        errors.append("MCP visual request route must select MATLAB")

    declared = (
        ("source", "source_sha256"),
        ("runner", "runner_sha256"),
        ("parameters", "parameters_sha256"),
    )
    resolved: dict[str, Path] = {}
    for path_field, hash_field in declared:
        value = str(request.get(path_field) or "").strip()
        if not value or not declared_file(root, value):
            errors.append(f"MCP visual request {path_field} is missing or outside project")
            continue
        path = resolve_project_path(root, value)
        resolved[path_field] = path
        expected_hash = str(request.get(hash_field) or "").strip().lower()
        if not valid_sha256(expected_hash) or sha256_file(path) != expected_hash:
            errors.append(f"MCP visual request {hash_field} does not match {path_field}")

    tool_arguments = request.get("tool_arguments")
    if not isinstance(tool_arguments, dict):
        errors.append("MCP visual request tool_arguments must be an object")
    elif "runner" in resolved:
        script_path = str(tool_arguments.get("script_path") or "").strip()
        try:
            argument_path = Path(script_path).resolve()
        except OSError:
            argument_path = Path()
        if argument_path != resolved["runner"]:
            errors.append("MCP visual request script_path must resolve to the saved runner")

    outputs = request.get("expected_outputs")
    if not isinstance(outputs, list) or not outputs:
        errors.append("MCP visual request expected_outputs must be a nonempty list")
    else:
        for value in outputs:
            text = str(value or "").strip()
            if not text:
                errors.append("MCP visual request expected_outputs contains an empty path")
            elif require_outputs and not declared_file(root, text):
                errors.append(f"MATLAB MCP output is missing or empty: {text}")
    return unique(errors)


def validate_mcp_response_envelope(
    request: dict[str, Any],
    response: Any,
) -> list[str]:
    """Verify that a saved tool result is bound to the prepared request."""
    if not isinstance(response, dict):
        return ["MATLAB MCP response envelope must be a JSON object"]
    errors: list[str] = []
    if response.get("schema_version") != MCP_RECEIPT_SCHEMA_VERSION:
        errors.append(f"MATLAB MCP response schema_version must be {MCP_RECEIPT_SCHEMA_VERSION}")
    for field_name in ("backend", "transport", "server", "tool_name", "request_id"):
        if str(response.get(field_name) or "").strip().lower() != str(
            request.get(field_name) or ""
        ).strip().lower():
            errors.append(f"MATLAB MCP response {field_name} does not match the request")
    started = parse_timestamp(response.get("started_at"), "MATLAB MCP response started_at", errors)
    finished = parse_timestamp(response.get("finished_at"), "MATLAB MCP response finished_at", errors)
    if started and finished and finished < started:
        errors.append("MATLAB MCP response finished_at must not precede started_at")
    result = response.get("result")
    if not isinstance(result, dict):
        errors.append("MATLAB MCP response result must be a tool-result object")
        return unique(errors)
    if result.get("isError") is True:
        errors.append("MATLAB MCP tool result reports an error")
    content = result.get("content")
    if not isinstance(content, list) or not content:
        errors.append("MATLAB MCP tool result must contain response content")
        return unique(errors)
    response_text = "\n".join(
        str(item.get("text") or "")
        for item in content
        if isinstance(item, dict) and item.get("type") == "text"
    )
    request_id = str(request.get("request_id") or "")
    if f"MIRA_MCP_REQUEST_ID={request_id}" not in response_text:
        errors.append("MATLAB MCP response is missing the bound request marker")
    if "MIRA_MATLAB_FIGURE_OK=" not in response_text:
        errors.append("MATLAB MCP response is missing the successful figure marker")
    return unique(errors)


def load_hashed_json(
    root: Path,
    value: str,
    expected_hash: str,
    label: str,
    errors: list[str],
) -> dict[str, Any] | None:
    if not value or not declared_file(root, value):
        errors.append(f"{label} file is missing or outside project")
        return None
    path = resolve_project_path(root, value)
    normalized_hash = expected_hash.strip().lower()
    if not valid_sha256(normalized_hash) or sha256_file(path) != normalized_hash:
        errors.append(f"{label} sha256 does not match the saved file")
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{label} is not valid JSON: {exc}")
        return None
    if not isinstance(payload, dict):
        errors.append(f"{label} must be a JSON object")
        return None
    return payload


def valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_timestamp(value: Any, label: str, errors: list[str]) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        errors.append(f"{label} is required")
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        errors.append(f"{label} must be an ISO-8601 timestamp")
        return None
    if parsed.tzinfo is None:
        errors.append(f"{label} must include a timezone")
        return None
    return parsed


def declared_file(root: Path, value: str) -> bool:
    try:
        path = resolve_project_path(root, value)
    except ValueError:
        return False
    return path.is_file() and path.stat().st_size > 0


def resolve_project_path(root: Path, value: str) -> Path:
    path = Path(str(value or "").strip())
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {value}") from exc
    return resolved


def relative_project_path(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {path}") from exc


def unique(values: list[str]) -> list[str]:
    return list(dict.fromkeys(values))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="action", required=True)
    register = subparsers.add_parser(
        "register-mcp",
        help="Validate a saved MATLAB MCP receipt and write the canonical record.",
    )
    register.add_argument("--root", default=".")
    register.add_argument("--receipt-json", required=True)
    register.add_argument(
        "--write-record",
        default="results/logs/matlab_visual_capability.json",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    receipt_path = resolve_project_path(root, args.receipt_json)
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8-sig"))
        if not isinstance(receipt, dict):
            raise ValueError("MCP receipt must be a JSON object")
        record = register_mcp_execution(root, receipt_path, receipt)
        errors = validate_execution_record(root, record, require_success=True)
        if errors:
            raise ValueError("invalid canonical MATLAB record: " + "; ".join(errors))
        output = resolve_project_path_for_write(root, args.write_record)
        if output == receipt_path:
            raise ValueError("write-record must differ from receipt-json")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def resolve_project_path_for_write(root: Path, value: str) -> Path:
    path = Path(str(value or "").strip())
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"output path escapes project root: {value}") from exc
    return resolved


if __name__ == "__main__":
    raise SystemExit(main())
