from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path


SKILL_ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = SKILL_ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from route_references import VISUAL_LEAF_RULES, build_route  # noqa: E402


class VisualReferenceRoutingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.visual_paths = {item.path for item in VISUAL_LEAF_RULES}

    def test_registry_has_four_categories_and_all_leaf_files_exist(self) -> None:
        self.assertEqual(len(VISUAL_LEAF_RULES), 25)
        self.assertEqual(len(self.visual_paths), len(VISUAL_LEAF_RULES))
        self.assertEqual(
            {item.category for item in VISUAL_LEAF_RULES},
            {"data_chart", "structural_diagram", "style_spec", "special_visual"},
        )
        for item in VISUAL_LEAF_RULES:
            with self.subTest(path=item.path):
                self.assertTrue((SKILL_ROOT / item.path).is_file())

    def test_specific_visual_intents_route_to_the_expected_leaf(self) -> None:
        cases = {
            "请绘制三维柱状图": "references/3d-bar-visualization-rules.md",
            "生成 point cloud 图并保留投影": "references/3d-scatter-visualization-rules.md",
            "需要响应面与二维等高线": "references/radar-taylor-surface-visualization-rules.md",
            "用箱线图比较各组误差": "references/distribution-visualization-rules.md",
            "画出 t-SNE 嵌入可视化": "references/tsne-visualization-rules.md",
            "用桑基图表达资源流向": "references/flow-visualization-rules.md",
            "绘制 Pareto front": "references/parallel-pareto-gantt-visualization-rules.md",
            "输出 CNN 架构图": "references/cnn-architecture-diagram-rules.md",
            "输出多模态融合架构": "references/multimodal-fusion-architecture-rules.md",
            "画几何示意图解释坐标": "references/structure-schematic-rules.md",
            "画系统流程图": "references/system-flowchart-diagram-rules.md",
            "使用 Mermaid 时序图": "references/mermaid-diagram-templates.md",
            "做一张 PPT 推理图": "references/ppt-reasoning-diagram-rules.md",
            "做伪三维可编辑示意图": "references/pseudo-3d-ppt-diagram-rules.md",
            "选择色盲配色": "references/color-palette-rules.md",
            "查找图表图库": "references/chart-gallery-index.md",
            "制作可追溯 AI 插图": "references/image-generation-visual-rules.md",
        }
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for request, expected in cases.items():
                with self.subTest(request=request):
                    route = build_route(root, "implementation", request)
                    selected = self._selected_visual_paths(route)
                    self.assertEqual(selected, {expected})

    def test_explicit_request_wins_over_saved_project_visual_vocabulary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            plan = root / "planning" / "modeling_plan.md"
            plan.parent.mkdir(parents=True)
            plan.write_text("需要 CNN 架构图解释网络。\n", encoding="utf-8")

            route = build_route(root, "implementation", "现在绘制三维散点图")

        self.assertEqual(
            self._selected_visual_paths(route),
            {"references/3d-scatter-visualization-rules.md"},
        )

    def test_conflicting_visual_intents_load_only_highest_priority_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            route = build_route(
                Path(temp_dir),
                "implementation",
                "先设计 CNN 架构图，同时考虑普通流程图",
            )

        self.assertEqual(
            self._selected_visual_paths(route),
            {"references/cnn-architecture-diagram-rules.md"},
        )
        self.assertTrue(any("not loaded" in note for note in route.notes))

    def test_generic_evidence_terms_do_not_select_a_visual_leaf(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            route = build_route(
                Path(temp_dir),
                "implementation",
                "检查敏感性、验证结果与基线比较",
            )
        self.assertEqual(self._selected_visual_paths(route), set())

    def test_analysis_stage_defers_visual_leaf_and_paper_routes_table_style(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            analysis = build_route(root, "analysis", "绘制三维散点图")
            paper = build_route(root, "paper", "统一三线表")

        self.assertEqual(self._selected_visual_paths(analysis), set())
        self.assertEqual(
            self._selected_visual_paths(paper),
            {"references/three-line-table-rules.md"},
        )

    def _selected_visual_paths(self, route: object) -> set[str]:
        return {
            item.path
            for item in route.load_now
            if item.path in self.visual_paths
            and item.path not in {"references/visual-backend-rules.md"}
        }


if __name__ == "__main__":
    unittest.main()
