import sys
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from knowledge_application_audit import _term_present  # noqa: E402


class KnowledgeApplicationSignalTests(unittest.TestCase):
    def test_method_signal_does_not_match_inside_an_unrelated_word(self) -> None:
        self.assertFalse(_term_present("this formulation is a modeling bridge", "ridge"))
        self.assertFalse(_term_present("the model uses forward propagation", "ode"))

    def test_method_signal_matches_a_standalone_term_or_phrase(self) -> None:
        self.assertTrue(_term_present("ridge regression is selected", "ridge"))
        self.assertTrue(_term_present("solve the ode with rk45", "ode"))
        self.assertTrue(_term_present("time-window routing", "time-window"))


if __name__ == "__main__":
    unittest.main()
