# Attachment Mapping Guard Rules

Use this guard before data cleaning, model coding, and final verification when
a contest project has data/media attachments.

## Core Rule

Every raw attachment must be mapped to exactly one official subquestion or to a
shared set such as `[SHARED: Q1,Q3]` before it enters code, cleaning, modeling,
or paper claims.

Do not infer `attachment1 -> Q1` from file order alone. Use the official
problem text, an explicit Qx token in the file name, or field/header evidence.
An official statement that introduces a supplied file by name under an
attachment heading is sufficient evidence for that alias.

## Required Artifact

Run:

```powershell
python $PROJECT_ROOT\.codex\skills\mira\scripts\attachment_mapping_guard.py --root <project-root> --write-report checks\attachment_mapping_report.md --write-json planning\attachment_mapping.json --write-md planning\attachment_mapping.md
```

The script inventories files under `data_raw/`, `data/raw/`,
`workspace/data/data_raw/`, and `workspace/data_raw/`. It reads only metadata,
headers, and the first three rows for tabular files.

## Ambiguities

Create `requires_user_decision` only when two or more mappings remain plausible
after checking the official statement, filenames, and field previews. A clear
mapping is accepted directly. Missing files and genuinely ambiguous mappings
remain visible in the `analysis` stage.

## Blocking Policy

- `missing` and `ambiguous` mappings block downstream work.
- Clear mappings do not require an approval field or approval marker.
- A paper may not freeze results from a data file whose attachment mapping is
  still unresolved.
- Fix by resolving the mapping, moving the file into `data_raw/`, or revising
  the model plan so the file is explicitly unused.

## Paper Use

The paper should not expose this as agent workflow prose. Instead, convert the
confirmed mapping into ordinary contest-paper language:

- "附件 1 给出了问题一评价指标矩阵..."
- "附件 2 作为问题二、问题三的共享路网参数..."
- "未使用的附件或字段须说明原因，避免重复计入同一信息。"
