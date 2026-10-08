import multiprocessing as mp
import subprocess
from pathlib import Path

from pacs.models.settings import MDsettings
from pacs.utils.logger import close_logger, generate_logger

LOGGER = generate_logger(__name__)


def detect_n_replica(settings: MDsettings, cycle: int) -> int:
    # detect the n_replica in cycle001
    n_replica = 0
    for replica in range(1, 1000):
        replica_dir = Path(settings.each_replica(_cycle=cycle, _replica=replica))
        if not replica_dir.exists():
            n_replica = replica - 1
            break

    if n_replica == 0:
        LOGGER.error(f"replica directory does not exist in cycle{cycle:03}")
        exit(1)
    return n_replica


def detect_n_cycle(settings: MDsettings) -> int:
    max_cycle = 0
    for cycle in range(1, 1000):
        cycle_dir = Path(settings.each_cycle(_cycle=cycle))
        if not cycle_dir.exists():
            max_cycle = cycle - 1
            break
    return max_cycle


def make_top(settings: MDsettings) -> None:
    if settings.analyzer == "mdtraj":
        make_top_mdtraj(settings)
    elif settings.analyzer == "gromacs":
        make_top_gmx(settings)
    elif settings.analyzer == "cpptraj":
        make_top_cpptraj(settings)
    elif settings.analyzer == "desmond":
        make_top_desmond(settings)
    else:
        LOGGER.error("analyze tool is not specified")
        exit(1)


def make_top_mdtraj(settings: MDsettings) -> None:
    import mdtraj as md

    dir = settings.each_replica(_cycle=0, _replica=1)
    ext = settings.trajectory_extension
    if Path(f"{dir}/rmmol_top.pdb").exists():
        LOGGER.warn(f"{dir}/rmmol_top.pdb already exists. continue")
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.error(f"{dir}/prd{ext} does not exist")
        exit(1)
    traj = md.load_frame(
        f"{dir}/prd{ext}",
        index=0,
        top=settings.top_mdtraj,
    )
    keep_select = traj.top.select(settings.keep_selection)
    extracted_traj = traj.atom_slice(keep_select)
    extracted_traj.save(f"{dir}/rmmol_top.pdb")
    LOGGER.info(f"topology file rmmol_top.pdb has been created in {dir}")


def make_top_gmx(settings: MDsettings) -> None:
    dir = settings.each_replica(_cycle=0, _replica=1)
    ext = settings.trajectory_extension
    if Path(f"{dir}/rmmol_top.pdb").exists():
        LOGGER.warn(f"{dir}/rmmol_top.pdb already exists. continue")
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.error(f"{dir}/prd{ext} does not exist")
        exit(1)
    # create new gro file without water
    cmd_convert_gro = f"echo {settings.keep_selection} \
            | {settings.cmd_gmx} trjconv \
            -f {dir}/prd{ext} \
            -s {settings.each_replica(_cycle=0, _replica=1)}/prd.tpr \
            -n {settings.index_file} \
            -o {dir}/rmmol_top.pdb \
            -b 0 \
            -e 0 \
            1> {dir}/convert_gro.log 2>&1"  # NOQA: E221
    res_convert_gro = subprocess.run(cmd_convert_gro, shell=True)
    if res_convert_gro.returncode != 0:
        LOGGER.error("error occurred at trjconv command")
        exit(1)

    # create a new topology file
    cmd_convert_tpr = f"echo {settings.keep_selection} \
            | {settings.cmd_gmx} convert-tpr \
            -s {settings.each_replica(_cycle=0, _replica=1)}/prd.tpr \
            -o {dir}/rmmol_top.tpr \
            -n {settings.index_file} \
            1> {dir}/convert_tpr.log 2>&1"  # NOQA: E221
    res_convert_tpr = subprocess.run(cmd_convert_tpr, shell=True)
    if res_convert_tpr.returncode != 0:
        LOGGER.error("error occurred at convert-tpr command")
        exit(1)
    LOGGER.info(f"topology file rmmol_top.pdb has been created in {dir}")


def make_top_cpptraj(settings: MDsettings) -> None:
    dir = settings.each_replica(_cycle=0, _replica=1)
    ext = settings.trajectory_extension
    if Path(f"{dir}/rmmol_top.pdb").exists():
        LOGGER.warn(f"{dir}/rmmol_top.pdb already exists. continue")
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.error(f"{dir}/prd{ext} does not exist")
        exit(1)
    cmd_cpptraj = [
        f"parm {settings.topology}",
        f"trajin {dir}/prd{ext}",
        f"strip !({settings.keep_selection})",
        f"trajout {dir}/rmmol_top.pdb onlyframes 1",
        "run",
        "quit",
    ]
    with open(f"{dir}/make_top.cpptraj", "w") as f:
        f.write("\n".join(cmd_cpptraj))
    run_cpptraj = f"cpptraj \
            -i {dir}/make_top.cpptraj \
            1> {dir}/make_top.log 2>&1"  # NOQA: E221
    res_cpptraj = subprocess.run(run_cpptraj, shell=True)
    if res_cpptraj.returncode != 0:
        LOGGER.error("error occurred at cpptraj command")
        exit(1)
    LOGGER.info(f"topology file rmmol_top.pdb has been created in {dir}")


def make_top_desmond(settings: MDsettings) -> None:
    from schrodinger.application.desmond.packages import traj_util, topo

    dir = settings.each_replica(_cycle=0, _replica=1)
    ext = settings.structure_extension
    if Path(f"{dir}/rmmol_top.cms").exists():
        LOGGER.warn(f"{dir}/rmmol_top.cms already exists. continue")
    if not Path(f"{dir}/prd-out{ext}").exists():
        LOGGER.error(f"{dir}/prd-out{ext} does not exist")
        exit(1)

    _, cms_model, _ = traj_util.read_cms_and_traj(f"{dir}/prd-out{ext}")
    reduced_cms_model, _ = topo.extract_subsystem(cms_model, settings.keep_selection)
    reduced_cms_model.write(f"{dir}/rmmol_top.cms")
    LOGGER.info(f"topology file rmmol_top.cms has been created in {dir}")


def rmmol(settings: MDsettings, cycle: int, last_cycle: bool) -> None:
    n_replica = detect_n_replica(settings, cycle)
    n_loop = (n_replica + settings.n_parallel - 1) // settings.n_parallel
    replicas = [x + 1 for x in range(n_replica)]
    for i in range(n_loop):
        processes = []
        start = i * settings.n_parallel
        end = min((i + 1) * settings.n_parallel, n_replica)
        for replica in replicas[start:end]:
            if settings.analyzer == "mdtraj":
                p = mp.Process(
                    target=rmmol_replica_mdtraj,
                    args=(settings, cycle, replica, last_cycle),
                )
            elif settings.analyzer == "gromacs":
                p = mp.Process(
                    target=rmmol_replica_gmx,
                    args=(settings, cycle, replica, last_cycle),
                )
            elif settings.analyzer == "cpptraj":
                p = mp.Process(
                    target=rmmol_replica_cpptraj,
                    args=(settings, cycle, replica, last_cycle),
                )
            elif settings.analyzer == "desmond":
                p = mp.Process(
                    target=rmmol_replica_desmond,
                    args=(settings, cycle, replica, last_cycle),
                )
            else:
                LOGGER.error("analyze tool is not specified")
                exit(1)
            p.start()
            processes.append(p)
        for p in processes:
            p.join()
        for p in processes:
            if p.exitcode != 0:
                LOGGER.error("error occurred at child process")
                exit(1)
        # Not necessary, but just in case.
        for p in processes:
            p.close()

    # LOGGER.info(f"trajectory files in cycle{cycle:03} have been reduced")
    record_finished(settings, cycle)


def rmmol_replica_mdtraj(
    settings: MDsettings, cycle: int, replica: int, last_cycle: bool
) -> None:
    import mdtraj as md

    ext = settings.trajectory_extension
    if cycle == 0 and replica >= 2:
        return
    dir = settings.each_replica(_cycle=cycle, _replica=replica)
    # file check
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.warn(f"{dir}/prd{ext} does not exist")
        return

    # create new trajectory without water
    traj = md.load(f"{dir}/prd{ext}", top=settings.top_mdtraj)
    keep_select = traj.top.select(settings.keep_selection)
    extracted_traj = traj.atom_slice(keep_select)
    extracted_traj.save(f"{dir}/prd_rmmol{ext}")

    # remove previous trajectory
    if not last_cycle:
        res_rm = subprocess.run(f"rm {dir}/prd{ext}", shell=True)
        if res_rm.returncode != 0:
            LOGGER.error("error occurred at rm command")
            exit(1)


def rmmol_replica_gmx(
    settings: MDsettings, cycle: int, replica: int, last_cycle: bool
) -> None:
    ext = settings.trajectory_extension
    if cycle == 0 and replica >= 2:
        return
    dir = settings.each_replica(_cycle=cycle, _replica=replica)
    # file check
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.warn(f"{dir}/prd{ext} does not exist")
        return

    # create new trajectory without water
    if settings.nojump is True:
        pbc_option = "-pbc nojump"
    else:
        pbc_option = "-pbc mol -ur compact"

    cmd_trjconv = f"echo {settings.keep_selection} \
            | {settings.cmd_gmx} trjconv \
            -f {dir}/prd{ext} \
            -s {dir}/prd.tpr \
            -o {dir}/prd_rmmol{ext} \
            -n {settings.index_file} \
            {pbc_option} \
            1> {dir}/rmmol.log 2>&1"  # NOQA: E221
    res_trjconv = subprocess.run(cmd_trjconv, shell=True)
    if res_trjconv.returncode != 0:
        LOGGER.error("error occurred at trjconv command")
        exit(1)

    # remove previous trajectory
    if not last_cycle:
        res_rm = subprocess.run(f"rm {dir}/prd{ext}", shell=True)
        if res_rm.returncode != 0:
            LOGGER.error("error occurred at rm command")
            exit(1)


def rmmol_replica_cpptraj(
    settings: MDsettings, cycle: int, replica: int, last_cycle: bool
) -> None:
    ext = settings.trajectory_extension
    if cycle == 0 and replica >= 2:
        return
    dir = settings.each_replica(_cycle=cycle, _replica=replica)
    # file check
    if not Path(f"{dir}/prd{ext}").exists():
        LOGGER.warn(f"{dir}/prd{ext} does not exist")
        return

    # create new trajectory without water
    cmd_cpptraj = [
        f"parm {settings.topology}",
        f"trajin {dir}/prd{settings.trajectory_extension}",
        "image",
        f"strip !({settings.keep_selection})",
        f"trajout {dir}/prd_rmmol{settings.trajectory_extension}",
        "run",
        "quit",
    ]
    with open(f"{dir}/rmmol.cpptraj", "w") as f:
        f.write("\n".join(cmd_cpptraj))

    res_cpptraj = subprocess.run(
        f"cpptraj -i {dir}/rmmol.cpptraj 1> {dir}/rmmol.log 2>&1", shell=True
    )
    if res_cpptraj.returncode != 0:
        LOGGER.error("error occurred at cpptraj command")
        exit(1)
    # remove previous trajectory
    if not last_cycle:
        res_rm = subprocess.run(f"rm {dir}/prd{ext}", shell=True)
        if res_rm.returncode != 0:
            LOGGER.error("error occurred at rm command")
            exit(1)


def rmmol_replica_desmond(
    settings: MDsettings, cycle: int, replica: int, last_cycle: bool
) -> None:
    from schrodinger.application.desmond.packages import traj, traj_util, topo

    ext = settings.structure_extension
    if cycle == 0 and replica >= 2:
        return
    dir = settings.each_replica(_cycle=cycle, _replica=replica)
    # file check
    if not Path(f"{dir}/prd-out{ext}").exists():
        LOGGER.warn(f"{dir}/prd-out{ext} does not exist")
        return

    # create new trajectory and topology without the stripped molecules
    msys_model, cms_model, tr = traj_util.read_cms_and_traj(f"{dir}/prd-out{ext}")
    aids = cms_model.select_atom(settings.keep_selection)
    if cms_model.need_msys:
        gids = topo.aids2gids(cms_model, aids, include_pseudoatoms=True)
    else:
        gids = cms_model.convert_to_gids(aids, with_pseudo=True)

    reduced_frames = [fr.reduce(gids) for fr in tr]
    reduced_cms_model, _ = topo.extract_subsystem(cms_model, settings.keep_selection)

    traj.write_traj(reduced_frames, f"{dir}/prd_rmmol_trj")
    rmmol_cms_path = f"{dir}/prd_rmmol-out{ext}"
    reduced_cms_model.write(rmmol_cms_path)
    # reduced_cms_model still carries the original prd_trj trajectory
    # reference (extract_subsystem does not update it), and the original
    # prd_trj gets deleted below when not last_cycle - without this fix
    # prd_rmmol-out's trajectory pointer would be permanently dangling.
    from pacs.utils.desmond_io import fix_trajectory_property

    fix_trajectory_property(rmmol_cms_path, "prd_rmmol_trj")

    # remove previous trajectory
    if not last_cycle:
        import shutil

        Path(f"{dir}/prd-out{ext}").unlink()
        shutil.rmtree(f"{dir}/prd_trj", ignore_errors=True)


def rmmol_log_add_info(settings: MDsettings) -> None:
    if settings.analyzer == "mdtraj":
        pass
    elif settings.analyzer == "gromacs":
        rmmol_log_add_info_gmx(settings)
    elif settings.analyzer == "cpptraj":
        pass
    elif settings.analyzer == "desmond":
        pass
    else:
        LOGGER.error("analyze tool is not specified")
        exit(1)


def record_finished(settings: MDsettings, cycle: int) -> None:
    dir = settings.each_cycle(_cycle=cycle)
    logger = generate_logger(f"{cycle}_rmmol", f"{dir}/summary/progress.log")
    logger.info(f"trajectory files in cycle{cycle:03} have been reduced")
    close_logger(logger)


def rmmol_log_add_info_gmx(settings: MDsettings) -> None:
    LOGGER.info("The 'prd.tpr' files are probably no longer needed.")
    LOGGER.info("It is recommended to remove 'prd.tpr' files to save disk space.")
    LOGGER.info(
        "If needed later, you can manually regenerate the 'prd.tpr' files from "
        "the 'input.gro' files."
    )


def rmmol_all(settings: MDsettings) -> None:
    max_cycle = detect_n_cycle(settings)
    for cycle in range(max_cycle + 1):
        rmmol(settings, cycle, cycle == max_cycle)
    LOGGER.info("rmmol has been finished successfully")
