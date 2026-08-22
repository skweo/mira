from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

from pypdf import PdfWriter


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
sys.path.insert(0, str(SCRIPTS))

from submission_compliance import evaluate_submission  # noqa: E402


class SubmissionComplianceTests(unittest.TestCase):
    def make_project(self, root: Path, pages: int = 2) -> dict:
        source = root / "paper" / "main.tex"
        source.parent.mkdir(parents=True)
        source.write_text(
            "\\title{城市配送优化模型}\n关键词：预测；优化\n\\section{问题重述}\n\\section{模型建立}\n",
            encoding="utf-8",
        )
        pdf = root / "output" / "contest_final" / "paper.pdf"
        pdf.parent.mkdir(parents=True)
        writer = PdfWriter()
        for _ in range(pages):
            writer.add_blank_page(width=595, height=842)
        with pdf.open("wb") as stream:
            writer.write(stream)
        return {
            "schema_version": 1,
            "paper": {
                "source": "paper/main.tex",
                "pdf": "output/contest_final/paper.pdf",
                "expected_title": "城市配送优化模型",
                "keywords": ["预测", "优化"],
                "required_sections": ["问题重述", "模型建立"],
                "page_limit": 3,
            },
            "anonymity": {"required": True, "identity_tokens": ["TEAM-SECRET"]},
            "required_files": ["output/contest_final/paper.pdf"],
            "forbidden_placeholders": ["DRAFT_ONLY"],
            "ai_disclosure": {"required": False, "artifact": ""},
        }

    def codes(self, payload: dict) -> set[str]:
        return {item["code"] for item in payload["findings"]}

    def test_configured_requirements_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements = self.make_project(root)
            payload = evaluate_submission(root, requirements)
        self.assertEqual(payload["verdict"], "PASS")
        self.assertEqual(payload["metrics"]["page_count"], 2)

    def test_missing_requirements_uses_generic_checks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(root)
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "submission_compliance.py"), "--root", str(root)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                check=False,
            )
            report = json.loads(
                (root / "checks" / "submission_compliance_report.json").read_text(encoding="utf-8")
            )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(report["verdict"], "PASS_WITH_WARNINGS")
        self.assertIn("requirements_fallback", self.codes(report))

    def test_optional_competition_fields_are_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            requirements = self.make_project(root)
            requirements["paper"].update(
                {"expected_title": "", "keywords": [], "required_sections": [], "page_limit": None}
            )
            payload = evaluate_submission(root, requirements)
        self.assertEqual(payload["verdict"], "PASS")

    def test_missing_title_keyword_and_section_fail(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            contract["paper"]["expected_title"] = "不存在的标题"
            contract["paper"]["keywords"] = ["不存在的关键词"]
            contract["paper"]["required_sections"] = ["不存在的章节"]
            payload = evaluate_submission(root, contract)
        self.assertTrue({"title_missing", "keywords_missing", "sections_missing"}.issubset(self.codes(payload)))

    def test_configured_page_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root, pages=2)
            contract["paper"]["page_limit"] = 1
            payload = evaluate_submission(root, contract)
        self.assertIn("page_limit", self.codes(payload))

    def test_identity_token_is_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            source = root / "paper" / "main.tex"
            source.write_text(source.read_text(encoding="utf-8") + "TEAM-SECRET\n", encoding="utf-8")
            payload = evaluate_submission(root, contract)
        self.assertIn("identity_leak", self.codes(payload))

    def test_required_ai_artifact_must_exist(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            contract["ai_disclosure"] = {
                "required": True,
                "artifact": "supporting/ai-disclosure.pdf",
            }
            payload = evaluate_submission(root, contract)
        self.assertIn("ai_artifact", self.codes(payload))

    def test_project_path_traversal_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            contract = self.make_project(root)
            contract["required_files"] = ["../outside.txt"]
            payload = evaluate_submission(root, deepcopy(contract))
        self.assertIn("required_file_path", self.codes(payload))


if __name__ == "__main__":
    unittest.main()
