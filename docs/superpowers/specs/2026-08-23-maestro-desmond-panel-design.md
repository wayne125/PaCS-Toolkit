# Maestro Desmond PaCS-MD Setup Panel — Design

## Purpose

A GUI plugin installable inside Schrodinger Maestro that generates the
`input.toml` (plus an exported starting structure) needed to run PaCS-MD's
Desmond adapter, without the user hand-writing TOML or exporting structures
manually. Scope for v1: generate config files only — it does not launch
`pacs mdrun` itself.

## Non-goals (v1)

- Does not support all 7 PaCS-MD analyzer types — only `target` and `rmsd`.
- Does not launch or monitor the PaCS-MD run itself.
- Does not generate or edit the `.msj`/`.cfg` production job files — it
  references existing ones (defaulting to `jobscripts/desmond/`).

## File structure

```
maestro_plugin/
  pacs_desmond_panel.py
```

Lives inside the PaCS-Toolkit repo (not a separate project) since it
generates PaCS-Toolkit's own config format and defaults to
`jobscripts/desmond/` templates already in this repo.

## Registration

Standard Maestro custom-panel convention, verified against both the official
docs (`maestro_overview.md`) and a real working plugin
(`schrodinger_utils/maestro_scripts/maestro_notes.py`):

```python
# Name: PaCS-MD Desmond Setup
# Command: pythonrun pacs_desmond_panel.PaCSDesmondPanel
```

Runs inside Maestro's own bundled Python/PyQt6 environment — no
`$SCHRODINGER/run` invocation needed (unlike the CLI exporter's
`traj_util`-based code, which runs standalone).

## Form fields

Grouped to mirror `input.toml`'s existing section layout:

- **Structure** (read-only): shows the currently selected Maestro project
  table entry, obtained via `maestro.project_table_get()`. Errors clearly if
  nothing is selected.
- **Simulator files**: `msj_file` / `mdconf` file pickers, default to
  `jobscripts/desmond/production.msj` / `production.cfg` resolved relative to
  the plugin's own file location (`os.path.dirname(__file__)/../jobscripts/desmond/`).
- **Analyzer**: `type` dropdown (`target`, `rmsd`), `threshold` (numeric),
  `reference` (file picker), `selection1` / `selection2` (ASL text fields).
- **Basic**: `n_replica`, `max_cycle`, `n_parallel`, `trial`, `centering`
  (checkbox, default on), `centering_selection` (text, default `"protein"`).
- **Output**: `working_dir` (directory picker) — destination for `input.toml`
  and the exported structure.
- **Advanced** (collapsed by default): `desmond_host`, `desmond_maxjob`,
  `desmond_lic`, `rmmol`, `rmfile` — mirroring `MDsettings` defaults.

`simulator = "desmond"` and `analyzer = "desmond"` are fixed, not
user-editable.

## Data flow

On "Generate":

1. **Validate** — entry selected, `working_dir` writable, `msj_file`/`mdconf`
   exist, `threshold` is numeric. Inline errors; nothing is written until
   all required fields are valid.
2. **Export structure** — write the selected entry to
   `{working_dir}/structure.cms`. Exact API call (fresh `StructureWriter`
   export vs. reusing an already-known source `.cms` path if the entry came
   from a prior Desmond job) is an implementation-time detail to confirm
   against the docs during planning, not resolved in this design.
3. **Write `input.toml`** — same section-grouped style as the reference
   example inspected during PaCS-Toolkit's own Desmond adapter work, with
   `simulator`/`analyzer` fixed to `"desmond"`.
4. **Confirm** — dialog: "written to `{working_dir}` — run with
   `pacs mdrun -t <trial> -f input.toml`".

## Error handling

Explicit, inline validation for: no entry selected, missing or nonexistent
`msj_file`/`mdconf` path, non-numeric `threshold`, unwritable `working_dir`.
No partial or silent writes — generation either fully succeeds or writes
nothing.

## Testing

No Maestro test harness is available, so anything touching the live
`maestro` module can't be unit-tested — same constraint the CLI exporter
adapter already has. Mitigation: split the design into two pieces —

- **GUI glue** (reading the Maestro entry, collecting form values) — 
  untestable without a real Maestro session; validated manually.
- **Settings → TOML serialization** — a pure function (dict of collected
  values in, TOML text out) with no Maestro dependency. This part follows
  normal TDD.

Real end-to-end validation (does the panel actually work inside Maestro,
does the generated `input.toml` actually run) has to be manual, done by the
user inside a real Maestro session.

## Open questions carried into planning

- Exact Maestro API call for structure export (see Data flow, step 2).
- Whether `jobscripts/desmond/` template defaults resolve correctly across
  different Maestro plugin install locations (symlink vs. copy) — needs a
  real-environment check.
