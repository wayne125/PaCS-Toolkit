# desmond

- Schrodinger Desmond, driven through its Python API (`$SCHRODINGER/run python3`).
- ⚠️ *experimental* — verified end-to-end (simulator, exporter, analyzer, and a
  real multi-cycle `pacs mdrun`) against real systems, but newer than the
  other three engines and with sharper edges. Read this whole file before
  your first run; every point below was a real failure hit while building
  and validating this adapter.

| simulator | analyzer | available |
| --------- | -------- | --------- |
| desmond   | desmond  | o         |
| desmond   | mdtraj/gromacs/cpptraj | x |
| gromacs/amber/namd | desmond | x |

`simulator` and `analyzer` must both be `"desmond"` together — any other
pairing is rejected at startup.

## 1. Run under `$SCHRODINGER/run python3`, not plain `python3`

The Desmond simulator/exporter/analyzer code imports `schrodinger.*` packages
at call time. Always invoke as:

```sh
export SCHRODINGER=/opt/schrodingerYYYY-N   # your install
$SCHRODINGER/run python3 -m pacs mdrun -t 1 -f input.toml
```

## 2. `tomli` is probably missing from Schrodinger's bundled Python

PaCS-Toolkit's own CLI parser needs `tomli` to read `input.toml`. Schrodinger's
bundled interpreter is a separate Python environment from whatever
conda/venv you normally `pip install pacs[all]` into, and it almost
certainly doesn't have it. `--user` installs are disabled on it too
(`Can not perform a '--user' install`). Install to a target directory instead
and put that directory on `PYTHONPATH`:

```sh
mkdir -p ~/pacs_pylibs
$SCHRODINGER/run python3 -m pip install --target=~/pacs_pylibs tomli
export PYTHONPATH=~/pacs_pylibs:$PYTHONPATH
```

## 3. `structure` and `working_dir` must be on a space-free path

This is a PaCS-Toolkit-wide limitation (every engine's simulator builds an
unquoted shell command string), not Desmond-specific — but Desmond setups
commonly start from files on an external drive mounted with a branded,
space-containing path (e.g. `/media/you/One Touch/...`). If `structure` or
`working_dir` resolves through a path with a space, the `cp`/`multisim`
shell commands silently break (`cannot create /media/you/One: Permission
denied`, or similar). Copy your starting structure and point `working_dir`
somewhere space-free first.

`msj_file`/`mdconf` are the one exception — the simulator copies them with
Python's `shutil.copy` (not a shell command), so they're safe to leave on a
space-containing path.

## 4. `production.cfg`'s `trajectory.interval` must stay well below `time`

If you shorten `time` (the per-cycle MD length) from whatever long
reference job you copied `production.cfg` from, you must shorten
`trajectory.interval` proportionally too. Otherwise the cycle's trajectory
only gets 2 frames (`t=0` and the forced last-step write), and PaCS-MD's
exporter crashes: `"The total number of frames now is 2. This is less than
the number of replicas N"`. Rule of thumb: `interval <= time / (2 * n_replica)`
so there's a comfortable margin of distinct candidate frames to rank and
pick `n_replica` winners from.

## 5. Start from a properly *equilibrated* structure, not just minimized

`production.cfg`'s single stage jumps straight into full-timestep NPT at
your target temperature with randomized velocities — there's no restrained
NVT/NPT heating ramp (PaCS-MD does that heating once, upstream, before PaCS
cycles start — it's not repeated every cycle). Feeding it an
energy-minimization-only structure (bad contacts not yet relaxed) reliably
crashes the very first step: `NAN encountered in piston`, `MPI_ABORT`,
`Multisim failed.` Run your own minimization → restrained heating →
unrestrained equilibration (e.g. via Maestro's Desmond GUI, or your own
multi-stage `.msj`) first, and use *that* output as PaCS-MD's `structure`.

## 6. `multisim`'s exit code does not reflect job success

Confirmed by reading Schrodinger's own source
(`multisimstartup.py`: `Startup(sys.argv).launch()` is a bare statement —
its return value is discarded, so the process falls through to exit 0 under
`-WAIT` regardless of whether the job actually succeeded). The adapter
compensates by reading `prd_multisim.log`'s own `"Multisim completed."` /
`"Multisim failed."` summary line — you don't need to do anything extra for
this, just don't be surprised if you ever see a "successful" shell exit
code on a run that actually crashed if you're inspecting things by hand.

## 7. Output files are named `prd-out.*`, not `prd.*`

`multisim` always writes `{JOBNAME}-out{ext}` (JOBNAME is fixed to `"prd"`
by the adapter) regardless of what you pass to `-o`. So a cycle's real
output structure is `prd-out.cms`, its trajectory directory is `prd_trj/`,
its energy log is `prd.ene`, and its own run log is `prd.log` (next to
`prd_multisim.log`, the higher-level orchestration log). If you're
inspecting a replica directory by hand, look for `prd-out.cms`.

## 8. If `multisim` fails immediately with a job-control/host error

```
schrodinger.infra.mmcheck.MmException: mmjob_hosts_length returned error
code 27 (MMJOB_ERROR) ... Connection refused
```

Desmond's local job-control daemon (`jobserverd`) isn't running, and its
state file is stale (commonly after a reboot that didn't shut it down
cleanly). Its `runstate` file lives under
`~/Documents/schrodinger/<user>/jobserverd-<hostname>/runstate` and records
a port/PID that no longer exists. Move or delete that file — the next
`multisim` invocation will start a fresh daemon.

## 9. `centering` is not implemented for Desmond

Set `centering = false`. If left `true`, the exporter just logs a warning
every cycle and uses coordinates as-is.

## 10. Single GPU means `n_parallel` doesn't buy you anything

`desmond_maxjob`/`n_parallel` beyond 1 just queue on the same GPU — set
`n_parallel = 1` unless you actually have multiple GPUs/hosts.

## See also

- [`maestro_plugin/pacs_desmond_panel.py`](../../maestro_plugin/pacs_desmond_panel.py) —
  generates `input.toml` from inside Maestro instead of hand-writing it.
- [`input.toml`](input.toml) — a real worked example matching the settings
  validated in this directory's own test runs.
