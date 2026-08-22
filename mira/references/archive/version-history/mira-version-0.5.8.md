# Mira 0.5.8

Mira 0.5.8 upgrades citation behavior from reference-count targets to precise
source binding.

## Added Capability

**Citation precision**

Mira should require sources only where they carry real evidence: method
selection, external data, parameter values, software/toolboxes, or domain
claims. The target is not "more references"; it is fewer unsupported claims and
fewer decorative citations.

Preferred artifacts:

- `planning/citation_binding.md`
- `results/tables/citation_binding.csv`

Preferred paper behavior:

- cite sources near the claims they support;
- bind every important citation to a method, parameter, data source, software
  claim, or domain assumption;
- avoid padding references to satisfy a count;
- use explicit waivers when no real source is available and the claim is
  instead based on problem data or an assumption.

## New Gate Behavior

The presentation budget, presentation-strength gate, quality-balance gate, and
award gate no longer treat a low reference count as a standalone weakness. They
check whether nontrivial method, parameter, data, software, and domain claims
have precise support, whether large bibliographies are actually bound to
in-text claims, and whether citation-binding artifacts exist when citations are
used heavily.
