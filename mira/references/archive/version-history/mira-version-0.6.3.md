# Mira 0.6.3

Mira 0.6.3 is a control-plane cleanup upgrade. It does not add a new modeling
gate. Its purpose is to reduce the chance that Mira's own accumulated version
history and repeated command lists distract later agents from the active
paper-generation contract.

## New Standard

- Keep `SKILL.md` as a lean control plane: current baseline, startup route,
  state machine, hard rules, and references to routed details.
- Keep version history in `references/mira-version-index.md` and individual
  `references/mira-version-*.md` notes instead of loading long historical
  paragraphs by default.
- Keep repeated phase commands in `scripts/command_profiles.py`; route reports
  may display commands, but `route_references.py` should not own the full
  command matrix.
- Do not delete historical rules or gates to reduce length. First route them,
  profile them, and validate that current paper runs still load the needed
  references.

## Non-goals

- Do not weaken 0.6.1 abstract/front-matter checks.
- Do not weaken 0.6.2 derivation-density checks.
- Do not remove quality gates merely because there are many scripts.
