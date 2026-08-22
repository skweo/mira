# Mira 0.4.1 Standard

Mira 0.4.1 is the active Mira baseline as of 2026-06-29. It is a small but
important upgrade over Mira 0.4: it keeps the 0.4 contest-final quality gates
and strengthens knowledge routing, rigid-chain geometry, collision checks, and
continuous-extremum validation.

## Upgrade Theme

| Area | 0.4 behavior | 0.4.1 behavior |
|---|---|---|
| Extended algorithm cards | Could be supplied manually, but were not a default retrieval source | `Math_Model/extended_knowledge_cards` is scanned by default when present |
| Retrieval record | Examples often wrote only `planning/knowledge_injection.md` | Standard command writes both MD and JSON so the audit can count card hits |
| Method coverage | Stronger for routing, heuristics, Monte Carlo, simulation, GA/BP, PSO | Adds signals for regression, logistic classification, clustering, PCA/factor analysis, ODEs, sensitivity, game theory, NSGA-II/multiobjective optimization, queueing, SVM, MIV, traffic CA, and YALMIP |
| Linked-geometry coverage | No dedicated rigid-chain/collision cards | Adds cards for rigid-chain kinematics and SAT rectangle collision |
| Discrete scan risk | Coarse grid scans could pass as final numbers if the result looked plausible | Continuous extrema, speed peaks, threshold crossings, collision boundaries, and scale factors require local refinement or a visible waiver |

## New Knowledge Cards

- `references/domain-knowledge/geometry/rigid-chain-kinematics.md`
- `references/domain-knowledge/geometry/collision-sat.md`
- `references/domain-knowledge/validation/continuous-extremum-search.md`
- `references/domain-knowledge/statistics/traffic-cellular-automata-nasch.md`
- `references/domain-knowledge/statistics/logistic-regression-classification.md`
- `references/domain-knowledge/statistics/neural-network-miv-feature-screening.md`
- `references/domain-knowledge/statistics/mm-sk-queue-simulation.md`
- `references/domain-knowledge/statistics/svm-classification.md`
- `references/domain-knowledge/optimization/yalmip-optimization-modeling.md`

The DeepSeek-provided cards remain in:

- `$PROJECT_ROOT\Math_Model\extended_knowledge_cards`

The retriever treats that directory as a first-class card source; the raw
materials are not copied into Mira so DeepSeek's contribution remains clearly
separated from Mira's promoted internal repair cards.

The second 0.4.1 material batch remains as executable case material under:

- `$PROJECT_ROOT\Math_Model\cellular_automata_traffic`
- `$PROJECT_ROOT\Math_Model\Logistic_regression_cases`
- `$PROJECT_ROOT\Math_Model\neural_network_MIV`
- `$PROJECT_ROOT\Math_Model\queueing_theory_cases`
- `$PROJECT_ROOT\Math_Model\SVM_cases`
- `$PROJECT_ROOT\Math_Model\YALMIP_example`

Mira does not copy those case files into the skill. It promotes only the
operational modeling and validation rules into domain-knowledge cards.

## Required Retrieval Command

Use both outputs:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\knowledge_retrieve.py `
  --root <project-root> `
  --query "<problem and method terms>" `
  --write-report planning\knowledge_injection.md `
  --write-json planning\knowledge_injection.json
```

The JSON file is required because `knowledge_application_audit.py` uses it to
identify retrieved cards and enforce traceability.

## Continuous Extremum Rule

For any continuous-time or continuous-parameter result, a sampled scan is only
candidate discovery. Mira must refine locally before final delivery when the
paper reports:

- maximum/minimum speed, cost, error, risk, pressure, or score;
- first crossing, threshold time, critical pitch, or limiting parameter;
- first collision, minimum clearance, or feasibility boundary;
- a scale factor or safety margin computed from a sampled peak.

Acceptable evidence includes bounded Brent/golden/ternary search, bisection or
root finding for crossings, interval halving for nonsmooth feasibility, or an
explicit statement that the decision variable is genuinely discrete. The final
result table must record the refined argument, refined value, tolerance, and
constraint audit.

## Continuous-Optimum Rule

An integer-grid peak is not a final continuous optimum. Reports of continuous
extrema require a bounded local refinement or a justified continuous solver,
with the final argument, value, tolerance, and constraint audit recorded.

## Compatibility

Mira 0.4 remains the previous high-award delivery standard. Mira 0.4.1 should be
used for all new contest-final runs because it is backward-compatible and adds
only stricter retrieval/validation behavior.
