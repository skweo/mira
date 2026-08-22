from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "attachment_mapping_guard.py"
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


class AttachmentMappingGuardTests(unittest.TestCase):
    def make_project(self, root: Path, statement: str, filename: str) -> None:
        (root / "problem").mkdir(parents=True)
        (root / "data_raw").mkdir()
        (root / "planning").mkdir()
        (root / "problem" / "problem_statement.txt").write_text(
            statement, encoding="utf-8"
        )
        (root / "data_raw" / filename).write_text(
            "node_id,value\n0,1\n1,2\n", encoding="utf-8"
        )
        (root / "planning" / "delivery_brief.md").write_text(
            "| Output level | contest_final |\n", encoding="utf-8"
        )

    def run_guard(self, root: Path, mapping: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--root",
                str(root),
                "--problem-text",
                "problem/problem_statement.txt",
                "--set",
                mapping,
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=ENV,
            check=False,
        )
        payload = json.loads(
            (root / "planning" / "attachment_mapping.json").read_text(
                encoding="utf-8"
            )
        )
        return result, payload

    def test_named_file_under_matching_appendix_satisfies_attachment_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(
                root,
                "注：附件 2 给出算例数据集介绍。\n"
                "\f附录 2：算例数据集\n"
                "测试数据通过提供的 参考算例.csv 文件给出。\n",
                "参考算例.csv",
            )
            result, payload = self.run_guard(
                root, "参考算例.csv=SHARED:Q1,Q2,Q3,Q4"
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(payload["verdict"], "PASS")
            evidence = payload["attachments"][0]["evidence"]
            self.assertTrue(any("附录 2" in item for item in evidence))

    def test_unrelated_file_does_not_satisfy_missing_attachment(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.make_project(
                root,
                "问题使用附件 2 的数据，当前目录另有 unrelated.csv。\n",
                "unrelated.csv",
            )
            result, payload = self.run_guard(
                root, "unrelated.csv=SHARED:Q1,Q2,Q3,Q4"
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(payload["verdict"], "FAIL")
            self.assertTrue(
                any(
                    item["item"] == "附件 2" and "no matching attachment" in item["message"]
                    for item in payload["findings"]
                )
            )


if __name__ == "__main__":
    unittest.main()
