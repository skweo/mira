from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
GENERATOR = SKILL_ROOT / "scripts" / "paper_strategy.py"
GATE = SKILL_ROOT / "scripts" / "paper_strategy_gate.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class PaperStrategyTests(unittest.TestCase):
    def run_generator(self, root: Path, text: str) -> dict:
        planning = root / "planning"
        planning.mkdir(parents=True, exist_ok=True)
        (planning / "problem_analysis.md").write_text(text, encoding="utf-8")
        subprocess.run(
            [sys.executable, str(GENERATOR), "--root", str(root)],
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
        )
        return json.loads((planning / "paper_strategy.json").read_text(encoding="utf-8"))

    def write_valid_strategy(
        self,
        root: Path,
        primary: str = "decision-first",
        supporting: list[str] | None = None,
    ) -> dict:
        payload = self.run_generator(root, "优化决策、目标函数、约束与调度方案")
        if primary != payload["primary_architecture"]:
            subprocess.run(
                [sys.executable, str(GENERATOR), "--root", str(root), "--architecture", primary],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
            )
            payload = json.loads((root / "planning" / "paper_strategy.json").read_text(encoding="utf-8"))
        payload.update(
            {
                "status": "approved_for_draft",
                "supporting_architectures": supporting or [],
                "hybrid_reason": "用情景对照检验决策在扰动条件下是否仍然成立" if supporting else "",
                "architecture_rationale": "先明确可执行决策和约束，再用同一评价尺度比较方案，最后给出稳健边界。",
                "one_sentence_thesis": "在满足资源与时序约束的前提下，分层决策模型能够降低总成本并保持扰动下的可行性。",
                "core_contributions": [
                    {"id": "C1", "claim": "重构决策变量与约束关系", "evidence": ["planning/modeling_plan.md"], "boundary": "适用于题设资源上限"},
                    {"id": "C2", "claim": "识别稳健方案的切换阈值", "evidence": ["results/tables/sensitivity.csv"], "boundary": "仅覆盖已计算情景"},
                ],
                "deleted_or_merged_sections": [
                    {"section": "独立的模型优缺点套话章节", "decision": "merged", "reason": "局限与适用边界并入对应证据段，避免脱离结果重复评价"}
                ],
                "paragraph_rhythm": {
                    "default_pattern": ["claim", "mathematical reason", "evidence", "decision implication"],
                    "variation_rules": ["证明段使用条件到命题到边界，结果段使用比较到解释到限制"],
                },
                "terminology_boundaries": [
                    {"term": "最优", "use": "仅用于有证书的求解范围", "avoid": "把启发式最好值称为全局最优"},
                    {"term": "稳健", "use": "通过既定扰动集验证", "avoid": "泛指结果看起来稳定"},
                ],
            }
        )
        for index, section in enumerate(payload["section_plan"], start=1):
            section["claim"] = f"第{index}个论证节点给出可核验的题目结论"
            section["evidence"] = [f"results/evidence_{index}.json"]
            section["keep_reason"] = "该节点承接前置条件并为后续结论提供必要证据"
        path = root / "planning" / "paper_strategy.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return payload

    def run_gate(self, root: Path, stage: str = "plan") -> tuple[subprocess.CompletedProcess[str], dict]:
        report = root / "checks" / "paper_strategy_report.json"
        result = subprocess.run(
            [
                sys.executable,
                str(GATE),
                "--root",
                str(root),
                "--stage",
                stage,
                "--write-json",
                str(report),
            ],
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
        )
        return result, json.loads(report.read_text(encoding="utf-8"))

    def test_problem_signals_produce_distinct_architectures(self) -> None:
        cases = {
            "mechanism-first": "根据守恒关系建立微分方程，分析传热机理、动力学和状态空间。",
            "decision-first": "建立调度优化模型，定义目标函数、资源约束、路径分配和选址决策。",
            "evidence-first": "利用观测数据完成回归预测、统计识别、残差分析和分类评价。",
            "theorem-first": "证明命题与引理，给出充分条件、必要条件、收敛性及上下界。",
            "scenario-first": "设计蒙特卡洛仿真与政策干预情景，比较风险和反事实结果。",
        }
        observed: set[str] = set()
        for expected, text in cases.items():
            with self.subTest(expected=expected), tempfile.TemporaryDirectory() as temp_dir:
                payload = self.run_generator(Path(temp_dir), text)
                self.assertEqual(payload["primary_architecture"], expected)
                observed.add(payload["primary_architecture"])
        self.assertEqual(len(observed), 5)

    def test_architecture_override_regenerates_owned_fields_and_preserves_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = self.write_valid_strategy(root, primary="decision-first")
            original_thesis = payload["one_sentence_thesis"]
            decision_only = next(item for item in payload["section_plan"] if item["role"] == "decision")
            decision_only["claim"] = "human-authored decision claim"
            shared = next(item for item in payload["section_plan"] if item["role"] == "foundation")
            shared["claim"] = "human-authored foundation claim"
            (root / "planning" / "paper_strategy.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            subprocess.run(
                [sys.executable, str(GENERATOR), "--root", str(root), "--architecture", "mechanism-first"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
            )
            updated = json.loads((root / "planning" / "paper_strategy.json").read_text(encoding="utf-8"))

            self.assertEqual(updated["primary_architecture"], "mechanism-first")
            self.assertEqual(updated["dominant_explanation_mode"], "causal-mechanistic")
            self.assertEqual(updated["status"], "draft")
            self.assertEqual(updated["architecture_rationale"], "")
            self.assertEqual(updated["one_sentence_thesis"], original_thesis)
            migrated = next(item for item in updated["section_plan"] if item["role"] == "foundation")
            self.assertEqual(migrated["claim"], "human-authored foundation claim")
            transition = updated["architecture_transition_history"][-1]
            self.assertEqual(transition["from_architecture"], "decision-first")
            self.assertEqual(transition["to_architecture"], "mechanism-first")
            archived_claims = {item.get("claim") for item in transition["unmapped_annotated_sections"]}
            self.assertIn("human-authored decision claim", archived_claims)

    def test_universal_skeleton_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = self.write_valid_strategy(root, primary="mechanism-first")
            for section in payload["section_plan"]:
                section["role"] = "question_answer"
            (root / "planning" / "paper_strategy.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result, report = self.run_gate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("universal_skeleton", {item["axis"] for item in report["findings"]})

    def test_internal_agent_language_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = self.write_valid_strategy(root)
            paper = root / "paper" / "main.tex"
            paper.parent.mkdir(parents=True)
            body = "\n".join(
                f"\\section{{{item['title']}}}\n本节给出题目证据与解释。" for item in payload["section_plan"]
            )
            paper.write_text(body + "\nMira gate PASS 后进入本轮优化。\n", encoding="utf-8")
            result, report = self.run_gate(root, stage="draft")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("internal_language_leak", {item["axis"] for item in report["findings"]})

    def test_reasoned_hybrid_architecture_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.write_valid_strategy(root, primary="decision-first", supporting=["scenario-first"])
            result, report = self.run_gate(root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["verdict"], "PASS")

    def test_dependency_that_points_forward_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            payload = self.write_valid_strategy(root)
            payload["section_plan"][2]["depends_on"] = [payload["section_plan"][-1]["id"]]
            (root / "planning" / "paper_strategy.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
            result, report = self.run_gate(root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("argument_dependency", {item["axis"] for item in report["findings"]})

    def test_command_profiles_route_strategy_gate(self) -> None:
        for phase in ("paper", "draft_gate"):
            result = subprocess.run(
                [sys.executable, str(SKILL_ROOT / "scripts" / "command_profiles.py"), "--phase", phase, "--output-level", "contest_final", "--json"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
            )
            commands = json.loads(result.stdout)["commands"]
            self.assertTrue(any("paper_strategy_gate.py" in item for item in commands), phase)

        for phase in ("verify", "iteration"):
            result = subprocess.run(
                [sys.executable, str(SKILL_ROOT / "scripts" / "command_profiles.py"), "--phase", phase, "--output-level", "contest_final", "--json"],
                check=True,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env=ENV,
            )
            commands = json.loads(result.stdout)["commands"]
            self.assertGreaterEqual(len(commands), 3, phase)
            self.assertLessEqual(len(commands), 4, phase)
            self.assertTrue(any("contest_final_pipeline.py" in item for item in commands), phase)


if __name__ == "__main__":
    unittest.main()
