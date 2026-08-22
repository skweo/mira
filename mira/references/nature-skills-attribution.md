# Third-Party Attribution: `nature-skills`

Mira's selective evidence-quality integration was informed by the open-source
repository [`Yuan1z0825/nature-skills`](https://github.com/Yuan1z0825/nature-skills),
fixed at commit `c2a37016ac2868708b262126c7e5684fa2cbd212`.

- License: Apache License 2.0. The complete license text and integration notice
  are retained inside Mira at
  `references/third-party/nature-skills/LICENSE` and
  `references/third-party/nature-skills/NOTICE.md`.
- Integrated scope: statistical evidence contracts, figure-source preflight,
  reference authenticity checks, material page/paragraph anchors, and
  claim-to-evidence-chain validation.
- Mira implementation: these capabilities were reimplemented as native Mira
  scripts, templates, and routing rules. The external skill directory and its
  164 training cases are not copied into the active skill.
- Adaptation notice: Mira adds Chinese mathematical-modeling contest semantics,
  fail-closed contest-final gates, Python/MATLAB provenance, result-ledger
  binding, and compatibility with existing Mira project contracts.
- Explicitly excluded: Nature journal or patent templates, R-only workflows,
  draw.io, Zotero/CNKI/MCP service dependencies, publisher machinery, and
  AI-generated images as quantitative evidence.

This file is the attribution and adaptation record for the selective
integration; it is not an endorsement of the external project's unrelated
workflows or an indication that Mira redistributes its skill tree.
