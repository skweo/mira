#!/usr/bin/env python3
"""Detect conditional Mira references from project facts and bounded text.

The router and the stage gate share this module so the trigger decision and the
coverage audit cannot drift into separate rule sets. Generated reports and old
route outputs are intentionally outside the evidence sources.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class TriggerEvidence:
    source_type: str
    location: str
    summary: str


@dataclass(frozen=True)
class TriggerHit:
    rule_id: str
    reference: str
    reason: str
    owner_stages: tuple[str, ...]
    evidence: tuple[TriggerEvidence, ...]
    disposition: str


@dataclass(frozen=True)
class StructuredSpec:
    paths: tuple[str, ...]
    key_pattern: re.Pattern[str]
    value_pattern: re.Pattern[str]
    require_key_and_value: bool = False


@dataclass(frozen=True)
class TriggerRule:
    rule_id: str
    reference: str
    reason: str
    owner_stages: tuple[str, ...]
    keyword_pattern: re.Pattern[str]
    structured: StructuredSpec


METHOD_PATTERN = re.compile(
    r"\b(?:SA|GA|PSO|NSGA(?:-?II)?|AHP|TOPSIS|SVM|ODE|PDE|PCA|VRP|"
    r"heuristic|Monte[ -]?Carlo|game theory|regression|clustering|queueing|"
    r"collision|optimization|linear programming|integer programming|"
    r"dynamic programming|Markov|time series|random forest|XGBoost|"
    r"neural network|CNN|LSTM)\b|"
    r"模拟退火|遗传算法|粒子群|蒙特卡洛|博弈|回归|微分方程|"
    r"聚类|排队论|线性规划|整数规划|动态规划|马尔可夫|时间序列|"
    r"随机森林|神经网络|优化",
    re.I,
)
VALIDATION_PATTERN = re.compile(
    r"\b(?:baseline|convergence|multi[-_ ]?seed|sensitivity|threshold|"
    r"ablation|optimality|robustness)\b|基线|收敛|多种子|敏感性|"
    r"阈值|消融|最优性|稳健性",
    re.I,
)
CITATION_PATTERN = re.compile(
    r"\b(?:citation|reference|bibliography|source[-_ ]?binding|claim[-_ ]?source)\b|"
    r"引用|参考文献|来源绑定|引文绑定",
    re.I,
)
MATERIAL_PATTERN = re.compile(
    r"\b(?:materials?|corpus|batch learning|excellent papers?)\b|"
    r"资料|语料|批量学习|优秀论文",
    re.I,
)
BATCH_PATTERN = re.compile(r"\b(?:batch(?: learning)?|bulk learning)\b|批量学习|批量资料", re.I)
MATH_MODEL_PATTERN = re.compile(
    r"\b(?:Math_Model|MathModel|math model corpus)\b|数学建模资料库", re.I
)

MODELING_JSON = (
    "planning/modeling_plan.json",
    "planning/model_route.json",
)
VALIDATION_JSON = (
    "planning/validation_plan.json",
    "planning/modeling_plan.json",
)
CITATION_JSON = (
    "planning/citation_plan.json",
    "planning/reference_authenticity.json",
    "planning/material_claim_anchors.json",
)
MATERIAL_JSON = (
    "planning/material_requests.json",
    "planning/delivery_brief.json",
    "planning/problem_analysis.json",
)

TRIGGER_RULES: tuple[TriggerRule, ...] = (
    TriggerRule(
        "method_domain_knowledge",
        "references/domain-knowledge-injection.md",
        "task-specific method knowledge",
        ("modeling", "implementation"),
        METHOD_PATTERN,
        StructuredSpec(
            MODELING_JSON,
            re.compile(
                r"^(?:solver|solvers|algorithm|algorithms|method|methods|model_family|"
                r"model_families|model_type|optimization_method|solution_method)$",
                re.I,
            ),
            METHOD_PATTERN,
            require_key_and_value=True,
        ),
    ),
    TriggerRule(
        "comparison_validation_evidence",
        "references/baseline-comparison-rules.md",
        "comparison or sensitivity evidence",
        ("modeling", "implementation"),
        VALIDATION_PATTERN,
        StructuredSpec(
            VALIDATION_JSON,
            re.compile(
                r"^(?:baseline|baselines|convergence|multi_seed|multiseed|sensitivity|"
                r"sensitivity_analysis|threshold|ablation|optimality|robustness)$",
                re.I,
            ),
            VALIDATION_PATTERN,
        ),
    ),
    TriggerRule(
        "citation_precision",
        "references/citation-precision-rules.md",
        "citation precision",
        ("paper",),
        CITATION_PATTERN,
        StructuredSpec(
            CITATION_JSON,
            re.compile(
                r"^(?:citation|citations|reference|references|bibliography|"
                r"source_binding|claim_source|citation_binding)$",
                re.I,
            ),
            CITATION_PATTERN,
        ),
    ),
    TriggerRule(
        "material_feeding",
        "references/material-feeding-guidelines.md",
        "explicit material-feeding request",
        ("analysis", "modeling", "paper"),
        MATERIAL_PATTERN,
        StructuredSpec(
            MATERIAL_JSON,
            re.compile(
                r"^(?:material|materials|material_request|corpus|corpora|"
                r"batch_learning|excellent_papers)$",
                re.I,
            ),
            MATERIAL_PATTERN,
        ),
    ),
    TriggerRule(
        "batch_material_learning",
        "references/batch-learning-protocol.md",
        "batch material learning",
        ("analysis", "modeling"),
        BATCH_PATTERN,
        StructuredSpec(
            MATERIAL_JSON,
            re.compile(r"^(?:batch|batch_learning|bulk_learning)$", re.I),
            BATCH_PATTERN,
        ),
    ),
    TriggerRule(
        "math_model_corpus",
        "references/math-model-corpus-protocol.md",
        "Math_Model corpus access",
        ("analysis", "modeling"),
        MATH_MODEL_PATTERN,
        StructuredSpec(
            MATERIAL_JSON,
            re.compile(r"^(?:math_model|mathmodel|math_model_corpus)$", re.I),
            MATH_MODEL_PATTERN,
        ),
    ),
)

KEYWORD_SOURCE_PATHS = (
    "planning/delivery_brief.md",
    "planning/problem_analysis.md",
    "planning/attachment_mapping.md",
    "planning/modeling_plan.md",
    "planning/validation_plan.md",
    "planning/citation_plan.md",
    "planning/material_requests.md",
)
PLACEHOLDERS = frozenset(
    {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "not_applicable",
        "not applicable",
        "false",
        "disabled",
        "todo",
        "tbd",
        "placeholder",
        "待定",
        "不适用",
    }
)


def evaluate_reference_triggers(root: Path, request: str = "") -> list[TriggerHit]:
    root = root.resolve()
    hits: list[TriggerHit] = []
    for rule in TRIGGER_RULES:
        evidence = _structured_evidence(root, rule)
        evidence.extend(_keyword_evidence(root, request, rule))
        evidence = _deduplicate_evidence(evidence)
        if evidence:
            hits.append(
                TriggerHit(
                    rule.rule_id,
                    rule.reference,
                    rule.reason,
                    rule.owner_stages,
                    tuple(evidence),
                    "detected",
                )
            )
    return hits


def route_trigger_hits(hits: list[TriggerHit], stage: str) -> list[TriggerHit]:
    return [
        replace(item, disposition="load_now" if stage in item.owner_stages else "deferred")
        for item in hits
    ]


def current_stage_hits(root: Path, stage: str) -> list[TriggerHit]:
    return [
        item
        for item in route_trigger_hits(evaluate_reference_triggers(root), stage)
        if item.disposition == "load_now"
    ]


def _structured_evidence(root: Path, rule: TriggerRule) -> list[TriggerEvidence]:
    evidence: list[TriggerEvidence] = []
    for relative in rule.structured.paths:
        payload = _load_json(root / relative)
        if payload is None:
            continue
        for key, location, value in _walk_active_leaves(payload):
            value_text = _value_text(value)
            key_match = bool(rule.structured.key_pattern.search(key))
            value_match = bool(rule.structured.value_pattern.search(value_text))
            matched = key_match and value_match if rule.structured.require_key_and_value else key_match or value_match
            if matched:
                evidence.append(
                    TriggerEvidence(
                        "structured",
                        f"{relative}#{location}",
                        _compact(f"{key}={value_text}"),
                    )
                )
    return evidence


def _keyword_evidence(root: Path, request: str, rule: TriggerRule) -> list[TriggerEvidence]:
    evidence: list[TriggerEvidence] = []
    sources = [("request", request)]
    sources.extend((relative, _read_text(root / relative)) for relative in KEYWORD_SOURCE_PATHS)
    for location, text in sources:
        match = rule.keyword_pattern.search(text or "")
        if match:
            evidence.append(
                TriggerEvidence(
                    "keyword",
                    location,
                    _compact(match.group(0)),
                )
            )
    return evidence


def _walk_active_leaves(value: Any, location: str = "$"):
    if isinstance(value, dict):
        if _disabled_container(value):
            return
        for key, item in value.items():
            child = f"{location}.{key}" if location != "$" else str(key)
            yield from _walk_active_leaves(item, child)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            yield from _walk_active_leaves(item, f"{location}[{index}]")
        return
    if _meaningful(value):
        key = re.split(r"[.\[]", location)[-1].rstrip("]")
        yield key, location, value


def _disabled_container(value: dict[str, Any]) -> bool:
    for key in ("enabled", "applicable", "required", "requested"):
        if key in value and value[key] is False:
            return True
    status = str(value.get("status") or "").strip().lower()
    return bool(status) and status in PLACEHOLDERS


def _meaningful(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, str) and value.strip().lower() in PLACEHOLDERS:
        return False
    return True


def _value_text(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _deduplicate_evidence(items: list[TriggerEvidence]) -> list[TriggerEvidence]:
    output: list[TriggerEvidence] = []
    seen: set[tuple[str, str, str]] = set()
    for item in items:
        key = (item.source_type, item.location, item.summary)
        if key not in seen:
            seen.add(key)
            output.append(item)
    return output


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig", errors="ignore"))
    except (json.JSONDecodeError, OSError):
        return None


def _read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="ignore")[:12000]


def _compact(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()[:160]
