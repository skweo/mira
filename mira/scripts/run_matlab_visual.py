#!/usr/bin/env python3
"""Scaffold and optionally execute Mira's MATLAB evidence-figure template."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from datetime import datetime
from pathlib import Path

from figure_provenance import write_figure_provenance
from matlab_execution_record import (
    MCP_RECEIPT_SCHEMA_VERSION,
    MCP_RUN_FILE_TOOL,
    MCP_VISUAL_REQUEST_KIND,
    build_execution_record,
    register_mcp_execution,
    sha256_file,
    validate_execution_record,
    validate_mcp_response_envelope,
    validate_mcp_visual_request,
)
from visual_backend_router import route_visual


TEMPLATE_DIR = Path(__file__).resolve().parents[1] / "assets" / "templates"
TEMPLATES = {
    "dynamic_response": TEMPLATE_DIR / "matlab_claim_figure.m",
    "geometry_3d": TEMPLATE_DIR / "matlab_geometry_3d.m",
}
DEFAULT_PREFIX = "matlab_core_evidence"
DEFAULT_PARAMETERS = {
    "schema_version": 1,
    "model": {
        "t_end": 12.0,
        "samples": 241,
        "decay": 0.52,
        "frequency": 1.72,
        "sine_weight": 0.18,
        "tolerance": 0.02,
        "steady_start": 7.0,
    },
}
DEFAULT_GEOMETRY_PARAMETERS = {
    "schema_version": 1,
    "geometry": {
        "vertices": [
            [-1.0, -0.8, 0.0], [1.0, -0.8, 0.0], [0.8, 0.8, 0.0], [-0.8, 0.8, 0.0],
            [-0.6, -0.5, 1.4], [0.6, -0.5, 1.4], [0.5, 0.5, 1.4], [-0.5, 0.5, 1.4],
        ],
        "faces": [
            [1, 2, 3, 4], [5, 8, 7, 6], [1, 5, 6, 2],
            [2, 6, 7, 3], [3, 7, 8, 4], [4, 8, 5, 1],
        ],
        "face_values": [0.15, 0.35, 0.55, 0.75, 0.95, 0.60],
        "unit": "m",
    },
    "display": {
        "view": [-35.0, 24.0],
        "data_aspect_ratio": [1.0, 1.0, 1.0],
        "face_alpha": 0.92,
        "color_mapping": "face",
        "colormap": "mira_muted",
        "lighting": "gouraud",
        "light_position": [-0.6, 0.4, 1.0],
        "material": "dull",
        "edge_mode": "subtle",
        "projection_plane": "xy",
    },
}
DEFAULT_REQUEST = {
    "data_shape": "simulation_trajectory",
    "statistical_goal": "dynamic system response",
    "evidence_role": "validation",
    "upstream_runtime": "matlab",
    "provenance_present": True,
    "units_present": True,
    "statistics_explicit": True,
    "offline_reproducible": True,
    "static_evidence_available": True,
    "interaction_required": False,
    "output_contract": ["png_300dpi", "vector_pdf", "mat_data"],
}
DEFAULT_GEOMETRY_REQUEST = {
    "data_shape": "mesh_polyhedron",
    "statistical_goal": "3d geometry structure",
    "evidence_role": "mechanism",
    "upstream_runtime": "matlab",
    "provenance_present": True,
    "units_present": True,
    "statistics_explicit": True,
    "offline_reproducible": True,
    "static_evidence_available": True,
    "interaction_required": False,
    "output_contract": ["png_300dpi", "vector_pdf", "mat_data", "projection_pdf"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--scaffold", action="store_true")
    parser.add_argument("--run", action="store_true")
    parser.add_argument(
        "--prepare-mcp",
        action="store_true",
        help="Scaffold an interactive MATLAB MCP request without claiming execution.",
    )
    parser.add_argument(
        "--complete-mcp",
        action="store_true",
        help="Validate a saved real MCP response and finish the visual evidence chain.",
    )
    parser.add_argument("--mcp-request-json", default="")
    parser.add_argument("--mcp-response-json", default="")
    parser.add_argument("--mcp-receipt-json", default="")
    parser.add_argument(
        "--write-record",
        default="results/logs/matlab_visual_capability.json",
    )
    parser.add_argument("--claim-id", default="UNBOUND")
    parser.add_argument("--request-json", default="")
    parser.add_argument("--parameters-json", default="")
    parser.add_argument(
        "--visual-kind",
        choices=tuple(TEMPLATES),
        default="dynamic_response",
        help="Select the reusable MATLAB evidence scaffold.",
    )
    parser.add_argument("--prefix", default=DEFAULT_PREFIX)
    parser.add_argument("--timeout", type=int, default=120)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    selected_actions = sum(bool(value) for value in (args.run, args.prepare_mcp, args.complete_mcp))
    if selected_actions > 1:
        print("ERROR: choose only one of --run, --prepare-mcp, or --complete-mcp")
        return 2
    if args.complete_mcp:
        return complete_mcp_visual(root, args)

    template = TEMPLATES[args.visual_kind]
    default_request = DEFAULT_GEOMETRY_REQUEST if args.visual_kind == "geometry_3d" else DEFAULT_REQUEST
    default_parameters = DEFAULT_GEOMETRY_PARAMETERS if args.visual_kind == "geometry_3d" else DEFAULT_PARAMETERS
    try:
        prefix = validate_prefix(args.prefix)
        request = load_json_object(root, args.request_json) if args.request_json else dict(default_request)
        route = route_visual(request)
        route["route_mode"] = "structured_confirmed" if args.request_json else "adapter_default"
        if route.get("status") != "READY":
            raise ValueError("visual route is blocked: " + ", ".join(route.get("blocking_requirements", [])))
        if route.get("backend") != "matlab" or route.get("library") != "matlab":
            raise ValueError(
                f"run_matlab_visual.py only implements MATLAB routes; received "
                f"{route.get('backend')}/{route.get('library')}"
            )
        parameters = load_json_object(root, args.parameters_json) if args.parameters_json else default_parameters
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2

    target = root / "code" / "matlab" / template.name
    if args.scaffold or args.run or args.prepare_mcp:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template, target)
    parameters_path = root / "results" / "figures_data" / f"{prefix}_parameters.json"
    parameters_path.parent.mkdir(parents=True, exist_ok=True)
    parameters_path.write_text(
        json.dumps(parameters, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )

    if args.prepare_mcp:
        try:
            packet_path, packet = prepare_mcp_visual(
                root=root,
                target=target,
                parameters_path=parameters_path,
                prefix=prefix,
                claim_id=args.claim_id,
                visual_kind=args.visual_kind,
                request=request,
                route=route,
                requested_path=args.mcp_request_json,
            )
        except (OSError, ValueError) as exc:
            print(f"ERROR: {exc}")
            return 2
        print(json.dumps({**packet, "request_file": relative(root, packet_path)}, ensure_ascii=False, indent=2))
        return 0

    executable = shutil.which("matlab") or ""
    created_at = timestamp_now()
    payload = build_execution_record(
        transport="batch",
        execution_context="unattended",
        installed=bool(executable),
        executable=executable or "matlab",
        source=relative(root, target),
        request={
            "claim_id": args.claim_id,
            "prefix": prefix,
            "visual_kind": args.visual_kind,
            "parameters": relative(root, parameters_path),
            "route_id": route.get("route_id"),
        },
        status="scaffolded",
        command_or_tool={
            "kind": "command",
            "argv": [executable or "matlab", "-batch", "<generated when --run is used>"],
        },
        started_at=created_at,
        finished_at=created_at,
    )
    payload.update({
        "claim_id": args.claim_id,
        "prefix": prefix,
        "visual_kind": args.visual_kind,
        "route": route,
        "parameters": relative(root, parameters_path),
    })
    if args.run:
        payload = execute_matlab(
            root, target, executable, args.timeout, payload, args.claim_id,
            parameters_path, prefix, target.stem, args.visual_kind,
        )
        if payload["executed"]:
            summary = load_json_object(
                root, f"results/figures_data/{prefix}_summary.json"
            )
            provenance_path, provenance = write_matlab_provenance(
                root, target, parameters_path, prefix, args.claim_id, route, summary, executable,
                args.visual_kind,
            )
            update_figure_index(root, prefix, args.visual_kind)
            update_evidence_manifest(
                root, args.claim_id, prefix, request, route, summary, provenance_path, provenance,
                target, args.visual_kind,
            )
            payload.update(
                {
                    "matlab_version": summary.get("matlab_version", ""),
                    "evidence": [relative(root, provenance_path)],
                    "outputs": output_paths(prefix, target, args.visual_kind),
                    "provenance": relative(root, provenance_path),
                }
            )

    report = root / "results" / "logs" / "matlab_visual_capability.json"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if not args.run or payload["executed"] else 2


def prepare_mcp_visual(
    *,
    root: Path,
    target: Path,
    parameters_path: Path,
    prefix: str,
    claim_id: str,
    visual_kind: str,
    request: dict,
    route: dict,
    requested_path: str,
) -> tuple[Path, dict]:
    """Create the exact runner and request packet for a later agent MCP call."""
    request_id = f"mira-matlab-{uuid.uuid4()}"
    runner = root / "code" / "matlab" / f"mira_{prefix}_mcp_runner.m"
    runner.write_text(
        matlab_mcp_runner(
            root=root,
            target=target,
            parameters_path=parameters_path,
            prefix=prefix,
            claim_id=claim_id,
            request_id=request_id,
        ),
        encoding="utf-8",
    )
    request_fields = {
        "claim_id": claim_id,
        "prefix": prefix,
        "visual_kind": visual_kind,
        "parameters": relative(root, parameters_path),
        "route_id": route.get("route_id"),
    }
    packet = {
        "schema_version": MCP_RECEIPT_SCHEMA_VERSION,
        "kind": MCP_VISUAL_REQUEST_KIND,
        "backend": "matlab",
        "transport": "mcp",
        "server": "matlab",
        "tool_name": MCP_RUN_FILE_TOOL,
        "request_id": request_id,
        "created_at": timestamp_now(),
        "source": relative(root, target),
        "source_sha256": sha256_file(target),
        "runner": relative(root, runner),
        "runner_sha256": sha256_file(runner),
        "parameters": relative(root, parameters_path),
        "parameters_sha256": sha256_file(parameters_path),
        "request": request_fields,
        "visual_request": request,
        "route": route,
        "tool_arguments": {"script_path": str(runner.resolve())},
        "expected_outputs": runtime_output_paths(prefix, visual_kind),
    }
    errors = validate_mcp_visual_request(root, packet, require_outputs=False)
    if errors:
        raise ValueError("invalid prepared MATLAB MCP request: " + "; ".join(errors))
    packet_path = resolve_for_write(
        root,
        requested_path or f"results/logs/{prefix}_matlab_mcp_request.json",
    )
    packet_path.parent.mkdir(parents=True, exist_ok=True)
    packet_path.write_text(
        json.dumps(packet, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return packet_path, packet


def complete_mcp_visual(root: Path, args: argparse.Namespace) -> int:
    """Finish evidence only after a real MATLAB MCP result has been saved."""
    if not args.mcp_request_json or not args.mcp_response_json:
        print("ERROR: --complete-mcp requires --mcp-request-json and --mcp-response-json")
        return 2
    try:
        request_path = resolve_existing(root, args.mcp_request_json)
        response_path = resolve_existing(root, args.mcp_response_json)
        packet = load_json_file(request_path, "MATLAB MCP request")
        response = load_json_file(response_path, "MATLAB MCP response")
        errors = validate_mcp_visual_request(root, packet, require_outputs=True)
        errors.extend(validate_mcp_response_envelope(packet, response))
        if errors:
            raise ValueError("invalid MATLAB MCP completion: " + "; ".join(dict.fromkeys(errors)))

        prefix = validate_prefix(str(packet["request"].get("prefix") or ""))
        visual_kind = str(packet["request"].get("visual_kind") or "")
        if visual_kind not in TEMPLATES:
            raise ValueError(f"unsupported visual_kind in MCP request: {visual_kind}")
        claim_id = str(packet["request"].get("claim_id") or "UNBOUND")
        target = resolve_existing(root, str(packet["source"]))
        parameters_path = resolve_existing(root, str(packet["parameters"]))
        summary = load_json_object(root, f"results/figures_data/{prefix}_summary.json")
        matlab_version = str(summary.get("matlab_version") or "").strip()
        if not matlab_version:
            raise ValueError("MATLAB summary does not report matlab_version")

        provenance_path, provenance = write_matlab_provenance(
            root,
            target,
            parameters_path,
            prefix,
            claim_id,
            packet["route"],
            summary,
            "MATLAB MCP",
            visual_kind,
        )
        update_figure_index(root, prefix, visual_kind)
        update_evidence_manifest(
            root,
            claim_id,
            prefix,
            packet["visual_request"],
            packet["route"],
            summary,
            provenance_path,
            provenance,
            target,
            visual_kind,
        )

        receipt_path = resolve_for_write(
            root,
            args.mcp_receipt_json or f"results/logs/{prefix}_matlab_mcp_receipt.json",
        )
        receipt = build_mcp_receipt(
            root=root,
            packet=packet,
            request_path=request_path,
            response=response,
            response_path=response_path,
            provenance_path=provenance_path,
            matlab_version=matlab_version,
            prefix=prefix,
            visual_kind=visual_kind,
        )
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        record = register_mcp_execution(root, receipt_path, receipt)
        record_errors = validate_execution_record(root, record, require_success=True)
        if record_errors:
            raise ValueError("invalid canonical MATLAB MCP record: " + "; ".join(record_errors))
        record_path = resolve_for_write(root, args.write_record)
        if record_path in {request_path, response_path, receipt_path}:
            raise ValueError("write-record must differ from MCP request, response, and receipt files")
        record_path.parent.mkdir(parents=True, exist_ok=True)
        record_path.write_text(
            json.dumps(record, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        print(f"ERROR: {exc}")
        return 2
    print(json.dumps(record, ensure_ascii=False, indent=2))
    return 0


def matlab_mcp_runner(
    *,
    root: Path,
    target: Path,
    parameters_path: Path,
    prefix: str,
    claim_id: str,
    request_id: str,
) -> str:
    function_name = target.stem
    return (
        "% Generated by Mira for one bound interactive MATLAB MCP call.\n"
        f"fprintf('MIRA_MCP_REQUEST_ID={matlab_quote(request_id)}\\n');\n"
        f"addpath('{matlab_quote(target.parent)}');\n"
        f"{function_name}('{matlab_quote(root)}','{matlab_quote(claim_id)}',"
        f"'{matlab_quote(parameters_path)}','{matlab_quote(prefix)}');\n"
    )


def matlab_quote(value: object) -> str:
    return str(value).replace("\\", "/").replace("'", "''")


def runtime_output_paths(prefix: str, visual_kind: str) -> list[str]:
    paths = [
        f"figures/{prefix}.png",
        f"figures/{prefix}.pdf",
        f"results/figures_data/{prefix}.csv",
        f"results/figures_data/{prefix}.mat",
        f"results/figures_data/{prefix}_summary.json",
        f"results/logs/{prefix}_matlab.log",
    ]
    if visual_kind == "geometry_3d":
        paths.extend(
            [f"figures/{prefix}_projection.png", f"figures/{prefix}_projection.pdf"]
        )
    return paths


def build_mcp_receipt(
    *,
    root: Path,
    packet: dict,
    request_path: Path,
    response: dict,
    response_path: Path,
    provenance_path: Path,
    matlab_version: str,
    prefix: str,
    visual_kind: str,
) -> dict:
    result_text = "\n".join(
        str(item.get("text") or "")
        for item in response["result"].get("content", [])
        if isinstance(item, dict) and item.get("type") == "text"
    ).strip()
    evidence = [
        relative(root, request_path),
        relative(root, response_path),
        relative(root, provenance_path),
    ]
    return {
        "schema_version": MCP_RECEIPT_SCHEMA_VERSION,
        "backend": "matlab",
        "transport": "mcp",
        "server": "matlab",
        "tool_name": packet["tool_name"],
        "request_id": packet["request_id"],
        "executed": True,
        "status": "ok",
        "matlab_version": matlab_version,
        "started_at": response["started_at"],
        "finished_at": response["finished_at"],
        "source": packet["source"],
        "request": packet["request"],
        "response_summary": result_text[-2000:] or "MATLAB MCP completed the bound request.",
        "log_files": [f"results/logs/{prefix}_matlab.log"],
        "evidence": evidence,
        "outputs": output_paths(prefix, Path(packet["source"]), visual_kind),
        "request_file": relative(root, request_path),
        "request_sha256": sha256_file(request_path),
        "response_file": relative(root, response_path),
        "response_sha256": sha256_file(response_path),
    }


def load_json_file(path: Path, label: str) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"{label} must be a JSON object")
    return payload


def resolve_existing(root: Path, value: str) -> Path:
    path = resolve_for_write(root, value)
    if not path.is_file() or path.stat().st_size == 0:
        raise ValueError(f"file is missing or empty: {value}")
    return path


def resolve_for_write(root: Path, value: str) -> Path:
    path = Path(str(value or "").strip())
    resolved = (path if path.is_absolute() else root / path).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path escapes project root: {value}") from exc
    return resolved


def validate_prefix(value: str) -> str:
    prefix = value.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}", prefix):
        raise ValueError("prefix must use 1-80 ASCII letters, digits, underscores, or hyphens")
    return prefix


def load_json_object(root: Path, value: str) -> dict:
    path = Path(value)
    path = path if path.is_absolute() else root / path
    payload = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON input must be an object: {path}")
    return payload


def execute_matlab(
    root: Path,
    target: Path,
    executable: str,
    timeout: int,
    payload: dict,
    claim_id: str,
    parameters_path: Path,
    prefix: str,
    function_name: str,
    visual_kind: str,
) -> dict:
    if not executable:
        timestamp = timestamp_now()
        payload.update(
            {
                "status": "not_installed",
                "started_at": timestamp,
                "finished_at": timestamp,
                "duration_seconds": 0.0,
            }
        )
        return payload
    started_at = timestamp_now()
    started_clock = time.perf_counter()
    command_argv = [executable, "-batch", "<command unavailable>"]
    try:
        runtime_root = matlab_runtime_root(root)
        with tempfile.TemporaryDirectory(prefix="run-", dir=runtime_root) as bridge_dir:
            bridge_root = Path(bridge_dir) / "project"
            bridge_target = bridge_root / "code" / "matlab" / target.name
            bridge_parameters = (
                bridge_root / "results" / "figures_data" / parameters_path.name
            )
            bridge_target.parent.mkdir(parents=True, exist_ok=True)
            bridge_parameters.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(target, bridge_target)
            shutil.copy2(parameters_path, bridge_parameters)

            command = matlab_command(
                bridge_root,
                bridge_target,
                bridge_parameters,
                claim_id,
                prefix,
                function_name,
            )
            command_argv = [executable, "-batch", command]
            result = subprocess.run(
                command_argv,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(timeout, 10),
                check=False,
                cwd=runtime_root,
            )
            marker_found = "MIRA_MATLAB_FIGURE_OK=" in result.stdout
            executed = result.returncode == 0 and marker_found
            missing_outputs: list[str] = []
            if executed:
                missing_outputs = sync_matlab_outputs(
                    bridge_root, root, prefix, visual_kind
                )
                executed = not missing_outputs
            status = "ok" if executed else matlab_failure_status(
                result.returncode, marker_found, missing_outputs
            )
            finished_at = timestamp_now()
            attempt_log = write_batch_attempt_log(
                root,
                prefix,
                command_argv,
                started_at,
                finished_at,
                status,
                result.returncode,
                result.stdout,
                result.stderr,
            )
            log_files = [attempt_log]
            matlab_log = f"results/logs/{prefix}_matlab.log"
            if executed and (root / matlab_log).is_file():
                log_files.append(matlab_log)
            payload.update(
                {
                    "executed": executed,
                    "status": status,
                    "command_or_tool": {"kind": "command", "argv": command_argv},
                    "returncode": result.returncode,
                    "started_at": started_at,
                    "finished_at": finished_at,
                    "duration_seconds": round(time.perf_counter() - started_clock, 6),
                    "log_files": log_files,
                    "stdout_tail": result.stdout[-2000:],
                    "stderr_tail": result.stderr[-2000:],
                    "missing_outputs": missing_outputs,
                    "execution_details": {"path_bridge": "ascii_temporary"},
                }
            )
            return payload
    except subprocess.TimeoutExpired as exc:
        finished_at = timestamp_now()
        stdout = exc.stdout if isinstance(exc.stdout, str) else ""
        stderr = exc.stderr if isinstance(exc.stderr, str) else ""
        attempt_log = write_batch_attempt_log(
            root,
            prefix,
            command_argv,
            started_at,
            finished_at,
            "timeout",
            None,
            stdout,
            stderr,
        )
        payload.update(
            {
                "status": "timeout",
                "command_or_tool": {"kind": "command", "argv": command_argv},
                "returncode": None,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(time.perf_counter() - started_clock, 6),
                "log_files": [attempt_log],
                "stdout_tail": stdout[-2000:],
                "stderr_tail": stderr[-2000:],
                "execution_details": {"path_bridge": "ascii_temporary"},
            }
        )
        return payload
    except OSError as exc:
        finished_at = timestamp_now()
        attempt_log = write_batch_attempt_log(
            root,
            prefix,
            command_argv,
            started_at,
            finished_at,
            "runtime_bridge_error",
            None,
            "",
            str(exc),
        )
        payload.update(
            {
                "status": "runtime_bridge_error",
                "command_or_tool": {"kind": "command", "argv": command_argv},
                "returncode": None,
                "started_at": started_at,
                "finished_at": finished_at,
                "duration_seconds": round(time.perf_counter() - started_clock, 6),
                "log_files": [attempt_log],
                "stderr_tail": str(exc),
                "execution_details": {"path_bridge": "ascii_temporary"},
            }
        )
        return payload


def timestamp_now() -> str:
    return datetime.now().astimezone().isoformat(timespec="milliseconds")


def write_batch_attempt_log(
    root: Path,
    prefix: str,
    command: list[str],
    started_at: str,
    finished_at: str,
    status: str,
    returncode: int | None,
    stdout: str,
    stderr: str,
) -> str:
    path = root / "results" / "logs" / f"{prefix}_matlab_batch.log"
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"started_at={started_at}",
        f"finished_at={finished_at}",
        f"status={status}",
        f"returncode={returncode}",
        "command=" + json.dumps(command, ensure_ascii=False),
        "",
        "[stdout]",
        stdout,
        "",
        "[stderr]",
        stderr,
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return relative(root, path)


def matlab_runtime_root(project_root: Path) -> Path:
    configured = os.environ.get("MIRA_MATLAB_RUNTIME_DIR", "").strip()
    candidates = [
        Path(configured).expanduser() if configured else None,
        Path(__file__).resolve().parents[4] / "tmp" / "mira-matlab-runtime",
        Path(__file__).resolve().parents[3] / ".mira-matlab-runtime",
        project_root / ".mira-matlab-runtime",
    ]
    for candidate in candidates:
        if candidate is None or not is_ascii_path(candidate):
            continue
        try:
            candidate.mkdir(parents=True, exist_ok=True)
            probe = candidate / ".write-probe"
            probe.write_text("ok\n", encoding="ascii")
            probe.unlink()
            return candidate
        except OSError:
            continue
    raise OSError(
        "MATLAB R2025a requires a writable ASCII runtime path. Set "
        "MIRA_MATLAB_RUNTIME_DIR to an ASCII-only directory outside the system profile."
    )


def is_ascii_path(path: Path) -> bool:
    try:
        str(path.resolve()).encode("ascii")
    except UnicodeEncodeError:
        return False
    return True


def matlab_command(
    bridge_root: Path,
    bridge_target: Path,
    bridge_parameters: Path,
    claim_id: str,
    prefix: str,
    function_name: str,
) -> str:
    def quote(value: object) -> str:
        return str(value).replace("\\", "/").replace("'", "''")

    return (
        f"addpath('{quote(bridge_target.parent)}'); "
        f"{function_name}('{quote(bridge_root)}','{quote(claim_id)}',"
        f"'{quote(bridge_parameters)}','{quote(prefix)}')"
    )


def sync_matlab_outputs(
    bridge_root: Path, project_root: Path, prefix: str, visual_kind: str
) -> list[str]:
    relatives = [
        Path("figures") / f"{prefix}.png",
        Path("figures") / f"{prefix}.pdf",
        Path("results") / "figures_data" / f"{prefix}.csv",
        Path("results") / "figures_data" / f"{prefix}.mat",
        Path("results") / "figures_data" / f"{prefix}_summary.json",
        Path("results") / "logs" / f"{prefix}_matlab.log",
    ]
    if visual_kind == "geometry_3d":
        relatives.extend(
            [
                Path("figures") / f"{prefix}_projection.png",
                Path("figures") / f"{prefix}_projection.pdf",
            ]
        )
    missing = [path.as_posix() for path in relatives if not (bridge_root / path).is_file()]
    if missing:
        return missing
    for relative_path in relatives:
        destination = project_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(bridge_root / relative_path, destination)
    return []


def matlab_failure_status(
    returncode: int, marker_found: bool, missing_outputs: list[str]
) -> str:
    if returncode:
        return f"exit_{returncode}"
    if not marker_found:
        return "marker_missing"
    if missing_outputs:
        return "missing_outputs"
    return "unknown_failure"


def output_paths(prefix: str, source: Path, visual_kind: str) -> list[str]:
    paths = [
        f"code/matlab/{source.name}",
        f"figures/{prefix}.png",
        f"figures/{prefix}.pdf",
        f"results/figures_data/{prefix}.csv",
        f"results/figures_data/{prefix}.mat",
        f"results/figures_data/{prefix}_parameters.json",
        f"results/figures_data/{prefix}_summary.json",
        f"results/figures_data/{prefix}_provenance.json",
        f"results/logs/{prefix}_matlab.log",
    ]
    if visual_kind == "geometry_3d":
        paths.extend([f"figures/{prefix}_projection.png", f"figures/{prefix}_projection.pdf"])
    return paths


def write_matlab_provenance(
    root: Path, source: Path, parameters: Path, prefix: str, claim_id: str,
    route: dict, summary: dict, executable: str, visual_kind: str,
) -> tuple[Path, dict]:
    data_dir = root / "results" / "figures_data"
    toolboxes = summary.get("required_toolboxes")
    if not isinstance(toolboxes, list) or not toolboxes:
        toolboxes = ["MATLAB base"]
    if visual_kind == "geometry_3d":
        statistics = {
            "kind": "deterministic_3d_geometry",
            "vertex_count": int(summary["vertex_count"]),
            "face_count": int(summary["face_count"]),
            "x_extent": float(summary["x_extent"]),
            "y_extent": float(summary["y_extent"]),
            "z_extent": float(summary["z_extent"]),
        }
        transformations = {
            "data_changes": ["none; geometry loaded from archived vertices and faces"],
            "display_only": ["camera, aspect ratio, alpha, color mapping, lighting, and material"],
            "display_parameters": summary["display_parameters"],
        }
        extra_exports = {
            "projection_png": root / "figures" / f"{prefix}_projection.png",
            "projection_pdf": root / "figures" / f"{prefix}_projection.pdf",
        }
    else:
        statistics = {
            "kind": "deterministic_dynamic_response",
            "rmse": float(summary["rmse"]),
            "steady_max_error": float(summary["steady_max_error"]),
            "tolerance": float(summary["tolerance"]),
        }
        transformations = {
            "data_changes": ["response computed from archived model parameters"],
            "display_only": ["steady-state residual inset"],
        }
        extra_exports = None
    return write_figure_provenance(
        root,
        figure_id=f"fig_{prefix}",
        claim_id=claim_id,
        route=route,
        source_code=source,
        input_data=data_dir / f"{prefix}.csv",
        source_artifacts={
            "mat_data": data_dir / f"{prefix}.mat",
            "parameters": parameters,
            "render_log": root / "results" / "logs" / f"{prefix}_matlab.log",
        },
        png=root / "figures" / f"{prefix}.png",
        pdf=root / "figures" / f"{prefix}.pdf",
        statistics=statistics,
        transformations=transformations,
        dpi=300, seed=None,
        runtime={
            "matlab": str(summary.get("matlab_version") or "unknown"),
            "matlab_executable": executable,
            "required_toolboxes": toolboxes,
        },
        export_artifacts=extra_exports,
    )


def update_figure_index(root: Path, prefix: str, visual_kind: str) -> None:
    path = root / "figures" / "figure_index.md"
    header = "# Figure Index\n\n| Figure | Backend | Source data | Supported claim |\n|---|---|---|---|\n"
    text = path.read_text(encoding="utf-8-sig") if path.exists() else header
    figure = f"figures/{prefix}.pdf"
    if visual_kind == "geometry_3d":
        if figure not in text:
            text += (
                f"| {figure} | MATLAB | results/figures_data/{prefix}.csv | "
                "Archived vertices and faces reproduce the 3D structure; the companion projection supports interpretation. |\n"
            )
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        return
    if figure not in text:
        text += (
            f"| {figure} | MATLAB | results/figures_data/{prefix}.csv | "
            "动态响应保持稳定，残差频谱可用于检查未建模结构。 |\n"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")


def update_evidence_manifest(
    root: Path, claim_id: str, prefix: str, request: dict, route: dict,
    summary: dict, provenance_path: Path, provenance: dict, source: Path,
    visual_kind: str,
) -> None:
    if visual_kind == "geometry_3d":
        update_geometry_evidence_manifest(
            root, claim_id, prefix, request, route, summary, provenance_path, provenance, source
        )
        return
    match = re.search(r"Q\s*([0-9]+)", claim_id, flags=re.I)
    question_id = f"Q{match.group(1)}" if match else "Q1"
    record = {
        "figure_id": f"fig_{prefix}",
        "claim_id": claim_id,
        "question_id": question_id,
        "evidence_role": str(request.get("evidence_role") or "validation"),
        "reader_question": "动态响应是否在规定时间内进入并保持在稳态容差带内？",
        "expected_inference": "主响应收敛到目标值，局部放大区间内的稳态误差满足给定容差。",
        "data_source": f"results/figures_data/{prefix}.csv",
        "backend": str(summary.get("backend") or "MATLAB"),
        "library": "matlab",
        "route_id": route["route_id"],
        "route_mode": route.get("route_mode", "structured_confirmed"),
        "recommended_route": route.get("recommended") or {
            "backend": route["backend"],
            "library": route["library"],
            "route_id": route["route_id"],
        },
        "route_override": route.get("override"),
        "backend_reason": "动态系统响应与稳态误差局部核验属于 MATLAB 优先的工程计算证据。",
        "source_file": "code/matlab/matlab_claim_figure.m",
        "log_file": f"results/logs/{prefix}_matlab.log",
        "provenance_file": relative(root, provenance_path),
        "provenance_sha256": provenance["record_sha256"],
        "vector_file": f"figures/{prefix}.pdf",
        "png_file": f"figures/{prefix}.png",
        "png_dpi": 300,
        "layout": "inset",
        "shared_scale": True,
        "comparison_reason": "",
        "has_local_inset": True,
        "legend_strategy": "主图仅区分目标、响应、容差带和最大偏差点，局部图沿用相同语义。",
        "palette": ["#1F2933", "#3D6E8C", "#A8594F", "#E0E8EB"],
        "prelude": "为检验动态响应的收敛性及稳态约束，图中同时给出完整响应和稳态误差局部放大。",
        "conclusion": "响应进入目标附近后保持稳定，局部放大显示稳态最大误差未超过设定容差。",
        "paper_section": "问题一模型验证",
        "statistics": provenance["statistics"],
        "transformations": provenance["transformations"],
        "key_values": [
            {"metric": "rmse", "value": float(summary["rmse"]), "tolerance": 1e-9},
            {"metric": "steady_max_error", "value": float(summary["steady_max_error"]), "tolerance": 1e-9},
        ],
    }
    path = root / "planning" / "figure_evidence.json"
    payload = {"version": 1, "figures": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict) and isinstance(loaded.get("figures"), list):
                payload = loaded
        except json.JSONDecodeError:
            pass
    payload["version"] = 1
    payload["figures"] = [
        item for item in payload["figures"]
        if not isinstance(item, dict) or item.get("figure_id") != record["figure_id"]
    ] + [record]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def update_geometry_evidence_manifest(
    root: Path, claim_id: str, prefix: str, request: dict, route: dict,
    summary: dict, provenance_path: Path, provenance: dict, source: Path,
) -> None:
    match = re.search(r"Q\s*([0-9]+)", claim_id, flags=re.I)
    question_id = f"Q{match.group(1)}" if match else "Q1"
    record = {
        "figure_id": f"fig_{prefix}",
        "claim_id": claim_id,
        "question_id": question_id,
        "evidence_role": str(request.get("evidence_role") or "mechanism"),
        "reader_question": "Do the archived vertices and faces reproduce the claimed spatial structure?",
        "expected_inference": "The 3D mesh and orthographic projection expose the same geometry without treating rendering as feasibility proof.",
        "data_source": f"results/figures_data/{prefix}.csv",
        "backend": str(summary.get("backend") or "MATLAB"),
        "library": "matlab",
        "route_id": route["route_id"],
        "route_mode": route.get("route_mode", "structured_confirmed"),
        "recommended_route": route.get("recommended") or {
            "backend": route["backend"],
            "library": route["library"],
            "route_id": route["route_id"],
        },
        "route_override": route.get("override"),
        "backend_reason": "MATLAB patch geometry directly consumes the archived face-vertex mesh and records the display transform.",
        "source_file": f"code/matlab/{source.name}",
        "log_file": f"results/logs/{prefix}_matlab.log",
        "provenance_file": relative(root, provenance_path),
        "provenance_sha256": provenance["record_sha256"],
        "vector_file": f"figures/{prefix}.pdf",
        "png_file": f"figures/{prefix}.png",
        "projection_file": f"figures/{prefix}_projection.pdf",
        "png_dpi": 300,
        "media_type": "3d",
        "layout": "single",
        "shared_scale": False,
        "comparison_reason": "",
        "has_local_inset": False,
        "legend_strategy": "Use one scalar color mapping and a colorbar; shape and the companion projection carry geometry identity.",
        "palette": ["#27343A", "#4C7880", "#AEBEB8", "#AD8E5F"],
        "prelude": "To inspect the modeled spatial structure, reconstruct the archived face-vertex mesh with a disclosed view and aspect ratio.",
        "conclusion": "The mesh and companion projection are geometrically consistent; physical feasibility still requires separate constraints or tests.",
        "paper_section": "Problem 1 geometry",
        "statistics": provenance["statistics"],
        "transformations": provenance["transformations"],
        "display_parameters": summary["display_parameters"],
        "key_values": [
            {"metric": "vertex_count", "value": int(summary["vertex_count"]), "tolerance": 0},
            {"metric": "face_count", "value": int(summary["face_count"]), "tolerance": 0},
            {"metric": "z_extent", "value": float(summary["z_extent"]), "tolerance": 1e-9},
        ],
    }
    path = root / "planning" / "figure_evidence.json"
    payload = {"version": 1, "figures": []}
    if path.is_file():
        try:
            loaded = json.loads(path.read_text(encoding="utf-8-sig"))
            if isinstance(loaded, dict) and isinstance(loaded.get("figures"), list):
                payload = loaded
        except json.JSONDecodeError:
            pass
    payload["version"] = 1
    payload["figures"] = [
        item for item in payload["figures"]
        if not isinstance(item, dict) or item.get("figure_id") != record["figure_id"]
    ] + [record]
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


if __name__ == "__main__":
    raise SystemExit(main())
