# Mira 0.8

Mira 0.8 fixes a final-paper polish regression: earlier versions had abstract
and visual-language rules, but several findings were WARN-level or only checked
LaTeX captions. A Chinese contest-final PDF could therefore ship with an
unsegmented abstract, weak keyword/result emphasis, missing selective emphasis
on final-answer formulas, or English text baked into matplotlib figures.

## New Gate

`scripts/final_polish_language_gate.py`

This gate is included in the `paper`, `verify`, and `iteration` command
profiles. It fails Chinese `contest_final` papers when:

- the abstract does not expose each official subquestion with a bold problem
  label;
- several subquestions are merged into one paragraph;
- the keyword line is missing, hidden, or has too few real terms;
- many final numbers appear in the abstract without bold answer emphasis;
- the paper has many display equations but no highlighted final-answer or
  key-conclusion formula marker such as `\boxed{...}`;
- figure/table captions contain English prose;
- matplotlib plot titles, axis labels, legend labels, colorbar labels, or
  in-figure annotations contain English prose.

Accepted exceptions include method acronyms, variables, and units such as
`DP`, `PSO`, `QUBO`, `kg`, `m`, `s`, `ms`, `rad`, and `deg`.

## Repair Rule

Do not repair these findings by deleting evidence. Return to implementation:

- rewrite the abstract as opening paragraph + one paragraph per problem +
  closing validation paragraph + keyword line;
- bold problem labels and scan-critical result numbers/strategy phrases;
- mark only terminal conclusion equations with `\boxed{...}` or an equivalent
  final-formula macro; do not box auxiliary derivations;
- regenerate figures with Chinese titles, axes, legends, labels, and callouts.
