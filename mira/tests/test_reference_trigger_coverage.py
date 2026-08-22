from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reference_trigger_coverage import evaluate_reference_triggers  # noqa: E402
from route_references import build_route  # noqa: E402
from stage_gate import StageGate  # noqa: E402


class ReferenceTriggerCoverageTests(unittest.TestCase):
    def test_structured_solver_fact_routes_domain_knowledge_without_free_text(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(root, "planning/modeling_plan.json", {"solver": "NSGA-II"})
            route = build_route(root, "modeling", "")

        self.assertIn(
            "references/domain-knowledge-injection.md",
            {item.path for item in route.load_now},
        )
        hit = next(item for item in route.trigger_hits if item.rule_id == "method_domain_knowledge")
        self.assertEqual(hit.disposition, "load_now")
        self.assertEqual({item.source_type for item in hit.evidence}, {"structured"})
        self.assertIn("planning/modeling_plan.json#solver", hit.evidence[0].location)

    def test_structured_validation_fact_routes_comparison_rules(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(
                root,
                "planning/validation_plan.json",
                {"validation": {"sensitivity": True, "multi_seed": 20}},
            )
            route = build_route(root, "modeling", "")

        self.assertIn(
            "references/baseline-comparison-rules.md",
            {item.path for item in route.load_now},
        )
        hit = next(item for item in route.trigger_hits if item.rule_id == "comparison_validation_evidence")
        self.assertTrue(all(item.source_type == "structured" for item in hit.evidence))

    def test_structured_citation_task_routes_precision_rules_in_paper_stage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(
                root,
                "planning/citation_plan.json",
                {"tasks": [{"source_binding": True, "claim_id": "C-01"}]},
            )
            route = build_route(root, "paper", "")

        self.assertIn(
            "references/citation-precision-rules.md",
            {item.path for item in route.load_now},
        )

    def test_generated_reports_and_old_routes_do_not_self_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "checks/generated_report.md", "convergence sensitivity NSGA-II citation\n")
            self._write_json(
                root,
                "planning/reference_route.json",
                {"notes": ["baseline convergence excellent paper"]},
            )
            hits = evaluate_reference_triggers(root, request="")

        self.assertEqual(hits, [])

    def test_placeholders_and_backend_capabilities_do_not_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(
                root,
                "planning/modeling_plan.json",
                {
                    "solver": "not_applicable",
                    "model_family": "",
                    "backend_capabilities": ["MATLAB", "Python"],
                    "validation": {"sensitivity": False, "baseline": None},
                },
            )
            hits = evaluate_reference_triggers(root, request="")

        self.assertEqual(hits, [])

    def test_short_algorithm_tokens_require_word_boundaries(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write(root, "planning/problem_analysis.md", "A legacy SAGA identifier and ODEON field.\n")
            hits = evaluate_reference_triggers(root, request="")

        self.assertNotIn("method_domain_knowledge", {item.rule_id for item in hits})

    def test_future_stage_trigger_is_deferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(root, "planning/modeling_plan.json", {"solver": "NSGA-II"})
            route = build_route(root, "analysis", "")

        self.assertNotIn(
            "references/domain-knowledge-injection.md",
            {item.path for item in route.load_now},
        )
        hit = next(item for item in route.trigger_hits if item.rule_id == "method_domain_knowledge")
        self.assertEqual(hit.disposition, "deferred")

    def test_stage_gate_detects_fact_added_after_route_was_written(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._modeling_fixture(Path(temp_dir))
            self._write_json(root, "planning/validation_plan.json", {"checks": []})
            self._write_route(root, build_route(root, "modeling", ""))
            self._write_json(
                root,
                "planning/validation_plan.json",
                {"checks": [{"kind": "sensitivity", "enabled": True}]},
            )
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()

        failures = [
            item for item in payload["checks"]
            if item["check"] == "reference_trigger_coverage" and item["level"] == "FAIL"
        ]
        self.assertEqual(len(failures), 1)
        self.assertIn("comparison_validation_evidence", failures[0]["message"])

    def test_rerouting_complete_trigger_evidence_restores_stage_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._modeling_fixture(Path(temp_dir))
            self._write_json(
                root,
                "planning/validation_plan.json",
                {"checks": [{"kind": "sensitivity", "enabled": True}]},
            )
            self._write_route(root, build_route(root, "modeling", ""))
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()

        coverage = [item for item in payload["checks"] if item["check"] == "reference_trigger_coverage"]
        self.assertEqual([(item["level"], item["stage"]) for item in coverage], [("PASS", "modeling")])
        self.assertEqual(payload["verdict"], "PASS")

    def test_route_from_another_stage_is_stale_for_current_trigger(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._modeling_fixture(Path(temp_dir))
            self._write_json(root, "planning/modeling_plan.json", {"solver": "NSGA-II"})
            self._write_route(root, build_route(root, "analysis", ""))
            payload = StageGate(root, "modeling", "reproducible_draft").evaluate()

        failure = next(
            item for item in payload["checks"]
            if item["check"] == "reference_trigger_coverage" and item["level"] == "FAIL"
        )
        self.assertIn("stage is analysis", failure["message"])

    def test_structured_and_keyword_evidence_are_deduplicated_per_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(root, "planning/modeling_plan.json", {"solver": "NSGA-II"})
            hits = evaluate_reference_triggers(root, request="Use NSGA-II optimization")

        method_hits = [item for item in hits if item.rule_id == "method_domain_knowledge"]
        self.assertEqual(len(method_hits), 1)
        self.assertEqual({item.source_type for item in method_hits[0].evidence}, {"structured", "keyword"})

    def test_keyword_supplement_routes_unstructured_current_request(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            route = build_route(Path(temp_dir), "modeling", "Run a multi-seed sensitivity analysis")

        hit = next(item for item in route.trigger_hits if item.rule_id == "comparison_validation_evidence")
        self.assertEqual(hit.disposition, "load_now")
        self.assertEqual({item.source_type for item in hit.evidence}, {"keyword"})

    def test_cli_write_emits_markdown_json_and_machine_readable_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_json(root, "planning/modeling_plan.json", {"solver": "NSGA-II"})
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "route_references.py"),
                    "--root",
                    str(root),
                    "--stage",
                    "modeling",
                    "--write",
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(
                (root / "planning" / "reference_route.json").read_text(encoding="utf-8")
            )
            report = (root / "planning" / "reference_route.md").read_text(encoding="utf-8")

        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(payload["schema_version"], 2)
        self.assertEqual(payload["stage"], "modeling")
        self.assertEqual(payload["trigger_hits"][0]["rule_id"], "method_domain_knowledge")
        self.assertIn("## Trigger Evidence", report)

    @classmethod
    def _modeling_fixture(cls, root: Path) -> Path:
        cls._write(root, "planning/delivery_brief.md", "| Output level | reproducible_draft |\n")
        cls._write(root, "planning/problem_analysis.md", "problem contract\n")
        cls._write(root, "planning/modeling_plan.md", "model contract\n")
        cls._write(root, "planning/validation_plan.md", "validation contract\n")
        return root

    @classmethod
    def _write_route(cls, root: Path, route: object) -> None:
        cls._write_json(root, "planning/reference_route.json", asdict(route))

    @staticmethod
    def _write_json(root: Path, relative: str, payload: object) -> None:
        ReferenceTriggerCoverageTests._write(
            root, relative, json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
        )

    @staticmethod
    def _write(root: Path, relative: str, content: str) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
