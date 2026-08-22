# Math Model Corpus Protocol

Use this protocol when Mira needs to learn from or search `$PROJECT_ROOT\Math_Model`. The corpus is a large external library, not a skill reference to load wholesale.

## First Action

If `materials/extracted/math_model_corpus_index.md` is missing or stale, run:

```powershell
python "$PROJECT_ROOT\.codex\skills\mira\scripts\index_math_model_corpus.py" `
  --root "$PROJECT_ROOT\Math_Model" `
  --output "<project-root>\materials\extracted\math_model_corpus_index.md"
```

Read the generated index before searching the corpus. Do not browse thousands of files manually.

## What To Extract

| Source area | Extract |
|---|---|
| `1-1按模型整理的美赛论文` | Method usage patterns, section structure, validation ideas, figure/table patterns, real citation candidates |
| `2-0研赛题目+论文` | Chinese contest structure, abstract/result style, evidence density |
| `2-1国赛题目+论文` | Problem-paper pairs, official-style reasoning, answer granularity |
| `2-1美赛题目+论文` | MCM/ICM modeling patterns and references |
| `3-1算法-Algorithms_MathModels` | MATLAB/Python-style implementation patterns, algorithm steps, test data |
| `3-2算法-现代的算法` | Heuristic variants; use only with validation and baseline checks |
| `5-1国赛官方的评阅要点` | Scoring criteria and hard judging signals |
| `5-2清风数学建模公开课的课件` | Workflow and teaching examples |
| `5-3数模经验分享与总结（30+篇）` | Writing/process heuristics, common pitfalls |

## Search Strategy

Start narrow, using the generated index and then `rg --files`. Search by contest, primary model class, algorithm keyword, or file type:

```powershell
rg --files "$PROJECT_ROOT\Math_Model" | rg -i "AHP|Topsis|熵权|评价|主成分|PCA"
rg --files "$PROJECT_ROOT\Math_Model" | rg -i "TSP|VRP|VRPTW|Dijkstra|Floyd|网络流|路径"
rg --files "$PROJECT_ROOT\Math_Model" | rg -i "线性规划|整数规划|模拟退火|遗传算法|粒子群|优化"
rg --files "$PROJECT_ROOT\Math_Model" | rg -i "评阅|评卷|官方答案|评分|格式规范|经验|心得"
rg --files "$PROJECT_ROOT\Math_Model" | rg -i "\.m$"
```

If filenames appear garbled in terminal output, still use the path returned by the shell. Windows can usually open the file by path even when display encoding is imperfect.

## Extraction Outputs

Create or update these files under the current contest project:

| Output | Purpose |
|---|---|
| `materials/extracted/math_model_corpus_index.md` | Local map of the corpus |
| `materials/extracted/source-index.md` | Specific sources actually used for this contest |
| `materials/extracted/model-library.md` | Reusable model cards or model-routing notes |
| `materials/extracted/code-patterns.md` | Algorithm and implementation patterns extracted from `.m`, `.py`, `.txt` |
| `materials/extracted/excellent-paper-patterns.md` | Writing, table, figure, and validation patterns from strong papers |
| `materials/extracted/scoring-rubric.md` | Official or credible judging signals |

Do not copy long passages from papers, books, or Word/PDF materials. Extract compact reusable rules and cite the raw source path.

## Contest Use

During problem analysis:

- Search for same contest/problem type and official judging points.
- Extract what the problem usually rewards: model completeness, constraints, validation, and result format.

During modeling:

- Search by primary model type and read at most a few high-value examples.
- Promote only operational knowledge: variables, assumptions, equations, constraints, solver route, validation.

During code implementation:

- Search algorithm code examples, especially `.m` files if MATLAB is a good fit.
- Treat examples as references, not trusted production code. Adapt, simplify, and validate.

During writing:

- Search excellent papers for section density, table placement, abstract style, and validation language.
- Do not copy prose.

## Promotion Rule

A corpus item can influence Mira permanently only after:

1. It is recorded in `materials/extracted/source-index.md`.
2. Its lesson is paraphrased as a rule, model card, code pattern, figure rule, or scoring rule.
3. Scope and non-scope are written explicitly.
4. The rule is checked against at least one actual contest use or known official expectation.
