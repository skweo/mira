from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from matlab_execution_record import (  # noqa: E402
    MCP_RUN_FILE_TOOL,
    MCP_VISUAL_REQUEST_KIND,
    register_mcp_execution,
    sha256_file,
)

SCRIPT = SKILL_ROOT / "scripts" / "release_verification_evidence.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class ReleaseVerificationEvidenceTests(unittest.TestCase):
    def write_json(self, path: Path, payload: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    def create_ready_latex_case(self, workspace: Path) -> tuple[Path, str]:
        project = workspace / "runs" / "case"
        source = project / "paper" / "main.tex"
        pdf = project / "output" / "contest_final" / "paper.pdf"
        build_log = project / "output" / "contest_final" / "build.log"
        for path, content in (
            (source, "\\documentclass{article}\n\\begin{document}ready\\end{document}\n"),
            (pdf, "%PDF-canonical-evidence\n"),
            (build_log, "Latexmk: All targets are up-to-date\nOutput written on main.xdv\n"),
        ):
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        rel = b"paper/main.tex"
        data = source.read_bytes()
        digest = hashlib.sha256()
        digest.update(len(rel).to_bytes(8, "big"))
        digest.update(rel)
        digest.update(len(data).to_bytes(8, "big"))
        digest.update(data)
        batch_id = "20260717T210000-deadbeef"
        self.write_json(
            project / "checks" / "final_delivery_report.json",
            {
                "schema_version": 1,
                "profile": "contest_final",
                "batch_id": batch_id,
                "source": "paper/main.tex",
                "pdf": "output/contest_final/paper.pdf",
                "verdict": "PASS",
                "findings": [],
                "blockers": [],
                "metrics": {"pdf_page_count": 27},
                "component_gates": [],
            },
        )
        self.write_json(
            project / "planning" / "delivery_manifest.json",
            {
                "schema_version": 1,
                "profile": "contest_final",
                "project_root": str(project.resolve()),
                "canonical_source": "paper/main.tex",
                "canonical_pdf": "output/contest_final/paper.pdf",
                "build_engine": "xelatex",
                "status": "READY",
                "batch_id": batch_id,
                "source": {"files": ["paper/main.tex"], "sha256": digest.hexdigest()},
                "pdf": {
                    "sha256": hashlib.sha256(pdf.read_bytes()).hexdigest(),
                    "page_count": 27,
                },
                "build": {
                    "status": "PASS",
                    "command": ["latexmk", "-xelatex", "main.tex"],
                    "returncode": 0,
                    "log": "output/contest_final/build.log",
                    "toolchain": {
                        "tools": {
                            "xelatex": {
                                "path": "xelatex",
                                "version": "XeTeX 3.141592653",
                                "returncode": 0,
                            }
                        }
                    },
                },
                "audit": {
                    "batch_id": batch_id,
                    "status": "PASS",
                    "report": "checks/final_delivery_report.json",
                    "blockers": [],
                },
            },
        )
        return project, batch_id

    def populate_passing_page_audit(self, project: Path) -> None:
        rendered = project / "output" / "contest_final" / "rendered"
        for page in range(1, 28):
            path = rendered / f"page-{page:02d}.png"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(f"png-page-{page}".encode("ascii"))
        component_gates = []
        for script in ("abstract_layout_audit.py", "table_style_audit.py", "mira_state.py"):
            log = project / "output" / "contest_final" / "component_logs" / script.replace(".py", ".log")
            log.parent.mkdir(parents=True, exist_ok=True)
            log.write_text(f"{script}: PASS\n", encoding="utf-8")
            component_gates.append(
                {
                    "script": script,
                    "returncode": 0,
                    "log": log.relative_to(project).as_posix(),
                }
            )
        report_path = project / "checks" / "final_delivery_report.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        report["metrics"] = {
            "pdf_page_count": 27,
            "rendered_page_count": 27,
            "effective_body_pages": 24,
            "abstract_pages": [1],
            "toc_pages": [2],
            "body_start_page": 3,
            "low_information_body_pages": [],
            "blank_rendered_pages": [],
            "edge_clipping_pages": [],
            "colored_heading_page_signals": [],
            "colored_title_heading_signals": [],
            "uses_booktabs": True,
            "markdown_table_rows": 0,
            "naked_math_token_count": 0,
            "unresolved_citations": [],
            "orphan_references": [],
            "unbound_citation_keys": [],
            "citation_binding_errors": [],
        }
        report["component_gates"] = component_gates
        self.write_json(report_path, report)

    def run_verification(
        self, workspace: Path, project: Path, verification_id: str
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        output = workspace / "evidence" / f"{verification_id}.json"
        result = subprocess.run(
            [
                sys.executable,
                "-B",
                str(SCRIPT),
                "--verification-id",
                verification_id,
                "--workspace-root",
                str(workspace),
                "--project-root",
                str(project),
                "--write-json",
                str(output),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        payload = json.loads(output.read_text(encoding="utf-8"))
        return result, payload

    def test_complete_python_render_chain_generates_hashed_pass_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project = workspace / "runs" / "case"
            source = project / "code" / "python" / "generate_python_figures.py"
            log = project / "results" / "logs" / "python_visual_generation.log"
            data = project / "results" / "figures_data" / "claim.csv"
            vector = project / "figures" / "claim.pdf"
            png = project / "figures" / "claim.png"
            for path, content in (
                (source, "print('figure')\n"),
                (log, "PYTHON_VISUAL_STATUS=PASS\nPython 3.12\nMatplotlib 3.10\n"),
                (data, "x,y\n0,1\n"),
                (vector, "%PDF-vector-evidence\n"),
                (png, "png-evidence"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            self.write_json(
                project / "planning" / "figure_evidence.json",
                {
                    "version": 1,
                    "figures": [
                        {
                            "figure_id": "PY-01",
                            "claim_id": "CLM-01",
                            "reader_question": "What does the result show?",
                            "expected_inference": "The mechanism supports the claim.",
                            "data_source": "results/figures_data/claim.csv",
                            "backend": "python/matplotlib",
                            "backend_reason": "A deterministic two-dimensional claim figure.",
                            "source_file": "code/python/generate_python_figures.py",
                            "log_file": "results/logs/python_visual_generation.log",
                            "vector_file": "figures/claim.pdf",
                            "png_file": "figures/claim.png",
                            "prelude": "Read the mechanism before the result.",
                            "conclusion": "The plotted evidence supports CLM-01.",
                            "png_dpi": 300,
                        }
                    ],
                    "waivers": [],
                },
            )
            self.write_json(
                project / "checks" / "figure_evidence_report.json",
                {
                    "schema_version": 1,
                    "verdict": "PASS",
                    "metrics": {
                        "figure_count": 1,
                        "python_figures": 1,
                        "matlab_figures": 0,
                        "failures": 0,
                    },
                    "findings": [],
                },
            )

            result, payload = self.run_verification(workspace, project, "python_render")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "python_render")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["python_figure_count"], 1)
            self.assertEqual(payload["summary"]["minimum_png_dpi"], 300)
            self.assertEqual(payload["findings"], [])
            source_hashes = {item["path"]: item["sha256"] for item in payload["sources"]}
            self.assertEqual(
                source_hashes["runs/case/checks/figure_evidence_report.json"],
                hashlib.sha256(
                    (project / "checks" / "figure_evidence_report.json").read_bytes()
                ).hexdigest().upper(),
            )
            artifact_paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("runs/case/code/python/generate_python_figures.py", artifact_paths)
            self.assertIn("runs/case/results/figures_data/claim.csv", artifact_paths)
            self.assertIn("runs/case/figures/claim.pdf", artifact_paths)
            self.assertIn("runs/case/figures/claim.png", artifact_paths)

    def test_python_render_rejects_failed_gate_and_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project = workspace / "runs" / "case"
            self.write_json(
                project / "planning" / "figure_evidence.json",
                {
                    "version": 1,
                    "figures": [
                        {
                            "figure_id": "PY-01",
                            "claim_id": "CLM-01",
                            "reader_question": "Question",
                            "expected_inference": "Inference",
                            "data_source": "results/figures_data/missing.csv",
                            "backend": "python/matplotlib",
                            "backend_reason": "Reason",
                            "source_file": "code/python/missing.py",
                            "log_file": "results/logs/missing.log",
                            "vector_file": "figures/missing.pdf",
                            "png_file": "figures/missing.png",
                            "prelude": "Prelude",
                            "conclusion": "Conclusion",
                            "png_dpi": 299,
                        }
                    ],
                },
            )
            self.write_json(
                project / "checks" / "figure_evidence_report.json",
                {
                    "schema_version": 1,
                    "verdict": "FAIL",
                    "metrics": {"python_figures": 1, "failures": 1},
                    "findings": [{"level": "FAIL"}],
                },
            )

            result, payload = self.run_verification(workspace, project, "python_render")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("figure_evidence_gate", codes)
            self.assertIn("artifact_missing", codes)
            self.assertIn("png_dpi", codes)

    def test_complete_matlab_render_chain_requires_execution_and_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project = workspace / "runs" / "case"
            source = project / "code" / "matlab" / "generate_matlab_figures.m"
            log = project / "results" / "logs" / "matlab_figures_batch.log"
            data = project / "results" / "figures_data" / "claim.csv"
            vector = project / "figures" / "claim.pdf"
            png = project / "figures" / "claim.png"
            for path, content in (
                (source, "disp('figure');\n"),
                (log, "MATLAB_VISUAL_STATUS=PASS\nMATLAB R2025a\n"),
                (data, "x,y\n0,1\n"),
                (vector, "%PDF-vector-evidence\n"),
                (png, "png-evidence"),
            ):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")

            self.write_json(
                project / "planning" / "figure_evidence.json",
                {
                    "version": 1,
                    "figures": [
                        {
                            "figure_id": "MATLAB-01",
                            "claim_id": "CLM-01",
                            "reader_question": "Where is the certified peak?",
                            "expected_inference": "The refined peak supports CLM-01.",
                            "data_source": "results/figures_data/claim.csv",
                            "backend": "MATLAB R2025a",
                            "backend_reason": "A parameter scan with local refinement.",
                            "source_file": "code/matlab/generate_matlab_figures.m",
                            "log_file": "results/logs/matlab_figures_batch.log",
                            "vector_file": "figures/claim.pdf",
                            "png_file": "figures/claim.png",
                            "prelude": "Read the full scan before the local peak.",
                            "conclusion": "The refined peak is stable.",
                            "png_dpi": 300,
                        }
                    ],
                    "waivers": [],
                },
            )
            self.write_json(
                project / "checks" / "figure_evidence_report.json",
                {
                    "schema_version": 1,
                    "verdict": "PASS",
                    "metrics": {
                        "figure_count": 1,
                        "python_figures": 0,
                        "matlab_figures": 1,
                        "failures": 0,
                    },
                    "findings": [],
                },
            )
            request_id = "mcp-001"
            request_details = {"claim_id": "CLM-01", "task": "render claim figure"}
            runner = project / "code" / "matlab" / "mira_figures_mcp_runner.m"
            runner.write_text(
                f"fprintf('MIRA_MCP_REQUEST_ID={request_id}\\n');\n",
                encoding="utf-8",
            )
            parameters = project / "results" / "figures_data" / "claim_parameters.json"
            parameters.write_text("{}\n", encoding="utf-8")
            request_path = project / "results" / "logs" / "matlab_mcp_request.json"
            request = {
                "schema_version": 1,
                "kind": MCP_VISUAL_REQUEST_KIND,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "created_at": "2026-07-28T10:00:00+08:00",
                "source": source.relative_to(project).as_posix(),
                "source_sha256": sha256_file(source),
                "runner": runner.relative_to(project).as_posix(),
                "runner_sha256": sha256_file(runner),
                "parameters": parameters.relative_to(project).as_posix(),
                "parameters_sha256": sha256_file(parameters),
                "request": request_details,
                "visual_request": {"evidence_role": "validation"},
                "route": {"backend": "matlab", "library": "matlab"},
                "tool_arguments": {"script_path": str(runner.resolve())},
                "expected_outputs": ["figures/claim.png", "figures/claim.pdf"],
            }
            self.write_json(request_path, request)
            response_path = project / "results" / "logs" / "matlab_mcp_response.json"
            response = {
                "schema_version": 1,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:02+08:00",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"MIRA_MCP_REQUEST_ID={request_id}\n"
                                "MIRA_MATLAB_FIGURE_OK=figures/claim.pdf"
                            ),
                        }
                    ]
                },
            }
            self.write_json(response_path, response)
            receipt_path = project / "results" / "logs" / "matlab_mcp_receipt.json"
            receipt = {
                "schema_version": 1,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "executed": True,
                "status": "ok",
                "matlab_version": "25.1.0 (R2025a)",
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:02+08:00",
                "source": "code/matlab/generate_matlab_figures.m",
                "request": request_details,
                "response_summary": "MATLAB completed and saved both declared figures.",
                "log_files": ["results/logs/matlab_figures_batch.log"],
                "evidence": [
                    request_path.relative_to(project).as_posix(),
                    response_path.relative_to(project).as_posix(),
                    "results/figures_data/claim.csv",
                ],
                "outputs": ["figures/claim.png", "figures/claim.pdf"],
                "request_file": request_path.relative_to(project).as_posix(),
                "request_sha256": sha256_file(request_path),
                "response_file": response_path.relative_to(project).as_posix(),
                "response_sha256": sha256_file(response_path),
            }
            self.write_json(receipt_path, receipt)
            execution_record = register_mcp_execution(project, receipt_path, receipt)
            self.write_json(
                project / "results" / "logs" / "matlab_visual_capability.json",
                execution_record,
            )
            self.write_json(
                project / "results" / "figures_data" / "matlab_figures_summary.json",
                {
                    "schema_version": "1.0",
                    "backend": "MATLAB R2025a batch",
                    "matlab_version": "25.1.0 (R2025a)",
                    "figures": [{"figure_id": "MATLAB-01"}],
                    "validation": {
                        "geometry_pass": True,
                        "state_consistency_pass": True,
                        "global_search_pass": True,
                        "local_extremum_pass": True,
                        "status": "PASS",
                    },
                },
            )

            result, payload = self.run_verification(workspace, project, "matlab_render")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "matlab_render")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["matlab_figure_count"], 1)
            self.assertEqual(payload["summary"]["minimum_png_dpi"], 300)
            self.assertTrue(payload["summary"]["executed"] )
            self.assertEqual(payload["summary"]["transport"], "mcp")
            self.assertEqual(payload["summary"]["execution_context"], "interactive")
            self.assertEqual(payload["summary"]["matlab_version"], "25.1.0 (R2025a)")
            self.assertEqual(payload["findings"], [])
            artifact_paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("runs/case/code/matlab/generate_matlab_figures.m", artifact_paths)
            self.assertIn("runs/case/results/logs/matlab_figures_batch.log", artifact_paths)
            self.assertIn("runs/case/results/figures_data/claim.csv", artifact_paths)
            self.assertIn("runs/case/figures/claim.pdf", artifact_paths)
            self.assertIn("runs/case/figures/claim.png", artifact_paths)

    def test_matlab_render_rejects_install_only_failed_validation_and_missing_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project = workspace / "runs" / "case"
            self.write_json(
                project / "planning" / "figure_evidence.json",
                {
                    "version": 1,
                    "figures": [
                        {
                            "figure_id": "MATLAB-01",
                            "claim_id": "CLM-01",
                            "reader_question": "Question",
                            "expected_inference": "Inference",
                            "data_source": "results/figures_data/missing.csv",
                            "backend": "MATLAB R2025a",
                            "backend_reason": "Reason",
                            "source_file": "code/matlab/missing.m",
                            "log_file": "results/logs/missing.log",
                            "vector_file": "figures/missing.pdf",
                            "png_file": "figures/missing.png",
                            "prelude": "Prelude",
                            "conclusion": "Conclusion",
                            "png_dpi": 299,
                        }
                    ],
                },
            )
            self.write_json(
                project / "checks" / "figure_evidence_report.json",
                {
                    "schema_version": 1,
                    "verdict": "PASS",
                    "metrics": {"matlab_figures": 1, "failures": 0},
                    "findings": [],
                },
            )
            self.write_json(
                project / "results" / "logs" / "matlab_visual_capability.json",
                {
                    "schema_version": 3,
                    "backend": "matlab",
                    "transport": "batch",
                    "execution_context": "unattended",
                    "installed": True,
                    "executable": "matlab",
                    "matlab_version": "25.1.0 (R2025a)",
                    "source": "code/matlab/missing.m",
                    "request": {"claim_id": "CLM-01"},
                    "command_or_tool": {
                        "kind": "command",
                        "argv": ["matlab", "-batch", "missing"],
                    },
                    "started_at": "2026-07-28T10:00:00+08:00",
                    "finished_at": "2026-07-28T10:00:01+08:00",
                    "duration_seconds": 1.0,
                    "executed": False,
                    "status": "not_run",
                    "returncode": None,
                    "log_files": ["results/logs/missing.log"],
                    "evidence": ["results/logs/missing.log"],
                    "outputs": ["figures/missing.png", "figures/missing.pdf"],
                },
            )
            self.write_json(
                project / "results" / "figures_data" / "matlab_figures_summary.json",
                {
                    "schema_version": "1.0",
                    "figures": [{"figure_id": "MATLAB-01"}],
                    "validation": {
                        "geometry_pass": True,
                        "state_consistency_pass": True,
                        "global_search_pass": False,
                        "local_extremum_pass": True,
                        "status": "FAIL",
                    },
                },
            )

            result, payload = self.run_verification(workspace, project, "matlab_render")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("matlab_execution", codes)
            self.assertIn("matlab_validation", codes)
            self.assertIn("artifact_missing", codes)
            self.assertIn("png_dpi", codes)

    def test_ready_xelatex_batch_generates_hashed_latex_build_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project, batch_id = self.create_ready_latex_case(workspace)

            result, payload = self.run_verification(workspace, project, "latex_build")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "latex_build")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["batch_id"], batch_id)
            self.assertEqual(payload["summary"]["source_file_count"], 1)
            self.assertEqual(payload["summary"]["build_engine"], "xelatex")
            self.assertEqual(payload["findings"], [])
            artifact_paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("runs/case/paper/main.tex", artifact_paths)
            self.assertIn("runs/case/output/contest_final/paper.pdf", artifact_paths)
            self.assertIn("runs/case/output/contest_final/build.log", artifact_paths)

    def test_latex_build_rejects_stale_hashes_and_fake_pass_findings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project, _ = self.create_ready_latex_case(workspace)
            manifest_path = project / "planning" / "delivery_manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["source"]["sha256"] = "0" * 64
            manifest["pdf"]["sha256"] = "1" * 64
            self.write_json(manifest_path, manifest)
            report_path = project / "checks" / "final_delivery_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["findings"] = [{"level": "FAIL", "code": "newer_blocker"}]
            self.write_json(report_path, report)

            result, payload = self.run_verification(workspace, project, "latex_build")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("source_hash", codes)
            self.assertIn("pdf_hash", codes)
            self.assertIn("audit_batch", codes)

    def test_complete_contest_final_page_audit_generates_hashed_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project, batch_id = self.create_ready_latex_case(workspace)
            self.populate_passing_page_audit(project)

            result, payload = self.run_verification(workspace, project, "page_audit")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "page_audit")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["batch_id"], batch_id)
            self.assertEqual(payload["summary"]["pdf_page_count"], 27)
            self.assertEqual(payload["summary"]["rendered_page_count"], 27)
            self.assertEqual(payload["summary"]["effective_body_pages"], 24)
            self.assertEqual(payload["summary"]["component_gate_count"], 3)
            self.assertEqual(payload["findings"], [])
            artifact_paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("runs/case/output/contest_final/paper.pdf", artifact_paths)
            self.assertIn("runs/case/output/contest_final/rendered/page-01.png", artifact_paths)
            self.assertIn("runs/case/output/contest_final/rendered/page-27.png", artifact_paths)
            self.assertIn(
                "runs/case/output/contest_final/component_logs/abstract_layout_audit.log",
                artifact_paths,
            )

    def test_page_audit_rejects_missing_page_bad_length_naked_math_and_failed_component(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            project, _ = self.create_ready_latex_case(workspace)
            self.populate_passing_page_audit(project)
            (project / "output" / "contest_final" / "rendered" / "page-13.png").unlink()
            report_path = project / "checks" / "final_delivery_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["metrics"]["effective_body_pages"] = 15
            report["metrics"]["naked_math_token_count"] = 2
            report["component_gates"][0]["returncode"] = 1
            self.write_json(report_path, report)

            result, payload = self.run_verification(workspace, project, "page_audit")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("effective_body_pages", codes)
            self.assertIn("typesetting_contract", codes)
            self.assertIn("rendered_pages", codes)
            self.assertIn("component_gate", codes)

    def test_current_clean_compaction_audit_generates_hashed_pass_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            (skill_root / "references").mkdir(parents=True)
            (skill_root / "scripts").mkdir(parents=True)
            (skill_root / "checks").mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "# Mira\n\nCurrent baseline: **Mira 0.10.0**.\n",
                encoding="utf-8",
            )
            (skill_root / "references" / "skill-compaction-control-rules.md").write_text(
                "# Compaction rules\n",
                encoding="utf-8",
            )
            report_path = skill_root / "checks" / "mira_skill_compaction_pre_release.json"
            self.write_json(
                report_path,
                {
                    "generated_at": "2026-07-17T21:30:00",
                    "skill_root": str(skill_root.resolve()),
                    "verdict": "PASS_WITH_WARNINGS",
                    "metrics": {
                        "skill_md_exists": True,
                        "skill_lines": 3,
                        "unmentioned_scripts": [],
                        "stale_version_route_hits": [],
                        "has_skill_compaction_rules": True,
                    },
                    "findings": [
                        {
                            "level": "WARN",
                            "axis": "reference_count",
                            "message": "References remain phase-routed.",
                        }
                    ],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "compaction_audit")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "compaction_audit")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["audit_verdict"], "PASS_WITH_WARNINGS")
            self.assertEqual(payload["summary"]["skill_lines"], 3)
            self.assertEqual(payload["summary"]["warning_count"], 1)
            self.assertEqual(payload["findings"], [])
            source_paths = {item["path"] for item in payload["sources"]}
            self.assertIn(
                ".codex/skills/mira/checks/mira_skill_compaction_pre_release.json",
                source_paths,
            )
            self.assertIn(".codex/skills/mira/SKILL.md", source_paths)
            self.assertIn(
                ".codex/skills/mira/references/skill-compaction-control-rules.md",
                source_paths,
            )

    def test_compaction_audit_rejects_forged_line_metric(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            (skill_root / "references").mkdir(parents=True)
            (skill_root / "scripts").mkdir(parents=True)
            (skill_root / "checks").mkdir(parents=True)
            (skill_root / "SKILL.md").write_text(
                "\n".join(f"control line {index}" for index in range(501)) + "\n",
                encoding="utf-8",
            )
            (skill_root / "references" / "skill-compaction-control-rules.md").write_text(
                "# Compaction rules\n",
                encoding="utf-8",
            )
            self.write_json(
                skill_root / "checks" / "mira_skill_compaction_pre_release.json",
                {
                    "generated_at": "2026-07-17T21:35:00",
                    "skill_root": str(skill_root.resolve()),
                    "verdict": "PASS",
                    "metrics": {
                        "skill_md_exists": True,
                        "skill_lines": 3,
                        "unmentioned_scripts": [],
                        "stale_version_route_hits": [],
                        "has_skill_compaction_rules": True,
                    },
                    "findings": [],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "compaction_audit")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("skill_line_mismatch", codes)
            self.assertIn("skill_size", codes)

    def test_complete_historical_registry_generates_hashed_pass_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            archive = workspace / "archive" / "mira-projects" / "case"
            for relative_path, content in (
                ("paper/main.pdf", "%PDF-historical\n"),
                ("results/result_report.md", "# Result report\n"),
                ("checks/artifact_manifest.json", "{}\n"),
                ("planning/result_ledger.json", "{}\n"),
            ):
                path = archive / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            registry_path = skill_root / "benchmarks" / "registry.json"
            self.write_json(
                registry_path,
                {
                    "schema_version": 2,
                    "release": "0.10.0",
                    "archive_root": "archive/mira-projects",
                    "candidate_release": "0.11.0",
                    "candidate_release_status": "BLOCKED",
                    "projects": [
                        {
                            "id": "case",
                            "competition": "CUMCM",
                            "year": 2024,
                            "problem": "A",
                            "mira_version": "0.10.0",
                            "type": "full_regression",
                            "verdict": "PASS",
                            "final_artifact": "paper/main.pdf",
                            "archive_path": "archive/mira-projects/case",
                            "retention": "canonical_full_case",
                            "canonical_summary": {
                                "status": "PRESERVED",
                                "text": "A canonical archived contest-paper regression.",
                                "evidence": ["results/result_report.md"],
                            },
                            "run_manifest": {
                                "status": "PRESERVED",
                                "evidence": ["checks/artifact_manifest.json"],
                            },
                            "key_results": {
                                "status": "PRESERVED",
                                "items": ["Canonical numerical claims remain in the result ledger."],
                                "evidence": ["planning/result_ledger.json"],
                            },
                            "final_decision": {
                                "status": "PRESERVED",
                                "verdict": "PASS",
                                "basis": "The archived historical verdict is retained without recomputation.",
                                "evidence": ["paper/main.pdf"],
                            },
                        }
                    ],
                    "comparisons": [],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "historical_registry")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verification_id"], "historical_registry")
            self.assertEqual(payload["status"], "PASS")
            self.assertEqual(payload["summary"]["project_count"], 1)
            self.assertEqual(payload["summary"]["comparison_count"], 0)
            self.assertEqual(payload["summary"]["not_available_section_count"], 0)
            self.assertEqual(payload["findings"], [])
            artifact_paths = {item["path"] for item in payload["artifacts"]}
            self.assertIn("archive/mira-projects/case/paper/main.pdf", artifact_paths)
            self.assertIn("archive/mira-projects/case/planning/result_ledger.json", artifact_paths)

    def test_historical_registry_accepts_user_release_with_deferred_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            archive = workspace / "archive" / "mira-projects" / "case"
            for relative_path, content in (
                ("paper/main.pdf", "%PDF-historical\n"),
                ("results/result_report.md", "# Result report\n"),
                ("checks/artifact_manifest.json", "{}\n"),
                ("planning/result_ledger.json", "{}\n"),
            ):
                path = archive / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            self.write_json(
                skill_root / "benchmarks" / "registry.json",
                {
                    "schema_version": 2,
                    "release": "0.11.0",
                    "archive_root": "archive/mira-projects",
                    "candidate_release": "0.11.0",
                    "candidate_release_status": "RELEASED",
                    "projects": [
                        {
                            "id": "case",
                            "verdict": "PASS",
                            "final_artifact": "paper/main.pdf",
                            "archive_path": "archive/mira-projects/case",
                            "canonical_summary": {
                                "status": "PRESERVED",
                                "text": "The archived case remains preserved.",
                                "evidence": ["results/result_report.md"],
                            },
                            "run_manifest": {
                                "status": "PRESERVED",
                                "evidence": ["checks/artifact_manifest.json"],
                            },
                            "key_results": {
                                "status": "PRESERVED",
                                "items": ["The canonical numerical claims remain preserved."],
                                "evidence": ["planning/result_ledger.json"],
                            },
                            "final_decision": {
                                "status": "PRESERVED",
                                "verdict": "PASS",
                                "basis": "The archived verdict remains unchanged.",
                                "evidence": ["paper/main.pdf"],
                            },
                        }
                    ],
                    "comparisons": [],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "historical_registry")

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["status"], "PASS")

    def test_historical_registry_rejects_unknown_release_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            self.write_json(
                skill_root / "benchmarks" / "registry.json",
                {
                    "schema_version": 2,
                    "archive_root": "archive/mira-projects",
                    "candidate_release_status": "RELEASED_WITH_DEFERRED_VALIDATION",
                    "projects": [],
                    "comparisons": [],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "historical_registry")

            self.assertNotEqual(result.returncode, 0)
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("candidate_release_status", codes)

    def test_historical_registry_rejects_escaped_evidence_missing_final_and_changed_verdict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            skill_root = workspace / ".codex" / "skills" / "mira"
            archive = workspace / "archive" / "mira-projects" / "case"
            for relative_path, content in (
                ("results/result_report.md", "# Result report\n"),
                ("checks/artifact_manifest.json", "{}\n"),
                ("planning/result_ledger.json", "{}\n"),
            ):
                path = archive / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content, encoding="utf-8")
            self.write_json(
                skill_root / "benchmarks" / "registry.json",
                {
                    "schema_version": 2,
                    "release": "0.10.0",
                    "archive_root": "archive/mira-projects",
                    "candidate_release": "0.11.0",
                    "candidate_release_status": "BLOCKED",
                    "projects": [
                        {
                            "id": "case",
                            "verdict": "PASS_WITH_WARNINGS",
                            "final_artifact": "paper/missing.pdf",
                            "archive_path": "archive/mira-projects/case",
                            "canonical_summary": {
                                "status": "PRESERVED",
                                "text": "Archived evidence must remain inside its project root.",
                                "evidence": ["../../../outside.txt"],
                            },
                            "run_manifest": {
                                "status": "PRESERVED",
                                "evidence": ["checks/artifact_manifest.json"],
                            },
                            "key_results": {
                                "status": "PRESERVED",
                                "items": ["The historical result ledger is retained."],
                                "evidence": ["planning/result_ledger.json"],
                            },
                            "final_decision": {
                                "status": "PRESERVED",
                                "verdict": "PASS",
                                "basis": "A registry must not rewrite the archived verdict.",
                                "evidence": ["results/result_report.md"],
                            },
                        }
                    ],
                    "comparisons": [],
                },
            )

            result, payload = self.run_verification(workspace, skill_root, "historical_registry")

            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["status"], "FAIL")
            codes = {item["code"] for item in payload["findings"]}
            self.assertIn("evidence_path", codes)
            self.assertIn("final_artifact", codes)
            self.assertIn("decision_verdict", codes)


if __name__ == "__main__":
    unittest.main()
