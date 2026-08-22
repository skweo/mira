# Mira Historical Projects

This file records the historical runs that previously lived under the workspace
archive. The full-project archive was removed on 2026-07-19; these entries are
provenance records only and are not loaded or treated as runnable evidence.

| Project | Role | Recorded state | Final artifact | Retention |
|---|---|---|---|---|
| `zjhychn_2024_B_mira_0_8_20` | latest full CUMCM regression | PASS | `paper/main.pdf` | canonical full case |
| `cumcm_2019_A_mira_0_6_17` | full 0.6.17 regression | PASS | `paper/main.pdf` | full case |
| `mira_cumcm_2019_b` | full paper comparison | PASS_WITH_WARNINGS | `paper/main_optimized.pdf` | historical record only |
| `cumcm_2020_A_mira_0_5_draft` | early draft regression | legacy state only | `paper/main_final_101_fix.pdf` | draft case |
| `cumcm_2024_B_mira_0_5` | large legacy full project | unverified | `paper/main_contest.pdf` | retain, do not route |
| `mira_mathorcup_a_2026` | initial MathorCup run | unverified | `paper/main.pdf` | comparison line |
| `mira_mathorcup_A_2026_rewrite` | rewrite comparison | unverified | `paper/main.pdf` | comparison line |
| `mira_mathorcup_A_2026_mira_v2` | failed development regression | FAIL | `paper/main.pdf` | negative case |
| `mira_mathorcup_A_2026_redo` | incomplete transition regression | FAIL | `paper/main.pdf` | negative case |
| `_mira_drawio_smoke` | diagram router smoke | artifact only | route report JSON | smoke fixture |
| `drawio_demo` | draw.io export demo | artifact only | preview PNG | visual fixture |
| `compare_renders` | paper-page render comparison | artifact only | comparison PNGs | comparison fixture |

All listed paths are former locations under `archive/mira-projects/`. Status is
historical and is not recomputed after removal. `registry.json` is the
machine-readable catalog and declares `archive_available: false`.

## Mira 0.11 Candidate Comparisons

These packages preserve real papers, problem inputs, hashes, anonymized copies,
and protocol findings. They are migration audits or external calibrations, not
fresh double runs. A `FAIL` below means the package correctly refused promotion;
it does not retroactively invalidate the historical paper.

| Comparison | Role | Evidence class | Verdict | Canonical limitation |
|---|---|---|---|---|
| `cumcm_2024_b_migration` | 0.10/0.11 internal comparison | migration audit | FAIL | historical roots, unknown budgets, identity leakage, no authorized dual review |
| `cumcm_2019_a_migration` | 0.10/0.11 internal comparison | migration audit | FAIL | historical roots, unknown budgets, incomplete floors/reviews |
| `mathorcup_2026_a_migration` | 0.10/0.11 internal comparison | migration audit | FAIL | historical roots, unknown budgets, incomplete floors/reviews |

The configuration authority is `benchmarks/comparisons/`; generated evidence is
under `runs/mira_0_11_comparisons/`. None of these records is promotion-eligible.
They must not be relabeled as `fresh_double_run` or used to claim that 0.11 beats
0.10 or an external paper. They are not a deferred roadmap, release gate, or
request to generate more papers; rerunning them is optional maintenance only.

## Historical Record Policy

- Do not route these removed projects into a normal Mira run.
- Do not claim that catalog metadata proves a current regression result.
- Keep only compact benchmark JSON or test fixtures that remain executable.
- New comparison evidence must point to files that actually exist.
