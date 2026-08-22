from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = SKILL_ROOT / "scripts" / "build_release_change_manifest.py"


class BuildReleaseChangeManifestTests(unittest.TestCase):
    def test_classifies_added_modified_removed_and_unchanged_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "current"
            current.mkdir()
            (current / "same.txt").write_text("same", encoding="utf-8")
            (current / "changed.txt").write_text("after", encoding="utf-8")
            (current / "added.txt").write_text("added", encoding="utf-8")

            import hashlib

            def row(path: str, content: str) -> dict[str, object]:
                raw = content.encode("utf-8")
                return {"path": path, "size": len(raw), "sha256": hashlib.sha256(raw).hexdigest().upper()}

            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps([row("same.txt", "same"), row("changed.txt", "before"), row("removed.txt", "removed")]),
                encoding="utf-8",
            )
            output = root / "manifest.json"
            report = root / "manifest.md"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(SCRIPT),
                    "--baseline-manifest",
                    str(baseline),
                    "--current-root",
                    str(current),
                    "--write-json",
                    str(output),
                    "--write-report",
                    str(report),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(output.read_text(encoding="utf-8"))
            statuses = {item["path"]: item["status"] for item in payload["files"]}
            self.assertEqual(
                statuses,
                {
                    "added.txt": "ADDED",
                    "changed.txt": "MODIFIED",
                    "removed.txt": "REMOVED",
                    "same.txt": "UNCHANGED",
                },
            )
            self.assertEqual(payload["counts"]["added"], 1)
            self.assertEqual(payload["counts"]["modified"], 1)
            self.assertEqual(payload["counts"]["removed"], 1)
            self.assertIn("## Changed Files", report.read_text(encoding="utf-8"))

    def test_explicit_control_metadata_exclusion_is_hashed_and_keeps_code_aggregate_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            current = root / "current"
            planning = current / "planning"
            planning.mkdir(parents=True)
            (current / "runtime.py").write_text("print('stable')\n", encoding="utf-8")
            control = planning / "release.json"
            control.write_text('{"verification_hash": "first"}\n', encoding="utf-8")

            import hashlib

            raw = b"print('stable')\n"
            baseline = root / "baseline.json"
            baseline.write_text(
                json.dumps(
                    [
                        {
                            "path": "runtime.py",
                            "size": len(raw),
                            "sha256": hashlib.sha256(raw).hexdigest().upper(),
                        }
                    ]
                ),
                encoding="utf-8",
            )

            def run(output_name: str) -> dict:
                output = root / output_name
                result = subprocess.run(
                    [
                        sys.executable,
                        "-B",
                        str(SCRIPT),
                        "--baseline-manifest",
                        str(baseline),
                        "--current-root",
                        str(current),
                        "--write-json",
                        str(output),
                        "--exclude-current",
                        "planning/release.json=release manifest embeds evidence hashes",
                    ],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                return json.loads(output.read_text(encoding="utf-8"))

            first = run("first.json")
            first_excluded = first["excluded_current_files"]
            self.assertEqual(
                first_excluded,
                [
                    {
                        "path": "planning/release.json",
                        "reason": "release manifest embeds evidence hashes",
                        "size": control.stat().st_size,
                        "sha256": hashlib.sha256(control.read_bytes()).hexdigest().upper(),
                    }
                ],
            )
            self.assertNotIn("planning/release.json", {item["path"] for item in first["files"]})

            control.write_text('{"verification_hash": "second"}\n', encoding="utf-8")
            second = run("second.json")
            self.assertEqual(first["current_aggregate_sha256"], second["current_aggregate_sha256"])
            self.assertNotEqual(
                first["excluded_current_files"][0]["sha256"],
                second["excluded_current_files"][0]["sha256"],
            )


if __name__ == "__main__":
    unittest.main()
