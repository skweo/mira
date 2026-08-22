# Mira 0.5.5

Mira 0.5.5 upgrades high-award writing with figure narrative and mechanism
explanation closure.

## Added Capability

**Figure narrative closure**

Important visuals must function as evidence, not decoration. Mira should make
every main-text figure or table answer three questions:

1. What role does it play: define, derive, compare, validate, explain, or
   decide?
2. What concrete value, threshold, case, policy, or mechanism does the caption
   expose?
3. What claim becomes stronger after the reader sees it?

Preferred artifacts:

- `planning/figure_storyboard.md`
- `figures/figure_index.md`
- `diagrams/diagram_index.md`

Preferred paper behavior:

- state the figure purpose before the figure;
- write a self-contained caption with the key number or decision;
- explain the supported mechanism, threshold, validation, or decision after the
  figure;
- move decorative or duplicate visuals to appendix or delete them.

## New Gate Behavior

The award gate checks whether papers with many figures also contain enough
figure-narrative terms and role records. A paper can now be warned for having
many included figures without clear role labels, mechanism explanations, or
decision-support text.
