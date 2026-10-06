# Simulator

- In PaCS-MD, simulations corresponding to the `simulator` are executed. Gromacs, Amber, NAMD, and Desmond are supported.
- In each cycle, `n_replica` simulations are executed. `n_parallel` simulations are will run in parallel. If `n_replica` is not a multiple of `n_parallel`, or in cycle 0, the remainder of the simulations will run in series.
- If you want to run multiple replica simulations in parallel using MPI, set `cmd_mpi`. If `cmd_mpi` is not set, parallel execution will be performed using the multiprocessing module of python.

*Content*
- [When are `cmd_serial` \& `cmd_parallel` used ?](#when-are-cmd_serial--cmd_parallel-used-)
- [Gromacs](#gromacs)
    - [keywords](#keywords)
- [Amber](#amber)
    - [keywords](#keywords-1)
- [NAMD](#namd)
    - [keywords](#keywords-2)
- [Desmond](#desmond)
    - [keywords](#keywords-3)


## When are `cmd_serial` & `cmd_parallel` used ?
- See the table below for `cmd_serial` and `cmd_parallel` in the input file. `cmd_serial` is used if cycle0 or `n_parallel`=1. If `n_replica` is not divisible by `n_parallel`, then `cmd_serial` is used for the remaining replicas. Otherwise, `cmd_parallel` is used.

| GPU | MPI | n_parallel | command      |
| --- | --- | ---------- | ------------ |
| x   | x   | 1          | cmd_serial   |
| x   | x   | n          | cmd_serial   |
| x   | o   | 1          | cmd_serial   |
| x   | o   | n          | cmd_parallel |
| o   | x   | 1          | cmd_serial   |
| o   | x   | n          | cmd_serial   |
| o   | o   | 1          | cmd_seiral   |
| o   | o   | n          | cmd_parallel |

## Gromacs
To run the simulation using gromacs, write in the inputfile as in [this example](inputfile.md#gromacs). The details of each keyword are as follows.

#### keywords
- **simulator: str, required**
  - Software used inside PaCS-MD. e.g. "gromacs"
- **cmd_mpi: str, default=""**
  - Command for MPI parallelizataion. e.g. "mpirun -np 4"
- **cmd_serial: str, required**
  - Command to run simulation in serial. e.g. "gmx_mpi mdrun -ntomp 6"
- **cmd_parallel: str, default=cmd_serial**
  - Command to run simulation in parallel. e.g. "gmx_mpi mdrun -ntomp 6"
- **structure: str, required**
  - Structure file path for MD simulation. e.g. "./input.gro"
  - This is also used as the initial structure of PaCS-MD
- **topology: str, required**
  - Topology file path for MD simulation. e.g. "./topol.top"
- **mdconf: str, required**
  - Parameter file path for MD simulation. e.g. "./parameter.mdp"
- **index_file: str, required**
  - Gromacs index file path. e.g. "./index.ndx"
- **trajectory_extension: str, required**
  - Trajectory file extension. (The "." is necessary.) e.g. ".trr"

## Amber
To run the simulation using amber, write in the inputfile as in [this example](inputfile.md#amber). The details of each keyword are as follows.

#### keywords
- **simulator: str, required**
  - Software used inside PaCS-MD. e.g. "amber"
- **cmd_mpi: str, default=""**
  - Command for MPI such as mpirun. e.g. "mpirun -np 4"
- **cmd_serial: str, required**
  - Command to run simulation in serial. e.g. "pmemd.cuda"
- **cmd_parallel: str, default=cmd_serial**
  - Command to run simulation in parallel. e.g. "pmemd.cuda"
- **structure: str, required**
  - Structure file path for MD simulation. e.g. "./input.rst7"
  - This is also used as the initial structure of PaCS-MD.
- **topology: str, required**
  - Topology file path for MD simulation. e.g. "./topology.parm7"
- **mdconf: str, required**
  - Parameter file path for MD simulation. e.g. "./parameter.mdin"
- **trajectory_extension: str, required**
  - Trajectory file extension. (The "." is necessary.) e.g. ".nc"

## NAMD
To run the simulation using NAMD, write in the inputfile as in [this example](inputfile.md#namd). The details of each keyword are as follows.

#### keywords
- **simulator: str, required**
  - Software used inside PaCS-MD. e.g. "namd"
- **cmd_mpi: str, default=""**
  - Command for MPI parallelizataion. e.g. "mpirun -np 4"
- **cmd_serial: str, required**
  - Command to run simulation in serial. e.g. "namd2 +p4"
- **cmd_parallel: str, default=cmd_serial**
  - Command to run simulation in parallel. e.g. "namd2 +p4"
- **structure: str, required**
  - Structure file path for MD simulation. e.g. "./input.pdb"
  - This is also used as the initial structure of PaCS-MD.
- **topology: str, required**
  - Topology file path for MD simulation. e.g. "./topology.psf"
- **mdconf: str, required**
  - Parameter file path for MD simulation. e.g. "./parameter.conf"
- **trajectory_extension: str, required**
  - Trajectory file extension. (The "." is necessary.) e.g. ".dcd"

## Desmond

⚠️ *experimental* - see [`jobscripts/desmond/README.md`](https://github.com/Kitaolab/PaCS-Toolkit/tree/main/jobscripts/desmond)
for required setup steps (running under `$SCHRODINGER/run python3`, a
space-free `structure`/`working_dir`, etc.) before using this. Unlike the
other three engines, Desmond is driven through the Schrodinger Python API
rather than a plain CLI command, so `cmd_serial` is fixed to
`"$SCHRODINGER/utilities/multisim"` and a few extra keywords are needed.

To run the simulation using Desmond, write in the inputfile as in [this example](inputfile.md#desmond). The details of each keyword are as follows.

#### keywords
- **simulator: str, required**
  - Software used inside PaCS-MD. e.g. "desmond"
- **cmd_serial: str, required**
  - Must be `"$SCHRODINGER/utilities/multisim"`.
- **structure: str, required**
  - A fully equilibrated Desmond `.cms` structure (not just energy-minimized - see the README linked above). e.g. "./start.cms"
  - This is also used as the initial structure of PaCS-MD, and as `topology` (the `.cms` serves both roles for Desmond).
- **mdconf: str, required**
  - Desmond `.cfg` parameter file for the production stage. e.g. "./production.cfg"
- **msj_file: str, required**
  - Desmond `.msj` job script for the production stage, referencing `mdconf` via a `cfg_file = "..."` field in its `simulate` block. e.g. "./production.msj"
- **desmond_host: str, default="localhost"**
  - Host passed to multisim's `-HOST` flag.
- **desmond_maxjob: int, default=1**
  - Passed to multisim's `-maxjob` flag. On a single-GPU workstation this has no effect on throughput.
- **desmond_lic: str, optional**
  - Desmond license class, e.g. "DESMOND_GPGPU:16". Only needed if your license setup requires it explicitly.
- **trajectory_extension: str, required**
  - Must be ".dtr" (Desmond's native trajectory format).

