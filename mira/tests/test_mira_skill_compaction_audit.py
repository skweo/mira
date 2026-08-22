from __future__ import annotations

import sys
import unittest
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from mira_skill_compaction_audit import mentioned_script_names  # noqa: E402


class MentionedScriptNamesTests(unittest.TestCase):
    def test_retired_legacy_paper_text_gate_stays_removed(self) -> None:
        self.assertFalse((SCRIPTS / "check_paper_text.py").exists())

    def test_retired_unrouted_flow_diagram_helper_stays_removed(self) -> None:
        self.assertFalse((SCRIPTS / "flow_diagram_style.py").exists())

    def test_counts_existing_local_modules_imported_without_py_suffix(self) -> None:
        text = """
from paper_scope import find_marker_page
import delivery_contract as contract, visual_style
import json
from missing_helper import value
"""

        names = mentioned_script_names(
            text,
            ["paper_scope.py", "delivery_contract.py", "visual_style.py"],
        )

        self.assertEqual(
            names,
            {"paper_scope.py", "delivery_contract.py", "visual_style.py"},
        )
        self.assertNotIn("json.py", names)
        self.assertNotIn("missing_helper.py", names)

    def test_preserves_explicit_script_mentions(self) -> None:
        names = mentioned_script_names(
            "Run scripts/route_references.py then quick_validate.py.",
            ["route_references.py", "quick_validate.py"],
        )

        self.assertEqual(names, {"route_references.py", "quick_validate.py"})


if __name__ == "__main__":
    unittest.main()
