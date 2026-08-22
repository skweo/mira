#!/usr/bin/env python3
"""Select a truthful plotting backend from evidence shape and local capability."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from matlab_execution_record import validate_execution_record


HARD_REQUIREMENTS = (
    "provenance_present",
    "units_present",
    "statistics_explicit",
    "offline_reproducible",
    "static_evidence_available",
)

DECISION_FIELDS = (
    "claim",
    "intended_inference",
    "reader_question",
    "data_shape",
    "evidence_role",
)

SHAPE_FAMILY_SPECS = (
    ("map", ("lat_lon", "latitude", "longitude", "geographic coordinates", "route geometry")),
    ("trajectory", ("simulation_trajectory", "ode trajectory", "dynamic trajectory")),
    ("vector_field", ("vector_field", "vector field", "flow field")),
    ("geometry", ("mesh", "polyhedron", "polyhedral", "patch object", "faces vertices", "triangulated geometry", "3d geometry", "3d", "volume")),
    ("scalar_field", ("regular_grid", "regular grid", "scalar field", "surface grid", "contour grid", "matrix field", "matrix", "surface", "contour")),
    ("residual_diagnostic", ("residual series", "regression diagnostic")),
    ("time_series", ("ordered_sequence", "ordered sequence", "time series", "temporal sequence")),
    ("distribution", ("tidy_long", "long table", "long-form data", "grouped samples", "grouped data", "distribution samples")),
    ("local_detail", ("precomputed_array", "precomputed array", "precomputed", "local inset data")),
    ("structural_diagram", ("dependency graph", "process graph", "model structure")),
)

INTENT_FAMILY_SPECS = (
    ("map", ("offline route map", "spatial route", "geographic path")),
    ("trajectory", ("dynamic system", "simulation trajectory", "ode trajectory", "state evolution", "animation")),
    ("vector_field", ("vector field", "flow direction", "direction and magnitude")),
    ("geometry", ("mesh geometry", "spatial structure", "polyhedron", "face-vertex", "3d geometry")),
    ("scalar_field", ("scalar field", "contour", "response surface", "surface values", "field gradient")),
    ("residual_diagnostic", ("residual", "regression", "statistical diagnostic", "model error structure", "goodness of fit diagnostic")),
    ("local_detail", ("local inset", "local enlargement", "zoom detail", "paper layout")),
    ("time_series", ("time series", "trend over time", "convergence", "prediction", "temporal change")),
    ("distribution", ("distribution", "uncertainty spread", "sampling variability", "grouped estimation", "estimation")),
    ("structural_diagram", ("workflow", "mechanism", "variable relation", "architecture", "process structure")),
    ("comparison", ("compare alternatives", "compare groups", "pairwise comparison", "ranking comparison")),
)

ROUTE_SPECS: dict[str, dict[str, Any]] = {
    "distribution": {"route_id": "R01", "backend": "python", "library": "seaborn", "fallback": ("python", "matplotlib"), "rationale": "Distribution evidence uses Seaborn's statistical semantics while Matplotlib retains export control.", "reference_cases": ("SB001", "SB028", "SB029"), "constraints": {}},
    "comparison": {"route_id": "R01", "backend": "python", "library": "seaborn", "fallback": ("python", "matplotlib"), "rationale": "Grouped comparison evidence uses Seaborn's semantic grouping and estimation layer.", "reference_cases": ("SB001", "SB028", "SB029"), "constraints": {}},
    "time_series": {"route_id": "R02", "backend": "python", "library": "matplotlib", "fallback": ("matlab", "matlab"), "rationale": "Ordered sequences and prediction traces use Matplotlib for precise two-dimensional evidence.", "reference_cases": ("MPL002", "MPL008", "MT003"), "constraints": {}},
    "scalar_field": {"route_id": "R03", "backend": "matlab", "library": "matlab", "fallback": ("python", "matplotlib"), "rationale": "The selected scalar-field form benefits from MATLAB's engineering-oriented grid and field tooling.", "reference_cases": ("MT017", "MT032", "MPL012", "MPL016"), "constraints": {}},
    "vector_field": {"route_id": "R04", "backend": "matlab", "library": "matlab", "fallback": ("python", "matplotlib"), "rationale": "The selected vector-field form benefits from MATLAB's field and geometry tooling.", "reference_cases": ("MT019", "MT023", "MPL014", "MPL059"), "constraints": {"three_d_companion": "projection_slice_or_table", "display_disclosure": True}},
    "geometry": {"route_id": "R04", "backend": "matlab", "library": "matlab", "fallback": ("python", "matplotlib"), "rationale": "The selected mesh or spatial-geometry form benefits from MATLAB's face-vertex tooling.", "reference_cases": ("MT019", "MT023", "MT025", "MPL014", "MPL059"), "constraints": {"three_d_companion": "projection_slice_or_table", "display_disclosure": True}},
    "residual_diagnostic": {"route_id": "R05", "backend": "python", "library": "seaborn", "fallback": ("python", "matplotlib"), "rationale": "Residual diagnostics benefit from Seaborn's statistical semantics.", "reference_cases": ("SB030", "SB031", "SB032", "SB033", "SB034"), "constraints": {}},
    "local_detail": {"route_id": "R06", "backend": "python", "library": "matplotlib", "fallback": ("matlab", "matlab"), "rationale": "Local enlargement and precise paper layouts require direct Matplotlib Figure/Axes control.", "reference_cases": ("MPL027", "MPL030", "MT031"), "constraints": {}},
    "structural_diagram": {"route_id": "R06", "backend": "python", "library": "matplotlib", "fallback": ("matlab", "matlab"), "rationale": "The selected structural diagram uses the editable Python diagram workflow.", "reference_cases": ("MPL027", "MPL030"), "constraints": {}},
    "trajectory": {"route_id": "R07", "backend": "matlab", "library": "matlab", "fallback": ("python", "matplotlib"), "rationale": "The selected simulation-trajectory form fits MATLAB's numerical runtime; static evidence remains mandatory.", "reference_cases": ("MT026", "MT027", "MPL071", "MPL072"), "constraints": {}},
    "map": {"route_id": "R08", "backend": "matlab", "library": "matlab", "fallback": ("python", "matplotlib"), "rationale": "The selected local-route form benefits from MATLAB numeric geometry without implying a map projection.", "reference_cases": ("MT011",), "constraints": {"projection": "none"}},
}

NON_GRAPHIC_FAMILIES = {"table", "proof_or_equation", "no_visual"}


MATLAB_SIGNALS = {
    "surface": 4, "contour": 3, "field": 4, "vector field": 5,
    "ode": 5, "pde": 6, "differential equation": 4,
    "signal": 5, "control": 5, "bode": 6, "step response": 6,
    "matrix spectrum": 6, "eigenvalue": 5, "spectral radius": 5,
    "optimization trajectory": 5, "parameter scan": 5, "3d geometry": 5,
    "mesh": 5, "polyhedron": 5, "polyhedral": 5, "triangulated geometry": 5,
    "patch object": 5, "faces vertices": 5,
    "simulation": 3, "image processing": 3, "wavelet": 4,
    "曲面": 4, "等高线": 3, "场": 4, "向量场": 5,
    "常微分": 5, "偏微分": 6, "微分方程": 4,
    "信号": 5, "控制": 5, "响应": 3, "频谱": 5,
    "矩阵谱": 6, "特征值": 5, "谱半径": 5,
    "优化轨迹": 5, "参数扫描": 5, "三维几何": 5,
    "仿真": 3, "图像处理": 3, "小波": 4,
}
PYTHON_SIGNALS = {
    "csv": 2, "xlsx": 2, "dataframe": 3, "comparison": 2, "residual": 3,
    "uncertainty": 4, "distribution": 4, "network": 4, "map": 3,
    "2d geometry": 4, "local inset": 3, "error": 3, "statistics": 3,
    "对比": 2, "残差": 3, "不确定性": 4, "分布": 4, "网络": 4, "地图": 3,
    "二维几何": 4, "局部放大": 3, "误差": 3, "统计": 3,
}


@dataclass
class Capability:
    installed: bool
    executable: str
    executed: bool
    version: str
    probe_status: str
    transport: str = ""
    execution_context: str = ""
    record_path: str = ""
    record_valid: bool = False
    record_errors: list[str] = field(default_factory=list)


def route_visual(request: dict[str, Any]) -> dict[str, Any]:
    """Route one claim-bearing visual after evidence prerequisites are explicit.

    This is the public structured routing seam.  It deliberately blocks before
    choosing a plotting library when the evidence contract is incomplete.
    """
    missing = [name for name in HARD_REQUIREMENTS if request.get(name) is not True]
    if missing:
        return unresolved_decision(
            "BLOCKED",
            "Evidence prerequisites must be explicit before visual-form selection.",
            missing,
        )

    visual = select_visual_form(request)
    if visual["status"] != "READY":
        return {
            **unresolved_decision(
                visual["status"],
                visual["rationale"],
                visual["blocking_requirements"],
            ),
            **visual,
        }
    if visual["chart_family"] in NON_GRAPHIC_FAMILIES:
        decision = {
            **visual,
            "backend": None,
            "library": None,
            "route_id": None,
            "fallback": None,
            "rationale": "The selected evidence form does not require a plotting backend.",
            "backend_rationale": "No plotting backend is applicable.",
            "blocking_requirements": [],
            "override": None,
            "reference_cases": [],
            "constraints": {},
        }
        if request.get("override") not in (None, "", {}):
            decision["status"] = "BLOCKED"
            decision["blocking_requirements"] = ["override_not_applicable_without_plotting_backend"]
        return decision

    decision = select_backend(request, visual)
    return apply_override(decision, request.get("override"))


def select_visual_form(request: dict[str, Any]) -> dict[str, Any]:
    """Choose the evidence expression without consulting plotting capabilities."""
    intended = str(request.get("intended_inference") or request.get("statistical_goal") or "").strip()
    basis = {
        "claim": str(request.get("claim") or "").strip(),
        "intended_inference": intended,
        "reader_question": str(request.get("reader_question") or "").strip(),
        "data_shape": str(request.get("data_shape") or "").strip(),
        "evidence_role": str(request.get("evidence_role") or "").strip(),
    }
    shape_context = basis["data_shape"].lower()
    intent_context = " ".join(
        basis[name] for name in ("claim", "intended_inference", "reader_question", "evidence_role")
    ).lower()
    full_context = f"{shape_context} {intent_context}".strip()

    non_graphic = match_non_graphic_family(full_context)
    if non_graphic:
        return visual_form_decision(
            visual_form=non_graphic,
            chart_family=non_graphic,
            basis=basis,
            rationale=f"The evidence contract explicitly selects {non_graphic.replace('_', ' ')} instead of a plotted figure.",
        )

    missing = []
    if not any(basis[name] for name in ("claim", "intended_inference", "reader_question")):
        missing.append("claim_or_intended_inference")
    if not basis["data_shape"]:
        missing.append("data_shape")
    if missing:
        return unresolved_visual_form(
            basis,
            missing,
            "The claim-level question and data shape must be explicit before choosing a visual form.",
        )

    shape_family = match_family(shape_context, SHAPE_FAMILY_SPECS)
    intent_family = match_family(intent_context, INTENT_FAMILY_SPECS)
    if shape_family and intent_family and shape_family != intent_family:
        compatible = shape_family == "distribution" and intent_family in {
            "comparison",
            "residual_diagnostic",
        }
        if not compatible:
            decision = unresolved_visual_form(
                basis,
                ["visual_family_conflict"],
                "The declared data shape and intended inference imply different visual families; resolve the evidence choice explicitly.",
            )
            decision["detected_families"] = {
                "data_shape": shape_family,
                "claim_or_inference": intent_family,
            }
            return decision

    chart_family = intent_family or shape_family
    if not chart_family:
        return unresolved_visual_form(
            basis,
            ["visual_form_or_chart_family"],
            "The supplied evidence description does not identify a defensible visual family.",
        )
    return visual_form_decision(
        visual_form="diagram" if chart_family == "structural_diagram" else "figure",
        chart_family=chart_family,
        basis=basis,
        rationale=(
            f"The claim-level inference and data shape select the {chart_family.replace('_', ' ')} family "
            "before any plotting backend is considered."
        ),
    )


def select_backend(request: dict[str, Any], visual: dict[str, Any]) -> dict[str, Any]:
    """Choose an implementation for an already-selected visual family."""
    chart_family = str(visual["chart_family"])
    spec = ROUTE_SPECS[chart_family]
    backend = str(spec["backend"])
    library = str(spec["library"])
    capability_state = matlab_capability_state(request)
    used_capability_fallback = backend == "matlab" and capability_state == "unavailable"
    if used_capability_fallback:
        backend, library = spec["fallback"]

    decision = ready_decision(
        str(spec["route_id"]),
        backend=backend,
        library=library,
        fallback=spec["fallback"],
        rationale=(
            f"MATLAB capability was explicitly unavailable, so the {chart_family.replace('_', ' ')} form keeps its identity and uses the declared fallback."
            if used_capability_fallback
            else str(spec["rationale"])
        ),
        reference_cases=spec["reference_cases"],
        constraints=spec["constraints"],
    )
    decision.update(visual)
    decision["backend_rationale"] = decision["rationale"]
    decision["backend_selection"] = {
        "matlab_capability": capability_state,
        "execution_context": str(request.get("execution_context") or "unspecified"),
    }
    if used_capability_fallback:
        decision["recommended"] = {
            "backend": spec["backend"],
            "library": spec["library"],
            "route_id": spec["route_id"],
        }
    return decision


def match_non_graphic_family(context: str) -> str | None:
    specs = (
        ("no_visual", ("no_visual", "no visual", "text-only evidence", "visual waiver")),
        ("proof_or_equation", ("proof_or_equation", "analytical proof", "formal derivation", "equation-only evidence")),
        ("table", ("summary_table", "result_table", "tabular summary", "exact-value lookup", "exact values table")),
    )
    return match_family(context, specs)


def match_family(context: str, specs: tuple[tuple[str, tuple[str, ...]], ...]) -> str | None:
    for family, terms in specs:
        if any(term in context for term in terms):
            return family
    return None


def matlab_capability_state(request: dict[str, Any]) -> str:
    value = request.get("matlab_capability")
    if value is None:
        return "unreported"
    if isinstance(value, bool):
        return "verified" if value else "unavailable"
    if not isinstance(value, dict):
        return "unavailable"
    if value.get("executed") is True and value.get("record_valid", True) is not False:
        return "verified"
    if value.get("available") is True and value.get("record_valid", True) is not False:
        return "verified"
    return "unavailable"


def visual_form_decision(
    *, visual_form: str, chart_family: str, basis: dict[str, str], rationale: str,
) -> dict[str, Any]:
    return {
        "status": "READY",
        "visual_form": visual_form,
        "chart_family": chart_family,
        "decision_basis": basis,
        "visual_rationale": rationale,
        "blocking_requirements": [],
    }


def unresolved_visual_form(
    basis: dict[str, str], blocking: list[str], rationale: str,
) -> dict[str, Any]:
    return {
        "status": "NEEDS_EVIDENCE_DECISION",
        "visual_form": None,
        "chart_family": None,
        "decision_basis": basis,
        "visual_rationale": rationale,
        "rationale": rationale,
        "blocking_requirements": blocking,
    }


def unresolved_decision(status: str, rationale: str, blocking: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "visual_form": None,
        "chart_family": None,
        "decision_basis": {},
        "visual_rationale": "",
        "backend": None,
        "library": None,
        "route_id": None,
        "fallback": None,
        "rationale": rationale,
        "backend_rationale": "",
        "blocking_requirements": blocking,
        "override": None,
        "reference_cases": [],
        "constraints": {},
    }


def apply_override(decision: dict[str, Any], value: Any) -> dict[str, Any]:
    if value in (None, "", {}):
        return decision
    if not isinstance(value, dict):
        return blocked_override(decision, ["override"])
    backend = str(value.get("backend") or "").strip().lower()
    library = str(value.get("library") or "").strip().lower()
    reason = str(value.get("reason") or "").strip()
    missing = []
    if backend not in {"python", "matlab"}:
        missing.append("override.backend")
    if library not in {"matplotlib", "seaborn", "matlab"}:
        missing.append("override.library")
    if len(reason) < 24:
        missing.append("override.reason")
    if backend == "matlab" and library != "matlab":
        missing.append("override.backend_library_consistency")
    if backend == "python" and library == "matlab":
        missing.append("override.backend_library_consistency")
    if missing:
        return blocked_override(decision, missing)
    recommendation = decision.get("recommended") or {
        "backend": decision["backend"],
        "library": decision["library"],
        "route_id": decision["route_id"],
    }
    decision["recommended"] = recommendation
    decision["backend"] = backend
    decision["library"] = library
    decision["override"] = {
        "applied": True,
        "backend": backend,
        "library": library,
        "reason": reason,
    }
    return decision


def blocked_override(decision: dict[str, Any], missing: list[str]) -> dict[str, Any]:
    return {
        **decision,
        "status": "BLOCKED",
        "recommended": decision.get("recommended") or {
            "backend": decision["backend"],
            "library": decision["library"],
            "route_id": decision["route_id"],
        },
        "blocking_requirements": missing,
        "override": {"applied": False},
    }


def ready_decision(
    route_id: str,
    *,
    backend: str,
    library: str,
    fallback: tuple[str, str],
    rationale: str,
    reference_cases: tuple[str, ...],
    constraints: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "status": "READY",
        "backend": backend,
        "library": library,
        "route_id": route_id,
        "fallback": {"backend": fallback[0], "library": fallback[1]},
        "rationale": rationale,
        "blocking_requirements": [],
        "override": None,
        "reference_cases": list(reference_cases),
        "constraints": dict(constraints or {}),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--task", default="", help="Figure need or modeling context.")
    parser.add_argument("--request-json", default="", help="Structured visual request JSON for a formal route decision.")
    parser.add_argument("--probe-matlab", action="store_true", help="Run a bounded MATLAB batch probe.")
    parser.add_argument("--probe-timeout", type=int, default=45)
    parser.add_argument("--matlab-capability-record", default="results/logs/matlab_visual_capability.json")
    parser.add_argument("--write-report", default="planning/visual_backend_route.md")
    parser.add_argument("--write-json", default="planning/visual_backend_route.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    if args.request_json:
        request_path = resolve(root, args.request_json)
        try:
            request = json.loads(request_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            print(f"ERROR: invalid structured visual request: {exc}")
            return 2
        if not isinstance(request, dict):
            print("ERROR: structured visual request must be a JSON object")
            return 2
        decision = route_visual(request)
        payload = {
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "route_mode": "structured_confirmed",
            "request_path": rel(root, request_path),
            **decision,
            "selected_backend": decision.get("backend"),
        }
        write_json(root, args.write_json, payload)
        write_text(root, args.write_report, structured_markdown(payload))
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if decision["status"] == "READY" else 1

    context = args.task.strip() or collect_context(root)
    recorded = read_matlab_capability(root, args.matlab_capability_record)
    if recorded and recorded.record_valid:
        capability = recorded
    else:
        capability = merge_invalid_record(
            recorded,
            probe_matlab(args.probe_matlab, args.probe_timeout),
        )
    matlab_score = score(context, MATLAB_SIGNALS)
    python_score = score(context, PYTHON_SIGNALS)
    explicit_matlab = "matlab" in context.lower()

    selected, reason = choose_backend(
        matlab_score, python_score, explicit_matlab, capability
    )

    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "route_mode": "inferred_pending_confirmation",
        "selected_backend": selected,
        "reason": reason,
        "scores": {"python": python_score, "matlab": matlab_score},
        "matlab_capability": asdict(capability),
        "required_outputs": [
            "editable source under code/python or code/matlab",
            "PNG at 300 DPI and vector PDF",
            "source data under results/figures_data",
            "claim-oriented summary JSON",
            "render validation report",
        ],
        "recommended_commands": commands(selected, capability.execution_context),
    }
    write_json(root, args.write_json, payload)
    write_text(root, args.write_report, markdown(payload))
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def choose_backend(
    matlab_score: int,
    python_score: int,
    explicit_matlab: bool,
    capability: Capability,
) -> tuple[str, str]:
    matlab_suited = matlab_score > python_score or explicit_matlab
    if matlab_suited and capability.executed:
        transport = capability.transport or "recorded transport"
        reason = (
            f"MATLAB was explicitly requested and {transport} execution was verified."
            if explicit_matlab
            else f"MATLAB-suited evidence signals dominate and {transport} execution was verified."
        )
        return "matlab", reason
    if matlab_suited and capability.installed:
        return (
            "matlab_pending_probe",
            "The task suits MATLAB, but installation alone is not execution evidence. Probe before drawing.",
        )
    if explicit_matlab:
        return "python", "MATLAB was requested but is unavailable; Python is the executable fallback."
    return "python", "Python is the safer reproducible route for the current evidence shape."


def probe_matlab(run: bool, timeout: int) -> Capability:
    executable = shutil.which("matlab") or ""
    if not executable:
        return Capability(
            False, "", False, "", "not_installed",
            transport="batch", execution_context="unattended",
        )
    if not run:
        return Capability(
            True, executable, False, "", "not_run",
            transport="batch", execution_context="unattended",
        )
    try:
        result = subprocess.run(
            [executable, "-batch", "fprintf('MIRA_MATLAB_VERSION=%s\\n', version)"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=max(timeout, 5), check=False,
        )
    except subprocess.TimeoutExpired:
        return Capability(
            True, executable, False, "", "timeout",
            transport="batch", execution_context="unattended",
        )
    marker = "MIRA_MATLAB_VERSION="
    version = ""
    for line in result.stdout.splitlines():
        if marker in line:
            version = line.split(marker, 1)[1].strip()
    executed = result.returncode == 0 and bool(version)
    return Capability(
        True, executable, executed, version,
        "ok" if executed else f"exit_{result.returncode}",
        transport="batch", execution_context="unattended",
    )


def read_matlab_capability(root: Path, value: str) -> Capability | None:
    path = resolve(root, value)
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None

    errors = validate_execution_record(root, payload, require_success=True)
    transport = str(payload.get("transport") or "").strip().lower()
    execution_context = str(payload.get("execution_context") or "").strip().lower()
    executable = str(payload.get("executable") or "").strip()
    executable_ok = transport == "mcp" or executable_available(executable)
    if transport == "batch" and not executable_ok:
        errors.append("recorded MATLAB executable is missing")

    valid = not errors
    return Capability(
        installed=bool(payload.get("installed")) and executable_ok,
        executable=executable,
        executed=valid,
        version=str(payload.get("matlab_version") or payload.get("version") or "").strip(),
        probe_status="verified_record" if valid else "invalid_record",
        transport=transport,
        execution_context=execution_context,
        record_path=rel(root, path),
        record_valid=valid,
        record_errors=errors,
    )


def merge_invalid_record(recorded: Capability | None, probed: Capability) -> Capability:
    if recorded is None:
        return probed
    if probed.executed:
        probed.record_path = recorded.record_path
        probed.record_errors = recorded.record_errors
        return probed
    return Capability(
        installed=recorded.installed or probed.installed,
        executable=recorded.executable if recorded.installed else probed.executable,
        executed=False,
        version=recorded.version or probed.version,
        probe_status=recorded.probe_status,
        transport=recorded.transport or probed.transport,
        execution_context=recorded.execution_context or probed.execution_context,
        record_path=recorded.record_path,
        record_valid=False,
        record_errors=recorded.record_errors,
    )


def executable_available(value: str) -> bool:
    if not value:
        return False
    path = Path(value)
    if path.is_absolute() or path.parent != Path("."):
        return path.is_file()
    return bool(shutil.which(value))
def collect_context(root: Path) -> str:
    chunks: list[str] = []
    for folder in ("planning", "results"):
        base = root / folder
        if not base.exists():
            continue
        for path in sorted(base.rglob("*")):
            if path.suffix.lower() in {".md", ".txt", ".json", ".csv"} and path.stat().st_size < 1_000_000:
                chunks.append(path.read_text(encoding="utf-8-sig", errors="ignore")[:40_000])
    return "\n".join(chunks)


def score(text: str, weights: dict[str, int]) -> int:
    lowered = text.lower()
    return sum(weight for term, weight in weights.items() if term in lowered)


def commands(selected: str, execution_context: str = "") -> list[str]:
    if selected.startswith("matlab"):
        if execution_context == "interactive":
            return [
                "python <mira-scripts>/run_matlab_visual.py --root <project-root> --prepare-mcp --prefix <figure-prefix> --claim-id <claim-id>",
                "agent: call mcp__matlab__run_matlab_file with the exact script_path in the saved request and save the raw response envelope",
                "python <mira-scripts>/run_matlab_visual.py --root <project-root> --complete-mcp --mcp-request-json <request.json> --mcp-response-json <response.json>",
                "python <mira-scripts>/visual_render_gate.py --root <project-root>",
            ]
        return [
            "python <mira-scripts>/run_matlab_visual.py --root <project-root> --scaffold --run",
            "python <mira-scripts>/visual_render_gate.py --root <project-root>",
        ]
    return [
        "python <mira-scripts>/plot_claim_figure.py --root <project-root> --demo --prefix core_evidence",
        "python <mira-scripts>/visual_render_gate.py --root <project-root>",
    ]


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path if path.is_absolute() else root / path


def rel(root: Path, path: Path) -> str:
    try:
        return str(path.resolve().relative_to(root)).replace("\\", "/")
    except ValueError:
        return str(path)


def write_json(root: Path, value: str, payload: dict) -> None:
    path = resolve(root, value); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_text(root: Path, value: str, content: str) -> None:
    path = resolve(root, value); path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def markdown(payload: dict) -> str:
    cap = payload["matlab_capability"]
    lines = ["# Visual Backend Route", "", f"- Selected: `{payload['selected_backend']}`", f"- Reason: {payload['reason']}", f"- Scores: Python {payload['scores']['python']}; MATLAB {payload['scores']['matlab']}", f"- MATLAB: installed={cap['installed']}, executed={cap['executed']}, status={cap['probe_status']}", "", "## Required Outputs", ""]
    lines.extend(f"- {item}" for item in payload["required_outputs"])
    lines += ["", "## Commands", ""] + [f"- `{item}`" for item in payload["recommended_commands"]]
    return "\n".join(lines) + "\n"


def structured_markdown(payload: dict[str, Any]) -> str:
    fallback = json.dumps(payload.get("fallback"), ensure_ascii=False)
    blockers = ", ".join(payload.get("blocking_requirements", [])) or "none"
    lines = [
        "# Visual Backend Route",
        "",
        f"- Mode: `{payload['route_mode']}`",
        f"- Status: **{payload['status']}**",
        f"- Visual form: `{payload.get('visual_form') or 'unresolved'}`",
        f"- Chart family: `{payload.get('chart_family') or 'unresolved'}`",
        f"- Route: `{payload.get('route_id') or 'unresolved'}`",
        f"- Backend/library: `{payload.get('backend') or '-'} / {payload.get('library') or '-'}`",
        f"- Rationale: {payload.get('rationale', '')}",
        f"- Blocking requirements: {blockers}",
        f"- Fallback: `{fallback}`",
        "",
        "## Reference fixtures",
        "",
    ]
    lines.extend(f"- `{item}`" for item in payload.get("reference_cases", []))
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    raise SystemExit(main())
