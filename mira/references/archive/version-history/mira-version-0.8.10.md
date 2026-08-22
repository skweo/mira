# Mira 0.8.10

## Scope

Mira 0.8.10 adds an effective-content page gate for contest-final mathematical
modeling papers.

The gate is not a word-count or padding target. It checks whether the main body
has enough decision-bearing material while keeping the paper compact enough for
competition reading.

## Definition

Effective content pages are counted from the first formal main-body section
such as `问题重述`, `问题分析`, `符号说明`, `模型假设`, or `模型建立` to the
page before `参考文献`, `附录`, supporting material, or AI-use disclosure.

The following do not count:

- cover pages;
- title/abstract pages;
- table of contents;
- references;
- appendix and support files;
- AI-use disclosure material.

## Gate

For `contest_final` and high-award outputs:

- fewer than 23 effective content pages is a blocking failure;
- more than 30 effective content pages is a blocking failure;
- unreadable or markerless PDFs that prevent measurement are blocking failures.

For lower output levels, the same measurement may warn without blocking.

## Repair Rule

Do not repair a low page count by adding filler prose. Return to the owning
phase and add missing:

- derivations and formula explanations;
- validation, sensitivity, robustness, or baseline comparison;
- claim-bearing figures and tables;
- result interpretation and decision discussion;
- assumption relaxation or limitation analysis.

Repair a high page count by compressing repeated prose, moving support material
to the appendix, and keeping the main body evidence-dense.
