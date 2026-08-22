# Citation Precision Rules

Use this reference when a contest-final paper uses nontrivial methods,
external data, parameter values, software/toolboxes, or domain claims that need
source support. The goal is precise source binding, not reference padding.

## Core Principle

References are evidence links, not decoration. A short reference list can be
excellent when every item supports a concrete method, parameter, dataset, or
domain assumption. A long reference list is weak when citations are unused,
generic, duplicated, or unrelated to the actual model.

## Binding Targets

Bind sources to these claims when they appear:

| target | needs source when | acceptable support |
|---|---|---|
| `method` | nontrivial method is selected, e.g. DP, Bayesian update, SVM, GA, queueing, YALMIP | textbook, paper, official documentation, or local knowledge card |
| `parameter` | parameter is not directly provided by the problem or computed from data | problem statement, estimation table, prior paper, handbook, or explicit assumption |
| `data` | external dataset, webpage, table, or historical record is used | source file, URL, official statistics, or provided attachment |
| `software` | solver/toolbox/API is named as executed | official documentation or runtime artifact |
| `domain_claim` | claim about real process, industry practice, or mechanism is not obvious from the problem | domain paper, standard, official document, or scoped assumption |

## Preferred Artifacts

- `planning/citation_binding.md`
- `results/tables/citation_binding.csv`

Suggested `citation_binding.csv` columns:

```csv
claim_id,claim_type,paper_location,citation_key,source_type,source_path_or_url,support_scope,used_for
```

## Writing Rules

1. Cite only sources that are actually used in the model, data processing,
   parameter setting, validation, or domain explanation.
2. Put citations near the claim they support; do not dump all citations in the
   introduction or conclusion.
3. Prefer one precise source over several generic sources.
4. Do not cite a source for a stronger claim than it supports.
5. If the problem statement supplies the value, cite the problem or state
   "题目给定" instead of adding an unrelated paper.
6. If a method is standard but the paper has no real source available, write a
   scoped waiver rather than fabricate a citation.

## Bad Patterns

- A long reference list with no in-text citation.
- Citing a general optimization paper for a specific industrial parameter.
- Adding references only to satisfy a count target.
- Citing a paper discovered in search results but never read or used.
- Using "参考相关文献" without saying what the reference supports.

