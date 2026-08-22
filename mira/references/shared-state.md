# Shared State

`planning/mira_state.json` is the cross-stage control summary. Artifacts remain
the evidence plane; shared state only points to blockers, pending decisions,
stale evidence, and the current public stage.

## Public Schema

```json
{
  "version": 2,
  "stage": {"current": "implementation", "requested": "implementation"},
  "phase": {"current": "implementation", "requested": "implementation"},
  "output_level": "reproducible_draft",
  "markers": [],
  "requires_user_decision": [],
  "open_items": [],
  "stale": [],
  "verdict": "PASS"
}
```

`phase` is retained only for old consumers and carries the normalized stage.
New code should read `stage.current`.

## Ownership

| Evidence or blocker | Owner stage |
|---|---|
| problem, attachment, field, unit, source, privacy, data readiness | `analysis` |
| method, assumption, symbol, objective, constraint, derivation, validation | `modeling` |
| code, solver, run, result, provenance, chart, structural diagram | `implementation` |
| paper structure, prose, table, citation, compilation, delivery | `paper` |

A check for a later stage includes blockers owned by all earlier stages.

## Decision State

Use `requires_user_decision` for unresolved choices. Each entry should contain:

- `stage`
- `source`
- `message`
- options and recommendation in the owning artifact when applicable
- decision evidence after resolution

Legacy decision, approval, prompt, and lineage files are ignored. They are not
loaded into shared state and cannot block a current stage. Create
`requires_user_decision` only for a current, concrete ambiguity that cannot be
resolved from the official statement or available evidence.

## Decision Marker

Only `[REQUIRES_USER_DECISION]` and its structured JSON equivalent create a
decision blocker. Use them only for a concrete ambiguity that cannot be
resolved from the official statement or available evidence. Arbitrary
`BLOCKER`, draft, approval, or pending-human text is ignored; current check
reports express technical failures directly as `FAIL`.

## Freshness

When source artifacts are newer than the reports or decisions that validate
them, state records a stale signal. Re-run the relevant stage checks instead of
trusting an older PASS.

## Commands

```powershell
python scripts\mira_state.py --root <project-root> --stage analysis --write --check
python scripts\mira_state.py --root <project-root> --stage modeling --write --check
python scripts\mira_state.py --root <project-root> --stage implementation --write --check
python scripts\mira_state.py --root <project-root> --stage paper --write --check
```
