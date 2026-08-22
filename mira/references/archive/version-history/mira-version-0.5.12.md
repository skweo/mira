# Mira 0.5.12

Mira 0.5.12 adds skill compaction and control-plane cleanup discipline on top of
Mira 0.5.11.

This is an engineering-quality upgrade for Mira itself. It does not add a new
mathematical modeling method. It prevents the skill from becoming slow,
duplicative, or hard to reason about as more contest lessons, references, and
quality gates are added.

## New Standard

When Mira is upgraded, audited, or suspected of becoming too large, run a skill
compaction audit before deleting or merging anything. The audit should report:

- `SKILL.md` size and version-history load;
- number and size of references and scripts;
- old version-note accumulation;
- references and scripts not visibly routed or mentioned;
- stale active-version references;
- duplicated command entries.

## New Gate

Run:

```bash
python scripts/mira_skill_compaction_audit.py --skill-root <mira-skill-root> --write-report checks/skill_compaction_report.md --write-json checks/skill_compaction_report.json
```

Use the report as a cleanup queue. Do not treat it as automatic deletion
permission.

## Non-goals

- Do not remove domain knowledge just to reduce file count.
- Do not collapse independent gates whose findings return to different phases.
- Do not make the main `SKILL.md` empty; it must remain the control plane.

