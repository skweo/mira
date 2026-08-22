# Flow Visualization Rules

Use this reference when a contest-final paper needs Sankey diagrams, circular
Sankey, chord diagrams, source-target flow, transfer structure, OD flow,
resource allocation, material flow, energy flow, information flow, or cost
composition transfer figures.

## When To Use

| Figure | Best use | Avoid when |
|---|---|---|
| Sankey diagram | Directed flow across stages: source -> process -> result. | The network has many cycles or no clear left-to-right story. |
| Circular Sankey / chord | Mutual association, OD flow, cross-category transfer, or dense many-to-many flow. | Exact direction is the main conclusion and labels cannot stay readable. |

Use a table for exact values, a stacked bar for simple composition, Sankey for
stage transfer, and chord/circular Sankey for many-to-many relationship strength.
For OD, reciprocal transfer, or cyclic networks, prefer `--kind chord`; use
`--kind all` only when comparing which visual is more readable.

## Data Contract

- Use an edge table with `source`, `target`, and positive `value` columns.
- Save cleaned/aggregated edges and a node summary with inflow, outflow, and
  throughput.
- Aggregate duplicate edges before plotting.
- Remove or explain self-loops; they are usually clearer in a table than in a
  Sankey/chord chart.
- Keep units consistent before plotting. Do not mix cost, count, mass, and
  probability in one flow-width scale.

## Figure Standards

- Line width or ribbon width must encode flow value.
- Node labels must remain readable after PDF compilation.
- Color should carry one meaning only: source node, flow category, or stage.
- For Sankey, arrange nodes in meaningful stages when the model has stages.
- For circular chord, use a meaningful node order when possible: geography,
  process order, cluster order, or descending throughput.
- If using `--node-order`, list the key nodes explicitly; the script appends
  omitted nodes by throughput so they are not silently dropped.
- Captions should state what the width means and what the visual proves:
  bottleneck, dominant pathway, allocation structure, transfer loop, or
  many-to-many coupling.

## Interpretation Discipline

Good wording:

> 桑基图显示主要流量从原料采购经部件加工进入半成品装配，最大流向为部件加工到半成品装配，说明该环节是物料主通道；拆解回收流量较小，但形成了回流路径，因此后续成本递推需要保留回收状态。

Avoid:

> 弦图很好看，因此本文加入弦图。

Do not claim exact percentages only from line width. Put exact values in a
nearby summary table or edge table.

## Script

Use the reusable script for CSV/XLSX edge tables:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\plot_flow.py `
  --root <project-root> `
  --input results\tables\flow_edges.csv `
  --source 来源 `
  --target 去向 `
  --value 流量 `
  --kind all `
  --prefix q3_resource_flow
```

The script writes Sankey/chord PNG and PDF figures, cleaned edges, node summary,
parameters, and a caption/caveat index.
