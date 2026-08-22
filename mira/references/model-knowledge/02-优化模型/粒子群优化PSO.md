# Model Card: 粒子群优化 PSO

## Use When

- 连续变量优化，目标函数非线性、不可导、多峰，且没有可靠梯度。
- 参数寻优、模型校准、函数极值、权重或阈值调参。
- 变量有明确上下界，可以自然表示为粒子位置。

## Avoid When

- 线性规划、凸优化、整数规划或最短路可用精确方法求解。
- 变量是排列、路径、车辆路线等离散结构，但没有编码和修复机制。
- 目标函数噪声很大且无法重复评估。
- 无法做基线比较、重复运行或约束审计。

## Typical Contest Tasks

- 非线性参数寻优。
- 预测模型超参数优化。
- 多目标权重搜索。
- 连续资源配置。

## Required Inputs

| Input | Meaning | Unit | Required? | Notes |
|---|---|---|---:|---|
| Objective function | 待最小化/最大化目标 | problem-specific | yes | 必须可重复计算 |
| Variable bounds | 每个维度的上下界 | problem-specific | yes | 位置更新后要截断或修复 |
| Particle count | 粒子数 | count | yes | 影响稳定性和时间 |
| Iteration limit | 最大迭代次数 | count | yes | 记录停止规则 |
| PSO parameters | 惯性权重、学习因子 | none | yes | 记录来源或敏感性 |
| Seed | 随机种子 | none | yes | 用于复现 |

## Outputs

| Output | Meaning | Paper use |
|---|---|---|
| Best position | 最优参数/方案 | 主要结果 |
| Best objective | 目标函数值 | 结果表 |
| Convergence trace | 每代最优值 | 收敛图和稳定性 |
| Multi-seed summary | 多次运行均值/方差/最好值 | 鲁棒性验证 |

## Variables and Parameters

| Symbol | Type | Meaning | Unit | Source or estimation |
|---|---|---|---|---|
| `x_i` | variable | 第 `i` 个粒子位置 | problem-specific | 当前候选解 |
| `v_i` | state | 第 `i` 个粒子速度 | problem-specific | 迭代更新 |
| `p_i` | state | 个体历史最优位置 | problem-specific | 算法记录 |
| `g` | state | 群体历史最优位置 | problem-specific | 算法记录 |
| `w` | parameter | 惯性权重 | none | 算法设置 |
| `c1,c2` | parameter | 个体/群体学习因子 | none | 算法设置 |

## Core Formulation

```text
v_i(t+1) = w v_i(t) + c1 r1 (p_i - x_i(t)) + c2 r2 (g - x_i(t))
x_i(t+1) = repair_or_clip(x_i(t) + v_i(t+1))
```

目标函数必须来自当前题目：

```text
minimize F(x) = objective(x) + penalty(hard_constraint_violations)
```

硬约束优先用可行编码或修复；只有无法直接保持可行时才使用惩罚项。

## Solver or Implementation Route

- Preferred language: Python for reproducible experiments; MATLAB acceptable
  when adapting a reviewed `.m` example.
- Recommended packages: `numpy`, `scipy`, `pandas`, `matplotlib`.
- Data preprocessing: scale variables so dimensions are comparable.
- Baseline: grid/random search, local optimizer, or a simple feasible rule.
- Complexity: `O(particle_count * iterations * objective_cost)`.

## Validation

- Feasibility check: bounds and hard constraints after every update.
- Sensitivity check: particle count, `w`, `c1`, `c2`, and seed.
- Baseline comparison: compare with random search or deterministic local method.
- Error or uncertainty check: repeated runs; report best/mean/std objective.

## Figure and Table Outputs

| Artifact | Purpose | Source data |
|---|---|---|
| `pso_convergence.csv` | 每代最优目标 | run log |
| `pso_multiseed_summary.csv` | 多种子稳定性 | repeated runs |
| `pso_solution_audit.csv` | 约束审计 | final solution |
| `pso_convergence.pdf` | 收敛图 | convergence csv |

## Paper Writing Notes

- 先说明为什么精确方法或梯度法不适合，再引入 PSO。
- 写清粒子编码、变量上下界和目标函数。
- 结果称为“PSO 搜索得到的较优方案”或“实验最优方案”，不要称为全局最优，除非有独立证明。

## Common Pitfalls

- 用 PSO 解决排列/路径问题但没有离散编码和修复。
- 只跑一次就报告结果。
- 只给收敛图，没有最终参数表和约束审计。
- 没有固定随机种子。

## Source Notes

- Extracted by: Mira algorithm learning round 1.
- Last updated: 2026-06-24.
