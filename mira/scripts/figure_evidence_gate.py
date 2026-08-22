#!/usr/bin/env python3
"""Audit claim-bound Python/MATLAB evidence figures for contest-final papers."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from figure_provenance import sha256_file, verify_record_sha256


MATLAB_PRIORITY_TERMS = (
    "surface", "field", "ode", "pde", "signal", "control", "spectrum", "eigenvalue", "matrix spectrum",
    "optimization trajectory", "parameter scan", "3d geometry", "曲面", "场", "常微分", "偏微分", "信号", "控制",
    "频谱", "矩阵谱", "优化轨迹", "参数扫描", "三维几何",
)
LOCAL_INSET_TERMS = (
    "critical", "threshold", "collision", "tangent", "peak error", "boundary contact",
    "临界", "阈值", "碰撞", "相切", "误差峰值", "边界接触",
)
REQUIRED_FIELDS = (
    "figure_id", "claim_id", "question_id", "evidence_role", "reader_question", "expected_inference",
    "data_source", "backend", "library", "route_id", "route_mode", "recommended_route", "backend_reason",
    "source_file", "log_file", "provenance_file", "provenance_sha256", "vector_file", "png_file",
    "legend_strategy", "prelude", "conclusion", "paper_section",
)


@dataclass
class Finding:
    level: str
    figure_id: str
    code: str
    message: str
    evidence: str = ""


class FigureEvidenceGate:
    def __init__(self, root: Path, manifest_path: Path) -> None:
        self.root = root.resolve()
        self.manifest_path = manifest_path.resolve()
        self.figures: list[dict[str, Any]] = []
        self.waivers: list[dict[str, Any]] = []
        self.findings: list[Finding] = []

    def run(self) -> dict[str, Any]:
        self._load()
        seen: set[str] = set()
        for record in self.figures:
            figure_id = str(record.get("figure_id") or "unknown")
            if figure_id in seen:
                self.fail(figure_id, "identity", "duplicate figure_id")
            seen.add(figure_id)
            self._check(record)
        for index, waiver in enumerate(self.waivers, start=1):
            self._check_waiver(waiver, index)
        failures = [item for item in self.findings if item.level == "FAIL"]
        return {
            "schema_version": 1,
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "root": str(self.root),
            "manifest": relative(self.root, self.manifest_path),
            "verdict": "FAIL" if failures else "PASS",
            "metrics": {
                "figure_count": len(self.figures),
                "python_figures": sum("python" in str(item.get("backend", "")).lower() for item in self.figures),
                "matlab_figures": sum("matlab" in str(item.get("backend", "")).lower() for item in self.figures),
                "waivers": len(self.waivers),
                "failures": len(failures),
            },
            "findings": [asdict(item) for item in self.findings],
        }

    def fail(self, figure_id: str, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("FAIL", figure_id, code, message, evidence))

    def warn(self, figure_id: str, code: str, message: str, evidence: str = "") -> None:
        self.findings.append(Finding("WARN", figure_id, code, message, evidence))

    def _load(self) -> None:
        if not self.manifest_path.is_file():
            self.fail("portfolio", "manifest", "planning/figure_evidence.json is missing", relative(self.root, self.manifest_path))
            return
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.fail("portfolio", "manifest", f"invalid figure evidence manifest: {exc}")
            return
        if not isinstance(payload, dict) or payload.get("version") != 1:
            self.fail("portfolio", "manifest", "figure evidence manifest version must be 1")
            return
        records = payload.get("figures")
        if not isinstance(records, list):
            self.fail("portfolio", "manifest", "figures must be a list")
            return
        self.figures = [item for item in records if isinstance(item, dict)]
        waivers = payload.get("waivers", [])
        if not isinstance(waivers, list):
            self.fail("portfolio", "manifest", "waivers must be a list")
            waivers = []
        self.waivers = [item for item in waivers if isinstance(item, dict)]
        if not self.figures and not self.waivers:
            self.fail("portfolio", "coverage", "contest_final requires claim-bearing visual evidence or documented proof/table waivers")

    def _check(self, record: dict[str, Any]) -> None:
        figure_id = str(record.get("figure_id") or "unknown")
        for field in REQUIRED_FIELDS:
            if not str(record.get(field) or "").strip():
                self.fail(figure_id, "contract", f"missing required field: {field}")
        for field in ("figure_id", "claim_id", "question_id"):
            value = str(record.get(field) or "").strip().upper()
            if value in {"UNBOUND", "UNKNOWN", "TBD", "TODO", "NONE", "N/A"}:
                self.fail(figure_id, "contract", f"placeholder is not allowed for {field}", value)
        if len(str(record.get("reader_question") or "")) < 18:
            self.fail(figure_id, "reasoning", "reader_question is too short to define the visual test")
        if len(str(record.get("expected_inference") or "")) < 18:
            self.fail(figure_id, "reasoning", "expected_inference is too short to define the intended conclusion")
        role = str(record.get("evidence_role") or "").lower()
        if role not in {
            "mechanism", "structure", "result", "validation", "comparison",
            "sensitivity", "uncertainty", "error", "flowchart",
        }:
            self.fail(figure_id, "evidence_role", "evidence_role is not recognized", role)
        backend = str(record.get("backend") or "").lower()
        context = " ".join(str(record.get(key) or "") for key in ("reader_question", "expected_inference", "paper_section")).lower()
        matlab_suited = contains_any(context, MATLAB_PRIORITY_TERMS)
        if matlab_suited and "python" in backend:
            reason = str(record.get("backend_reason") or "")
            if len(reason) < 20 or not re.search(r"MATLAB|不可用|依赖|复现|数据管线|交互", reason, flags=re.I):
                self.fail(figure_id, "backend_choice", "MATLAB-priority evidence drawn with Python needs a concrete reason")
        if "python" not in backend and "matlab" not in backend:
            self.fail(figure_id, "backend", "main figures must use Python or MATLAB", backend)
        expected_suffix = ".m" if "matlab" in backend else ".py"
        source = self._require_file(figure_id, "source_file", str(record.get("source_file") or ""), {expected_suffix})
        data = self._require_file(figure_id, "data_source", str(record.get("data_source") or ""), {".csv", ".json", ".mat", ".xlsx", ".txt"})
        log = self._require_file(figure_id, "log_file", str(record.get("log_file") or ""), {".log", ".txt", ".json"})
        vector = self._require_file(figure_id, "vector_file", str(record.get("vector_file") or ""), {".pdf"})
        png = self._require_file(figure_id, "png_file", str(record.get("png_file") or ""), {".png"})
        if "matlab" in backend and log and "MATLAB" not in read_text(log)[:10000]:
            self.fail(figure_id, "matlab_version", "MATLAB log must record the MATLAB version", relative(self.root, log))
        if vector and vector.stat().st_size < 1000:
            self.fail(figure_id, "vector_output", "PDF output is suspiciously small", relative(self.root, vector))
        if png:
            self._check_png(figure_id, png, record)
        layout = str(record.get("layout") or "single").lower()
        if layout not in {"single", "inset", "comparison"}:
            self.fail(figure_id, "layout", "layout must be single, inset, or comparison", layout)
        if layout == "comparison":
            if record.get("shared_scale") is not True or len(str(record.get("comparison_reason") or "")) < 12:
                self.fail(figure_id, "comparison_layout", "side-by-side comparison requires a shared scale and concrete reason")
        media_type = str(record.get("media_type") or "static").strip().lower()
        if media_type in {"animation", "animated", "video"}:
            summary_value = str(record.get("static_summary_file") or "").strip()
            keyframes = record.get("keyframe_files")
            if not summary_value or not isinstance(keyframes, list) or not keyframes:
                self.fail(
                    figure_id,
                    "animation_static_evidence",
                    "animation requires a static summary figure and at least one archived keyframe",
                )
            else:
                self._require_file(figure_id, "static_summary_file", summary_value, {".png", ".pdf"})
                for keyframe in keyframes:
                    self._require_file(figure_id, "keyframe_files", str(keyframe), {".png", ".pdf"})
        if media_type in {"3d", "three_d", "three-dimensional"} or str(record.get("route_id") or "") == "R04":
            companions = [
                ("projection_file", {".png", ".pdf"}),
                ("slice_file", {".png", ".pdf"}),
                ("companion_table", {".csv", ".json", ".xlsx", ".tex"}),
            ]
            declared = [(field, suffixes, str(record.get(field) or "").strip()) for field, suffixes in companions]
            if not any(value for _, _, value in declared):
                self.fail(
                    figure_id,
                    "three_d_companion",
                    "3D claim evidence requires a 2D projection, slice, or companion table",
                )
            else:
                for field, suffixes, value in declared:
                    if value:
                        self._require_file(figure_id, field, value, suffixes)
            self._check_3d_display(figure_id, record)
        inset_roles = {"result", "validation", "comparison", "sensitivity", "uncertainty", "error"}
        if role in inset_roles and contains_any(context, LOCAL_INSET_TERMS) and not (
            layout == "inset" or record.get("has_local_inset") is True
        ):
            self.fail(figure_id, "local_inset", "critical/threshold/collision evidence requires a local inset or enlarged companion view")
        palette = record.get("palette")
        if not isinstance(palette, list) or not 2 <= len(palette) <= 5:
            self.fail(figure_id, "palette", "record a restrained 2-5 color palette")
        elif any(is_rainbow_color(str(color)) for color in palette):
            self.fail(figure_id, "palette", "rainbow-like saturated colors are not allowed", str(palette))
        if len(str(record.get("prelude") or "")) < 18:
            self.fail(figure_id, "paper_narrative", "pre-figure guidance is too short")
        if len(str(record.get("conclusion") or "")) < 18:
            self.fail(figure_id, "paper_narrative", "post-figure conclusion is too short")
        values = record.get("key_values")
        if not isinstance(values, list) or not values:
            self.fail(figure_id, "numeric_binding", "main figure must expose key_values for ledger consistency")
        else:
            for item in values:
                if not isinstance(item, dict) or not all(key in item for key in ("metric", "value", "tolerance")):
                    self.fail(figure_id, "numeric_binding", "every key value needs metric, value, and tolerance")
        if source and data and log:
            newest_input = max(source.stat().st_mtime, data.stat().st_mtime)
            if log.stat().st_mtime + 1 < newest_input:
                self.fail(figure_id, "stale_render", "render log is older than source or data")
            outputs = [item for item in (vector, png) if item is not None]
            if outputs and min(item.stat().st_mtime for item in outputs) + 1 < newest_input:
                self.fail(figure_id, "stale_render", "figure output is older than source or data")
        self._check_provenance_record(figure_id, record)

    def _check_3d_display(self, figure_id: str, record: dict[str, Any]) -> None:
        display = record.get("display_parameters")
        if not isinstance(display, dict):
            self.fail(
                figure_id,
                "three_d_display",
                "3D evidence must disclose view, aspect ratio, alpha, color mapping, lighting, and material",
            )
            return

        def numeric_vector(name: str, count: int, *, positive: bool = False) -> None:
            value = display.get(name)
            valid = (
                isinstance(value, list)
                and len(value) == count
                and all(isinstance(item, (int, float)) and not isinstance(item, bool) for item in value)
            )
            if valid and positive:
                valid = all(item > 0 for item in value)
            if not valid:
                self.fail(figure_id, "three_d_display", f"display_parameters.{name} must contain {count} valid numbers")

        numeric_vector("view", 2)
        numeric_vector("data_aspect_ratio", 3, positive=True)
        alpha = display.get("face_alpha")
        if not isinstance(alpha, (int, float)) or isinstance(alpha, bool) or not 0 < alpha <= 1:
            self.fail(figure_id, "three_d_display", "display_parameters.face_alpha must be in (0, 1]")
        color_mapping = str(display.get("color_mapping") or "").lower()
        if color_mapping not in {"face", "vertex"}:
            self.fail(figure_id, "three_d_display", "display_parameters.color_mapping must be face or vertex")
        colormap = str(display.get("colormap") or "").lower()
        if not colormap:
            self.fail(figure_id, "three_d_display", "display_parameters.colormap is required")
        elif colormap in {"jet", "hsv", "turbo", "rainbow"}:
            self.fail(figure_id, "three_d_display", "rainbow-like 3D colormaps are not allowed", colormap)
        lighting = str(display.get("lighting") or "").lower()
        if lighting not in {"none", "flat", "gouraud", "phong"}:
            self.fail(figure_id, "three_d_display", "display_parameters.lighting is invalid", lighting)
        if lighting != "none":
            numeric_vector("light_position", 3)
        if not str(display.get("material") or "").strip():
            self.fail(figure_id, "three_d_display", "display_parameters.material is required")
        if str(display.get("projection_plane") or "").lower() not in {"xy", "xz", "yz"}:
            self.fail(figure_id, "three_d_display", "display_parameters.projection_plane must be xy, xz, or yz")

    def _check_provenance_record(self, figure_id: str, record: dict[str, Any]) -> None:
        value = str(record.get("provenance_file") or "").strip()
        if not value:
            return
        path = self._require_file(figure_id, "provenance_file", value, {".json"})
        if path is None:
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, json.JSONDecodeError) as exc:
            self.fail(figure_id, "provenance_record", f"invalid provenance JSON: {exc}", value)
            return
        if not isinstance(payload, dict) or not verify_record_sha256(payload):
            self.fail(
                figure_id,
                "provenance_record_hash",
                "provenance canonical record hash is missing or does not match its content",
                value,
            )
            return
        manifest_hash = str(record.get("provenance_sha256") or "")
        if manifest_hash != str(payload.get("record_sha256") or ""):
            self.fail(
                figure_id,
                "provenance_record_hash",
                "figure manifest does not reference the provenance canonical record hash",
                value,
            )
        route = payload.get("route")
        actual_backend = ""
        actual_library = ""
        if not isinstance(route, dict):
            self.fail(figure_id, "provenance_route", "provenance route is missing", value)
        else:
            actual = route.get("actual") if isinstance(route.get("actual"), dict) else {}
            actual_backend = str(actual.get("backend") or "").lower()
            actual_library = str(actual.get("library") or "").lower()
            manifest_backend = str(record.get("backend") or "").lower().split("/", 1)[0].split()[0]
            route_pairs = {
                "route_id": (record.get("route_id"), route.get("route_id")),
                "route_mode": (record.get("route_mode"), route.get("route_mode")),
                "backend": (manifest_backend, actual_backend),
                "library": (str(record.get("library") or "").lower(), actual_library),
            }
            mismatches = [name for name, (manifest, proven) in route_pairs.items() if manifest != proven]
            if record.get("recommended_route") != route.get("recommended"):
                mismatches.append("recommended_route")
            if record.get("route_override") != route.get("override"):
                mismatches.append("route_override")
            if mismatches:
                self.fail(
                    figure_id,
                    "provenance_route",
                    "figure manifest and provenance route disagree: " + ", ".join(mismatches),
                    value,
                )
        source_section = payload.get("source") if isinstance(payload.get("source"), dict) else {}
        export_section = payload.get("export") if isinstance(payload.get("export"), dict) else {}
        media_type = str(record.get("media_type") or "static").strip().lower()
        if media_type in {"3d", "three_d", "three-dimensional"} or str(record.get("route_id") or "") == "R04":
            transformations = payload.get("transformations") if isinstance(payload.get("transformations"), dict) else {}
            if transformations.get("display_parameters") != record.get("display_parameters"):
                self.fail(
                    figure_id,
                    "three_d_display_provenance",
                    "3D display parameters in the manifest and provenance record must match",
                    value,
                )
        required_source = {"source_code", "input_data"}
        if actual_backend == "matlab":
            required_source.update({"mat_data", "parameters", "render_log"})
        missing_source = sorted(required_source - set(source_section))
        if missing_source:
            self.fail(
                figure_id,
                "provenance_contract",
                "provenance is missing reproducibility artifacts: " + ", ".join(missing_source),
                value,
            )
        if not {"png", "pdf"}.issubset(export_section):
            self.fail(figure_id, "provenance_contract", "provenance requires PNG and PDF exports", value)
        try:
            export_dpi = int(export_section.get("dpi", 0))
        except (TypeError, ValueError):
            export_dpi = 0
        if export_dpi < 300:
            self.fail(figure_id, "provenance_contract", "provenance export DPI must be at least 300", str(export_dpi))
        if actual_library == "seaborn":
            statistics = payload.get("statistics") if isinstance(payload.get("statistics"), dict) else {}
            runtime = payload.get("runtime") if isinstance(payload.get("runtime"), dict) else {}
            errorbar = statistics.get("errorbar")
            errorbar_valid = (
                isinstance(errorbar, dict)
                and bool(str(errorbar.get("method") or "").strip())
                and isinstance(errorbar.get("level"), (int, float))
            )
            if not str(statistics.get("estimator") or "").strip() or not errorbar_valid or runtime.get("seed") is None:
                self.fail(
                    figure_id,
                    "seaborn_statistics",
                    "Seaborn evidence requires explicit estimator, errorbar method/level, and seed",
                    value,
                )
            source_code = source_section.get("source_code")
            if isinstance(source_code, dict):
                source_path = resolve(self.root, str(source_code.get("path") or ""))
                if source_path.is_file() and re.search(r"\bci\s*=", read_text(source_path)):
                    self.fail(figure_id, "seaborn_statistics", "legacy Seaborn ci= API is not allowed", relative(self.root, source_path))
        for section_name in ("source", "export"):
            section = payload.get(section_name)
            if not isinstance(section, dict):
                self.fail(figure_id, "provenance_contract", f"provenance {section_name} section is missing", value)
                continue
            for artifact_name, artifact_record in section.items():
                if not isinstance(artifact_record, dict) or "path" not in artifact_record:
                    continue
                artifact_value = str(artifact_record.get("path") or "").strip()
                artifact_path = resolve(self.root, artifact_value)
                if self.root != artifact_path and self.root not in artifact_path.parents:
                    self.fail(
                        figure_id,
                        "provenance_artifact_path",
                        f"provenance artifact must stay inside project root: {section_name}.{artifact_name}",
                        artifact_value,
                    )
                    continue
                if not artifact_path.is_file():
                    self.fail(
                        figure_id,
                        "provenance_artifact_missing",
                        f"provenance artifact is missing: {section_name}.{artifact_name}",
                        artifact_value,
                    )
                    continue
                expected = str(artifact_record.get("sha256") or "")
                actual = sha256_file(artifact_path)
                if expected != actual:
                    self.fail(
                        figure_id,
                        "provenance_artifact_hash",
                        f"provenance artifact hash mismatch: {section_name}.{artifact_name}",
                        artifact_value,
                    )

    def _check_waiver(self, waiver: dict[str, Any], index: int) -> None:
        waiver_id = str(waiver.get("waiver_id") or f"waiver-{index}")
        required = ("claim_id", "question_id", "evidence_form", "reason", "source")
        for field in required:
            if not str(waiver.get(field) or "").strip():
                self.fail(waiver_id, "waiver", f"missing waiver field: {field}")
        if str(waiver.get("evidence_form") or "").lower() not in {"proof", "table"}:
            self.fail(waiver_id, "waiver", "figure waiver evidence_form must be proof or table")
        if len(str(waiver.get("reason") or "")) < 24:
            self.fail(waiver_id, "waiver", "figure waiver needs a concrete evidence-form reason")
        source_value = str(waiver.get("source") or "")
        if source_value:
            source_path = resolve(self.root, source_value.split("#", 1)[0])
            if not source_path.is_file():
                self.fail(waiver_id, "waiver", "waiver source does not exist", source_value)

    def _require_file(self, figure_id: str, field: str, value: str, suffixes: set[str]) -> Path | None:
        if not value:
            return None
        path = resolve(self.root, value)
        if self.root != path and self.root not in path.parents:
            self.fail(figure_id, field, "evidence file must stay inside the project root", value)
            return None
        if not path.is_file():
            self.fail(figure_id, field, f"file does not exist: {value}")
            return None
        if path.suffix.lower() not in suffixes:
            self.fail(figure_id, field, f"unexpected file type: {path.suffix}", value)
            return None
        return path

    def _check_png(self, figure_id: str, path: Path, record: dict[str, Any]) -> None:
        try:
            from PIL import Image, ImageStat

            with Image.open(path) as image:
                dpi = image.info.get("dpi", (0, 0))
                required = int(record.get("png_dpi") or 300)
                if min(float(dpi[0]), float(dpi[1])) < required - 5:
                    self.fail(figure_id, "png_dpi", f"PNG is below {required} DPI", str(dpi))
                width, height = image.size
                if width < 1200 or height < 700:
                    self.fail(figure_id, "resolution", "main figure raster dimensions are too small", f"{width}x{height}")
                stat = ImageStat.Stat(image.convert("L"))
                if stat.stddev[0] < 5:
                    self.fail(figure_id, "blank_render", "PNG appears blank", relative(self.root, path))
        except Exception as exc:
            self.fail(figure_id, "png_read", f"cannot inspect PNG: {exc}", relative(self.root, path))


def contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lower = text.lower()
    return any(term.lower() in lower for term in terms)


def is_rainbow_color(color: str) -> bool:
    value = color.strip().lower()
    return value in {"red", "lime", "blue", "cyan", "magenta", "yellow", "#ff0000", "#00ff00", "#0000ff", "#00ffff", "#ff00ff", "#ffff00"}


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="ignore")


def resolve(root: Path, value: str) -> Path:
    path = Path(value)
    return path.resolve() if path.is_absolute() else (root / path).resolve()


def relative(root: Path, path: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def write_reports(payload: dict[str, Any], json_path: Path, markdown_path: Path) -> None:
    json_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Figure Evidence Gate",
        "",
        f"- Verdict: **{payload['verdict']}**",
        f"- Manifest: `{payload['manifest']}`",
        "",
        "| Level | Figure | Code | Message | Evidence |",
        "|---|---|---|---|---|",
    ]
    if payload["findings"]:
        for item in payload["findings"]:
            cells = [str(item.get(key, "")).replace("|", "\\|").replace("\n", " ") for key in ("level", "figure_id", "code", "message", "evidence")]
            lines.append("| " + " | ".join(cells) + " |")
    else:
        lines.append("| INFO | - | complete | no findings | - |")
    markdown_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--manifest", default="planning/figure_evidence.json")
    parser.add_argument("--write-json", default="checks/figure_evidence_report.json")
    parser.add_argument("--write-report", default="checks/figure_evidence_report.md")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    root = Path(args.root).resolve()
    payload = FigureEvidenceGate(root, resolve(root, args.manifest)).run()
    write_reports(payload, resolve(root, args.write_json), resolve(root, args.write_report))
    print(f"VERDICT: {payload['verdict']}")
    print(json.dumps(payload["metrics"], ensure_ascii=False))
    return 1 if payload["verdict"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
