#!/usr/bin/env python3
"""Build, render, audit, and close Mira's canonical contest-final artifact."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from contest_final_audit import ContestFinalAuditor, write_report
from delivery_contract import (
    CANONICAL_PDF,
    CANONICAL_SOURCE,
    DeliveryContractError,
    begin_batch,
    canonical_pdf,
    canonical_source,
    record_audit,
    record_build,
    record_pdf,
    record_supplemental_evidence,
    relative,
    write_manifest,
)
from workflow_stages import normalize_stage_path


SCRIPT_DIR = Path(__file__).resolve().parent
BUILD_REL = "output/contest_final/build"
RENDER_REL = "output/contest_final/rendered"
BUILD_LOG_REL = "output/contest_final/build.log"
REPORT_JSON_REL = "checks/final_delivery_report.json"
REPORT_MD_REL = "checks/final_delivery_report.md"
TEX_TOOL_COMMANDS: dict[str, tuple[str, ...]] = {
    "latexmk": ("-v",),
    "xelatex": ("--version",),
    "bibtex": ("--version",),
}
# Portable defaults; set MIRA_TEX_BIN to your own TeX bin dir when it is not on PATH.
DEFAULT_TEX_BIN_CANDIDATES = (
    Path(r"C:\texlive\2024\bin\windows"),
    Path(r"C:\texlive\bin\windows"),
    Path("/usr/local/texlive/2024/bin/x86_64-linux"),
    Path("/Library/TeX/texbin"),
)
POPPLER_VERSION_ARGS = ("-v",)


COMPONENT_GATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "abstract_layout_audit.py",
        (
            "--paper",
            CANONICAL_SOURCE,
            "--write-report",
            "checks/abstract_layout_report.md",
            "--write-json",
            "checks/abstract_layout_report.json",
        ),
    ),
    (
        "table_style_audit.py",
        (
            "--paper",
            CANONICAL_SOURCE,
            "--write-report",
            "checks/table_style_report.md",
            "--write-json",
            "checks/table_style_report.json",
        ),
    ),
    (
        "flowchart_diagram_gate.py",
        (
            "--paper",
            CANONICAL_SOURCE,
            "--write-report",
            "checks/flowchart_diagram_report.md",
            "--write-json",
            "checks/flowchart_diagram_report.json",
        ),
    ),
    (
        "structured_flowchart_gate.py",
        (
            "--write-report",
            "checks/structured_flowchart_gate.md",
            "--write-json",
            "checks/structured_flowchart_gate.json",
        ),
    ),
    (
        "visual_render_gate.py",
        (
            "--write-report",
            "checks/visual_render_report.md",
            "--write-json",
            "checks/visual_render_report.json",
        ),
    ),
    (
        "visual_asset_audit.py",
        (
            "--write-report",
            "checks/visual_asset_audit_report.md",
            "--write-json",
            "checks/visual_asset_audit_report.json",
        ),
    ),
    (
        "figure_source_preflight.py",
        (
            "--write-report",
            "checks/figure_source_preflight.md",
            "--write-json",
            "checks/figure_source_preflight.json",
        ),
    ),
    (
        "figure_evidence_gate.py",
        (
            "--manifest",
            "planning/figure_evidence.json",
            "--write-report",
            "checks/figure_evidence_report.md",
            "--write-json",
            "checks/figure_evidence_report.json",
        ),
    ),
    (
        "material_anchor_index.py",
        (
            "--text-dir",
            "materials/extracted",
            "--contract",
            "planning/material_claim_anchors.json",
            "--write-index",
            "checks/material_anchor_index.json",
            "--write-report",
            "checks/material_anchor_report.md",
            "--write-json",
            "checks/material_anchor_report.json",
        ),
    ),
    (
        "statistical_evidence_gate.py",
        (
            "--contract",
            "planning/statistical_evidence.json",
            "--paper",
            CANONICAL_SOURCE,
            "--write-report",
            "checks/statistical_evidence_report.md",
            "--write-json",
            "checks/statistical_evidence_report.json",
        ),
    ),
    (
        "professional_modeling_gate.py",
        (
            "--contract",
            "planning/professional_modeling.json",
            "--write-report",
            "checks/professional_modeling_report.md",
            "--write-json",
            "checks/professional_modeling_report.json",
        ),
    ),
    (
        "result_ledger.py",
        (
            "--confidence-json",
            "checks/result_confidence_report.json",
            "--check",
            "--output-level",
            "contest_final",
            "--write-report",
            "planning/result_ledger.md",
            "--write-json",
            "planning/result_ledger.json",
        ),
    ),
    (
        "reference_authenticity_gate.py",
        (
            "--contract",
            "planning/reference_authenticity.json",
            "--ledger",
            "planning/result_ledger.json",
            "--write-report",
            "checks/reference_authenticity_report.md",
            "--write-json",
            "checks/reference_authenticity_report.json",
        ),
    ),
    (
        "contest_evidence_chain_gate.py",
        (
            "--contract",
            "planning/contest_evidence_chains.json",
            "--ledger",
            "planning/result_ledger.json",
            "--write-report",
            "checks/contest_evidence_chain_report.md",
            "--write-json",
            "checks/contest_evidence_chain_report.json",
        ),
    ),
    (
        "visual_reasoning_audit.py",
        (
            "--paper",
            CANONICAL_SOURCE,
            "--write-report",
            "checks/visual_reasoning_report.md",
            "--write-json",
            "checks/visual_reasoning_report.json",
        ),
    ),
    (
        "check_presentation_strength.py",
        (
            "--main",
            CANONICAL_SOURCE,
            "--pdf",
            CANONICAL_PDF,
            "--output-level",
            "contest_final",
            "--write-report",
            "checks/presentation_strength_report.md",
        ),
    ),
    (
        "check_quality_balance.py",
        (
            "--main",
            CANONICAL_SOURCE,
            "--pdf",
            CANONICAL_PDF,
            "--output-level",
            "contest_final",
            "--write-report",
            "checks/quality_balance_report.md",
        ),
    ),
    (
        "submission_compliance.py",
        (
            "--contract",
            "planning/submission_requirements.json",
            "--write-report",
            "checks/submission_compliance_report.md",
            "--write-json",
            "checks/submission_compliance_report.json",
        ),
    ),
    (
        "mira_state.py",
        (
            "--write",
            "--write-report",
            "planning/mira_state.md",
            "--check",
            "--stage",
            "paper",
            "--allow-built-manifest",
        ),
    ),
)


class ContestFinalPipeline:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = Path(args.root).resolve()
        self.source = canonical_source(self.root)
        self.pdf = canonical_pdf(self.root)
        self.build_dir = self.root / BUILD_REL
        self.render_dir = self.root / RENDER_REL
        self.log_path = self.root / BUILD_LOG_REL
        self.report_json = self.root / REPORT_JSON_REL
        self.report_md = self.root / REPORT_MD_REL
        self.env = build_environment()
        self.toolchain: dict[str, Any] = {}
        self.manifest = begin_batch(self.root)

    def run(self) -> int:
        preflight = self._preflight()
        if preflight:
            self._close_prebuild_failure(preflight)
            return 1
        self._prepare_directories()
        command, result = self._build()
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.log_path.write_text(result.stdout, encoding="utf-8", errors="replace")
        record_build(
            self.root,
            self.manifest,
            command=command,
            returncode=result.returncode,
            log=result.stdout,
            log_path=BUILD_LOG_REL,
            toolchain=self.toolchain,
        )
        if result.returncode != 0:
            self.manifest["audit"] = {
                "batch_id": self.manifest["batch_id"],
                "status": "NOT_RUN",
                "report": REPORT_JSON_REL,
                "blockers": [blocker("latex_build", "XeLaTeX build failed", "paper", "paper", BUILD_LOG_REL)],
            }
            write_manifest(self.root, self.manifest)
            self._write_pipeline_failure("latex_build", "XeLaTeX build failed", BUILD_LOG_REL)
            self._print_summary("FAIL", 1)
            return 1
        built_pdf = self.build_dir / "main.pdf"
        if not built_pdf.is_file():
            self._close_prebuild_failure([blocker("build_output", "latexmk did not produce main.pdf", "paper", "paper", BUILD_REL)])
            return 1
        self.pdf.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.pdf.with_suffix(".pdf.tmp")
        shutil.copy2(built_pdf, temporary)
        temporary.replace(self.pdf)
        record_pdf(self.root, self.manifest)
        record_supplemental_evidence(self.root, self.manifest)
        write_manifest(self.root, self.manifest)
        render_failure = self._render_pages()
        payload = ContestFinalAuditor(self.root, self.render_dir).run()
        if render_failure:
            payload["findings"].append(render_failure)
            payload["blockers"].append(render_failure)
            payload["verdict"] = "FAIL"
        if not self.args.skip_components:
            component_results = self._run_component_gates()
            payload["component_gates"] = component_results
            for item in component_results:
                if item["returncode"] != 0:
                    finding = blocker(
                        f"component:{item['script']}",
                        f"component gate failed: {item['script']}",
                        item["owner_phase"],
                        item["return_to"],
                        item["log"],
                    )
                    payload["findings"].append(finding)
                    payload["blockers"].append(finding)
                    payload["verdict"] = "FAIL"
        normalize_payload_stages(payload)
        write_report(payload, self.report_json, self.report_md)
        record_audit(
            self.root,
            self.manifest,
            verdict=payload["verdict"],
            report=REPORT_JSON_REL,
            blockers=payload["blockers"],
        )
        self._print_summary(payload["verdict"], len(payload["blockers"]))
        return 1 if payload["verdict"] == "FAIL" else 0

    def _preflight(self) -> list[dict[str, Any]]:
        failures: list[dict[str, Any]] = []
        if not self.source.is_file():
            failures.append(blocker("canonical_source", f"missing {CANONICAL_SOURCE}", "paper", "paper", CANONICAL_SOURCE))
        elif self.source.suffix.lower() != ".tex":
            failures.append(blocker("canonical_source", "contest_final source must be .tex", "paper", "paper", CANONICAL_SOURCE))
        for tool in TEX_TOOL_COMMANDS:
            if shutil.which(tool, path=self.env.get("PATH")) is None:
                failures.append(blocker("missing_tool", f"required executable not found: {tool}", "paper", "paper", tool))
        self.toolchain, toolchain_failures = inspect_tex_toolchain(self.env, self.root)
        failures.extend(toolchain_failures)
        poppler, poppler_failures = inspect_poppler_toolchain(self.env, self.root)
        failures.extend(poppler_failures)
        if poppler:
            self.toolchain.setdefault("tools", {})["pdftoppm"] = poppler
        try:
            import pypdf  # noqa: F401
            from PIL import Image  # noqa: F401
        except ImportError as exc:
            failures.append(blocker("missing_python_dependency", str(exc), "paper", "paper", "pypdf/Pillow"))
        return failures

    def _prepare_directories(self) -> None:
        contest_dir = self.root / "output" / "contest_final"
        contest_dir.mkdir(parents=True, exist_ok=True)
        for path in (self.build_dir, self.render_dir):
            resolved = path.resolve()
            if self.root not in resolved.parents:
                raise DeliveryContractError(f"refusing to clear path outside project: {resolved}")
            if resolved.exists():
                shutil.rmtree(resolved)
            resolved.mkdir(parents=True, exist_ok=True)

    def _build(self) -> tuple[list[str], subprocess.CompletedProcess[str]]:
        latexmk = self.toolchain.get("tools", {}).get("latexmk", {}).get("path") or "latexmk"
        command = [
            str(latexmk),
            "-xelatex",
            "-interaction=nonstopmode",
            "-halt-on-error",
            "-file-line-error",
            f"-outdir={self.build_dir}",
            self.source.name,
        ]
        result = subprocess.run(
            command,
            cwd=self.source.parent,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=self.env,
            check=False,
        )
        return command, result

    def _render_pages(self) -> dict[str, Any] | None:
        prefix = self.render_dir / "page"
        executable = self.toolchain.get("tools", {}).get("pdftoppm", {}).get("path")
        if not executable:
            return blocker("page_render_tool", "preflight did not resolve pdftoppm", "paper", "paper", "pdftoppm")
        command = [str(executable), "-png", "-r", str(self.args.render_dpi), str(self.pdf), str(prefix)]
        try:
            result = subprocess.run(
                command,
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=self.env,
                check=False,
            )
        except OSError as exc:
            result = subprocess.CompletedProcess(command, 1, stdout=str(exc))
        log = self.root / "output" / "contest_final" / "render.log"
        log.write_text(result.stdout, encoding="utf-8")
        if result.returncode != 0:
            return blocker("page_render", "pdftoppm page rendering failed", "paper", "paper", relative(self.root, log))
        return None

    def _run_component_gates(self) -> list[dict[str, Any]]:
        logs_dir = self.root / "output" / "contest_final" / "component_logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        results: list[dict[str, Any]] = []
        for script, arguments in COMPONENT_GATES:
            command = [sys.executable, str(SCRIPT_DIR / script), "--root", str(self.root), *arguments]
            run = subprocess.run(
                command,
                cwd=self.root,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            log_path = logs_dir / f"{Path(script).stem}.log"
            log_path.write_text(run.stdout, encoding="utf-8")
            owner, return_to = component_owner(script)
            results.append(
                {
                    "script": script,
                    "returncode": run.returncode,
                    "log": relative(self.root, log_path),
                    "owner_phase": owner,
                    "return_to": return_to,
                }
            )
        return results

    def _close_prebuild_failure(self, failures: list[dict[str, Any]]) -> None:
        self.manifest["build"] = {
            "status": "FAIL",
            "command": [],
            "returncode": 1,
            "log": BUILD_LOG_REL,
            "toolchain": self.toolchain,
        }
        self.manifest["audit"] = {
            "batch_id": self.manifest["batch_id"],
            "status": "NOT_RUN",
            "report": REPORT_JSON_REL,
            "blockers": failures,
        }
        write_manifest(self.root, self.manifest)
        payload = failure_payload(self.root, self.manifest["batch_id"], failures)
        write_report(payload, self.report_json, self.report_md)
        self._print_summary("FAIL", len(failures))

    def _write_pipeline_failure(self, code: str, message: str, evidence: str) -> None:
        failures = [blocker(code, message, "paper", "paper", evidence)]
        payload = failure_payload(self.root, self.manifest["batch_id"], failures)
        write_report(payload, self.report_json, self.report_md)

    def _print_summary(self, verdict: str, blockers_count: int) -> None:
        print(f"VERDICT: {verdict}")
        print(f"status: {self.manifest.get('status', 'DRAFT')}")
        print(f"batch: {self.manifest.get('batch_id', '')}")
        print(f"blockers: {blockers_count}")
        print(f"manifest: {self.root / 'planning' / 'delivery_manifest.json'}")
        print(f"report: {self.report_json}")


def blocker(code: str, message: str, owner: str, return_to: str, evidence: str = "") -> dict[str, Any]:
    owner_stage = public_stage(owner)
    return_stage = public_stage(return_to)
    return {
        "level": "FAIL",
        "code": code,
        "message": message,
        "owner_stage": owner_stage,
        "return_stage": return_stage,
        "owner_phase": owner_stage,
        "return_to": return_stage,
        "evidence": evidence,
    }


def public_stage(value: str) -> str:
    """Normalize legacy audit ownership labels at the public report boundary."""
    return normalize_stage_path(value, "paper")


def normalize_payload_stages(payload: dict[str, Any]) -> None:
    seen: set[int] = set()
    for key in ("findings", "blockers"):
        for item in payload.get(key, []):
            if not isinstance(item, dict) or id(item) in seen:
                continue
            seen.add(id(item))
            owner = public_stage(str(item.get("owner_stage") or item.get("owner_phase") or "paper"))
            return_stage = public_stage(str(item.get("return_stage") or item.get("return_to") or owner))
            item["owner_stage"] = owner
            item["return_stage"] = return_stage
            item["owner_phase"] = owner
            item["return_to"] = return_stage


def build_environment(
    base_env: dict[str, str] | None = None,
    git_executable: str | os.PathLike[str] | None = None,
    tex_bin_candidates: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...] | None = None,
) -> dict[str, str]:
    """Return one environment with one complete TeX suite and Git's Perl when available."""
    env = dict(os.environ if base_env is None else base_env)
    env["PYTHONIOENCODING"] = "utf-8"
    path_value = env.get("PATH", "")
    configured = env.get("MIRA_TEX_BIN", "").strip()
    candidates = list(tex_bin_candidates if tex_bin_candidates is not None else DEFAULT_TEX_BIN_CANDIDATES)
    if configured:
        candidates.insert(0, configured)
    tex_bin = select_complete_tex_bin(candidates)
    if tex_bin is not None:
        path_value = prepend_path(path_value, tex_bin)
        texlive_perl = tex_bin.parent.parent / "tlpkg" / "tlperl" / "bin" / "perl.exe"
        if texlive_perl.is_file():
            path_value = prepend_path(path_value, texlive_perl.parent)
        env["PATH"] = path_value

    if shutil.which("perl", path=path_value) is None:
        git_value = str(git_executable) if git_executable is not None else shutil.which("git", path=path_value)
        if git_value:
            candidate = Path(git_value).resolve().parent.parent / "usr" / "bin" / "perl.exe"
            if candidate.is_file():
                env["PATH"] = prepend_path(path_value, candidate.parent)
    return env


def prepend_path(path_value: str, directory: str | os.PathLike[str]) -> str:
    directory_text = str(Path(directory).resolve())
    entries = [item for item in path_value.split(os.pathsep) if item]
    target = os.path.normcase(os.path.abspath(directory_text))
    remaining = [item for item in entries if os.path.normcase(os.path.abspath(item)) != target]
    return os.pathsep.join((directory_text, *remaining))


def select_complete_tex_bin(candidates: list[str | os.PathLike[str]] | tuple[str | os.PathLike[str], ...]) -> Path | None:
    """Select a directory only when all TeX executables resolve inside it."""
    for raw_candidate in candidates:
        candidate = Path(raw_candidate).expanduser().resolve()
        if not candidate.is_dir():
            continue
        resolved = [shutil.which(tool, path=str(candidate)) for tool in TEX_TOOL_COMMANDS]
        if all(path and Path(path).resolve().parent == candidate for path in resolved):
            return candidate
    return None


def inspect_tex_toolchain(env: dict[str, str], cwd: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Capture exact TeX paths and versions and reject mixed executable roots."""
    tools: dict[str, Any] = {}
    failures: list[dict[str, Any]] = []
    parents: set[Path] = set()
    for tool, version_args in TEX_TOOL_COMMANDS.items():
        executable = shutil.which(tool, path=env.get("PATH"))
        if executable is None:
            continue
        executable_path = Path(executable).resolve()
        parents.add(executable_path.parent)
        entry: dict[str, Any] = {"path": str(executable_path), "version": ""}
        try:
            runtime = subprocess.run(
                [str(executable_path), *version_args],
                cwd=cwd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                timeout=20,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            failures.append(blocker(f"{tool}_runtime", f"{tool} runtime check failed: {exc}", "paper", "paper", str(executable_path)))
        else:
            entry["version"] = next((line.strip() for line in runtime.stdout.splitlines() if line.strip()), "")
            entry["returncode"] = runtime.returncode
            if runtime.returncode != 0:
                failures.append(blocker(f"{tool}_runtime", f"{tool} cannot run: {entry['version'] or 'unknown runtime error'}", "paper", "paper", str(executable_path)))
        tools[tool] = entry
    common_bin = str(next(iter(parents))) if len(parents) == 1 else ""
    evidence = {"common_bin": common_bin, "tools": tools}
    if len(parents) > 1:
        detail = ", ".join(f"{name}={item['path']}" for name, item in tools.items())
        failures.append(blocker("tex_toolchain_mixed", "latexmk, xelatex, and bibtex must come from one TeX bin directory", "paper", "paper", detail))
    return evidence, failures


def select_poppler_executable(path_value: str, configured: str | os.PathLike[str] | None = None) -> Path | None:
    """Resolve Poppler deterministically and never accept MiKTeX's namesake binary."""
    candidates: list[Path] = []
    if configured:
        configured_path = Path(configured).expanduser()
        if configured_path.is_dir():
            found = shutil.which("pdftoppm", path=str(configured_path))
            if found:
                candidates.append(unwrap_bundled_poppler(Path(found).resolve()))
        elif configured_path.is_file():
            candidates.append(unwrap_bundled_poppler(configured_path.resolve()))
    for entry in (item for item in path_value.split(os.pathsep) if item):
        found = shutil.which("pdftoppm", path=entry)
        if found:
            candidate = unwrap_bundled_poppler(Path(found).resolve())
            if candidate not in candidates:
                candidates.append(candidate)

    usable = [candidate for candidate in candidates if "miktex" not in {part.lower() for part in candidate.parts}]
    if not usable:
        return None

    def rank(candidate: Path) -> tuple[int, int]:
        normalized = "/".join(part.lower() for part in candidate.parts)
        if "codex-runtimes/" in normalized and "/dependencies/bin/override/" in normalized:
            priority = 0
        elif "/dependencies/native/poppler/" in normalized:
            priority = 1
        elif "poppler" in normalized:
            priority = 2
        else:
            priority = 3
        return priority, candidates.index(candidate)

    return min(usable, key=rank)


def unwrap_bundled_poppler(candidate: Path) -> Path:
    """Bypass bundled cmd wrappers whose batch expansion corrupts Unicode paths."""
    if candidate.suffix.lower() != ".cmd":
        return candidate
    normalized = "/".join(part.lower() for part in candidate.parts)
    real_candidates: list[Path] = []
    if "/dependencies/bin/override/" in normalized:
        dependencies = candidate.parent.parent.parent
        real_candidates.append(dependencies / "native" / "poppler" / "Library" / "bin" / "pdftoppm.exe")
    if "/dependencies/native/poppler/bin/" in normalized:
        real_candidates.append(candidate.parent.parent / "Library" / "bin" / "pdftoppm.exe")
    return next((path.resolve() for path in real_candidates if path.is_file()), candidate)


def inspect_poppler_toolchain(env: dict[str, str], cwd: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    configured = env.get("MIRA_POPPLER_BIN", "").strip()
    executable = select_poppler_executable(env.get("PATH", ""), configured or None)
    if executable is None:
        path_match = shutil.which("pdftoppm", path=env.get("PATH"))
        if path_match and "miktex" in {part.lower() for part in Path(path_match).resolve().parts}:
            message = "MiKTeX pdftoppm is not an accepted Poppler renderer; bundled/native Poppler is required"
            code = "poppler_miktex_hijack"
            evidence = str(Path(path_match).resolve())
        else:
            message = "required Poppler executable not found: pdftoppm"
            code = "missing_tool"
            evidence = "pdftoppm"
        return {}, [blocker(code, message, "paper", "paper", evidence)]

    entry: dict[str, Any] = {"path": str(executable), "version": ""}
    failures: list[dict[str, Any]] = []
    try:
        runtime = subprocess.run(
            [str(executable), *POPPLER_VERSION_ARGS],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            env=env,
            timeout=20,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        failures.append(blocker("pdftoppm_runtime", f"pdftoppm runtime check failed: {exc}", "paper", "paper", str(executable)))
    else:
        entry["version"] = next((line.strip() for line in runtime.stdout.splitlines() if line.strip()), "")
        entry["returncode"] = runtime.returncode
        if runtime.returncode != 0:
            failures.append(blocker("pdftoppm_runtime", f"pdftoppm cannot run: {entry['version'] or 'unknown runtime error'}", "paper", "paper", str(executable)))
    return entry, failures


def failure_payload(root: Path, batch_id: str, failures: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "generated_at": "",
        "root": str(root),
        "profile": "contest_final",
        "batch_id": batch_id,
        "source": CANONICAL_SOURCE,
        "pdf": CANONICAL_PDF,
        "verdict": "FAIL",
        "metrics": {},
        "findings": failures,
        "blockers": failures,
    }


def component_owner(script: str) -> tuple[str, str]:
    if script == "submission_compliance.py":
        return "paper", "paper"
    if script == "mira_state.py":
        return "paper", "paper"
    if script == "result_ledger.py":
        return "implementation", "implementation"
    if "flowchart" in script or "visual" in script or "figure" in script:
        return "implementation", "implementation"
    if "statistical_evidence" in script:
        return "implementation", "implementation"
    if "material_anchor" in script:
        return "analysis", "analysis"
    if "reference_authenticity" in script:
        return "paper", "paper"
    if "contest_evidence_chain" in script:
        return "paper", "analysis"
    if "professional_modeling" in script:
        return "modeling", "modeling"
    if "abstract" in script or "table" in script or "presentation" in script:
        return "paper", "paper"
    return "paper", "paper"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Contest project root")
    parser.add_argument("--render-dpi", type=int, default=150, help="DPI for page-level audit renders")
    parser.add_argument("--skip-components", action="store_true", help=argparse.SUPPRESS)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        return ContestFinalPipeline(args).run()
    except DeliveryContractError as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
