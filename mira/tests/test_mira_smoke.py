from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
WORKSPACE_ROOT = SKILL_ROOT.parents[2]


class MiraSmokeTests(unittest.TestCase):
    def test_release_metadata_is_consistent(self) -> None:
        version = (SKILL_ROOT / "VERSION").read_text(encoding="utf-8").strip()
        skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8-sig")
        changelog = (SKILL_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertEqual(version, "1.0.0")
        self.assertIn("Mira 1.0.0", skill)
        self.assertIn("## 1.0.0", changelog)

    def test_selective_nature_integration_keeps_attribution_record(self) -> None:
        attribution = (SKILL_ROOT / "references" / "nature-skills-attribution.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Yuan1z0825/nature-skills", attribution)
        self.assertIn("c2a37016ac2868708b262126c7e5684fa2cbd212", attribution)
        self.assertIn("Apache License 2.0", attribution)
        self.assertIn("164 training cases are not copied", attribution)

    def test_mathodology_layout_qa_keeps_attribution_record(self) -> None:
        attribution = (SKILL_ROOT / "references" / "mathodology-attribution.md").read_text(
            encoding="utf-8"
        )
        license_text = (
            SKILL_ROOT / "references" / "third-party" / "mathodology" / "LICENSE"
        ).read_text(encoding="utf-8")
        self.assertIn("sweetcornna/mathodology", attribution)
        self.assertIn("8b57eb0f5e00db6e7b53310729e5d02e71cfc7e1", attribution)
        self.assertIn("figqa.py", attribution)
        self.assertIn("MIT License", license_text)

    def test_mathmodel_skill_integration_is_idea_only(self) -> None:
        notice = (
            SKILL_ROOT / "references" / "third-party" / "mathmodel-skill" / "NOTICE.md"
        ).read_text(encoding="utf-8")
        self.assertIn("handsomeZR-netizen/mathmodel-skill", notice)
        self.assertIn("d3941e14d8693fb4a79948e59afff3098734127e", notice)
        self.assertIn("No upstream source code", notice)

    def test_all_python_sources_parse(self) -> None:
        failures: list[str] = []
        for path in sorted(SKILL_ROOT.rglob("*.py")):
            try:
                ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
            except (SyntaxError, UnicodeError) as exc:
                failures.append(f"{path.relative_to(SKILL_ROOT)}: {exc}")
        self.assertFalse(failures, "\n".join(failures))

    def test_command_profiles_resolve_from_installed_skill(self) -> None:
        source = (SCRIPTS / "command_profiles.py").read_text(encoding="utf-8-sig")
        self.assertNotIn('SKILL_SCRIPTS: Final[str] = r"D:', source)
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "command_profiles.py"),
                "--phase",
                "benchmark",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        payload = json.loads(result.stdout)
        self.assertEqual(payload["stage"], "implementation")
        self.assertEqual(payload["phase"], "implementation")
        self.assertTrue(payload["commands"])
        self.assertIn(str(SCRIPTS / "benchmark_regression.py"), payload["commands"][0])

    def test_public_profiles_are_bounded_four_stage_profiles(self) -> None:
        for stage in ("analysis", "modeling", "implementation", "paper"):
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "command_profiles.py"),
                    "--stage",
                    stage,
                    "--output-level",
                    "contest_final",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            commands = json.loads(result.stdout)["commands"]
            self.assertGreaterEqual(len(commands), 3, stage)
            self.assertLessEqual(len(commands), 4, stage)
            self.assertTrue(any("stage_gate.py" in command for command in commands), stage)
            self.assertFalse(any("decision_gate.py" in command or "--gate G" in command for command in commands), stage)

    def test_runtime_scripts_do_not_pin_the_old_checkout(self) -> None:
        legacy_checkout = r"$PROJECT_ROOT\.codex\skills\mira"
        offenders = []
        for path in sorted(SCRIPTS.rglob("*.py")):
            source = path.read_text(encoding="utf-8-sig")
            if legacy_checkout in source or legacy_checkout.replace("\\", "/") in source:
                offenders.append(str(path.relative_to(SKILL_ROOT)))
        self.assertFalse(offenders, "fixed Mira checkout paths: " + ", ".join(offenders))

    def test_generated_project_commands_use_installed_skill(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_math_modeling_project.py"),
                    temp_dir,
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            route = (Path(temp_dir) / "planning" / "reference_route.md").read_text(
                encoding="utf-8"
            )
            state = (Path(temp_dir) / "planning" / "mira_state.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(str(SCRIPTS / "route_references.py"), route)
            self.assertIn(str(SCRIPTS / "mira_state.py"), state)
            initialized_state = json.loads(
                (Path(temp_dir) / "planning" / "mira_state.json").read_text(encoding="utf-8")
            )
            self.assertEqual(initialized_state["stage"]["current"], "analysis")
            self.assertFalse((Path(temp_dir) / "planning" / "decision_gates.json").exists())
            self.assertFalse((Path(temp_dir) / "planning" / "artifact_dependencies.json").exists())
            self.assertFalse((Path(temp_dir) / "planning" / "change_impact.json").exists())
            self.assertTrue((Path(temp_dir) / "planning" / "submission_requirements.json").is_file())

            method_json = Path(temp_dir) / "planning" / "method_route.json"
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "method_route.py"),
                    "--root",
                    temp_dir,
                    "--write-json",
                    str(method_json),
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(method_json.read_text(encoding="utf-8"))
            self.assertIn(str(SCRIPTS / "knowledge_retrieve.py"), payload["commands"][0])
            self.assertIn(str(SCRIPTS / "validation_plan.py"), payload["commands"][1])

    def test_reference_router_smoke(self) -> None:
        phases = {
            "startup": "analysis",
            "benchmark": "implementation",
            "iteration": "paper",
            "verify": "paper",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            for phase, expected_stage in phases.items():
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "route_references.py"),
                        "--root",
                        temp_dir,
                        "--phase",
                        phase,
                        "--json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                payload = json.loads(result.stdout)
                self.assertEqual(payload["stage"], expected_stage)
                self.assertEqual(payload["phase"], expected_stage)
                for item in payload["load_now"]:
                    self.assertTrue(
                        (SKILL_ROOT / item["path"]).is_file(),
                        f"missing routed reference for {phase}: {item['path']}",
                    )

    def test_standard_contest_paper_route_has_bounded_core_load(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "route_references.py"),
                    "--root",
                    temp_dir,
                    "--phase",
                    "paper",
                    "--request",
                    "contest_final complete contest paper",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(result.stdout)
            paths = {item["path"] for item in payload["load_now"]}
            self.assertLessEqual(len(paths), 12)
            self.assertIn("references/contest-final-writing-contract.md", paths)
            self.assertNotIn("references/cnn-architecture-diagram-rules.md", paths)
            self.assertNotIn("references/pseudo-3d-ppt-diagram-rules.md", paths)
            self.assertNotIn("references/chart-gallery-index.md", paths)

    def test_active_visual_routes_do_not_call_drawio(self) -> None:
        profiles = (SCRIPTS / "command_profiles.py").read_text(encoding="utf-8-sig")
        self.assertNotIn("generate_drawio_diagrams.py", profiles)
        with tempfile.TemporaryDirectory() as temp_dir:
            context = Path(temp_dir) / "planning" / "modeling_plan.md"
            context.parent.mkdir(parents=True)
            context.write_text("需要结构图、架构图和变量关系图。", encoding="utf-8")
            for phase in ("figures", "diagrams", "paper", "verify", "iteration"):
                result = subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "route_references.py"),
                        "--root",
                        temp_dir,
                        "--phase",
                        phase,
                        "--json",
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                routed = json.loads(result.stdout)
                paths = {item["path"] for item in routed["load_now"]}
                self.assertNotIn("references/drawio-diagram-rules.md", paths)

    def test_rigid_chain_route_ignores_generated_report_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            checks = root / "checks"
            planning.mkdir(parents=True)
            checks.mkdir(parents=True)
            (planning / "workflow_lane.md").write_text(
                "Selected lane: **deep**\n", encoding="utf-8"
            )
            (planning / "delivery_brief.md").write_text(
                "| Output level | contest_final |\n", encoding="utf-8"
            )
            (planning / "modeling_plan.md").write_text(
                "Linked rigid segments move along a spiral with fixed joint spacing; validate oriented-body collisions and continuous extrema.\n",
                encoding="utf-8",
            )
            (planning / "figure_claims_template.json").write_text(
                '{"template_help": "CNN multimodal fusion pseudo-3D PPT"}', encoding="utf-8"
            )
            (checks / "figure_claim_ownership_report.md").write_text(
                "CNN architecture, multimodal fusion, pseudo-3D PPT", encoding="utf-8"
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "route_references.py"),
                    "--root",
                    temp_dir,
                    "--phase",
                    "figures",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            paths = {item["path"] for item in json.loads(result.stdout)["load_now"]}
            self.assertNotIn("references/cnn-architecture-diagram-rules.md", paths)
            self.assertNotIn("references/multimodal-fusion-architecture-rules.md", paths)
            self.assertNotIn("references/pseudo-3d-ppt-diagram-rules.md", paths)

    def test_generic_geometry_mechanisms_retrieve_required_knowledge_cards(self) -> None:
        cases = [
            (
                "rigid_chain",
                "A rigid chain of linked segments moves along an Archimedean spiral while fixed joint spacing is enforced.",
                "geometry_chain",
                "rigid-chain-kinematics",
            ),
            (
                "collision",
                "Detect collision and overlap between oriented rectangles with the separating axis theorem (SAT).",
                "collision_audit",
                "collision-sat",
            ),
            (
                "continuous_extremum",
                "A coarse scan locates the continuous peak, followed by continuous refinement for the maximum.",
                "continuous_extremum",
                "continuous-extremum-search",
            ),
        ]
        for case_id, problem_text, expected_route, expected_card in cases:
            with self.subTest(case=case_id), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                planning = root / "planning"
                planning.mkdir(parents=True)
                (planning / "problem_analysis.md").write_text(problem_text, encoding="utf-8")

                route_json = planning / "method_route.json"
                subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "method_route.py"),
                        "--root",
                        temp_dir,
                        "--write-json",
                        str(route_json),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                route_payload = json.loads(route_json.read_text(encoding="utf-8"))
                route = next(
                    item for item in route_payload["routes"] if item["route_id"] == expected_route
                )
                self.assertIn(expected_card, route["required_cards"])

                knowledge_json = planning / "knowledge_injection.json"
                subprocess.run(
                    [
                        sys.executable,
                        str(SCRIPTS / "knowledge_retrieve.py"),
                        "--root",
                        temp_dir,
                        "--query",
                        route_payload["recommended_query"],
                        "--write-json",
                        str(knowledge_json),
                    ],
                    check=True,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                )
                knowledge_payload = json.loads(knowledge_json.read_text(encoding="utf-8"))
                retrieved_cards = {Path(item["path"]).stem for item in knowledge_payload["hits"]}
                self.assertIn(expected_card, retrieved_cards)

    def test_convergence_does_not_route_cnn_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir(parents=True)
            (planning / "modeling_plan.md").write_text(
                "Convergence analysis, multi-seed baseline comparison, and sensitivity checks.",
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "route_references.py"),
                    "--root",
                    temp_dir,
                    "--phase",
                    "results",
                    "--json",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            paths = {item["path"] for item in json.loads(result.stdout)["load_now"]}
            self.assertNotIn("references/cnn-architecture-diagram-rules.md", paths)

    def test_matlab_router_does_not_confuse_installation_with_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "visual_backend_router.py"),
                    "--root",
                    temp_dir,
                    "--task",
                    "control signal response surface",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(result.stdout)
            self.assertGreater(payload["scores"]["matlab"], payload["scores"]["python"])
            self.assertFalse(payload["matlab_capability"]["executed"])
            expected = "matlab_pending_probe" if payload["matlab_capability"]["installed"] else "python"
            self.assertEqual(payload["selected_backend"], expected)

    def test_matlab_router_reuses_complete_successful_execution_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            files = [
                "code/matlab/plot.m",
                "results/logs/matlab.log",
                "results/figures_data/summary.json",
                "figures/result.pdf",
                "figures/result.png",
            ]
            for relative in files:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"evidence")
            executable = root / "matlab.exe"
            executable.write_bytes(b"binary")
            record = {
                "schema_version": 3,
                "backend": "matlab",
                "transport": "batch",
                "execution_context": "unattended",
                "installed": True,
                "executable": str(executable),
                "matlab_version": "R2025a",
                "source": files[0],
                "request": {"task": "control response surface"},
                "command_or_tool": {
                    "kind": "command",
                    "argv": [str(executable), "-batch", "plot"],
                },
                "started_at": "2026-07-28T10:00:00+08:00",
                "finished_at": "2026-07-28T10:00:01+08:00",
                "duration_seconds": 1.0,
                "executed": True,
                "status": "ok",
                "returncode": 0,
                "log_files": [files[1]],
                "evidence": [files[2]],
                "outputs": files[3:],
            }
            record_path = root / "results" / "logs" / "matlab_visual_capability.json"
            record_path.write_text(json.dumps(record), encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "visual_backend_router.py"), "--root", temp_dir, "--task", "control response surface"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["selected_backend"], "matlab")
            self.assertTrue(payload["matlab_capability"]["executed"])
            self.assertTrue(payload["matlab_capability"]["record_valid"])
            self.assertEqual(payload["matlab_capability"]["probe_status"], "verified_record")

    def test_matlab_router_rejects_incomplete_execution_record(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            executable = root / "matlab.exe"
            executable.write_bytes(b"binary")
            record_path = root / "results" / "logs" / "matlab_visual_capability.json"
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(
                json.dumps({
                    "schema_version": 3,
                    "backend": "matlab",
                    "transport": "batch",
                    "execution_context": "unattended",
                    "installed": True,
                    "executable": str(executable),
                    "matlab_version": "R2025a",
                    "source": "code/matlab/missing.m",
                    "request": {"task": "control response surface"},
                    "command_or_tool": {
                        "kind": "command",
                        "argv": [str(executable), "-batch", "plot"],
                    },
                    "started_at": "2026-07-28T10:00:00+08:00",
                    "finished_at": "2026-07-28T10:00:01+08:00",
                    "duration_seconds": 1.0,
                    "executed": True,
                    "status": "ok",
                    "returncode": 0,
                    "log_files": ["results/logs/missing.log"],
                    "evidence": ["results/logs/missing.log"],
                    "outputs": ["figures/missing.pdf"],
                }),
                encoding="utf-8",
            )
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "visual_backend_router.py"), "--root", temp_dir, "--task", "control response surface"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(result.stdout)
            self.assertFalse(payload["matlab_capability"]["executed"])
            self.assertFalse(payload["matlab_capability"]["record_valid"])
            self.assertEqual(payload["matlab_capability"]["probe_status"], "invalid_record")
            self.assertTrue(payload["matlab_capability"]["record_errors"])

    def test_python_claim_figure_renders_and_passes_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "plot_claim_figure.py"),
                    "--root",
                    temp_dir,
                    "--demo",
                    "--prefix",
                    "smoke_evidence",
                ],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            gate = subprocess.run(
                [sys.executable, str(SCRIPTS / "visual_render_gate.py"), "--root", temp_dir],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            self.assertIn("VERDICT: PASS", gate.stdout)
            self.assertGreater((Path(temp_dir) / "figures" / "smoke_evidence.png").stat().st_size, 8000)
            self.assertTrue((Path(temp_dir) / "figures" / "smoke_evidence.pdf").is_file())

    def test_matlab_template_has_evidence_output_contract(self) -> None:
        source = (SKILL_ROOT / "assets" / "templates" / "matlab_claim_figure.m").read_text(encoding="utf-8")
        for token in ("tiledlayout", "steady_mask", "局部放大", "exportgraphics", "'Resolution',300", ".png", ".pdf", "writetable", "jsonencode", "MIRA_MATLAB_FIGURE_OK"):
            with self.subTest(token=token):
                self.assertIn(token, source)

    def test_benchmark_registry_and_json_files(self) -> None:
        benchmark_dir = SKILL_ROOT / "benchmarks"
        for path in benchmark_dir.glob("*.json"):
            with self.subTest(path=path.name):
                json.loads(path.read_text(encoding="utf-8-sig"))

        registry = json.loads((benchmark_dir / "registry.json").read_text(encoding="utf-8"))
        self.assertEqual(registry["release"], "1.0.0")
        self.assertEqual(
            registry["candidate_release_status"],
            "RELEASED",
        )
        self.assertNotIn("competitive_claim_allowed", registry)
        self.assertNotIn("deferred_validations", registry)
        self.assertFalse(registry["archive_available"])
        self.assertEqual(registry["archive_status"], "REMOVED_2026_07_19")
        self.assertGreaterEqual(len(registry["projects"]), 10)
        for project in registry["projects"]:
            archive_path = WORKSPACE_ROOT / Path(project["archive_path"])
            self.assertFalse(archive_path.exists(), project["archive_path"])

    def test_version_notes_are_outside_active_reference_root(self) -> None:
        active_notes = sorted((SKILL_ROOT / "references").glob("mira-version-*.md"))
        self.assertEqual([path.name for path in active_notes], ["mira-version-index.md"])
        archived = list(
            (SKILL_ROOT / "references" / "archive" / "version-history").glob(
                "mira-version-*.md"
            )
        )
        self.assertGreaterEqual(len(archived), 70)

    def test_agent_metadata_matches_active_contract(self) -> None:
        metadata = (SKILL_ROOT / "agents" / "openai.yaml").read_text(encoding="utf-8")
        self.assertNotIn("AI-use compliance", metadata)
        self.assertIn("verification", metadata)
        self.assertIn("change-impact", metadata)
        self.assertIn("submission", metadata)


if __name__ == "__main__":
    unittest.main()
