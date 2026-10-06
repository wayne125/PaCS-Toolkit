import os
import shutil
import subprocess
from typing import List

from pacs.mdrun.simulator.superSimulator import SuperSimulator
from pacs.models.settings import MDsettings
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


class DESMOND(SuperSimulator):
    def run_md(self, settings: MDsettings, cycle: int, replica: int) -> None:
        dir = settings.each_replica(_cycle=cycle, _replica=replica)

        # Copy msj_file/mdconf into this replica's own dir and run multisim
        # with cwd=dir, instead of cwd=dirname(msj_file). Desmond's job
        # control ignores -o's absolute path for WHERE output actually
        # lands when run through job control (even with -HOST localhost):
        # all {JOBNAME}-prefixed output files are written to multisim's
        # cwd, not to -o's directory - confirmed against a real run.
        # Running with cwd=dirname(msj_file) directly (one shared
        # jobscripts/ dir) would therefore make every parallel replica's
        # subprocess write prd-out.cms/prd_trj/prd.log etc into the SAME
        # directory, colliding under PaCS-MD's parallel replica execution.
        # The msj's own `cfg_file = "production.cfg"` reference is a fixed
        # literal basename (see jobscripts/desmond/production.msj), so the
        # copied cfg must be named exactly that regardless of mdconf's own
        # source filename.
        shutil.copy(str(settings.mdconf), f"{dir}/production.cfg")
        msj_basename = os.path.basename(str(settings.msj_file))
        shutil.copy(str(settings.msj_file), f"{dir}/{msj_basename}")

        # Build the multisim command for Desmond
        # Input .cms as positional arg, -m for the .msj job script,
        # -o for output .cms, -JOBNAME for job name, -HOST, -maxjob, -mode, -lic from settings
        #
        # NOTE: no -c flag here. production.msj's own
        # `simulate { cfg_file = "production.cfg" ... }` stage already
        # supplies the cfg for this single-stage job. Passing -c
        # <settings.mdconf> (an absolute path) IN ADDITION to that relative
        # cfg_file reference makes the job server's input-file sandbox see
        # two different source paths both mapped to the destination
        # basename "production.cfg" and fail with:
        # "error adding input file: Two different input files (...) are
        # being sent to the same runtime destination" - confirmed against
        # a real run. settings.mdconf is still required/validated elsewhere
        # (see MDsettings.check) since it is what production.msj's
        # cfg_file field must agree with.
        # -WAIT: without it, multisim submits the job to job control and
        # returns immediately (prints "JobId: ..." and exits 0) instead of
        # blocking until the MD run actually finishes - confirmed against
        # a real run, where prd.cms was never written because run_md
        # returned before the job had even started computing.
        lic_flag = f"-lic {settings.desmond_lic}" if settings.desmond_lic else ""
        cmd_run = f"{settings.cmd_mpi} {settings.cmd_serial} \
                input{settings.structure_extension} \
                -JOBNAME prd \
                -HOST {settings.desmond_host} \
                -maxjob {settings.desmond_maxjob} \
                -m {msj_basename} \
                -mode umbrella \
                -o prd{settings.structure_extension} \
                -WAIT \
                {lic_flag} \
                1> multisim_stdout.log 2>&1"  # NOQA: E221

        # cwd=dir (not dirname(msj_file)): multisim's actual output
        # filenames are {JOBNAME}-prefixed and always land in cwd
        # regardless of -o's directory, so cwd must be this replica's own
        # dir both to resolve cfg_file (now copied alongside) and to keep
        # each parallel replica's job files isolated.
        res_run = subprocess.run(cmd_run, shell=True, cwd=dir)

        # NOTE: do not trust res_run.returncode alone. Confirmed against a
        # real run that crashed mid-simulation ("NAN encountered in
        # piston", MPI_ABORT, "Multisim failed." in prd_multisim.log): the
        # subprocess still exits 0. Root cause, confirmed in Schrodinger's
        # own source (multisimstartup.py: `Startup(sys.argv).launch()` is
        # a bare statement - its return value is discarded and the
        # process falls through to the interpreter's default exit code 0
        # under -WAIT, regardless of job outcome). multisim's own
        # prd_multisim.log (the high-level orchestration log - NOT
        # prd.log, which is desmond's raw backend log and never contains
        # this text) always prints one of "Multisim completed."/"Multisim
        # partially completed."/"Multisim failed." (see cmj.py) - that
        # line is the only reliable success signal for a job-control-
        # launched run.
        multisim_log = f"{dir}/prd_multisim.log"
        multisim_ok = False
        try:
            with open(multisim_log) as f:
                log_text = f.read()
            multisim_ok = "Multisim completed." in log_text
        except FileNotFoundError:
            pass

        if res_run.returncode != 0 or not multisim_ok:
            LOGGER.error("error occurred at run command")
            LOGGER.error(f"see {dir}/multisim_stdout.log and {multisim_log}")
            exit(1)

    def run_MPI(
        self, settings: MDsettings, cycle: int, groupreplica: List[int]
    ) -> None:
        pass
