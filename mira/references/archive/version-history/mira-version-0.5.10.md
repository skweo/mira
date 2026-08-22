# Mira 0.5.10

Mira 0.5.10 adds three-line table presentation discipline on top of Mira 0.5.9.

## Added Capability

**Three-line table style**

Mira should prefer formal three-line tables for contest-final papers, especially
in LaTeX output. This makes result, comparison, sensitivity, and appendix
summary tables look closer to strong Chinese mathematical modeling papers.

Preferred LaTeX table style:

- use `booktabs`;
- use `\toprule`, `\midrule`, and `\bottomrule`;
- avoid vertical rules and repeated `\hline`;
- keep captions informative and units in headers;
- move large raw tables to the appendix.

## New Gate Behavior

The final-paper chain now includes `scripts/table_style_audit.py`. This gate
checks whether final-paper tables use three-line/booktabs style when possible
and reports cluttered grid-table patterns as paper presentation repairs.

This gate does not change numbers or table content. It only improves table
format, readability, and contest-paper polish.
