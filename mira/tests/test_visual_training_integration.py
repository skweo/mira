from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from visual_backend_router import route_visual  # noqa: E402
from figure_provenance import canonical_sha256  # noqa: E402
from figure_storyboard import sync_three_d_candidates  # noqa: E402
from visual_opportunity_audit import (  # noqa: E402
    apply_three_d_dispositions,
    audit,
    build_three_d_candidates,
    collect_table_profiles,
)


def skip_matlab_startup_failure(test: unittest.TestCase, result: subprocess.CompletedProcess[str]) -> None:
    output = result.stdout + result.stderr
    startup_errors = (
        "Fatal Startup Error",
        "System Error: File system inconsistency",
        "runtime_bridge_error",
    )
    if result.returncode != 0 and any(marker in output for marker in startup_errors):
        test.skipTest("MATLAB is installed but its batch runtime could not start in this environment")


class StructuredVisualRouterTests(unittest.TestCase):
    def complete_request(self, **overrides: object) -> dict[str, object]:
        request: dict[str, object] = {
            "data_shape": "tidy_long_table",
            "statistical_goal": "compare grouped distributions",
            "evidence_role": "uncertainty",
            "upstream_runtime": "python",
            "provenance_present": True,
            "units_present": True,
            "statistics_explicit": True,
            "offline_reproducible": True,
            "static_evidence_available": True,
            "interaction_required": False,
            "output_contract": ["png_300dpi", "vector_pdf"],
        }
        request.update(overrides)
        return request

    def test_missing_evidence_prerequisite_blocks_routing(self) -> None:
        request = {
            "data_shape": "tidy_long_table",
            "statistical_goal": "compare grouped distributions",
            "evidence_role": "uncertainty",
            "upstream_runtime": "python",
            "provenance_present": False,
            "units_present": True,
            "statistics_explicit": True,
            "offline_reproducible": True,
            "static_evidence_available": True,
            "interaction_required": False,
            "output_contract": ["png_300dpi", "vector_pdf"],
        }

        decision = route_visual(request)

        self.assertEqual(decision["status"], "BLOCKED")
        self.assertEqual(decision["blocking_requirements"], ["provenance_present"])

    def test_tidy_statistical_distribution_routes_to_seaborn(self) -> None:
        decision = route_visual(self.complete_request())

        self.assertEqual(decision["status"], "READY")
        self.assertEqual(decision["visual_form"], "figure")
        self.assertEqual(decision["chart_family"], "distribution")
        self.assertEqual(decision["route_id"], "R01")
        self.assertEqual((decision["backend"], decision["library"]), ("python", "seaborn"))
        self.assertEqual(decision["fallback"], {"backend": "python", "library": "matplotlib"})

    def test_visual_family_is_selected_before_backend_capability(self) -> None:
        fields = {
            "claim": "The response changes smoothly across the two-parameter domain.",
            "intended_inference": "Inspect the scalar field gradient and contour structure.",
            "reader_question": "Where are the high-response regions?",
            "data_shape": "regular_grid",
            "statistical_goal": "scalar field contour",
        }
        verified = route_visual(
            self.complete_request(
                **fields,
                matlab_capability={"executed": True, "record_valid": True},
            )
        )
        unavailable = route_visual(
            self.complete_request(
                **fields,
                matlab_capability={"executed": False, "record_valid": False},
            )
        )

        self.assertEqual(verified["chart_family"], "scalar_field")
        self.assertEqual(unavailable["chart_family"], "scalar_field")
        self.assertEqual(verified["backend"], "matlab")
        self.assertEqual(unavailable["backend"], "python")
        self.assertEqual(verified["route_id"], unavailable["route_id"])

    def test_claim_and_shape_select_time_series_before_python(self) -> None:
        decision = route_visual(
            self.complete_request(
                claim="The estimate converges after the initial transient.",
                intended_inference="Read the convergence trend over time.",
                reader_question="When does the sequence stabilize?",
                data_shape="ordered_sequence",
                statistical_goal="convergence prediction",
            )
        )

        self.assertEqual(decision["chart_family"], "time_series")
        self.assertEqual(decision["route_id"], "R02")
        self.assertEqual((decision["backend"], decision["library"]), ("python", "matplotlib"))

    def test_incomplete_visual_intent_needs_evidence_decision(self) -> None:
        decision = route_visual(
            self.complete_request(data_shape="", statistical_goal="", evidence_role="")
        )

        self.assertEqual(decision["status"], "NEEDS_EVIDENCE_DECISION")
        self.assertEqual(
            decision["blocking_requirements"],
            ["claim_or_intended_inference", "data_shape"],
        )
        self.assertIsNone(decision["backend"])
        self.assertIsNone(decision["library"])

    def test_conflicting_claim_and_data_shape_do_not_default_to_python(self) -> None:
        decision = route_visual(
            self.complete_request(
                claim="The grouped sample distributions differ.",
                intended_inference="Compare grouped distributions and uncertainty spread.",
                reader_question="Which group has the widest distribution?",
                data_shape="regular_grid",
                statistical_goal="compare grouped distributions",
            )
        )

        self.assertEqual(decision["status"], "NEEDS_EVIDENCE_DECISION")
        self.assertEqual(decision["blocking_requirements"], ["visual_family_conflict"])
        self.assertEqual(
            decision["detected_families"],
            {"data_shape": "scalar_field", "claim_or_inference": "distribution"},
        )
        self.assertIsNone(decision["backend"])

    def test_non_graphic_evidence_stops_before_backend_selection(self) -> None:
        cases = (
            ("summary_table", "table"),
            ("analytical proof", "proof_or_equation"),
            ("visual waiver", "no_visual"),
        )
        for intended_inference, family in cases:
            with self.subTest(family=family):
                decision = route_visual(
                    self.complete_request(
                        data_shape="",
                        statistical_goal="",
                        intended_inference=intended_inference,
                    )
                )
                self.assertEqual(decision["status"], "READY")
                self.assertEqual(decision["chart_family"], family)
                self.assertIsNone(decision["backend"])
                self.assertIsNone(decision["library"])
                self.assertIsNone(decision["route_id"])

    def test_visual_evidence_shapes_use_the_eight_route_table(self) -> None:
        cases = (
            ({"data_shape": "ordered_sequence", "statistical_goal": "convergence prediction"}, "R02", "matplotlib"),
            ({"data_shape": "regular_grid", "statistical_goal": "scalar field contour"}, "R03", "matlab"),
            ({"data_shape": "vector_field_3d", "statistical_goal": "volume structure"}, "R04", "matlab"),
            ({"data_shape": "tidy_long_table", "statistical_goal": "regression residual diagnostic"}, "R05", "seaborn"),
            ({"data_shape": "precomputed_array", "statistical_goal": "local inset paper layout"}, "R06", "matplotlib"),
            ({"data_shape": "simulation_trajectory", "statistical_goal": "dynamic system animation"}, "R07", "matlab"),
            ({"data_shape": "local_lat_lon_route", "statistical_goal": "offline route map"}, "R08", "matlab"),
        )
        for fields, route_id, library in cases:
            with self.subTest(route_id=route_id):
                decision = route_visual(self.complete_request(**fields))
                self.assertEqual(decision["route_id"], route_id)
                self.assertEqual(decision["library"], library)
        geo = route_visual(self.complete_request(data_shape="local_lat_lon_route", statistical_goal="offline route map"))
        self.assertEqual(geo["constraints"], {"projection": "none"})
        mesh = route_visual(
            self.complete_request(data_shape="mesh_polyhedron", statistical_goal="patch object geometry")
        )
        self.assertEqual(mesh["route_id"], "R04")
        self.assertIn("MT025", mesh["reference_cases"])
        self.assertTrue(mesh["constraints"]["display_disclosure"])

    def test_manual_override_requires_a_reason_and_preserves_recommendation(self) -> None:
        blocked = route_visual(
            self.complete_request(override={"backend": "python", "library": "matplotlib"})
        )
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertIn("override.reason", blocked["blocking_requirements"])

        decision = route_visual(
            self.complete_request(
                override={
                    "backend": "python",
                    "library": "matplotlib",
                    "reason": "Direct Axes control is required for the paper's local inset and shared annotation layer.",
                }
            )
        )
        self.assertEqual(decision["library"], "matplotlib")
        self.assertEqual(decision["recommended"]["library"], "seaborn")
        self.assertTrue(decision["override"]["applied"])
        self.assertEqual(decision["chart_family"], "distribution")

    def test_structured_request_cli_is_formal_but_task_text_is_pending(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request_path = root / "request.json"
            request_path.write_text(json.dumps(self.complete_request()), encoding="utf-8")
            structured = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "visual_backend_router.py"),
                    "--root",
                    str(root),
                    "--request-json",
                    str(request_path),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(structured.returncode, 0, structured.stdout + structured.stderr)
            self.assertEqual(json.loads(structured.stdout)["route_mode"], "structured_confirmed")

            inferred = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "visual_backend_router.py"),
                    "--root",
                    str(root),
                    "--task",
                    "grouped distribution",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(inferred.returncode, 0, inferred.stdout + inferred.stderr)
            self.assertEqual(json.loads(inferred.stdout)["route_mode"], "inferred_pending_confirmation")


class ThreeDOpportunityDetectionTests(unittest.TestCase):
    @staticmethod
    def write_table(root: Path, name: str, headers: list[str], rows: list[list[object]]) -> None:
        table_dir = root / "results" / "tables"
        table_dir.mkdir(parents=True, exist_ok=True)
        lines = [",".join(headers)]
        lines.extend(",".join(str(value) for value in row) for row in rows)
        (table_dir / name).write_text("\n".join(lines) + "\n", encoding="utf-8")

    @staticmethod
    def detect(root: Path) -> dict[str, object]:
        return {
            candidate.source: candidate
            for candidate in build_three_d_candidates(root, collect_table_profiles(root))
        }

    def test_structured_tables_detect_all_supported_three_d_candidate_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            grid_rows = [[x, y, x * x + y] for x in range(3) for y in range(3)]
            self.write_table(root, "q1_surface_grid.csv", ["x", "y", "z"], grid_rows)
            self.write_table(
                root,
                "q2_sensitivity.csv",
                ["alpha", "lambda", "objective"],
                [[alpha, lam, alpha + lam] for alpha in range(3) for lam in range(3)],
            )
            self.write_table(
                root, "q3_coordinates.csv", ["x", "y", "z"], [[0, 0, 0], [1, 2, 3], [2, 5, 8], [4, 9, 16]]
            )
            self.write_table(
                root, "q4_point_cloud.csv", ["x", "y", "z"], [[i, i % 7, i * 0.25] for i in range(30)]
            )
            self.write_table(
                root,
                "q5_trajectory.csv",
                ["time", "x", "y", "z"],
                [[i, i * 0.5, i * i, i * 0.25] for i in range(5)],
            )
            self.write_table(
                root,
                "q6_mesh_vertices.csv",
                ["x", "y", "z", "face_1", "face_2", "face_3"],
                [[0, 0, 0, 1, 2, 3], [1, 0, 0, 1, 3, 4], [0, 1, 0, 1, 4, 2]],
            )
            self.write_table(
                root,
                "q7_scalar_field.csv",
                ["x", "y", "z", "temperature"],
                [[i, i + 1, i + 2, 20 + i] for i in range(4)],
            )
            self.write_table(
                root,
                "q8_vector_field.csv",
                ["x", "y", "z", "u", "v", "w"],
                [[i, i + 1, i + 2, 1, -1, 0.5] for i in range(4)],
            )

            detected = self.detect(root)

            expected = {
                "results/tables/q1_surface_grid.csv": "surface_grid",
                "results/tables/q2_sensitivity.csv": "two_parameter_sensitivity",
                "results/tables/q3_coordinates.csv": "spatial_coordinates",
                "results/tables/q4_point_cloud.csv": "point_cloud_3d",
                "results/tables/q5_trajectory.csv": "trajectory_3d",
                "results/tables/q6_mesh_vertices.csv": "mesh_geometry",
                "results/tables/q7_scalar_field.csv": "scalar_field_3d",
                "results/tables/q8_vector_field.csv": "vector_field_3d",
            }
            self.assertEqual({source: item.kind for source, item in detected.items()}, expected)
            for candidate in detected.values():
                self.assertEqual(candidate.required_companion, "contour_projection_slice_or_table")

    def test_two_dimensional_data_and_matlab_capability_do_not_change_detection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_table(
                root, "q1_grid_response.csv", ["x", "y", "z"], [[x, y, x + y] for x in range(3) for y in range(3)]
            )
            self.write_table(root, "q2_ordinary_2d.csv", ["x", "value"], [[i, i * i] for i in range(12)])
            capability = root / "results" / "logs" / "matlab_visual_capability.json"
            capability.parent.mkdir(parents=True, exist_ok=True)
            capability.write_text(json.dumps({"executed": False, "record_valid": False}), encoding="utf-8")
            unavailable = {source: item.kind for source, item in self.detect(root).items()}
            capability.write_text(json.dumps({"executed": True, "record_valid": True}), encoding="utf-8")
            available = {source: item.kind for source, item in self.detect(root).items()}

            self.assertEqual(unavailable, available)
            self.assertEqual(unavailable, {"results/tables/q1_grid_response.csv": "surface_grid"})

    def test_dispositions_require_a_real_figure_or_specific_evidence_backed_waiver(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_table(root, "q1_coordinates.csv", ["x", "y", "z"], [[0, 0, 0], [1, 2, 3], [2, 4, 7], [3, 8, 12]])
            candidates = list(self.detect(root).values())
            candidate_id = candidates[0].candidate_id
            figure = root / "figures" / "q1_coordinates.png"
            figure.parent.mkdir(parents=True, exist_ok=True)
            figure.write_bytes(b"figure evidence")
            apply_three_d_dispositions(
                root, candidates, [{"candidate_id": candidate_id, "status": "generated", "artifact": "figures/q1_coordinates.png"}]
            )
            self.assertEqual(candidates[0].status, "generated")

            waived = list(self.detect(root).values())
            apply_three_d_dispositions(
                root,
                waived,
                [
                    {
                        "candidate_id": candidate_id,
                        "status": "waived",
                        "waiver_reason": "The four samples are too sparse to support an interpolated 3D surface without implying structure.",
                        "waiver_evidence": ["results/tables/q1_coordinates.csv has only four irregular samples"],
                    }
                ],
            )
            self.assertEqual(waived[0].status, "waived")

            invalid_dispositions = (
                {"status": "generated", "artifact": "figures/missing.png"},
                {"status": "generated", "artifact": "results/tables/q1_coordinates.csv"},
                {"status": "waived", "waiver_reason": "", "waiver_evidence": ["sample count"]},
                {"status": "waived", "waiver_reason": "The samples cannot support a truthful volume view.", "waiver_evidence": ["TBD"]},
                {"status": "waived", "waiver_reason": "not needed", "waiver_evidence": ["sample count"]},
            )
            for disposition in invalid_dispositions:
                with self.subTest(disposition=disposition):
                    unresolved = list(self.detect(root).values())
                    apply_three_d_dispositions(root, unresolved, [{"candidate_id": candidate_id, **disposition}])
                    findings, _ = audit(root, collect_table_profiles(root), [], unresolved, "", "contest_final")
                    self.assertEqual(unresolved[0].status, "unresolved")
                    self.assertIn("FAIL", {finding.level for finding in findings if finding.axis == "three_d_opportunity_disposition"})

    def test_storyboard_refresh_preserves_three_d_disposition(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_table(root, "q1_coordinates.csv", ["x", "y", "z"], [[0, 0, 0], [1, 2, 3], [2, 4, 7], [3, 8, 12]])
            candidate = next(iter(self.detect(root).values()))
            existing = [
                {
                    "candidate_id": candidate.candidate_id,
                    "status": "waived",
                    "artifact": "",
                    "waiver_reason": "Sparse coordinates are clearer as an exact table than an interpolated volume.",
                    "waiver_evidence": ["results/tables/q1_coordinates.csv"],
                }
            ]

            refreshed = sync_three_d_candidates(root, existing)

            self.assertEqual(len(refreshed), 1)
            self.assertEqual(refreshed[0]["status"], "waived")
            self.assertEqual(refreshed[0]["waiver_reason"], existing[0]["waiver_reason"])
            self.assertEqual(refreshed[0]["waiver_evidence"], existing[0]["waiver_evidence"])


class FigureProvenanceIntegrationTests(unittest.TestCase):
    def test_figure_evidence_gate_rejects_incomplete_seaborn_statistics(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request_path = root / "visual_request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "data_shape": "tidy_long_table",
                        "statistical_goal": "compare grouped distributions",
                        "evidence_role": "uncertainty",
                        "upstream_runtime": "python",
                        "provenance_present": True,
                        "units_present": True,
                        "statistics_explicit": True,
                        "offline_reproducible": True,
                        "static_evidence_available": True,
                        "interaction_required": False,
                        "output_contract": ["png_300dpi", "vector_pdf"],
                    }
                ),
                encoding="utf-8",
            )
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--visual-kind",
                    "distribution",
                    "--request-json",
                    str(request_path),
                    "--prefix",
                    "bad_statistics",
                    "--claim-id",
                    "C-Q1-STATS",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            provenance_path = root / "results" / "figures_data" / "bad_statistics_provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["statistics"].pop("errorbar", None)
            unsigned = {key: value for key, value in provenance.items() if key != "record_sha256"}
            provenance["record_sha256"] = canonical_sha256(unsigned)
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["figures"][0]["provenance_sha256"] = provenance["record_sha256"]
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("seaborn_statistics", {item["code"] for item in report["findings"]})

    def test_figure_evidence_gate_rejects_tampered_provenance_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "tampered_record",
                    "--claim-id",
                    "C-Q1-TAMPER",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)

            provenance_path = root / "results" / "figures_data" / "tampered_record_provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            provenance["statistics"]["rmse"] = 999.0
            provenance_path.write_text(json.dumps(provenance), encoding="utf-8")

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("provenance_record_hash", {item["code"] for item in report["findings"]})

    def test_figure_evidence_gate_rejects_artifact_changed_after_render(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "stale_artifact",
                    "--claim-id",
                    "C-Q1-STALE",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            (root / "results" / "figures_data" / "stale_artifact.csv").write_text(
                "x,observed,predicted\n0,999,999\n", encoding="utf-8"
            )

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("provenance_artifact_hash", {item["code"] for item in report["findings"]})

    def test_figure_evidence_gate_rejects_manifest_route_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "route_mismatch",
                    "--claim-id",
                    "C-Q1-ROUTE",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["figures"][0]["route_id"] = "R07"
            manifest["figures"][0]["library"] = "matlab"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            report = json.loads((root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8"))
            self.assertIn("provenance_route", {item["code"] for item in report["findings"]})

    def test_figure_evidence_gate_enforces_specialized_static_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            render = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--prefix",
                    "specialized_static",
                    "--claim-id",
                    "C-Q1-STATIC",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )
            self.assertEqual(render.returncode, 0, render.stdout + render.stderr)
            manifest_path = root / "planning" / "figure_evidence.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            record = manifest["figures"][0]
            record["media_type"] = "animation"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            animation = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(animation.returncode, 0, animation.stdout + animation.stderr)
            animation_report = json.loads(
                (root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8")
            )
            self.assertIn("animation_static_evidence", {item["code"] for item in animation_report["findings"]})

            record["media_type"] = "3d"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            three_d = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(three_d.returncode, 0, three_d.stdout + three_d.stderr)
            three_d_report = json.loads(
                (root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8")
            )
            self.assertIn("three_d_companion", {item["code"] for item in three_d_report["findings"]})
            self.assertIn("three_d_display", {item["code"] for item in three_d_report["findings"]})

    def test_matlab_geometry_scaffold_is_selective_and_parameterized(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_matlab_visual.py"),
                    "--root",
                    str(root),
                    "--scaffold",
                    "--visual-kind",
                    "geometry_3d",
                    "--prefix",
                    "q1_geometry",
                    "--claim-id",
                    "C-Q1-GEOMETRY",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["schema_version"], 3)
            self.assertEqual(payload["transport"], "batch")
            self.assertEqual(payload["execution_context"], "unattended")
            self.assertNotIn("execution_mode", payload)
            self.assertEqual(payload["visual_kind"], "geometry_3d")
            self.assertEqual(payload["route"]["route_id"], "R04")
            source = root / "code" / "matlab" / "matlab_geometry_3d.m"
            parameters = root / "results" / "figures_data" / "q1_geometry_parameters.json"
            self.assertTrue(source.is_file())
            self.assertTrue(parameters.is_file())
            source_text = source.read_text(encoding="utf-8")
            for token in ("patch", "FaceAlpha", "light_position", "projection_plane", "exportgraphics"):
                self.assertIn(token, source_text)
            config = json.loads(parameters.read_text(encoding="utf-8"))
            self.assertEqual(len(config["geometry"]["vertices"]), 8)
            self.assertEqual(config["display"]["colormap"], "mira_muted")

    def test_interactive_matlab_mcp_visual_chain_requires_and_registers_tool_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            prepare = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_matlab_visual.py"),
                    "--root",
                    str(root),
                    "--prepare-mcp",
                    "--prefix",
                    "q2_mcp_dynamic",
                    "--claim-id",
                    "C-Q2-MCP",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )
            self.assertEqual(prepare.returncode, 0, prepare.stdout + prepare.stderr)
            packet = json.loads(prepare.stdout)
            self.assertEqual(packet["transport"], "mcp")
            self.assertEqual(packet["tool_name"], "mcp__matlab__run_matlab_file")
            self.assertFalse((root / "results/logs/matlab_visual_capability.json").exists())
            runner = root / packet["runner"]
            runner_text = runner.read_text(encoding="utf-8")
            self.assertIn(f"MIRA_MCP_REQUEST_ID={packet['request_id']}", runner_text)

            prefix = packet["request"]["prefix"]
            for relative_path, content in (
                (f"figures/{prefix}.png", b"PNG evidence\n"),
                (f"figures/{prefix}.pdf", b"%PDF evidence\n"),
                (f"results/figures_data/{prefix}.csv", b"t,response\n0,0\n"),
                (f"results/figures_data/{prefix}.mat", b"MAT evidence\n"),
                (f"results/logs/{prefix}_matlab.log", b"status=success\n"),
            ):
                path = root / relative_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(content)
            summary_path = root / f"results/figures_data/{prefix}_summary.json"
            summary_path.write_text(
                json.dumps(
                    {
                        "backend": "MATLAB R2025a",
                        "matlab_version": "R2025a",
                        "required_toolboxes": ["MATLAB base"],
                        "rmse": 0.12,
                        "steady_max_error": 0.01,
                        "tolerance": 0.02,
                    }
                ),
                encoding="utf-8",
            )
            response_path = root / f"results/logs/{prefix}_matlab_mcp_response.json"
            response_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "backend": "matlab",
                        "transport": "mcp",
                        "server": "matlab",
                        "tool_name": packet["tool_name"],
                        "request_id": packet["request_id"],
                        "started_at": "2026-07-28T10:00:00+08:00",
                        "finished_at": "2026-07-28T10:00:02+08:00",
                        "result": {
                            "content": [
                                {
                                    "type": "text",
                                    "text": (
                                        f"MIRA_MCP_REQUEST_ID={packet['request_id']}\n"
                                        f"MIRA_MATLAB_FIGURE_OK=figures/{prefix}.png"
                                    ),
                                }
                            ]
                        },
                    }
                ),
                encoding="utf-8",
            )
            complete = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_matlab_visual.py"),
                    "--root",
                    str(root),
                    "--complete-mcp",
                    "--mcp-request-json",
                    packet["request_file"],
                    "--mcp-response-json",
                    response_path.relative_to(root).as_posix(),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"},
                check=False,
            )
            self.assertEqual(complete.returncode, 0, complete.stdout + complete.stderr)
            record = json.loads(complete.stdout)
            self.assertEqual(record["transport"], "mcp")
            self.assertEqual(record["execution_context"], "interactive")
            self.assertNotIn("returncode", record)
            self.assertTrue((root / f"results/logs/{prefix}_matlab_mcp_receipt.json").is_file())
            self.assertTrue((root / f"results/figures_data/{prefix}_provenance.json").is_file())

    def test_seaborn_statistical_figure_exports_reproducible_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request_path = root / "visual_request.json"
            request_path.write_text(
                json.dumps(
                    {
                        "data_shape": "tidy_long_table",
                        "statistical_goal": "compare grouped distributions",
                        "evidence_role": "uncertainty",
                        "upstream_runtime": "python",
                        "provenance_present": True,
                        "units_present": True,
                        "statistics_explicit": True,
                        "offline_reproducible": True,
                        "static_evidence_available": True,
                        "interaction_required": False,
                        "output_contract": ["png_300dpi", "vector_pdf"],
                    }
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    str(root),
                    "--demo",
                    "--visual-kind",
                    "distribution",
                    "--request-json",
                    str(request_path),
                    "--prefix",
                    "q1_uncertainty",
                    "--claim-id",
                    "C-Q1-UNCERTAINTY",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8", "MPLBACKEND": "Agg"},
                check=False,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            provenance_path = root / "results" / "figures_data" / "q1_uncertainty_provenance.json"
            provenance = json.loads(provenance_path.read_text(encoding="utf-8"))
            self.assertEqual(provenance["route"]["route_id"], "R01")
            self.assertEqual(provenance["route"]["actual"], {"backend": "python", "library": "seaborn"})
            self.assertEqual(provenance["runtime"]["seaborn"], "0.13.2")
            self.assertEqual(provenance["statistics"]["estimator"], "mean")
            self.assertEqual(provenance["statistics"]["errorbar"], {"method": "ci", "level": 95})
            self.assertTrue(provenance["statistics"]["raw_observations_overlaid"])

            for section, key in (
                ("source", "source_code"),
                ("source", "input_data"),
                ("export", "png"),
                ("export", "pdf"),
            ):
                artifact = provenance[section][key]
                self.assertTrue((root / artifact["path"]).is_file())
                self.assertRegex(artifact["sha256"], r"^[0-9a-f]{64}$")

            evidence = json.loads((root / "planning" / "figure_evidence.json").read_text(encoding="utf-8"))
            record = evidence["figures"][0]
            self.assertEqual(record["library"], "seaborn")
            self.assertEqual(record["route_id"], "R01")
            self.assertEqual(record["provenance_file"], "results/figures_data/q1_uncertainty_provenance.json")
            self.assertEqual(record["provenance_sha256"], provenance["record_sha256"])

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB batch runtime is unavailable")
    def test_matlab_batch_exports_reproducible_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            request_path = root / "visual_request.json"
            request_path.write_text(
                json.dumps(
                    {
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
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_matlab_visual.py"),
                    "--root",
                    str(root),
                    "--scaffold",
                    "--run",
                    "--request-json",
                    str(request_path),
                    "--prefix",
                    "q2_dynamic",
                    "--claim-id",
                    "C-Q2-DYNAMIC",
                    "--timeout",
                    "180",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            skip_matlab_startup_failure(self, result)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            expected = (
                "figures/q2_dynamic.png",
                "figures/q2_dynamic.pdf",
                "results/figures_data/q2_dynamic.csv",
                "results/figures_data/q2_dynamic.mat",
                "results/figures_data/q2_dynamic_parameters.json",
                "results/figures_data/q2_dynamic_provenance.json",
                "results/logs/q2_dynamic_matlab.log",
            )
            for relative_path in expected:
                self.assertTrue((root / relative_path).is_file(), relative_path)

            provenance = json.loads(
                (root / "results" / "figures_data" / "q2_dynamic_provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(provenance["route"]["route_id"], "R07")
            self.assertEqual(provenance["route"]["actual"], {"backend": "matlab", "library": "matlab"})
            self.assertRegex(provenance["runtime"]["matlab"], r"^R?2025a|25\.")
            self.assertEqual(provenance["runtime"]["required_toolboxes"], ["MATLAB base"])
            self.assertRegex(provenance["source"]["input_data"]["sha256"], r"^[0-9a-f]{64}$")
            self.assertRegex(provenance["source"]["mat_data"]["sha256"], r"^[0-9a-f]{64}$")

            evidence = json.loads((root / "planning" / "figure_evidence.json").read_text(encoding="utf-8"))
            record = evidence["figures"][0]
            self.assertEqual(record["library"], "matlab")
            self.assertEqual(record["route_id"], "R07")
            self.assertEqual(record["provenance_file"], "results/figures_data/q2_dynamic_provenance.json")

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)
            (root / "results" / "figures_data" / "q2_dynamic.mat").unlink()
            missing_mat = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertNotEqual(missing_mat.returncode, 0, missing_mat.stdout + missing_mat.stderr)
            missing_report = json.loads(
                (root / "checks" / "figure_evidence_report.json").read_text(encoding="utf-8")
            )
            self.assertIn("provenance_artifact_missing", {item["code"] for item in missing_report["findings"]})

    @unittest.skipUnless(shutil.which("matlab"), "MATLAB batch runtime is unavailable")
    def test_matlab_geometry_batch_exports_3d_provenance_and_projection(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "run_matlab_visual.py"),
                    "--root",
                    str(root),
                    "--scaffold",
                    "--run",
                    "--visual-kind",
                    "geometry_3d",
                    "--prefix",
                    "q1_geometry",
                    "--claim-id",
                    "C-Q1-GEOMETRY",
                    "--timeout",
                    "180",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            skip_matlab_startup_failure(self, result)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            expected = (
                "code/matlab/matlab_geometry_3d.m",
                "figures/q1_geometry.png",
                "figures/q1_geometry.pdf",
                "figures/q1_geometry_projection.png",
                "figures/q1_geometry_projection.pdf",
                "results/figures_data/q1_geometry.csv",
                "results/figures_data/q1_geometry.mat",
                "results/figures_data/q1_geometry_parameters.json",
                "results/figures_data/q1_geometry_provenance.json",
                "results/logs/q1_geometry_matlab.log",
            )
            for relative_path in expected:
                self.assertTrue((root / relative_path).is_file(), relative_path)

            provenance = json.loads(
                (root / "results" / "figures_data" / "q1_geometry_provenance.json").read_text(encoding="utf-8")
            )
            self.assertEqual(provenance["route"]["route_id"], "R04")
            self.assertEqual(provenance["statistics"]["kind"], "deterministic_3d_geometry")
            self.assertRegex(provenance["export"]["projection_pdf"]["sha256"], r"^[0-9a-f]{64}$")
            evidence = json.loads((root / "planning" / "figure_evidence.json").read_text(encoding="utf-8"))
            record = evidence["figures"][0]
            self.assertEqual(record["media_type"], "3d")
            self.assertEqual(record["projection_file"], "figures/q1_geometry_projection.pdf")
            self.assertEqual(record["display_parameters"]["projection_plane"], "xy")

            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_evidence_gate.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            self.assertEqual(gate.returncode, 0, gate.stdout + gate.stderr)


if __name__ == "__main__":
    unittest.main()
