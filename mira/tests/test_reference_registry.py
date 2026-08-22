from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from reference_registry_audit import CANDIDATE_STATUSES, audit_registry  # noqa: E402
from route_references import (  # noqa: E402
    MATERIAL_REFS,
    MAINTENANCE_REFS,
    PUBLIC_RISK_REFS,
    PUBLIC_STAGE_REFS,
    VISUAL_LEAF_RULES,
    build_route,
)


class ReferenceRegistryTests(unittest.TestCase):
    def test_live_registry_covers_all_top_level_references(self) -> None:
        payload = audit_registry(SKILL_ROOT)
        registry_paths = {item["path"] for item in self._live_registry()["entries"]}
        disk_paths = {
            f"references/{path.name}"
            for path in (SKILL_ROOT / "references").glob("*.md")
        }

        self.assertEqual(payload["verdict"], "PASS", payload["findings"])
        self.assertEqual(registry_paths, disk_paths)
        self.assertEqual(payload["metrics"]["actual_top_level_references"], len(disk_paths))
        self.assertEqual(payload["metrics"]["registered_references"], len(registry_paths))

    def test_unregistered_top_level_reference_is_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._fixture(Path(temp_dir))
            (root / "references" / "new-unregistered-rule.md").write_text("# New\n", encoding="utf-8")

            payload = audit_registry(root)

        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue(any("new-unregistered-rule.md" in item["message"] for item in payload["findings"]))

    def test_active_reference_without_a_caller_is_a_hard_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._fixture(Path(temp_dir))
            registry_path = root / "references" / "reference-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            entry = next(item for item in registry["entries"] if item["status"] == "active_indirect")
            entry["callers"] = []
            registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

            payload = audit_registry(root)

        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue(any("active reference has no caller" in item["message"] for item in payload["findings"]))

    def test_existing_caller_must_declare_the_registered_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = self._fixture(Path(temp_dir))
            registry_path = root / "references" / "reference-registry.json"
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            entry = next(item for item in registry["entries"] if item["status"] == "active_indirect")
            unrelated = root / "scripts" / "unrelated.py"
            unrelated.parent.mkdir(parents=True, exist_ok=True)
            unrelated.write_text("# no rule declaration\n", encoding="utf-8")
            entry["callers"] = ["scripts/unrelated.py"]
            registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")

            payload = audit_registry(root)

        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue(any("does not declare" in item["message"] for item in payload["findings"]))

    def test_attribution_records_need_no_contest_route(self) -> None:
        registry = self._live_registry()
        attribution = [item for item in registry["entries"] if item["status"] == "attribution_only"]

        self.assertEqual(len(attribution), 2)
        self.assertTrue(all(item["callers"] == [] for item in attribution))
        self.assertTrue(all(item["load_policy"] == "never_runtime" for item in attribution))
        self.assertEqual(audit_registry(SKILL_ROOT)["verdict"], "PASS")

    def test_cleanup_candidates_are_not_directly_routed_and_merged_rules_are_gone(self) -> None:
        registry = self._live_registry()
        candidate_paths = {
            item["path"]
            for item in registry["entries"]
            if item["status"] in CANDIDATE_STATUSES
        }
        direct_paths = {path for paths in PUBLIC_STAGE_REFS.values() for path in paths}
        direct_paths.update(item[1] for item in PUBLIC_RISK_REFS)
        direct_paths.update(MATERIAL_REFS.values())
        direct_paths.update(MAINTENANCE_REFS.values())
        direct_paths.update(item.path for item in VISUAL_LEAF_RULES)

        audit_candidates = set(audit_registry(SKILL_ROOT)["metrics"]["cleanup_queue"])
        self.assertEqual(candidate_paths, audit_candidates)
        self.assertTrue(candidate_paths.isdisjoint(direct_paths))
        self.assertTrue(all((SKILL_ROOT / path).is_file() for path in candidate_paths))
        merged_paths = {
            "references/artifact-management.md",
            "references/contest-final-writing-patterns.md",
            "references/excellent-paper-extraction.md",
            "references/excellent-paper-quality-patterns.md",
            "references/final-paper-quality-gate.md",
            "references/iteration-loop.md",
            "references/mathmodelagent-integration.md",
        }
        self.assertTrue(merged_paths.isdisjoint(candidate_paths))
        self.assertTrue(all(not (SKILL_ROOT / path).exists() for path in merged_paths))

    def test_visual_registry_matches_all_25_one_leaf_routes(self) -> None:
        registry = self._live_registry()
        visual_entries = {
            item["path"]: item
            for item in registry["entries"]
            if item["status"] == "active_visual_leaf"
        }

        self.assertEqual(set(visual_entries), {item.path for item in VISUAL_LEAF_RULES})
        self.assertEqual(len(visual_entries), 25)
        self.assertTrue(all(item["load_policy"] == "one_visual_leaf" for item in visual_entries.values()))

    def test_registry_does_not_expand_normal_stage_base_routes(self) -> None:
        expected = {stage: set(paths) for stage, paths in PUBLIC_STAGE_REFS.items()}
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for stage in ("analysis", "modeling", "implementation", "paper"):
                route = build_route(root, stage, "")
                with self.subTest(stage=stage):
                    self.assertEqual({item.path for item in route.load_now}, expected[stage])

    def test_material_routes_are_deferred_outside_analysis_and_modeling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = build_route(root, "analysis", "batch Math_Model corpus learning")
            paper = build_route(root, "paper", "batch Math_Model corpus learning")

        material_paths = set(MATERIAL_REFS.values())
        self.assertTrue(material_paths.issubset({item.path for item in analysis.load_now}))
        self.assertTrue(material_paths.isdisjoint({item.path for item in paper.load_now}))
        self.assertTrue(any("deferred until the owning stage" in note for note in paper.notes))

    def test_deep_lane_adds_validation_rules_only_to_modeling(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir(parents=True)
            (planning / "workflow_lane.md").write_text("Selected lane: **deep**\n", encoding="utf-8")
            analysis = build_route(root, "analysis", "")
            modeling = build_route(root, "modeling", "")

        self.assertNotIn("references/validation-patterns.md", {item.path for item in analysis.load_now})
        self.assertIn("references/validation-patterns.md", {item.path for item in modeling.load_now})

    def _live_registry(self) -> dict[str, object]:
        return json.loads(
            (SKILL_ROOT / "references" / "reference-registry.json").read_text(encoding="utf-8")
        )

    def _fixture(self, root: Path) -> Path:
        registry = self._live_registry()
        registry_path = root / "references" / "reference-registry.json"
        registry_path.parent.mkdir(parents=True)
        registry_path.write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
        caller_mentions: dict[str, set[str]] = {}
        test_paths: set[str] = set()
        for entry in registry["entries"]:
            path = root / entry["path"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("# Fixture\n", encoding="utf-8")
            for relative in entry["callers"]:
                caller_mentions.setdefault(relative, set()).add(entry["path"])
            test_paths.update(entry["tests"])
        for relative, mentions in caller_mentions.items():
            caller = root / relative
            caller.parent.mkdir(parents=True, exist_ok=True)
            caller.write_text("\n".join(sorted(mentions)) + "\n", encoding="utf-8")
        for relative in test_paths:
            test = root / relative
            test.parent.mkdir(parents=True, exist_ok=True)
            test.touch()
        return root


if __name__ == "__main__":
    unittest.main()
