# Model Knowledge Routing

Use this file when selecting models, absorbing materials, looking for examples, or deciding which part of the local math-modeling corpus to inspect. Do not load large repositories wholesale.

## Source Priority

1. `references/model-knowledge/` inside Mira: compact operational notes. Read this first.
2. `references/domain-knowledge/` inside Mira: compact expert experience cards. Retrieve these before finalizing risky method choices.
3. Project candidate cards under `materials/extracted/knowledge-cards/`: use these when the current user has fed newer algorithm materials.
4. Project notes at `$PROJECT_ROOT\model-knowledge` when present: same compact structure, useful if newer than the embedded copy.
5. Large corpus at `$PROJECT_ROOT\Math_Model` when present: read `math-model-corpus-protocol.md`, generate/read `materials/extracted/math_model_corpus_index.md`, then use targeted search for examples, judging points, templates, algorithms, and real references.
6. Raw papers or notes provided by the user for the current task: store under `materials/raw/` and extract using `material-feeding-guidelines.md`.

## Compact Knowledge Map

| Need | Read first |
|---|---|
| Identify problem type | `references/model-knowledge/01-问题分类/数学建模问题类型与选方法.md` |
| Decide model depth and algorithm claim strength | `references/model-depth-rules.md` |
| Linear/integer optimization | `references/model-knowledge/02-优化模型/线性规划与整数规划.md` |
| Transportation and supply-demand allocation | `references/model-knowledge/02-优化模型/运输问题.md` |
| Dynamic programming and staged decisions | `references/model-knowledge/02-优化模型/动态规划.md` |
| Goal programming and multi-objective optimization | `references/model-knowledge/02-优化模型/目标规划与多目标优化.md` |
| Simulated annealing | `references/model-knowledge/02-优化模型/模拟退火.md` |
| Genetic algorithm | `references/model-knowledge/02-优化模型/遗传算法.md` |
| Particle swarm optimization | `references/model-knowledge/02-优化模型/粒子群优化PSO.md` |
| Evaluation/ranking | `references/model-knowledge/03-评价模型/` |
| Forecasting/time series | `references/model-knowledge/04-预测模型/` |
| Regression modeling and diagnostics | `references/model-knowledge/04-预测模型/回归建模与诊断.md` |
| Parameter identification, calibration, inverse problem, deformation/fault parameter estimation | `references/model-knowledge/04-预测模型/参数辨识与反问题.md` |
| Neural-network boundary | `references/model-knowledge/04-预测模型/神经网络使用边界.md` |
| Graph/network shortest path | `references/model-knowledge/05-图论与网络/最短路径Dijkstra.md` |
| Network flow/min-cost flow | `references/model-knowledge/05-图论与网络/网络流与最小费用流.md` |
| Traffic travel-time and route optimization | `references/model-knowledge/05-图论与网络/交通时间预测与路径优化.md` |
| Uncertainty/simulation | `references/model-knowledge/06-概率统计/蒙特卡洛模拟.md` |
| Differential equations | `references/model-knowledge/07-微分方程/传染病模型.md` |
| Paper structure | `references/model-knowledge/08-论文写作/论文结构模板.md` |
| Taxi supply-demand and fare planning | `references/model-knowledge/09-交通与服务规划/出租车供需与价格规划.md` |
| Interpolation, missing values, spatial field, resampling, arbitrary slice | `references/model-knowledge/10-数值计算与插值/三维插值与空间重采样.md` |
| Engineering algorithm simulation, DSP, ASIC/FPGA, fixed-point, bit width, throughput, resource tradeoff | `references/model-knowledge/11-信号处理与工程实现/工程算法仿真与资源权衡.md` |
| Wavelet analysis, signal/image denoising, time-frequency features, wavelet neural network | `references/model-knowledge/11-信号处理与工程实现/小波分析与小波神经网络.md` |

## Algorithm Coverage Checklist

When the problem type is still unclear after the first pass, use this checklist
as routing coverage only. Do not select a method just because it appears here:

| Family | Use as a routing hint for |
|---|---|
| Monte Carlo / simulation | random systems, uncertainty, validation by generated scenarios |
| Fitting / parameter estimation / interpolation | data processing, calibration, missing values, spatial or curve reconstruction |
| Mathematical programming | constrained optimization, allocation, scheduling, routing, resource planning |
| Graph algorithms | shortest path, network flow, matching, connectivity, routing |
| Dynamic programming / search / branch-and-bound | staged decisions, discrete search, exact or bounded combinatorial optimization |
| Heuristic optimization | large, nonconvex, or difficult discrete optimization after structured baselines fail |
| Grid or exhaustive search | small-dimensional parameter search or baseline sanity check |
| Discretization | continuous physical/geometric models implemented numerically |
| Numerical analysis | equation solving, integration, matrix computation, numerical stability |
| Image processing / visualization | image inputs, spatial slices, reconstruction, and result explanation figures |
| Signal/time-frequency processing | denoising, multiscale decomposition, transient detection, wavelet features |

## Large Corpus Routing

Generate a local index first when possible:

```powershell
python "$PROJECT_ROOT\.codex\skills\mira\scripts\index_math_model_corpus.py" `
  --root "$PROJECT_ROOT\Math_Model" `
  --output "materials\extracted\math_model_corpus_index.md"
```

Then use `rg --files` against `$PROJECT_ROOT\Math_Model` and filter by method, contest, or topic. Examples:

```powershell
rg --files '$PROJECT_ROOT\Math_Model' | rg -i 'mathorcup|mathor|挑战赛'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i 'topsis|层次|AHP|熵权|评价'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i 'TSP|VRP|VRPTW|Dijkstra|Floyd|网络流|路径'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i 'ARIMA|灰色|GM|预测|回归'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '参数辨识|参数识别|标定|校准|反问题|反演|检测数据|最小二乘|lsqcurvefit'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '模拟退火|遗传算法|粒子群|整数规划|线性规划|运输问题|动态规划|单纯形|对偶|灵敏度'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '插值|interpolation|重采样|空间场|栅格|曲面|等值线|slice|grid'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i 'DSP|ASIC|FPGA|定点|位宽|资源|相噪|载波恢复|RSNR|BER|芯片|吞吐|流水线'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '小波|wavelet|时频|去噪|denois|特征提取|Morlet|Mexican'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '评阅|评分|规范|模板|LaTeX'
rg --files '$PROJECT_ROOT\Math_Model' | rg -i '\.m$'
```

For algorithm-heavy learning from `3-1算法-Algorithms_MathModels` and
`3-2算法-现代的算法`, generate the algorithm index:

```powershell
python "$PROJECT_ROOT\.codex\skills\mira\scripts\index_algorithm_corpus.py" `
  --root "$PROJECT_ROOT\Math_Model\3-1算法-Algorithms_MathModels" `
  --root "$PROJECT_ROOT\Math_Model\3-2算法-现代的算法" `
  --output-dir "materials\extracted\algorithm-learning"
```

Read `materials/extracted/algorithm-learning/algorithm_corpus_index.md` before
opening many files. Treat the index as routing only; confirm by reading
representative code or documents.

If `rg` is unavailable, use `Get-ChildItem -Recurse -File` with a narrow folder and filename filter.

If `materials/extracted/batch-learning/batch_learning_summary.md` exists, read it before opening large PDF folders. Use its candidate list to pick 1-3 relevant papers for deep reading; do not treat batch tags as verified model knowledge.

## Large Corpus Roles

| Folder | Use for |
|---|---|
| `1-1按模型整理的美赛论文` | Method-specific excellent paper examples and citation candidates |
| `2-0研赛题目+论文` | Chinese postgraduate contest examples and structures |
| `2-1国赛题目+论文` | CUMCM problem-paper pairs and official thinking patterns |
| `2-1美赛题目+论文` | MCM/ICM examples, Summary style, method references |
| `3-1算法-Algorithms_MathModels` | Algorithm code patterns and implementation hints |
| `3-2算法-现代的算法` | Heuristic/modern algorithm references; use only if validation is possible |
| `4-1书籍-机器学习` | ML method understanding; avoid adding heavy ML unless data size supports it |
| `4-2书籍-LaTeX学习` | LaTeX syntax or template repair |
| `5-1国赛官方的评阅要点` | Scoring signals, official expectations, common judging priorities |
| `5-2清风数学建模公开课的课件` | Contest workflow and teaching examples |
| `5-3数模经验分享与总结（30+篇）` | Writing/process heuristics; extract as rules, not authority |

## Corpus File-Type Rules

| File type | Handling |
|---|---|
| `.pdf` | Extract structure, formulas, figures, references, or scoring signals; avoid long quotes |
| `.doc/.docx/.ppt/.pptx` | Use only when directly relevant; extract rules and source path |
| `.m` | Treat as MATLAB algorithm examples; adapt into current `code/matlab/` or translate to Python |
| `.xls/.xlsx/.csv/.dat/.mat` | Treat as example data or current-task attachments only after schema inspection |
| `.exe/.bat` | Do not execute |

## Model Selection Guardrails

- Prefer the simplest model that answers the subquestion, can be implemented, and can be validated during the contest.
- Define variables, objective, constraints, and validation before naming the algorithm.
- Use traditional contest-friendly methods before deep learning unless the data scale, features, and validation plan justify ML.
- Prefer exact or structured methods before heuristics when the scale permits.
- Check classical operations-research structures before heuristics: LP/MILP,
  transportation problem, dynamic programming, shortest path, network flow,
  matching, and goal programming when the objective/constraints fit.
- For optimization, write the exact objective and constraints before choosing a heuristic.
- For heuristics, include a baseline, fixed seed, multiple runs, and a constraint audit. Do not claim global optimality without proof or exact comparison.
- For evaluation models, define indicator direction, normalization, weight source, and sensitivity to weights.
- For prediction models, avoid time leakage and include validation error or uncertainty.
- For inverse, calibration, or parameter-identification tasks, build the forward
  model first, define the correct observed target, and validate estimated
  parameters on holdout data or sensitivity checks when possible.
- For graph/routing models, check connectivity, capacity, time windows, duplicate visits, and route continuity.
- For traffic routing, define "optimal" explicitly and validate predicted edge weights before path optimization.
- For taxi or public-service planning, produce both technical result tables and requested policy/data-collection deliverables.
- When adapting corpus code, read `computation-backends.md` and save run logs, constraint audits, and outputs.

## Domain Card Retrieval

Before contest-final modeling or iteration repair for heuristic, routing,
time-window, inverse, calibration, ML-heavy, or penalty-sensitive methods, run:

```powershell
python "$PROJECT_ROOT\.codex\skills\mira\scripts\knowledge_retrieve.py" `
  --root "<contest-project-root>" `
  --query "Q3 VRPTW no-wait time window simulated annealing penalty clustering" `
  --write-report "planning\knowledge_injection.md" `
  --write-json "planning\knowledge_injection.json"
```

Treat `planning/knowledge_injection.md` as modeling obligations: concrete
operators/mechanisms, parameter/scaling rules, validation requirements, failure
signs, repair moves, and paper-claim limits must enter `modeling_plan.md`,
code outputs, result analysis, or a recorded waiver.

## Promotion Rule

External material becomes Mira knowledge only after extraction:

1. Raw file stays under `materials/raw/`.
2. Reusable rule goes to `materials/extracted/`.
3. Stable method knowledge becomes a model card using `model-card-template.md`.
4. Expert algorithm experience becomes a knowledge card using `domain-knowledge-injection.md`.
5. Only general, checked rules move into `references/` or `references/domain-knowledge/`.
