# Batch Learning Protocol

Use this protocol when the user asks Mira to learn from many files in `$PROJECT_ROOT\Math_Model`.

## Purpose

Batch learning is triage and pattern discovery. It is not a substitute for per-paper deep reading. It should identify candidate papers, model coverage, extraction failures, and reusable routing signals without copying source prose.

## Workflow

1. Generate or refresh `materials/extracted/math_model_corpus_index.md`.
2. Run `scripts/batch_learn_math_model_corpus.py` with a bounded limit, usually 50-150 PDFs.
3. Read `materials/extracted/batch-learning/batch_learning_summary.md` first when it exists, then inspect the detailed reports under `materials/extracted/batch-learning/`.
4. Select the best candidates for per-paper notes under `materials/extracted/paper-learning/`.
5. Promote only stable, operational rules into Mira references after manual/deep confirmation.

## Command

```powershell
python "$PROJECT_ROOT\.codex\skills\mira\scripts\batch_learn_math_model_corpus.py" `
  --root "$PROJECT_ROOT\Math_Model" `
  --output-dir "$PROJECT_ROOT\materials\extracted\batch-learning" `
  --limit 100 `
  --deep-limit 30
```

## Outputs

| File | Purpose |
|---|---|
| `corpus_scan.jsonl` | Machine-readable per-PDF metadata, model tags, quality tags, headings, and extraction status |
| `batch_learning_summary.md` | Human-readable batch summary, top candidates, coverage, and next deep-reading batches |
| `topic_map.md` | Model-topic map for routing future problems |
| `model_coverage.md` | Counts by model tag, source type, and quality signal |
| `excellent_paper_candidates.md` | Ranked list for later deep learning |
| `extraction_failures.md` | Low-text or failed PDFs that need OCR/visual review |
| `paper-patterns-batch.md` | Batch-level triage rules; not final model knowledge |

## Promotion Rules

- Promote a rule only after it is confirmed by deep reading or official judging material.
- Do not promote rules from low-text PDFs without visual review.
- Do not copy abstract, conclusion, or body prose into Mira.
- Use batch tags to route attention, not to declare a method universally appropriate.
- Record each completed batch in `materials/extracted/source-index.md` with an ID such as `B1`, `B2`, and keep it labeled as triage.

## Existing Batch Entry

The current first batch is `B1` under `$PROJECT_ROOT\materials\extracted\batch-learning`. It scanned 100 PDFs and produced coverage across forecasting, optimization, evaluation, statistics, simulation, network/routing, parameter estimation, heuristic, differential-equation, and queueing topics. Use `batch_learning_summary.md` as the entry point.

## Good Batch Targets

- `2-0研赛题目+论文\优秀论文按年份`
- `2-1国赛题目+论文`
- `1-1按模型整理的美赛论文`
- `5-1国赛官方的评阅要点`
- `5-3数模经验分享与总结（30+篇）`
