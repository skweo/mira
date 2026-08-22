# Skill Compaction Control Rules

Use these rules when upgrading or auditing Mira itself. The goal is to keep Mira
usable as a skill instead of letting every new contest lesson become permanent
startup context.

## Principles

- Do not delete first. Audit, classify, route, then archive or merge only after
  evidence shows a file is stale or duplicated.
- Keep `SKILL.md` as the control plane: current version, startup, state machine,
  hard rules, and routing instructions. Move detailed rules into `references/`
  and deterministic checks into `scripts/`.
- Keep old version knowledge available but out of the default path. Historical
  notes should be routed only when investigating regressions or version history.
- Prefer one gate per quality axis. When two gates overlap, define precedence
  rather than deleting either immediately.

## Size Targets

- `SKILL.md`: target under 250 lines; warning zone above 300 lines; hard refactor
  zone above 500 lines.
- Long references: any file over 100 lines should have clear headings; any file
  over 10 KB should be routed only when needed.
- Version notes: keep the latest version and a compact index active; archive old
  one-version files when they are no longer routed.
- Scripts: scripts are cheap until they are unreferenced, duplicated, or
  untested. Do not remove solver or audit scripts only because count is high.

## Classification

Classify Mira files into:

1. **Active control plane**: `SKILL.md`, `route_references.py`, state/control
   scripts, current version note.
2. **Stage references**: analysis, modeling, implementation, paper, and
   iteration rules.
3. **Domain knowledge**: model cards, method routing, and knowledge injection.
4. **Quality gates**: deterministic scripts and their rule references.
5. **Historical/archive**: old version notes, imported lessons, and obsolete
   experiments.
6. **Candidate cleanup**: files not referenced by routes, SKILL, imports, or
   recent usage.

## Audit Workflow

1. Run `scripts/mira_skill_compaction_audit.py --skill-root <mira-skill-root>`.
2. Review warnings before changing files. Treat the report as a cleanup queue,
   not as permission to delete.
3. For each suspected duplicate, decide: keep separate, merge into one
   reference, or archive the older one.
4. After any compaction, run
   `python -m unittest discover -s tests -p "test_*.py" -v`, `py_compile` for
   changed scripts, and a route smoke test.
5. For a release candidate, run `scripts/build_release_change_manifest.py`
   against the frozen prior-release `file-manifest.json`; keep the generated
   JSON and Markdown outside the live skill root so they do not hash themselves.

## Safe Compaction Moves

- Move old version paragraphs out of `SKILL.md` into a version index.
- Replace repeated command lists with one runner script or one referenced
  command profile.
- Keep detailed writing/visual/model rules in references and route them by
  phase or risk trigger.
- Convert "always load" references into risk-triggered references when they are
  not needed for every contest-final paper.

## Unsafe Moves

- Do not delete a script that is called by another script.
- Do not delete a reference just because it is not in `route_references.py`; it
  may be a material-feeding or knowledge-card template.
- Do not merge rules that intentionally check different surfaces, such as
  visual asset quality, visual reasoning, and official-showcase evidence.
- Do not optimize away validation gates only to make Mira faster; create fast,
  standard, and deep profiles instead.
