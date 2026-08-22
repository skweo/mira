import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from mira_state import MiraState  # noqa: E402


def arguments(root: Path, *, allow_built: bool = False, phase: str = "final") -> argparse.Namespace:
    return argparse.Namespace(
        root=str(root),
        write=False,
        write_report=None,
        check=True,
        phase=phase,
        output_level="contest_final",
        allow_built_manifest=allow_built,
    )


class MiraStateTests(unittest.TestCase):
    def test_explanatory_blocker_word_is_not_a_control_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir()
            (planning / "delivery_brief.md").write_text(
                "Any unresolved hard blocker prevents delivery.\n",
                encoding="utf-8",
            )

            state = MiraState(arguments(root, phase="1"))
            state._scan_markers()

            self.assertEqual(state.markers, [])

    def test_legacy_blocker_marker_does_not_create_a_stage_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir()
            (planning / "modeling_plan.md").write_text(
                "[BLOCKER] Search range has no certificate.\n",
                encoding="utf-8",
            )

            state = MiraState(arguments(root, phase="1"))
            state._scan_markers()

            self.assertEqual(state.markers, [])

    def test_requires_user_decision_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            planning = root / "planning"
            planning.mkdir()
            (planning / "problem_analysis.md").write_text(
                "[REQUIRES_USER_DECISION] Official statement leaves the unit undefined.\n",
                encoding="utf-8",
            )

            state = MiraState(arguments(root, phase="analysis"))
            state._scan_markers()

            self.assertEqual(len(state.markers), 1)
            self.assertEqual(state.markers[0].type, "requires_user_decision")

    def test_normal_final_check_rejects_built_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_manifest(root, complete=True)

            state = MiraState(arguments(root, allow_built=False))
            state._check_final_delivery_manifest()

            self.assertEqual(len(state.markers), 1)
            self.assertIn("not READY", state.markers[0].message)

    def test_internal_final_check_accepts_only_complete_built_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self._write_manifest(root, complete=True)
            state = MiraState(arguments(root, allow_built=True))
            state._check_final_delivery_manifest()
            self.assertEqual(state.markers, [])

            self._write_manifest(root, complete=False)
            state = MiraState(arguments(root, allow_built=True))
            state._check_final_delivery_manifest()
            self.assertEqual(len(state.markers), 1)
            self.assertIn("incomplete", state.markers[0].message)

    @staticmethod
    def _write_manifest(root: Path, *, complete: bool) -> None:
        path = root / "planning" / "delivery_manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "status": "BUILT",
            "batch_id": "batch-1",
            "build": {"status": "PASS", "returncode": 0},
            "pdf": {"sha256": "abc" if complete else ""},
            "audit": {"status": "NOT_RUN"},
        }
        path.write_text(json.dumps(payload), encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
