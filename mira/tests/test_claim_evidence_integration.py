from __future__ import annotations

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

EVIDENCE_SCRIPT = SKILL_ROOT / "scripts" / "evidence_planner.py"
STORYBOARD_SCRIPT = SKILL_ROOT / "scripts" / "figure_storyboard.py"
PLOT_SCRIPT = SKILL_ROOT / "scripts" / "plot_claim_figure.py"
CLAIM_ID = "CLM-Q1-BOUND"


class ClaimEvidenceIntegrationTests(unittest.TestCase):
    def write_ledger(self, root: Path, *, supporting: bool = False) -> None:
        entries = [
            {
                "key": "q1.bound",
                "claim_id": CLAIM_ID,
                "question": "Q1",
                "centrality": "central",
                "claim_type": "bound",
                "mechanism": "The active constraint determines the bound.",
                "evidence": ["results/tables/bound.csv"],
                "decision_implication": "Use the audited bound as the ceiling.",
            }
        ]
        if supporting:
            entries.append(
                {
                    "key": "q1.samples",
                    "claim_id": "CLM-Q1-SAMPLES",
                    "question": "Q1",
                    "centrality": "supporting",
                }
            )
        path = root / "planning" / "result_ledger.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"schema_version": 2, "entries": entries}), encoding="utf-8")

    def base_item(self, form: str, artifact: str, source_data: str, backend: str = "none") -> dict:
        return {
            "item_id": "EVD-001",
            "claim_id": CLAIM_ID,
            "claim_key": "q1.bound",
            "question": "Q1",
            "role": "result",
            "reader_question": "Why should the reader accept the bound?",
            "chosen_evidence_form": form,
            "alternatives_considered": ["figure" if form != "figure" else "table"],
            "intended_inference": "The audited value is the active feasible ceiling.",
            "backend": backend,
            "backend_rationale": "This form exposes the decisive evidence directly.",
            "provenance": {
                "source_data": source_data,
                "script": "not_applicable",
                "output": artifact,
            },
            "artifact": artifact,
            "caption": "Audited evidence for the active bound.",
            "paper_location": "Section 3.2",
            "waiver": {"applies": False, "reason": "", "scope": "", "evidence": []},
        }

    def run_evidence(self, root: Path, items: list[dict]) -> tuple[subprocess.CompletedProcess[str], dict]:
        self.write_ledger(root)
        storyboard = root / "planning" / "figure_storyboard.json"
        storyboard.write_text(json.dumps({"schema_version": 2, "items": items}), encoding="utf-8")
        result = subprocess.run(
            [
                sys.executable,
                str(EVIDENCE_SCRIPT),
                "--root",
                str(root),
                "--check",
                "--output-level",
                "contest_final",
                "--write-json",
                "planning/evidence_plan.json",
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        payload = json.loads((root / "planning" / "evidence_plan.json").read_text(encoding="utf-8"))
        return result, payload

    def prepare_matlab_figure(self, root: Path) -> dict:
        files = {
            "figures/matlab_bound.png": b"png",
            "figures/matlab_bound.pdf": b"pdf",
        }
        for relative, content in files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
        data = root / "results" / "figures_data"
        data.mkdir(parents=True, exist_ok=True)
        (data / "matlab_bound.csv").write_text("x,y\n1,2\n", encoding="utf-8")
        (data / "matlab_bound_summary.json").write_text(
            json.dumps({"claim_id": CLAIM_ID, "backend": "MATLAB R2025a"}),
            encoding="utf-8",
        )
        source = root / "code" / "matlab" / "plot_bound.m"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("disp('ok');\n", encoding="utf-8")
        item = self.base_item(
            "figure",
            "figures/matlab_bound.pdf",
            "results/figures_data/matlab_bound.csv",
            backend="matlab",
        )
        item["provenance"]["script"] = "code/matlab/plot_bound.m"
        return item

    def write_matlab_execution_record(self, root: Path, transport: str) -> None:
        log = root / "results" / "logs" / "matlab.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        log.write_text("MATLAB completed.\n", encoding="utf-8")
        request_details = {"claim_id": CLAIM_ID, "task": "render claim figure"}
        if transport == "mcp":
            request_id = "mcp-claim-bound-001"
            source = root / "code" / "matlab" / "plot_bound.m"
            runner = root / "code" / "matlab" / "mira_bound_mcp_runner.m"
            runner.write_text(
                f"fprintf('MIRA_MCP_REQUEST_ID={request_id}\\n');\n",
                encoding="utf-8",
            )
            parameters = root / "results" / "figures_data" / "matlab_bound_parameters.json"
            parameters.write_text("{}\n", encoding="utf-8")
            request_path = root / "results" / "logs" / "matlab_mcp_request.json"
            request = {
                "schema_version": 1,
                "kind": MCP_VISUAL_REQUEST_KIND,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "created_at": "2026-07-28T10:00:00+08:00",
                "source": source.relative_to(root).as_posix(),
                "source_sha256": sha256_file(source),
                "runner": runner.relative_to(root).as_posix(),
                "runner_sha256": sha256_file(runner),
                "parameters": parameters.relative_to(root).as_posix(),
                "parameters_sha256": sha256_file(parameters),
                "request": request_details,
                "visual_request": {"evidence_role": "result"},
                "route": {"backend": "matlab", "library": "matlab"},
                "tool_arguments": {"script_path": str(runner.resolve())},
                "expected_outputs": [
                    "figures/matlab_bound.pdf",
                    "figures/matlab_bound.png",
                ],
            }
            request_path.write_text(json.dumps(request), encoding="utf-8")
            response_path = root / "results" / "logs" / "matlab_mcp_response.json"
            response = {
                "schema_version": 1,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:01+08:00",
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                f"MIRA_MCP_REQUEST_ID={request_id}\n"
                                "MIRA_MATLAB_FIGURE_OK=figures/matlab_bound.pdf"
                            ),
                        }
                    ]
                },
            }
            response_path.write_text(json.dumps(response), encoding="utf-8")
            receipt_path = root / "results" / "logs" / "matlab_mcp_receipt.json"
            receipt = {
                "schema_version": 1,
                "backend": "matlab",
                "transport": "mcp",
                "server": "matlab",
                "tool_name": MCP_RUN_FILE_TOOL,
                "request_id": request_id,
                "executed": True,
                "status": "ok",
                "matlab_version": "R2025a",
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:01+08:00",
                "source": "code/matlab/plot_bound.m",
                "request": request_details,
                "response_summary": "MATLAB completed and saved the claim figure.",
                "log_files": ["results/logs/matlab.log"],
                "evidence": [
                    request_path.relative_to(root).as_posix(),
                    response_path.relative_to(root).as_posix(),
                    "results/figures_data/matlab_bound_summary.json",
                ],
                "outputs": ["figures/matlab_bound.pdf", "figures/matlab_bound.png"],
                "request_file": request_path.relative_to(root).as_posix(),
                "request_sha256": sha256_file(request_path),
                "response_file": response_path.relative_to(root).as_posix(),
                "response_sha256": sha256_file(response_path),
            }
            receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
            record = register_mcp_execution(root, receipt_path, receipt)
        else:
            record = {
                "schema_version": 3,
                "backend": "matlab",
                "transport": "batch",
                "execution_context": "unattended",
                "installed": True,
                "executed": True,
                "status": "ok",
                "matlab_version": "R2025a",
                "source": "code/matlab/plot_bound.m",
                "request": request_details,
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:01+08:00",
                "duration_seconds": 1.0,
                "log_files": ["results/logs/matlab.log"],
                "evidence": ["results/figures_data/matlab_bound_summary.json"],
                "outputs": ["figures/matlab_bound.pdf", "figures/matlab_bound.png"],
                "executable": "matlab",
                "returncode": 0,
                "command_or_tool": {
                    "kind": "command",
                    "argv": ["matlab", "-batch", "plot_bound"],
                },
            }
        path = root / "results" / "logs" / "matlab_visual_capability.json"
        path.write_text(json.dumps(record), encoding="utf-8")

    def test_proof_table_and_no_visual_waiver_can_cover_a_claim(self) -> None:
        for form in ("proof", "table", "no_visual_waiver"):
            with self.subTest(form=form), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                paper = root / "paper" / "main.tex"
                table = root / "results" / "tables" / "bound.csv"
                paper.parent.mkdir(parents=True, exist_ok=True)
                table.parent.mkdir(parents=True, exist_ok=True)
                paper.write_text("proof", encoding="utf-8")
                table.write_text("bound\n12.5\n", encoding="utf-8")
                if form == "proof":
                    item = self.base_item(form, "paper/main.tex#proof", "paper/main.tex#proof")
                    item["caption"] = ""
                elif form == "table":
                    item = self.base_item(form, "results/tables/bound.csv", "results/tables/bound.csv")
                else:
                    item = self.base_item(form, "TBD", "TBD")
                    item["caption"] = ""
                    item["waiver"] = {
                        "applies": True,
                        "reason": "The exact proof is clearer than an additional visual.",
                        "scope": "Only this exact bound claim.",
                        "evidence": ["paper/main.tex#proof"],
                    }
                result, payload = self.run_evidence(root, [item])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(payload["verdict"], "PASS")

    def test_missing_and_question_misbound_claims_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result, payload = self.run_evidence(Path(temp_dir), [])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["metrics"]["missing"], 1)
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "paper" / "main.tex"
            proof.parent.mkdir(parents=True, exist_ok=True)
            proof.write_text("proof", encoding="utf-8")
            item = self.base_item("proof", "paper/main.tex", "paper/main.tex")
            item["question"] = "Q2"
            result, payload = self.run_evidence(root, [item])
            self.assertEqual(result.returncode, 1)
            self.assertGreater(payload["metrics"]["misbound"], 0)

    def test_duplicate_evidence_and_supporting_claim_binding_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "paper" / "main.tex"
            proof.parent.mkdir(parents=True, exist_ok=True)
            proof.write_text("proof", encoding="utf-8")
            first = self.base_item("proof", "paper/main.tex", "paper/main.tex")
            second = dict(first)
            second["item_id"] = "EVD-002"
            result, payload = self.run_evidence(root, [first, second])
            self.assertEqual(result.returncode, 1)
            self.assertEqual(payload["metrics"]["redundant"], 1)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_ledger(root, supporting=True)
            proof = root / "paper" / "main.tex"
            proof.parent.mkdir(parents=True, exist_ok=True)
            proof.write_text("proof", encoding="utf-8")
            item = self.base_item("proof", "paper/main.tex", "paper/main.tex")
            item["claim_id"] = "CLM-Q1-SAMPLES"
            storyboard = root / "planning" / "figure_storyboard.json"
            storyboard.write_text(json.dumps({"items": [item]}), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(EVIDENCE_SCRIPT), "--root", str(root), "--check", "--output-level", "contest_final", "--write-json", "planning/evidence_plan.json"],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            payload = json.loads((root / "planning" / "evidence_plan.json").read_text(encoding="utf-8"))
            self.assertEqual(result.returncode, 1)
            self.assertGreater(payload["metrics"]["misbound"], 0)

    def test_python_render_with_matching_claim_summary_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [sys.executable, str(PLOT_SCRIPT), "--root", str(root), "--demo", "--prefix", "claim_bound", "--claim-id", CLAIM_ID],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            item = self.base_item(
                "figure",
                "figures/claim_bound.pdf",
                "results/figures_data/claim_bound.csv",
                backend="python",
            )
            item["provenance"]["script"] = str(PLOT_SCRIPT)
            result, payload = self.run_evidence(root, [item])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verdict"], "PASS")

    def test_matlab_figure_requires_valid_successful_execution_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            item = self.prepare_matlab_figure(root)
            result, payload = self.run_evidence(root, [item])
            self.assertEqual(result.returncode, 1)
            backend_failures = [finding for finding in payload["findings"] if finding["axis"] == "backend"]
            self.assertTrue(backend_failures)
            self.assertIn("MCP or batch execution record", backend_failures[0]["message"])

    def test_matlab_figure_accepts_valid_mcp_or_batch_execution_record(self) -> None:
        for transport in ("mcp", "batch"):
            with self.subTest(transport=transport), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                item = self.prepare_matlab_figure(root)
                self.write_matlab_execution_record(root, transport)
                result, payload = self.run_evidence(root, [item])
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                self.assertEqual(payload["verdict"], "PASS")

    def test_storyboard_is_claim_driven_and_preserves_manual_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_ledger(root, supporting=True)
            existing = {
                "items": [
                    {
                        "claim_id": CLAIM_ID,
                        "item_id": "MANUAL-1",
                        "chosen_evidence_form": "table",
                        "intended_inference": "Manual inference survives refresh.",
                        "alternatives_considered": ["figure"],
                    }
                ]
            }
            storyboard_path = root / "planning" / "figure_storyboard.json"
            storyboard_path.write_text(json.dumps(existing), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STORYBOARD_SCRIPT), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(storyboard_path.read_text(encoding="utf-8"))
            self.assertEqual(payload["mode"], "central_claim")
            self.assertEqual(len(payload["items"]), 1)
            self.assertEqual(payload["items"][0]["item_id"], "MANUAL-1")
            self.assertEqual(payload["items"][0]["intended_inference"], "Manual inference survives refresh.")

    def test_storyboard_imports_all_claim_matched_figure_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_ledger(root)
            evidence = {
                "figures": [
                    {
                        "figure_id": "FIG-Q1-01",
                        "claim_id": CLAIM_ID,
                        "evidence_role": "validation",
                        "reader_question": "Does the bound survive the full scan?",
                        "expected_inference": "The full scan confirms the active bound.",
                        "data_source": "results/figures_data/q1_scan.csv",
                        "backend": "python/matplotlib",
                        "backend_reason": "The evidence is a two-dimensional residual scan.",
                        "source_file": "code/python/plot_q1.py",
                        "log_file": "results/logs/q1.log",
                        "vector_file": "figures/q1_scan.pdf",
                        "png_file": "figures/q1_scan.png",
                        "prelude": "Inspect the complete domain before accepting the bound.",
                        "conclusion": "No larger feasible point was found in the certified domain.",
                        "paper_section": "Section 3.2",
                        "layout": "single",
                        "legend_strategy": "Neutral scan with one highlighted active point.",
                    },
                    {
                        "figure_id": "FIG-Q1-02",
                        "claim_id": CLAIM_ID,
                        "evidence_role": "zoom",
                        "reader_question": "Is the local crossing resolved?",
                        "expected_inference": "The refined crossing agrees with the reported bound.",
                        "data_source": "results/figures_data/q1_zoom.csv",
                        "backend": "MATLAB R2025a",
                        "backend_reason": "MATLAB overlays the refined candidates.",
                        "source_file": "code/matlab/plot_q1.m",
                        "log_file": "results/logs/q1_matlab.log",
                        "vector_file": "figures/q1_zoom.pdf",
                        "png_file": "figures/q1_zoom.png",
                        "prelude": "Magnify the crossing hidden in the global scan.",
                        "conclusion": "The local residual changes sign at the reported value.",
                        "paper_section": "Section 3.2",
                        "layout": "single",
                        "legend_strategy": "Use distinct line styles for the bracket endpoints.",
                    },
                ]
            }
            evidence_path = root / "planning" / "figure_evidence.json"
            evidence_path.write_text(json.dumps(evidence), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(STORYBOARD_SCRIPT), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads((root / "planning" / "figure_storyboard.json").read_text(encoding="utf-8"))
            self.assertEqual(len(payload["items"]), 2)
            by_id = {item["evidence_id"]: item for item in payload["items"]}
            self.assertEqual(by_id["FIG-Q1-01"]["chosen_evidence_form"], "figure")
            self.assertEqual(by_id["FIG-Q1-01"]["role"], "validate")
            self.assertEqual(by_id["FIG-Q1-01"]["provenance"]["source_data"], "results/figures_data/q1_scan.csv")
            self.assertEqual(by_id["FIG-Q1-02"]["backend"], "MATLAB R2025a")
            self.assertEqual(by_id["FIG-Q1-02"]["prelude"], "Magnify the crossing hidden in the global scan.")
            self.assertEqual(by_id["FIG-Q1-02"]["layout"], "single")

    def test_storyboard_keeps_manual_decision_while_adding_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_ledger(root)
            storyboard = root / "planning" / "figure_storyboard.json"
            storyboard.write_text(
                json.dumps({"items": [{
                    "item_id": "MANUAL-TABLE",
                    "claim_id": CLAIM_ID,
                    "chosen_evidence_form": "table",
                    "intended_inference": "The exact table remains the primary evidence.",
                }]}),
                encoding="utf-8",
            )
            (root / "planning" / "figure_evidence.json").write_text(
                json.dumps({"figures": [{
                    "figure_id": "FIG-Q1-01",
                    "claim_id": CLAIM_ID,
                    "expected_inference": "The plot provides supporting context.",
                    "vector_file": "figures/q1.pdf",
                }]}),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(STORYBOARD_SCRIPT), "--root", str(root)],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(storyboard.read_text(encoding="utf-8"))
            self.assertEqual(len(payload["items"]), 2)
            manual = next(item for item in payload["items"] if item["item_id"] == "MANUAL-TABLE")
            self.assertEqual(manual["chosen_evidence_form"], "table")
            self.assertEqual(manual["intended_inference"], "The exact table remains the primary evidence.")

    def test_generated_item_id_is_used_consistently_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            proof = root / "paper" / "main.tex"
            proof.parent.mkdir(parents=True, exist_ok=True)
            proof.write_text("proof", encoding="utf-8")
            item = self.base_item("proof", "paper/main.tex", "paper/main.tex")
            item.pop("item_id")
            result, payload = self.run_evidence(root, [item])
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["items"][0]["item_ids"], ["item-1"])


if __name__ == "__main__":
    unittest.main()
