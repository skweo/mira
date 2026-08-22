# Computation Backends

Use this file during code implementation, result analysis, and reproducibility checks. Mira may use Python and MATLAB, but must keep outputs traceable and reproducible.

## Expected Local Tools

The user's Windows environment is expected to have:

| Tool | Typical role |
|---|---|
| Python 3.12 | Main data cleaning, optimization, ML, plotting, table/PDF support |
| MATLAB R2025a | MATLAB algorithm examples, numerical experiments, legacy `.m` code from `Math_Model` |
| MiKTeX / `xelatex` | LaTeX compilation for final Chinese contest papers |
| `rg` | Fast local corpus/file search |

Do not assume every Python package or MATLAB toolbox is available. Check before use and record the check in `results/logs/environment_report.md` or `checks/compliance_report.md`.

## Backend Choice

For paper visuals, choose the evidence form before choosing the computation
backend. The claim, intended inference, reader question, data shape, and
evidence role determine whether the evidence should be a chart family, a
structural diagram, a table, a proof/equation, or no visual. Python/MATLAB
availability may change only the implementation or fallback of an already
selected chart family. It must never create a chart choice or erase a
three-dimensional, field, or trajectory requirement. Use the structured
two-layer contract in `visual-backend-rules.md`.

Prefer Python when:

- Data is in CSV/XLSX and needs pandas cleaning.
- Optimization can be handled by `scipy`, installed MILP libraries, or custom heuristics.
- Figures need consistent PDF output through matplotlib.
- The final workflow should be easy to rerun inside the contest project.

Prefer MATLAB when:

- The best available corpus example is `.m` and closely matches the task.
- The task is numerical simulation, matrix computation, image processing, curve fitting, or legacy algorithm reproduction.
- MATLAB toolbox functions materially reduce implementation risk and are available.

Do not mix Python and MATLAB casually. If both are used, define the handoff file format, usually CSV, MAT, JSON, or XLSX, and record it in the result report.

## Python Execution Contract

Python scripts should:

- Live under `code/python/` for new projects, or `code/` for existing simple projects.
- Use relative paths from the project root or resolve paths from `__file__`.
- Save paper-ready outputs to `results/tables/`, `results/logs/`, `results/audits/`, `figures/`, or `results/figures_data/`.
- Fix random seeds for stochastic algorithms.
- Save key parameters and configuration to JSON or Markdown.
- Export figures as PDF when intended for LaTeX/Typst.
- For each paper-intended figure, save a short feature summary next to the figure data, e.g. in `results/figures_data/<figure_stem>_summary.json` or in `figures/figure_index.md`.
- Use bounded retry behavior. If an implementation fails repeatedly, record the last error and switch to a simpler baseline or create a blocker instead of looping.
- Write or update a run log under `results/logs/` for every major run. Include command, timestamp, backend, input files, output files, seed, status, stdout/stderr summary, and traceback summary if failed.
- Regenerate `checks/artifact_manifest.json` and `checks/artifact_manifest.md` after code outputs change.
- Before `contest_final` paper writing or delivery, run
  `build_artifact_manifest.py --root <project-root> --strict`; unresolved
  missing code, major run logs, result reports, indexed figure evidence, or
  paper assets return to their owning stage.
- When using a built-in library or toolbox function that replaces custom code,
  record the function name, package/toolbox, key inputs, parameters, and output
  files. A tool call is evidence only when its input and output artifacts are
  saved.

Recommended environment probe:

```powershell
python --version
python -c "import importlib.util; mods=['numpy','pandas','matplotlib','scipy','sklearn','openpyxl']; [print(m, 'OK' if importlib.util.find_spec(m) else 'MISS') for m in mods]"
```

## MATLAB Execution Contract

Choose the MATLAB transport from the execution context:

- Codex interactive work uses the configured MATLAB MCP server. The agent makes
  the tool call, saves its receipt and outputs, and then registers the receipt.
- Unattended, scheduled, CI, and reproducibility runs use `matlab -batch`.
- Do not let a Python subprocess claim an MCP execution. It may only validate
  and register a receipt from a tool call that already happened.

MATLAB scripts should:

- Live under `code/matlab/` when created by Mira.
- Be runnable non-interactively with `matlab -batch "<command>"`.
- Avoid relying on the current GUI session or unsaved workspace variables.
- Save outputs to files rather than only to figures or console.
- Export figures using `exportgraphics` or `print` to PDF/PNG.
- Save numeric arrays/tables to CSV/XLSX/MAT and summarize them in `results/result_report.md`.
- For each exported figure, save the data source and a short feature summary that the paper stage can cite.
- Write or update a run log under `results/logs/` and regenerate the artifact manifest after outputs change.
- When using toolbox functions such as image processing, fitting,
  optimization, or statistics routines, record the function name, toolbox,
  inputs, parameters, and saved outputs.

Both transports write `results/logs/matlab_visual_capability.json` with schema
version 3. The shared fields are `backend`, `transport`, `execution_context`,
`installed`, `executed`, `status`, `matlab_version`, `source`, `request`,
`command_or_tool`, start/finish timestamps, duration, `log_files`, `evidence`,
and `outputs`. Batch records additionally require `executable` and
`returncode`; MCP records forbid those fields and instead require the MATLAB
server, tool name, request ID, and saved receipt.

For an interactive visual, first prepare a bound request. This creates the
MATLAB source, parameters, a one-use runner, and a request JSON with a unique
request ID plus source/runner/parameter hashes. It does not create a success
record:

```powershell
python <mira-scripts>\run_matlab_visual.py --root <project-root> --prepare-mcp --prefix <figure-prefix> --claim-id <claim-id>
```

The agent must call `mcp__matlab__run_matlab_file` with the exact `script_path`
stored in that request. Save the returned MCP tool-result object inside a
response envelope containing the same server, tool name, request ID, and the
actual start/finish timestamps. Do not rewrite the result content. Then finish
the chain:

```powershell
python <mira-scripts>\run_matlab_visual.py --root <project-root> --complete-mcp --mcp-request-json <request.json> --mcp-response-json <response.json>
```

Completion requires the response to contain both the unique
`MIRA_MCP_REQUEST_ID` marker and MATLAB's `MIRA_MATLAB_FIGURE_OK` marker. It
also verifies request hashes and every declared output before creating figure
provenance, the MCP receipt, and the schema-version-3 capability record.

`matlab_execution_record.py register-mcp` remains available when a complete
receipt already exists:

```powershell
python <mira-scripts>\matlab_execution_record.py register-mcp --root <project-root> --receipt-json results\logs\matlab_mcp_receipt.json
```

`matlab_execution_record.py` validates the saved request and raw response as
well as the normalized receipt; it does not start MATLAB or fabricate a
successful call. A context/transport mismatch, changed request hash, mismatched
request ID, missing raw response, missing output, empty log, or incomplete MCP
identity makes the record invalid.

Recommended environment probe:

```powershell
matlab -batch "disp(version); disp(matlabroot)"
```

If MATLAB startup is slow or times out, keep the failed batch record and log,
then use Python unless MATLAB is essential. An interactive MCP success does not
replace the need for a later batch run when unattended reproducibility is the
claim being checked.

## Reusing Corpus Code

When using `.m` code from `Math_Model`:

1. Copy only the minimal needed files into `materials/raw/code_examples/` or cite the source path in `materials/extracted/code-patterns.md`.
2. Read the code and identify inputs, outputs, algorithm, hardcoded data, random behavior, and dependencies.
3. Rewrite or adapt into the current project's `code/matlab/` or `code/python/`; do not run unknown `.exe` files from the corpus.
4. Add a small sanity test or known benchmark.
5. Save run logs and outputs.

## Result Compatibility

Every backend must produce artifacts the paper can cite:

| Artifact | Required fields |
|---|---|
| Run log | command, timestamp, backend, package/toolbox notes, seed |
| Result table | row meaning, units, method, source script |
| Constraint audit | constraint, left/right side or slack, pass/fail |
| Figure data | source table or generated CSV/JSON |
| Figure summary | figure stem, key pattern, metrics, supported claim, intended paper section |
| Summary JSON | key paper numbers and source file paths |
| Artifact manifest | inventory of code, logs, tables, audits, figure data, figures, diagrams, paper files, references, and unresolved findings |

If a backend cannot produce saved outputs, it does not pass the code phase.

## Notebook And Interpreter Record

A Jupyter notebook may be used to preserve exploratory cells, stdout/stderr, rich outputs, and errors. Treat it as an audit trail:

- keep notebooks under `code/` or `results/logs/`;
- do not rely on notebook memory as the only source of a number;
- save final tables, metrics, figures, and figure data as standalone files;
- when a notebook creates images, update `figures/figure_index.md` with the image source data, generation cell/script, observed features, and supported claim.

For long tasks, use a before/after file scan of `figures/` and `results/figures_data/` to identify new outputs, then add them to the manifest.

## Figure Feature Summaries

The paper stage cannot infer figure content from a filename. For every figure that may appear in the paper, record what the figure shows.

Recommended fields:

| Figure type | Summary fields |
|---|---|
| Time series | time range, start/end values, trend direction, peak, valley |
| Model fit | model name, R2/MAE/RMSE/MAPE or task metric, validation split, fit judgment |
| Correlation | strongest positive/negative correlation, variables, coefficient |
| Feature importance | top variables and importance values |
| Forecast interval | point forecast, interval bounds, confidence or scenario label |
| Classification | sample count, accuracy/F1, main error mode |
| Optimization | best objective, feasibility status, iteration count, active constraints |
| Sensitivity | parameter, perturbation range, result-change range, most sensitive item |

A concise JSON shape is enough:

```json
{
  "figure": "fig_q1_prediction.pdf",
  "source_data": "results/figures_data/q1_prediction.csv",
  "type": "forecast",
  "key_features": ["MAE=...", "peak error occurs at ..."],
  "supported_claim": "问题一预测模型在验证集上误差可接受",
  "paper_location": "问题一结果分析"
}
```

## Safety

- Do not execute unknown `.exe`, `.bat`, or downloaded binary files from `Math_Model`.
- Treat old MATLAB code as illustrative. Many examples use global state, hardcoded paths, or outdated plotting; clean these before use.
- Validate constraints and units independently after adapting any code.
