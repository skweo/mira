from __future__ import annotations

import argparse
import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from semantic_audit import SemanticAudit  # noqa: E402
from table_style_audit import collect_metrics, review  # noqa: E402
from plan_presentation_budget import detect_method_families  # noqa: E402


class PresentationBudgetDetectionTests(unittest.TestCase):
    def test_short_algorithm_acronyms_require_standalone_tokens(self) -> None:
        families = detect_method_families(
            "sample baseline data; dynamic programming and sensitivity validation"
        )

        self.assertIn("exact_dp", families)
        self.assertIn("validation_sensitivity", families)
        self.assertNotIn("heuristic_local_search", families)

    def test_explicit_sa_is_detected(self) -> None:
        self.assertIn("heuristic_local_search", detect_method_families("solver: SA; seed=7"))


class SemanticAuditContextTests(unittest.TestCase):
    def make_project(self, root: Path) -> None:
        for folder in ("planning", "paper", "results/tables", "results/audits", "results/logs"):
            (root / folder).mkdir(parents=True, exist_ok=True)
        frozen = {qid: {"objective": index} for index, qid in enumerate(("q1", "q2", "q3", "q4"), start=1)}
        (root / "results" / "frozen_numbers.json").write_text(json.dumps(frozen), encoding="utf-8")
        (root / "planning" / "modeling_plan.md").write_text(
            "Q1 使用精确二项枚举；Q2 完整枚举；Q3 采用动态规划；Q4 进行后验传播。",
            encoding="utf-8",
        )
        (root / "paper" / "main.tex").write_text("精确枚举和动态规划给出有限动作集内的最优解。", encoding="utf-8")
        self.write_csv(root / "results/tables/q1_asn_comparison.csv", [{"p": "0.1", "single": "22", "two_stage": "20"}])
        self.write_csv(
            root / "results/tables/baseline_comparison.csv",
            [{"question": "Q2", "case": "1", "baseline": "none", "strategy": "best"}],
        )
        self.write_csv(root / "results/tables/q3_enumeration_check.csv", [{"dp": "1", "enumeration": "1"}])
        self.write_csv(root / "results/tables/posterior_policy_frequency.csv", [{"question": "Q3", "probability": "0.8"}])
        ledger = {
            "entries": [
                {
                    "key": "q4.posterior",
                    "question": "Q4",
                    "evidence": ["results/tables/posterior_policy_frequency.csv"],
                }
            ]
        }
        (root / "planning/result_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")

    @staticmethod
    def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)

    @staticmethod
    def audit(root: Path) -> SemanticAudit:
        audit = SemanticAudit(argparse.Namespace(root=str(root), frozen=None, write_report=None))
        audit._load()
        audit._collect_metrics()
        audit._check_baselines_and_heuristics()
        return audit

    def test_generated_presentation_budget_does_not_create_heuristic_execution(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            (root / "planning/presentation_budget.md").write_text(
                "Method families: heuristic_local_search; heuristic validation needs convergence.",
                encoding="utf-8",
            )

            audit = self.audit(root)

            self.assertGreater(audit.metrics["heuristic_mentions_raw"], 0)
            self.assertEqual(audit.metrics["heuristic_terms"], 0)
            self.assertFalse(any(item.level == "FAIL" for item in audit.findings))
            self.assertTrue(all(audit.metrics["question_validation_evidence"].values()))

    def test_executed_heuristic_without_history_is_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            (root / "planning/modeling_plan.md").write_text("采用模拟退火算法求解，并输出最优方案。", encoding="utf-8")

            audit = self.audit(root)

            self.assertGreater(audit.metrics["heuristic_terms"], 0)
            self.assertTrue(
                any(item.level == "FAIL" and "convergence/history" in item.message for item in audit.findings)
            )

    def test_case_numbers_are_not_treated_as_question_ids(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            self.write_csv(
                root / "results/tables/baseline_comparison.csv",
                [{"case": "Q1", "baseline": "none", "strategy": "best"}],
            )

            audit = self.audit(root)

            self.assertNotIn("results/tables/baseline_comparison.csv", audit.metrics["question_validation_evidence"]["Q1"])


class TableHeaderAuditTests(unittest.TestCase):
    @staticmethod
    def args(root: Path) -> argparse.Namespace:
        return argparse.Namespace(root=str(root), paper=None, write_report=None, write_json=None)

    def test_engineering_token_outside_header_is_ignored(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text(
                r"""\usepackage{booktabs}
\begin{table}\begin{tabular}{cc}\toprule
节点 & 成本 \\
\midrule
node-1 & 2 \\
\bottomrule\end{tabular}\end{table}
\label{tab:q3-node}
""",
                encoding="utf-8",
            )

            metrics = collect_metrics(root, self.args(root))

            self.assertEqual(metrics["raw_header_terms"], 0)
            self.assertFalse(any(item.axis == "raw_table_headers" for item in review(metrics)))

    def test_engineering_token_in_header_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "paper").mkdir()
            (root / "paper/main.tex").write_text(
                r"""\usepackage{booktabs}
\begin{table}\begin{tabular}{cc}\toprule
node & cost \\
\midrule
1 & 2 \\
\bottomrule\end{tabular}\end{table}
""",
                encoding="utf-8",
            )

            metrics = collect_metrics(root, self.args(root))

            self.assertEqual(metrics["raw_header_hits"], ["node"])
            self.assertTrue(any(item.axis == "raw_table_headers" for item in review(metrics)))


if __name__ == "__main__":
    unittest.main()
