from __future__ import annotations

import json
import os
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "professional_modeling_gate.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}
PARSE_NUMBERS = runpy.run_path(str(SCRIPT))["parse_numbers"]


class ProfessionalModelingGateTests(unittest.TestCase):
    def test_long_decimal_is_not_truncated(self) -> None:
        value = 412.47383768211023
        self.assertEqual(PARSE_NUMBERS(f"terminal_time_s={value}"), [value])

    def test_comma_grouped_decimal_is_parsed(self) -> None:
        self.assertEqual(PARSE_NUMBERS("population=1,234.56789"), [1234.56789])

    def make_project(self, root: Path) -> dict:
        paper = root / "paper" / "main.tex"
        paper.parent.mkdir(parents=True)
        paper.write_text(
            r"\section{问题四}\label{q4-model}由区间界证明全局最优值为 $13.66\,\mathrm{m}$。\cite{source1}"
            "\n" + r"\section{推广}\label{generalization}模型可迁移到具有相同几何约束的场景。",
            encoding="utf-8",
        )
        results = root / "results"
        results.mkdir()
        (results / "mechanism.txt").write_text("constraint mechanism", encoding="utf-8")
        (results / "validation.csv").write_text("metric,value\nobjective,13.66\n", encoding="utf-8")
        (results / "error.csv").write_text("metric,value\nrmse,0.001\n", encoding="utf-8")
        (results / "sensitivity.csv").write_text("parameter,change\na,0.01\n", encoding="utf-8")
        (results / "optimality.json").write_text(json.dumps({"lower": 13.659, "upper": 13.661}), encoding="utf-8")
        (results / "convergence.txt").write_text("gap converged below 0.002", encoding="utf-8")
        ledger = {"entries": [{"claim_id": "C-Q4-OPT", "metric": "objective", "value": 13.66}]}
        (root / "planning").mkdir()
        (root / "planning" / "result_ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
        (root / "planning" / "figure_evidence.json").write_text(
            json.dumps(
                {
                    "version": 1,
                    "figures": [
                        {
                            "claim_id": "C-Q4-OPT",
                            "key_values": [{"metric": "objective", "value": 13.66, "tolerance": 0.001}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        return {
            "version": 1,
            "symbol_definitions": [
                {"symbol": "L", "definition": "最小转弯空间长度", "unit": "m", "first_location": "问题四模型建立"}
            ],
            "questions": [
                {
                    "question_id": "Q4",
                    "mechanism_evidence": [{"form": "equation", "claim_id": "C-Q4-MECH", "source": "results/mechanism.txt"}],
                    "result_validation_evidence": [{"form": "table", "claim_id": "C-Q4-OPT", "source": "results/validation.csv"}],
                }
            ],
            "error_analysis": {
                "sources": [
                    {
                        "name": "离散误差",
                        "mechanism": "离散步长改变相切点定位精度",
                        "direction": "可能使所需空间长度轻微偏高",
                        "claim_id": "C-ERR-01",
                        "source": "results/error.csv",
                    }
                ],
                "residual_or_uncertainty": {"metric": "rmse", "value": 0.001, "source": "results/error.csv", "claim_id": "C-ERR-01"},
                "sensitivity_or_robustness": {
                    "method": "对几何间距执行正负百分之一扰动",
                    "parameter_range": "参数在基准值的正负百分之一内变化",
                    "finding": "最优空间长度变化小于允许误差范围",
                    "source": "results/sensitivity.csv",
                },
                "conclusion_impact": {"text": "误差不会改变可行性结论，但空间长度只保留到厘米精度。", "affected_claims": ["C-Q4-OPT"]},
            },
            "generalization": {
                "transferable_core": "几何递推、碰撞检测和区间认证可迁移到同类链式结构。",
                "assumptions_to_modify": "需要按照新结构修改节距、宽度和转向曲线连续性假设。",
                "applicability_boundaries": "仅适用于刚性连接、平面运动且连接间距已知的场景。",
                "new_scenario_validation": "应重新采集边界尺寸并执行全域扫描、相切残差和实测轨迹核验。",
                "source": "paper/main.tex#generalization",
            },
            "optimality_certificates": [
                {
                    "claim_id": "C-Q4-OPT",
                    "problem_type": "continuous",
                    "conclusion_scope": "global",
                    "certificate_type": "interval_bound",
                    "search_domain": {
                        "variables": [{"name": "L", "lower": 12.0, "upper": 15.0, "unit": "m"}],
                        "basis": "由结构总长、边界包络和可行构型的解析界共同确定搜索域。",
                        "boundary_checked": True,
                    },
                    "paper_wording": "在给定搜索域内获得全局最优值。",
                    "evidence": "results/optimality.json",
                    "convergence_evidence": "results/convergence.txt",
                }
            ],
            "numeric_bindings": [
                {
                    "metric": "objective",
                    "claim_id": "C-Q4-OPT",
                    "canonical_value": 13.66,
                    "tolerance": 0.001,
                    "consumers": [
                        {"kind": "ledger", "path": "planning/result_ledger.json", "json_pointer": "/entries/0/value", "value": 13.66},
                        {"kind": "paper", "path": "paper/main.tex", "value": 13.66},
                    ],
                }
            ],
            "reference_bindings": [
                {
                    "citation_key": "source1",
                    "claim_id": "C-Q4-MECH",
                    "supported_statement": "支持相切约束与几何边界的建模表达。",
                    "paper_location": "问题四模型建立",
                }
            ],
        }

    def run_gate(self, root: Path, contract: dict) -> tuple[subprocess.CompletedProcess[str], dict]:
        path = root / "planning" / "professional_modeling.json"
        path.write_text(json.dumps(contract, ensure_ascii=False), encoding="utf-8")
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "--root", str(root)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        report = json.loads((root / "checks" / "professional_modeling_report.json").read_text(encoding="utf-8"))
        return result, report

    def test_complete_professional_contract_passes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            result, report = self.run_gate(root, contract)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["verdict"], "PASS")

    def test_continuous_coarse_grid_cannot_claim_global_optimum(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            contract["optimality_certificates"][0]["certificate_type"] = "coarse_grid"
            result, report = self.run_gate(root, contract)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("unsupported_global", {item["code"] for item in report["findings"]})

    def test_cross_artifact_numeric_conflict_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            contract["numeric_bindings"][0]["consumers"][1]["value"] = 13.36
            result, report = self.run_gate(root, contract)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("conflict", {item["code"] for item in report["findings"]})

    def test_schema_v2_ledger_key_binding_is_stable_across_entry_order(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            ledger_path = root / "planning" / "result_ledger.json"
            ledger_path.write_text(
                json.dumps(
                    {
                        "schema_version": 2,
                        "entries": [
                            {"key": "q1.decoy", "value": 999},
                            {"key": "q4.objective", "value": 13.66},
                        ],
                    }
                ),
                encoding="utf-8",
            )
            contract["numeric_bindings"][0]["consumers"][0].pop("json_pointer")
            contract["numeric_bindings"][0]["consumers"][0]["ledger_key"] = "q4.objective"
            result, report = self.run_gate(root, contract)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(report["verdict"], "PASS")


if __name__ == "__main__":
    unittest.main()
