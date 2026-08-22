from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))


def load_module(name: str):
    path = SCRIPTS / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


class StatisticalEvidenceGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("statistical_evidence_gate")

    def test_deterministic_analysis_does_not_require_significance_testing(self) -> None:
        contract = {
            "schema_version": 1,
            "analyses": [
                {
                    "analysis_id": "ANA-Q1-GEOMETRY",
                    "claim_id": "CLM-Q1-FEASIBLE",
                    "analysis_mode": "deterministic",
                    "analysis_unit": "bench segment",
                    "n_definition": "all 223 linked segments",
                    "independent_n": "not_applicable",
                    "repeat_structure": "not_applicable",
                    "effect_size": "not_applicable",
                    "interval": "not_applicable",
                    "test": "not_applicable",
                    "multiplicity": "not_applicable",
                    "missing_data": "not_applicable",
                    "not_applicable_reason": "The claim follows from deterministic geometry and residual checks.",
                    "evidence_artifacts": ["results/tables/q1_residuals.csv"],
                }
            ],
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            artifact = root / "results" / "tables" / "q1_residuals.csv"
            artifact.parent.mkdir(parents=True)
            artifact.write_text("max_residual\n0.0001\n", encoding="utf-8")
            result = self.module.evaluate_contract(root, contract, paper_text="")
        self.assertEqual(result["verdict"], "PASS", result["findings"])

    def test_inferential_analysis_rejects_pseudoreplication_and_missing_contracts(self) -> None:
        contract = {
            "schema_version": 1,
            "analyses": [
                {
                    "analysis_id": "ANA-Q2-TEST",
                    "claim_id": "CLM-Q2-EFFECT",
                    "analysis_mode": "inferential",
                    "analysis_unit": "time point",
                    "n_definition": "120 time points from 6 devices",
                    "independent_n": 6,
                    "observed_n": 120,
                    "repeat_structure": {"type": "none"},
                    "effect_size": {},
                    "interval": {},
                    "test": {"name": "t-test"},
                    "multiplicity": {},
                    "missing_data": {"handling": "dropna"},
                    "evidence_artifacts": [],
                }
            ],
        }
        result = self.module.evaluate_contract(Path.cwd(), contract, paper_text="")
        codes = {item["code"] for item in result["findings"] if item["level"] == "FAIL"}
        self.assertIn("pseudoreplication", codes)
        self.assertIn("effect_size", codes)
        self.assertIn("interval", codes)
        self.assertIn("multiplicity", codes)
        self.assertIn("missing_data_counts", codes)

    def test_significance_difference_fallacy_is_flagged(self) -> None:
        contract = {"schema_version": 1, "analyses": []}
        text = "方案 A 显著，而方案 B 不显著，因此 A 与 B 之间存在显著差异。"
        result = self.module.evaluate_contract(Path.cwd(), contract, paper_text=text)
        self.assertTrue(
            any(item["code"] == "significance_difference_fallacy" for item in result["findings"])
        )

    def test_inferential_analysis_requires_observed_n_and_assumptions(self) -> None:
        contract = {
            "schema_version": 1,
            "analyses": [
                {
                    "analysis_id": "ANA-Q2-INFERENCE",
                    "claim_id": "CLM-Q2-EFFECT",
                    "analysis_mode": "inferential",
                    "analysis_unit": "device",
                    "n_definition": "six independently sampled devices",
                    "independent_n": 6,
                    "repeat_structure": {"type": "independent"},
                    "effect_size": {"name": "mean_difference", "value": 0.2},
                    "interval": {"level": 0.95, "lower": 0.1, "upper": 0.3},
                    "test": {"name": "Welch t-test"},
                    "multiplicity": {"method": "not_applicable", "reason": "one planned contrast"},
                    "missing_data": {"handling": "none"},
                    "evidence_artifacts": ["results/tables/q2_test.csv"],
                }
            ],
        }
        result = self.module.evaluate_contract(Path.cwd(), contract, paper_text="")
        codes = {item["code"] for item in result["findings"] if item["level"] == "FAIL"}
        self.assertIn("observed_n", codes)
        self.assertIn("test_assumptions", codes)

    def test_simulation_requires_design_convergence_and_claim_domain(self) -> None:
        contract = {
            "schema_version": 1,
            "analyses": [
                {
                    "analysis_id": "ANA-Q3-SIM",
                    "claim_id": "CLM-Q3-RISK",
                    "analysis_mode": "simulation",
                    "analysis_unit": "scenario",
                    "n_definition": "10000 Monte Carlo scenarios",
                    "simulation_repetitions": 10000,
                    "seed": 42,
                    "interval": {"level": 0.95, "method": "empirical quantile"},
                    "evidence_artifacts": ["results/tables/q3_simulation.csv"],
                }
            ],
        }
        result = self.module.evaluate_contract(Path.cwd(), contract, paper_text="")
        codes = {item["code"] for item in result["findings"] if item["level"] == "FAIL"}
        self.assertIn("scenario_design", codes)
        self.assertIn("convergence_evidence", codes)
        self.assertIn("claim_domain", codes)

    def test_deterministic_analysis_rejects_partial_not_applicable_contract(self) -> None:
        contract = {
            "schema_version": 1,
            "analyses": [
                {
                    "analysis_id": "ANA-Q1-PARTIAL",
                    "claim_id": "CLM-Q1-BOUNDARY",
                    "analysis_mode": "deterministic",
                    "analysis_unit": "boundary point",
                    "n_definition": "all certified boundary points",
                    "independent_n": "not_applicable",
                    "not_applicable_reason": "The claim is certified by deterministic equations and residual checks.",
                    "evidence_artifacts": ["results/tables/q1_boundary.csv"],
                }
            ],
        }
        result = self.module.evaluate_contract(Path.cwd(), contract, paper_text="")
        self.assertTrue(
            any(item["code"] == "deterministic_na_contract" for item in result["findings"])
        )


class FigureSourcePreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("figure_source_preflight")

    def test_python_claim_figure_with_vector_and_300_dpi_export_passes(self) -> None:
        source = '''
import matplotlib.pyplot as plt
plt.rcParams.update({"font.size": 8, "pdf.fonttype": 42})
fig, ax = plt.subplots(figsize=(6.8, 4.2))
ax.plot(x, y, color="#4F7C82")
fig.savefig("figure.png", dpi=300, bbox_inches="tight")
fig.savefig("figure.pdf", bbox_inches="tight")
'''
        payload = self.module.evaluate_source(source, "python")
        self.assertEqual(payload["verdict"], "PASS", payload["findings"])

    def test_matlab_jet_low_dpi_and_missing_vector_export_fail(self) -> None:
        source = '''
fig = figure('Color','w');
surf(X,Y,Z);
colormap(jet(256));
exportgraphics(fig, 'figure.png', 'Resolution', 96);
'''
        payload = self.module.evaluate_source(source, "matlab")
        codes = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("unsafe_colormap", codes)
        self.assertIn("low_raster_dpi", codes)
        self.assertIn("missing_vector_export", codes)

    def test_matlab_log_transform_requires_positive_domain_guard(self) -> None:
        source = '''
fig = figure('Color','w');
semilogy(x, y);
exportgraphics(fig, 'figure.png', 'Resolution', 300);
exportgraphics(fig, 'figure.pdf', 'ContentType', 'vector');
'''
        payload = self.module.evaluate_source(source, "matlab")
        self.assertTrue(any(item["code"] == "unguarded_log_domain" for item in payload["findings"]))

    def test_cli_audits_sources_named_by_provenance_records(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "code" / "python" / "plot.py"
            source.parent.mkdir(parents=True)
            source.write_text(
                "import matplotlib.pyplot as plt\n"
                "plt.rcParams.update({'font.size': 8, 'pdf.fonttype': 42})\n"
                "fig, ax = plt.subplots()\nax.plot(x, y)\n"
                "fig.savefig('f.png', dpi=300)\nfig.savefig('f.pdf')\n",
                encoding="utf-8",
            )
            provenance = root / "results" / "figures_data" / "f_provenance.json"
            provenance.parent.mkdir(parents=True)
            provenance.write_text(
                json.dumps(
                    {
                        "figure_id": "fig_f",
                        "source": {"source_code": {"path": "code/python/plot.py"}},
                        "route": {"actual": {"backend": "python"}},
                    }
                ),
                encoding="utf-8",
            )
            result = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "figure_source_preflight.py"),
                    "--root",
                    str(root),
                    "--write-json",
                    "checks/figure_source_preflight.json",
                    "--write-report",
                    "checks/figure_source_preflight.md",
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            payload = json.loads(
                (root / "checks" / "figure_source_preflight.json").read_text(encoding="utf-8")
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["sources_audited"], 1)

    def test_project_audit_fails_when_no_figure_sources_are_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            payload = self.module.audit_project(Path(temp_dir), [])
        self.assertEqual(payload["verdict"], "FAIL")
        self.assertTrue(any(item["code"] == "no_sources_audited" for item in payload["findings"]))

    def test_malformed_provenance_is_not_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            provenance = root / "results" / "figures_data" / "bad_provenance.json"
            provenance.parent.mkdir(parents=True)
            provenance.write_text(
                json.dumps(
                    {
                        "figure_id": "fig_bad",
                        "source": {"source_code": {}},
                        "route": {"actual": {"backend": "python"}},
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [sys.executable, str(SCRIPTS / "figure_source_preflight.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            payload = json.loads(
                (root / "checks" / "figure_source_preflight.json").read_text(encoding="utf-8")
            )
        self.assertNotEqual(completed.returncode, 0)
        self.assertTrue(any(item["code"] == "provenance_source_path" for item in payload["findings"]))


class ReferenceAuthenticityGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("reference_authenticity_gate")

    def base_reference(self) -> dict:
        return {
            "reference_id": "REF-01",
            "citation_key": "smith2024",
            "reference_type": "journal_article",
            "cited_metadata": {
                "authors": ["Smith J", "Lee K"],
                "title": "Robust optimization under uncertainty",
                "year": 2024,
                "journal": "Operations Research Letters",
                "volume": "52",
                "issue": "2",
                "pages": "100-112",
                "doi": "10.1000/example.1",
            },
            "in_text_locations": ["paper/main.tex:142"],
            "supported_claim_ids": ["CLM-Q2-ROBUST"],
        }

    @staticmethod
    def create_bindings(root: Path, *claim_ids: str) -> dict:
        paper = root / "paper" / "main.tex"
        paper.parent.mkdir(parents=True, exist_ok=True)
        paper.write_text(
            "\n".join(f"paper line {index}" for index in range(1, 181)) + "\n",
            encoding="utf-8",
        )
        return {
            "schema_version": 2,
            "entries": [{"claim_id": claim_id} for claim_id in claim_ids],
        }

    def test_matching_authoritative_metadata_is_verified(self) -> None:
        row = self.base_reference()
        row["verification_sources"] = [
            {
                "source": "crossref",
                "status": "matched",
                "locator": "https://doi.org/10.1000/example.1",
                "metadata": dict(row["cited_metadata"]),
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "VERIFIED")
        self.assertEqual(payload["verdict"], "PASS")

    def test_offline_lookup_remains_unverifiable(self) -> None:
        row = self.base_reference()
        row["verification_sources"] = [
            {"source": "crossref", "status": "offline", "locator": "", "metadata": {}}
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "FAIL")

    def test_locally_anchored_chinese_standard_can_be_local_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            scan = root / "materials" / "gb-standard.pdf"
            scan.parent.mkdir(parents=True)
            scan.write_bytes(b"local standard evidence")
            row = {
                "reference_id": "REF-GB",
                "citation_key": "gb2020",
                "reference_type": "standard",
                "cited_metadata": {"authors": ["国家标准化管理委员会"], "title": "示例国家标准", "year": 2020},
                "in_text_locations": ["paper/main.tex:80"],
                "supported_claim_ids": ["CLM-Q1-PARAMETER"],
                "verification_sources": [
                    {
                        "source": "local_authoritative_copy",
                        "status": "local",
                        "locator": "materials/gb-standard.pdf#page=1",
                        "authority": "National standardization authority",
                        "passage": "The first page states the parameter definition used by the model.",
                        "metadata": {
                            "authors": ["国家标准化管理委员会"],
                            "title": "示例国家标准",
                            "year": 2020,
                        },
                    }
                ],
            }
            ledger = self.create_bindings(root, "CLM-Q1-PARAMETER")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "LOCAL_ONLY")
        self.assertEqual(payload["verdict"], "PASS")

    def test_doi_or_title_conflict_is_a_hard_failure(self) -> None:
        row = self.base_reference()
        row["verification_sources"] = [
            {
                "source": "crossref",
                "status": "matched",
                "locator": "https://doi.org/10.1000/different",
                "metadata": {
                    "authors": ["Other A"],
                    "title": "A completely different paper",
                    "year": 2019,
                    "doi": "10.1000/different",
                },
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "CONFLICT")
        self.assertEqual(payload["verdict"], "FAIL")

    def test_empty_authoritative_metadata_cannot_be_verified(self) -> None:
        row = self.base_reference()
        row["verification_sources"] = [
            {
                "source": "crossref",
                "status": "matched",
                "locator": "https://doi.org/10.1000/example.1",
                "metadata": {},
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "UNVERIFIABLE")
        self.assertEqual(payload["verdict"], "FAIL")

    def test_local_copy_requires_authority_passage_and_metadata(self) -> None:
        row = self.base_reference()
        row["reference_type"] = "standard"
        row["verification_sources"] = [
            {
                "source": "local_authoritative_copy",
                "status": "local",
                "locator": "materials/source.pdf#page=1",
                "metadata": {},
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            source = root / "materials" / "source.pdf"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"not enough to establish authority")
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        self.assertEqual(payload["references"][0]["status"], "UNVERIFIABLE")

    def test_in_text_location_and_claim_binding_must_resolve(self) -> None:
        row = self.base_reference()
        row["in_text_locations"] = ["paper/main.tex:999"]
        row["supported_claim_ids"] = ["CLM-NOT-IN-LEDGER"]
        row["verification_sources"] = [
            {
                "source": "crossref",
                "status": "matched",
                "locator": "https://doi.org/10.1000/example.1",
                "metadata": dict(row["cited_metadata"]),
            }
        ]
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            ledger = self.create_bindings(root, "CLM-Q2-ROBUST")
            payload = self.module.evaluate_references(root, {"schema_version": 1, "references": [row]}, ledger)
        codes = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("in_text_location", codes)
        self.assertIn("unknown_supported_claim", codes)


class MaterialAnchorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("material_anchor_index")

    def test_page_and_paragraph_anchors_preserve_exact_source_text(self) -> None:
        text = "# attachment.pdf\n\n## Page 1\n\n第一段说明决策变量。\n\n第二段给出约束条件。\n\n## Page 2\n\n第三段给出数据范围。\n"
        index = self.module.index_text("attachment.pdf", "materials/texts/attachment.md", text)
        self.assertEqual(index["blocks"][0]["locator"], "attachment.pdf#page=1&paragraph=1")
        contract = {
            "schema_version": 1,
            "claims": [
                {
                    "claim_id": "SRC-Q1-CONSTRAINT",
                    "source_path": "materials/texts/attachment.md",
                    "locator": "attachment.pdf#page=1&paragraph=2",
                    "basis": "quoted",
                    "excerpt": "第二段给出约束条件。",
                    "reasoning": "",
                }
            ],
        }
        payload = self.module.validate_claim_anchors(index, contract)
        self.assertEqual(payload["verdict"], "PASS", payload["findings"])

    def test_inference_requires_reasoning_and_cannot_be_labeled_as_quote(self) -> None:
        text = "## Page 1\n\n材料仅给出两组观测值。\n"
        index = self.module.index_text("data.pdf", "materials/texts/data.md", text)
        contract = {
            "schema_version": 1,
            "claims": [
                {
                    "claim_id": "SRC-Q1-INFERENCE",
                    "source_path": "materials/texts/data.md",
                    "locator": "data.pdf#page=1&paragraph=1",
                    "basis": "inferred",
                    "excerpt": "材料证明两组具有因果关系。",
                    "reasoning": "",
                }
            ],
        }
        payload = self.module.validate_claim_anchors(index, contract)
        codes = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("inference_reasoning", codes)
        self.assertIn("inference_excerpt", codes)


class ContestEvidenceChainGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.module = load_module("contest_evidence_chain_gate")

    @staticmethod
    def ledger(*claim_ids: str) -> dict:
        return {
            "schema_version": 2,
            "entries": [
                {
                    "claim_id": claim_id,
                    "centrality": "central",
                    "final_claim": True,
                    "question": "Q1",
                }
                for claim_id in claim_ids
            ],
        }

    @staticmethod
    def chain(claim_id: str) -> dict:
        return {
            "chain_id": f"CHAIN-{claim_id}",
            "claim_id": claim_id,
            "decision_value": "This result determines the feasible operating boundary.",
            "scope": "Valid under the stated geometry and tolerance assumptions.",
            "evidence_gap": "none",
            "stages": {
                "problem_interpretation": {
                    "statement": "Translate the requested boundary into a geometric constraint.",
                    "artifact": "materials/problem.md",
                    "locator": "materials/problem.md#paragraph=2",
                },
                "model_derivation": {
                    "statement": "Derive the boundary equation from the linked-segment geometry.",
                    "artifact": "paper/main.tex",
                    "locator": "paper/main.tex:120",
                },
                "result_evidence": {
                    "statement": "The certified boundary is reported in the result table.",
                    "artifact": "results/tables/q1_boundary.csv",
                    "locator": "results/tables/q1_boundary.csv:2",
                },
                "validation": {
                    "statement": "Independent residual checks remain below tolerance.",
                    "artifact": "results/tables/q1_residuals.csv",
                    "locator": "results/tables/q1_residuals.csv:2",
                },
                "paper_conclusion": {
                    "statement": "The conclusion states the boundary and its valid scope.",
                    "artifact": "paper/main.tex",
                    "locator": "paper/main.tex:410",
                },
            },
        }

    @staticmethod
    def create_artifacts(root: Path) -> None:
        problem = root / "materials" / "problem.md"
        problem.parent.mkdir(parents=True, exist_ok=True)
        problem.write_text("first paragraph\n\nsecond paragraph\n", encoding="utf-8")
        paper = root / "paper" / "main.tex"
        paper.parent.mkdir(parents=True, exist_ok=True)
        paper.write_text(
            "\n".join(f"paper line {index}" for index in range(1, 421)) + "\n",
            encoding="utf-8",
        )
        for relative in ("results/tables/q1_boundary.csv", "results/tables/q1_residuals.csv"):
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("metric,value\nresidual,0.0001\n", encoding="utf-8")

    def test_complete_chain_covers_every_central_ledger_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_artifacts(root)
            payload = self.module.evaluate_contract(
                root,
                {"schema_version": 1, "chains": [self.chain("CLM-Q1-BOUNDARY")]},
                self.ledger("CLM-Q1-BOUNDARY"),
            )
        self.assertEqual(payload["verdict"], "PASS", payload["findings"])
        self.assertEqual(payload["metrics"]["central_claims_covered"], 1)

    def test_ledger_central_claim_without_chain_is_a_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_artifacts(root)
            payload = self.module.evaluate_contract(
                root,
                {"schema_version": 1, "chains": [self.chain("CLM-Q1-BOUNDARY")]},
                self.ledger("CLM-Q1-BOUNDARY", "CLM-Q2-OPTIMUM"),
            )
        failures = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("missing_central_claim_chain", failures)

    def test_missing_stage_artifact_and_unanchored_locator_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_artifacts(root)
            chain = self.chain("CLM-Q1-BOUNDARY")
            chain["stages"]["validation"]["artifact"] = "results/tables/missing.csv"
            chain["stages"]["paper_conclusion"]["locator"] = "conclusion"
            payload = self.module.evaluate_contract(
                root,
                {"schema_version": 1, "chains": [chain]},
                self.ledger("CLM-Q1-BOUNDARY"),
            )
        failures = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("missing_stage_artifact", failures)
        self.assertIn("unresolved_stage_locator", failures)

    def test_locator_line_must_exist_in_the_stage_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.create_artifacts(root)
            chain = self.chain("CLM-Q1-BOUNDARY")
            chain["stages"]["paper_conclusion"]["locator"] = "paper/main.tex:999"
            payload = self.module.evaluate_contract(
                root,
                {"schema_version": 1, "chains": [chain]},
                self.ledger("CLM-Q1-BOUNDARY"),
            )
        failures = {item["code"] for item in payload["findings"] if item["level"] == "FAIL"}
        self.assertIn("unresolved_stage_locator", failures)


class NatureWorkflowIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.profiles = load_module("command_profiles")

    def test_specialized_quality_checks_stay_inside_final_pipeline(self) -> None:
        for stage in ("analysis", "modeling", "implementation", "paper"):
            commands = self.profiles.commands_for_phase(stage)
            self.assertGreaterEqual(len(commands), 3, stage)
            self.assertLessEqual(len(commands), 4, stage)

        pipeline_source = (SCRIPTS / "contest_final_pipeline.py").read_text(encoding="utf-8")
        for script in (
            "material_anchor_index.py",
            "statistical_evidence_gate.py",
            "figure_source_preflight.py",
            "reference_authenticity_gate.py",
            "contest_evidence_chain_gate.py",
        ):
            self.assertIn(f'"{script}"', pipeline_source)

    def test_evidence_authenticity_rules_are_routed_to_relevant_phases(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            expected = {
                "problem": True,
                "modeling": True,
                "results": False,
                "figures": False,
                "paper": True,
                "verify": True,
            }
            for phase, should_route in expected.items():
                completed = subprocess.run(
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
                paths = {item["path"] for item in json.loads(completed.stdout)["load_now"]}
                if should_route:
                    self.assertIn("references/evidence-authenticity-rules.md", paths, phase)
                else:
                    self.assertNotIn("references/evidence-authenticity-rules.md", paths, phase)

    def test_material_anchor_cli_uses_the_standard_extracted_materials_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            extracted = root / "materials" / "extracted" / "attachment.md"
            extracted.parent.mkdir(parents=True)
            extracted.write_text("## Page 1\n\nA contest constraint.\n", encoding="utf-8")
            contract = root / "planning" / "material_claim_anchors.json"
            contract.parent.mkdir(parents=True)
            contract.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "claims": [
                            {
                                "claim_id": "SRC-Q1-CONSTRAINT",
                                "source_path": "materials/extracted/attachment.md",
                                "locator": "attachment#page=1&paragraph=1",
                                "basis": "quoted",
                                "excerpt": "A contest constraint.",
                                "reasoning": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "material_anchor_index.py"),
                    "--root",
                    str(root),
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            payload = json.loads(
                (root / "checks" / "material_anchor_report.json").read_text(encoding="utf-8")
            )
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertEqual(payload["sources_indexed"], 1)

    def test_project_initializer_creates_quality_contract_templates(self) -> None:
        expected_lists = {
            "statistical_evidence.json": "analyses",
            "reference_authenticity.json": "references",
            "material_claim_anchors.json": "claims",
            "contest_evidence_chains.json": "chains",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    str(SCRIPTS / "init_math_modeling_project.py"),
                    temp_dir,
                ],
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            root = Path(temp_dir)
            payloads = {
                name: json.loads((root / "planning" / name).read_text(encoding="utf-8"))
                for name in expected_lists
            }
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        for name, list_key in expected_lists.items():
            self.assertEqual(payloads[name]["schema_version"], 1, name)
            self.assertIsInstance(payloads[name][list_key], list, name)
            self.assertIn("field_guide", payloads[name], name)


class ProjectPathContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.provenance = load_module("figure_provenance")

    def test_figure_provenance_rejects_source_outside_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            workspace = Path(temp_dir)
            root = workspace / "project"
            root.mkdir()
            outside_source = workspace / "outside.py"
            outside_source.write_text("print('outside')\n", encoding="utf-8")
            artifacts = {}
            for name in ("input.csv", "figure.png", "figure.pdf"):
                path = root / name
                path.write_bytes(b"test artifact")
                artifacts[name] = path

            with self.assertRaisesRegex(ValueError, "outside project root"):
                self.provenance.write_figure_provenance(
                    root,
                    figure_id="fig_q1",
                    claim_id="C-Q1-01",
                    route={"backend": "python", "library": "matplotlib"},
                    source_code=outside_source,
                    input_data=artifacts["input.csv"],
                    png=artifacts["figure.png"],
                    pdf=artifacts["figure.pdf"],
                    statistics={},
                    transformations={},
                    dpi=300,
                    seed=0,
                )


if __name__ == "__main__":
    unittest.main()
