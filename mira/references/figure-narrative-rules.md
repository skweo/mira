# Figure Narrative Rules

Use this reference when a contest-final paper has multiple figures/tables or
when figures are meant to carry decisions, mechanisms, thresholds, sensitivity,
or robustness claims. The goal is to make every important visual a reasoning
step, not decoration.

## Required Visual Roles

Assign each main visual exactly one primary role:

| role | purpose |
|---|---|
| `define` | define structure, state, process, geometry, or data flow |
| `derive` | show a transformation from process to equation or algorithm |
| `compare` | compare methods, policies, cases, or baselines |
| `validate` | show fit, residual, constraint audit, robustness, or sensitivity |
| `explain` | explain mechanism, scale, cost source, or strategy switch |
| `decide` | directly support an accept/reject/select/execute decision |

Update `figures/figure_index.md` or `diagrams/diagram_index.md` with the role,
source data, generation script, and supported claim.

## Figure Text Loop

For every main-text figure:

1. **Before**: state what the figure is meant to define, compare, validate,
   explain, or decide.
2. **Caption**: include the concrete value, variable, threshold, policy, or
   case that makes the figure useful.
3. **After**: state the claim the figure supports and what changes because of
   it.

Good pattern:

> 为定位边际检测动作，绘制前 15 名策略差距图。图 ... 表明
> C3、C6、C8 的利润差仅 ...，因此这三个零件应进入复抽样清单。

Weak pattern:

> 图 ... 展示了结果。

## Self-Contained Caption

Captions should be readable without searching the paragraph:

- include the case/question;
- include key numeric value or threshold;
- name the decision/policy;
- avoid vague words such as "变化趋势" unless the trend is specified.

## Mechanism Over Decoration

Prefer visuals that reveal mechanism:

- cost composition or information flow;
- strategy switch boundary;
- local zoom of critical area;
- baseline gap;
- posterior/stability frequency;
- node/branch contribution.

Remove decorative, duplicate, or low-information visuals from the paper; keep
them as separate diagnostic files only when they remain useful, or delete
them.

## Gate Rules

For high-award `contest_final` output:

- Each main figure should have a role and a nearby claim.
- If a figure is kept, the paper must say what decision, validation, or
  mechanism it supports.
- A figure/table count is not enough; visuals must raise claim strength.
- If many visuals exist but few narrative terms such as "支撑、表明、解释、决策、
  对应、临界、边界" appear, return to implementation.
