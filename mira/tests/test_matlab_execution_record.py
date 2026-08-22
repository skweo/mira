from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from matlab_execution_record import (  # noqa: E402
    MCP_RUN_FILE_TOOL,
    MCP_VISUAL_REQUEST_KIND,
    build_execution_record,
    execution_transport,
    register_mcp_execution,
    sha256_file,
    validate_execution_record,
)


class MatlabExecutionRecordTests(unittest.TestCase):
    def write(self, root: Path, relative: str, content: str = "evidence\n") -> Path:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def complete_receipt(self, root: Path) -> tuple[Path, dict]:
        source = self.write(root, "code/matlab/figure.m", "disp('ok');\n")
        runner = self.write(
            root,
            "code/matlab/mira_figure_mcp_runner.m",
            "fprintf('MIRA_MCP_REQUEST_ID=mcp-request-001\\n');\n",
        )
        parameters = self.write(root, "results/figures_data/figure_parameters.json", "{}\n")
        self.write(root, "results/logs/matlab_mcp.log")
        self.write(root, "results/figures_data/figure_provenance.json", "{}\n")
        self.write(root, "figures/figure.pdf", "%PDF evidence\n")
        request_path = root / "results" / "logs" / "matlab_mcp_request.json"
        request = {
            "schema_version": 1,
            "kind": MCP_VISUAL_REQUEST_KIND,
            "backend": "matlab",
            "transport": "mcp",
            "server": "matlab",
            "tool_name": MCP_RUN_FILE_TOOL,
            "request_id": "mcp-request-001",
            "created_at": "2026-07-28T10:00:00+08:00",
            "source": source.relative_to(root).as_posix(),
            "source_sha256": sha256_file(source),
            "runner": runner.relative_to(root).as_posix(),
            "runner_sha256": sha256_file(runner),
            "parameters": parameters.relative_to(root).as_posix(),
            "parameters_sha256": sha256_file(parameters),
            "request": {"claim_id": "CLM-01", "task": "render figure"},
            "visual_request": {"evidence_role": "validation"},
            "route": {"backend": "matlab", "library": "matlab", "route_id": "R07"},
            "tool_arguments": {"script_path": str(runner.resolve())},
            "expected_outputs": ["figures/figure.pdf"],
        }
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(json.dumps(request), encoding="utf-8")
        response_path = root / "results" / "logs" / "matlab_mcp_response.json"
        response = {
            "schema_version": 1,
            "backend": "matlab",
            "transport": "mcp",
            "server": "matlab",
            "tool_name": MCP_RUN_FILE_TOOL,
            "request_id": "mcp-request-001",
            "started_at": "2026-07-28T10:00:00+08:00",
            "finished_at": "2026-07-28T10:00:02+08:00",
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "MIRA_MCP_REQUEST_ID=mcp-request-001\n"
                            "MIRA_MATLAB_FIGURE_OK=figures/figure.pdf"
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
            "request_id": "mcp-request-001",
            "executed": True,
            "status": "ok",
            "matlab_version": "R2025a",
            "started_at": "2026-07-28T10:00:00+08:00",
            "finished_at": "2026-07-28T10:00:02+08:00",
            "source": "code/matlab/figure.m",
            "request": {"claim_id": "CLM-01", "task": "render figure"},
            "response_summary": "MATLAB completed and saved the declared output.",
            "log_files": ["results/logs/matlab_mcp.log"],
            "evidence": [
                request_path.relative_to(root).as_posix(),
                response_path.relative_to(root).as_posix(),
                "results/figures_data/figure_provenance.json",
            ],
            "outputs": ["figures/figure.pdf"],
            "request_file": request_path.relative_to(root).as_posix(),
            "request_sha256": sha256_file(request_path),
            "response_file": response_path.relative_to(root).as_posix(),
            "response_sha256": sha256_file(response_path),
        }
        receipt_path.parent.mkdir(parents=True, exist_ok=True)
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        return receipt_path, receipt

    def test_execution_policy_is_explicit(self) -> None:
        self.assertEqual(execution_transport("interactive"), "mcp")
        self.assertEqual(execution_transport("unattended"), "batch")
        with self.assertRaises(ValueError):
            execution_transport("notebook")

    def test_complete_batch_record_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write(root, "code/matlab/figure.m")
            log = self.write(root, "results/logs/matlab_batch.log")
            evidence = self.write(root, "results/figures_data/provenance.json", "{}\n")
            output = self.write(root, "figures/figure.pdf", "%PDF evidence\n")
            record = build_execution_record(
                transport="batch",
                execution_context="unattended",
                installed=True,
                executable="matlab",
                source=source.relative_to(root).as_posix(),
                request={"task": "render figure"},
                executed=True,
                status="ok",
                matlab_version="R2025a",
                command_or_tool={"kind": "command", "argv": ["matlab", "-batch", "figure"]},
                returncode=0,
                started_at="2026-07-28T10:00:00+08:00",
                finished_at="2026-07-28T10:00:01+08:00",
                duration_seconds=1.0,
                log_files=[log.relative_to(root).as_posix()],
                evidence=[evidence.relative_to(root).as_posix()],
                outputs=[output.relative_to(root).as_posix()],
            )

            self.assertEqual(validate_execution_record(root, record), [])

    def test_complete_mcp_receipt_registers_without_batch_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, receipt = self.complete_receipt(root)

            record = register_mcp_execution(root, receipt_path, receipt)

            self.assertEqual(validate_execution_record(root, record), [])
            self.assertEqual(record["transport"], "mcp")
            self.assertEqual(record["execution_context"], "interactive")
            self.assertNotIn("returncode", record)
            self.assertNotIn("executable", record)

    def test_cli_registers_existing_mcp_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, _ = self.complete_receipt(root)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "matlab_execution_record.py"),
                    "register-mcp",
                    "--root",
                    str(root),
                    "--receipt-json",
                    str(receipt_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(
                (root / "results" / "logs" / "matlab_visual_capability.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(record["command_or_tool"]["request_id"], "mcp-request-001")

    def test_incomplete_mcp_receipt_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, receipt = self.complete_receipt(root)
            receipt.pop("request_id")
            receipt.pop("response_summary")

            with self.assertRaisesRegex(ValueError, "request_id"):
                register_mcp_execution(root, receipt_path, receipt)

    def test_mcp_receipt_with_forged_response_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, receipt = self.complete_receipt(root)
            response_path = root / receipt["response_file"]
            response = json.loads(response_path.read_text(encoding="utf-8"))
            response["request_id"] = "different-request"
            response_path.write_text(json.dumps(response), encoding="utf-8")
            receipt["response_sha256"] = sha256_file(response_path)

            with self.assertRaisesRegex(ValueError, "does not match the request"):
                register_mcp_execution(root, receipt_path, receipt)

    def test_mcp_receipt_with_missing_response_file_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, receipt = self.complete_receipt(root)
            (root / receipt["response_file"]).unlink()

            with self.assertRaisesRegex(ValueError, "response file is missing"):
                register_mcp_execution(root, receipt_path, receipt)

    def test_mcp_receipt_with_missing_declared_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            receipt_path, receipt = self.complete_receipt(root)
            (root / "figures" / "figure.pdf").unlink()

            with self.assertRaisesRegex(ValueError, "output"):
                register_mcp_execution(root, receipt_path, receipt)

    def test_transport_context_mismatch_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = self.write(root, "code/matlab/figure.m")
            log = self.write(root, "results/logs/matlab.log")
            evidence = self.write(root, "results/figures_data/provenance.json", "{}\n")
            output = self.write(root, "figures/figure.pdf", "%PDF evidence\n")
            record = build_execution_record(
                transport="batch",
                execution_context="interactive",
                installed=True,
                executable="matlab",
                source=source.relative_to(root).as_posix(),
                request={"task": "render figure"},
                executed=True,
                status="ok",
                matlab_version="R2025a",
                command_or_tool={"kind": "command", "argv": ["matlab", "-batch", "figure"]},
                returncode=0,
                started_at="2026-07-28T10:00:00+08:00",
                finished_at="2026-07-28T10:00:01+08:00",
                duration_seconds=1.0,
                log_files=[log.relative_to(root).as_posix()],
                evidence=[evidence.relative_to(root).as_posix()],
                outputs=[output.relative_to(root).as_posix()],
            )

            errors = validate_execution_record(root, record)
            self.assertIn("interactive execution must use mcp, not batch", errors)

    def test_non_object_execution_record_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            errors = validate_execution_record(Path(temp_dir), ["not", "an", "object"])
            self.assertEqual(errors, ["execution record must be a JSON object"])


if __name__ == "__main__":
    unittest.main()
