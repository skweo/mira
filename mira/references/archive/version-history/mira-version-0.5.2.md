# Mira 0.5.2

Mira 0.5.2 upgrades the high-award critique-response layer with quantitative
sensitivity and strategy-switch evidence.

## Added Capability

**Sensitivity and threshold evidence**

Contest-final papers should not only say that a parameter is important. They
should show how the recommendation changes when key parameters move.

Preferred artifacts:

- `results/tables/sensitivity_scan.csv`
- `results/tables/threshold_analysis.csv`
- `results/tables/sample_size_sensitivity.csv`
- `figures/sensitivity_*.png`
- `figures/strategy_switch_*.png`

Preferred paper sections:

- `定量灵敏度分析`
- `策略切换边界`
- `参数临界值分析`
- `样本量敏感性分析`

## New Gate Behavior

The award gate checks whether the paper has quantitative sensitivity or
threshold signals, not only generic "敏感/稳健" prose. Missing evidence is a
high-award warning when the paper makes recommendations under uncertain or
assumed parameters.

