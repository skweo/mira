from __future__ import annotations

import sys
import tempfile
import unittest
import warnings
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

warnings.filterwarnings("ignore", message=r"Glyph .* missing from font")


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from matplotlib_layout_qa import FigureLayoutError, inspect_figure
from visual_style import save_mira_figure


class MatplotlibLayoutQATests(unittest.TestCase):
    def tearDown(self) -> None:
        plt.close("all")

    def test_clean_chinese_bar_labels_inside_bars_pass(self) -> None:
        fig, ax = plt.subplots(figsize=(5.2, 3.6))
        heights = [3, 5, 4]
        ax.bar(range(3), heights, label="方案得分")
        ax.set_ylim(0, 10)
        for index, height in enumerate(heights):
            ax.text(index, height / 2, str(height), ha="center", va="center")
        ax.legend(loc="upper center")

        self.assertEqual(inspect_figure(fig), [])

    def test_legend_covering_bars_is_reported(self) -> None:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.bar([0, 1, 2], [3, 5, 4], label="方案得分")
        ax.set_ylim(0, 6)
        ax.legend(loc="center")

        findings = inspect_figure(fig)
        self.assertIn("legend-over-data", {item.code for item in findings})

    def test_line_and_scatter_under_chinese_annotation_are_reported(self) -> None:
        fig, ax = plt.subplots(figsize=(5, 3.5))
        ax.plot([0, 1], [0.5, 0.5])
        ax.scatter([0.5], [0.5], s=50)
        ax.text(0.5, 0.5, "最优参数", ha="center", va="center")
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)

        codes = {item.code for item in inspect_figure(fig)}
        self.assertIn("line-through-text", codes)
        self.assertIn("point-under-text", codes)

    def test_text_overlap_covers_titles_ticks_and_multiple_axes(self) -> None:
        fig, axes = plt.subplots(1, 2, figsize=(5, 2.5))
        axes[0].set_title("左侧分析标题")
        fig.suptitle("总标题覆盖左侧分析标题", x=0.28, y=0.9)
        axes[1].text(0.5, 0.5, "结论标签甲", ha="center", va="center")
        axes[1].text(0.5, 0.5, "结论标签乙", ha="center", va="center")

        findings = inspect_figure(fig)
        self.assertTrue(
            any(item.code == "text-over-text" and item.axes == 1 for item in findings),
            findings,
        )
        self.assertTrue(
            any(
                item.code == "text-over-text"
                and "title" in item.primary + item.secondary
                for item in findings
            ),
            findings,
        )

    def test_dense_tick_labels_are_discovered(self) -> None:
        fig, ax = plt.subplots(figsize=(2.2, 2.4))
        ax.set_xticks([0, 0.01])
        ax.set_xticklabels(["非常长的方案甲标签", "非常长的方案乙标签"], fontsize=13)
        ax.set_xlim(-0.1, 0.1)

        findings = inspect_figure(fig)
        self.assertTrue(
            any(
                item.code == "text-over-text"
                and item.primary.startswith("tick ")
                and item.secondary.startswith("tick ")
                for item in findings
            ),
            findings,
        )

    def test_axis_off_ignores_ticks_that_matplotlib_does_not_draw(self) -> None:
        fig, ax = plt.subplots(figsize=(2.2, 2.4))
        ax.set_xticks([0, 0.01])
        ax.set_xticklabels(["hidden tick label one", "hidden tick label two"], fontsize=14)
        ax.set_axis_off()

        self.assertEqual(inspect_figure(fig), [])

    def test_table_text_is_discovered(self) -> None:
        fig, ax = plt.subplots(figsize=(3, 2))
        ax.set_axis_off()
        first = ax.table(cellText=[["很长的方案甲结论"]], loc="center")
        second = ax.table(cellText=[["很长的方案乙结论"]], loc="center")
        for table in (first, second):
            table.auto_set_font_size(False)
            table.set_fontsize(18)

        findings = inspect_figure(fig)
        self.assertTrue(
            any(
                item.code == "text-over-text"
                and "table " in item.primary + item.secondary
                for item in findings
            ),
            findings,
        )

    def test_partial_canvas_exit_is_reported_for_free_text(self) -> None:
        fig, ax = plt.subplots(figsize=(4, 3))
        ax.text(0.0, 0.5, "边缘注释", transform=fig.transFigure, ha="center")

        self.assertIn(
            "text-outside-canvas",
            {item.code for item in inspect_figure(fig)},
        )

    def test_warn_mode_exports_and_strict_mode_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            fig, ax = plt.subplots(figsize=(4, 3))
            ax.bar([0, 1], [4, 5], label="series")
            ax.legend(loc="center")

            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always")
                save_mira_figure(fig, root / "warn.png")
                save_mira_figure(fig, root / "warn.pdf")
            layout_warnings = [item for item in caught if "layout QA" in str(item.message)]
            self.assertEqual(len(layout_warnings), 1)
            self.assertTrue((root / "warn.png").is_file())
            self.assertTrue((root / "warn.pdf").is_file())

            strict_fig, strict_ax = plt.subplots(figsize=(4, 3))
            strict_ax.plot([0, 1], [0.5, 0.5])
            strict_ax.text(0.5, 0.5, "blocked", ha="center", va="center")
            with self.assertRaises(FigureLayoutError):
                save_mira_figure(strict_fig, root / "strict.png", layout_qa="strict")
            self.assertFalse((root / "strict.png").exists())

    def test_off_mode_preserves_intentional_overlap(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output = Path(temp_dir) / "intentional.png"
            fig, ax = plt.subplots(figsize=(3, 2))
            ax.plot([0, 1], [0.5, 0.5])
            ax.text(0.5, 0.5, "intentional", ha="center", va="center")

            save_mira_figure(fig, output, layout_qa="off")
            self.assertTrue(output.is_file())


if __name__ == "__main__":
    unittest.main()
