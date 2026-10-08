import subprocess
from pathlib import Path
from typing import Dict

import numpy as np
from pacs.models.settings import MDsettings
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


def genrepresent(settings: MDsettings) -> None:
    if settings.analyzer == "mdtraj":
        genrepresent_mdtraj(settings)
    elif settings.analyzer == "gromacs":
        genrepresent_gmx(settings)
    elif settings.analyzer == "cpptraj":
        genrepresent_cpptraj(settings)
    elif settings.analyzer == "desmond":
        genrepresent_desmond(settings)
    else:
        LOGGER.error("analyze tool is not specified")
        exit(1)


# using mdtraj
def genrepresent_mdtraj(settings: MDsettings) -> None:
    import mdtraj as md

    # create the directory to store the repr trajectory
    repr_dir = make_reprdir(settings)

    # detect the last cycle
    last_cycle = detect_lastcycle(settings)

    # exetract the repr trajectory from each cycle
    ext = settings.trajectory_extension
    trajs = []
    for cycle in range(last_cycle, -1, -1):  # itration until cycle 0
        cycle_dir = settings.each_cycle(_cycle=cycle)
        if cycle == last_cycle:
            selected_replica = 1
        with open(f"{cycle_dir}/summary/cv_ranked.log", "r") as f:
            for idx, line in enumerate(f):
                if idx == (selected_replica - 1):
                    line = line.strip()
                    (_, selected_replica, _, last_frame, _, _) = line.split(" ")
                    last_frame = int(last_frame)
                    selected_replica = int(selected_replica)
                    LOGGER.info(
                        f"cycle: {cycle}, replica: {selected_replica}, frame: {last_frame}"
                    )
                    break

        # extract trajectory
        rep_dir = Path(settings.each_replica(_cycle=cycle, _replica=selected_replica))
        traj = md.load(
            f"{rep_dir}/{settings.trajectory}",
            top=settings.topology,
        )

        extracted_traj = traj[1 : last_frame + 1]
        trajs.append(extracted_traj)

    # concatenate the repr trajectory from all cycles
    trajs = trajs[::-1]
    concat_traj = md.join(trajs)
    concat_traj.save(f"{repr_dir}/repr_complete{ext}")

    LOGGER.info("genrepresent has been extracted successfully")


# using gmx
def genrepresent_gmx(settings: MDsettings) -> None:
    # create the directory to store the repr trajectory
    repr_dir = make_reprdir(settings)

    # detect the last cycle
    last_cycle = detect_lastcycle(settings)

    frame_time_dict = load_frame_to_time(settings)

    # exetract the repr trajectory from each cycle
    ext = settings.trajectory_extension
    for cycle in range(last_cycle, -1, -1):  # itration until cycle 0
        cycle_dir = settings.each_cycle(_cycle=cycle)
        if cycle == last_cycle:
            selected_replica = 1
        with open(f"{cycle_dir}/summary/cv_ranked.log", "r") as f:
            for idx, line in enumerate(f):
                if idx == (selected_replica - 1):
                    line = line.strip()
                    (_, selected_replica, _, last_frame, _, _) = line.split(" ")
                    last_frame = int(last_frame)
                    selected_replica = int(selected_replica)
                    LOGGER.info(
                        f"cycle: {cycle}, replica: {selected_replica}, frame: {last_frame}"
                    )
                    break
        rep_dir = Path(settings.each_replica(_cycle=cycle, _replica=selected_replica))
        trj = f"{rep_dir}/{settings.trajectory}"
        top = settings.topology
        # extract trajectory from frame 0 to last_frame,
        # but the first frame is truncated when performing trjcat
        # but only for the first cycle, the first frame is not truncated,
        # so not include the first frame
        first_frame = 1 if cycle == 0 else 0
        cmd_trjconv = f"echo System \
            | {settings.cmd_gmx} trjconv \
            -f {trj} \
            -s {top} \
            -o {repr_dir}/repr_cycle{cycle:03}{ext} \
            -b {frame_time_dict[first_frame]} \
            -e {frame_time_dict[last_frame]} \
            1> {repr_dir}/{cycle}_trjconv.log 2>&1"  # NOQA: E221
        res_trjconv = subprocess.run(cmd_trjconv, shell=True)
        if res_trjconv.returncode != 0:
            LOGGER.error("error occurred at trjconv command")
            exit(1)

    # concatenate the repr trajectory from all cycles
    cmd_trjcat = f"for i in $(seq {last_cycle + 1}); \
        do echo c; done \
        | {settings.cmd_gmx} trjcat \
        -f {repr_dir}/repr_cycle*{ext} \
        -o {repr_dir}/repr_complete{ext} \
        -settime \
        1> {repr_dir}/trjcat.log 2>&1"  # NOQA: E702,E221
    res_trjcat = subprocess.run(cmd_trjcat, shell=True)
    if res_trjcat.returncode != 0:
        LOGGER.error("error occurred at trjcat command")
        exit(1)

    # remove the repr trajectory from each cycle
    res_rm = subprocess.run(f"rm {repr_dir}/repr_cycle*", shell=True)
    if res_rm.returncode != 0:
        LOGGER.error(f"error occurred at rm command in cycle {cycle}")
        exit(1)
    LOGGER.info("genrepresent has been extracted successfully")


def genrepresent_cpptraj(settings: MDsettings) -> None:
    # create the directory to store the repr trajectory
    repr_dir = make_reprdir(settings)

    # detect the last cycle
    last_cycle = detect_lastcycle(settings)

    # exetract the repr trajectory from each cycle
    ext = settings.trajectory_extension
    for cycle in range(last_cycle, -1, -1):  # itration until cycle 0
        cycle_dir = settings.each_cycle(_cycle=cycle)
        if cycle == last_cycle:
            selected_replica = 1
        with open(f"{cycle_dir}/summary/cv_ranked.log", "r") as f:
            for idx, line in enumerate(f):
                if idx == (selected_replica - 1):
                    line = line.strip()
                    (_, selected_replica, _, last_frame, _, _) = line.split(" ")
                    last_frame = int(last_frame)
                    selected_replica = int(selected_replica)
                    LOGGER.info(
                        f"cycle: {cycle}, replica: {selected_replica}, frame: {last_frame}"
                    )
                    break
        rep_dir = Path(settings.each_replica(_cycle=cycle, _replica=selected_replica))
        trj = f"{rep_dir}/{settings.trajectory}"
        top = settings.topology
        cmd_cpptraj = [
            f"parm {top}",
            f"trajin {trj}",
            f"trajout {repr_dir}/repr_cycle{cycle:03}{ext} onlyframes 1-{last_frame + 1}",
            "run",
            "quit",
        ]
        with open(f"{repr_dir}/genrepresent.cpptraj", "w") as f:
            f.write("\n".join(cmd_cpptraj))

        res_cpptraj = subprocess.run(
            f"cpptraj -i {repr_dir}/genrepresent.cpptraj 1> {repr_dir}/genrepresent.log \
                    2> {repr_dir}/genrepresent.log --log {repr_dir}/repr_dir.log",
            shell=True,
        )
        if res_cpptraj.returncode != 0:
            LOGGER.error("error occurred at cpptraj command")
            exit(1)

    # concatenate the repr trajectory from all cycles
    cmd_cpptraj = [
        f"parm {top}",
        f"trajin {repr_dir}/repr_cycle*{ext}",
        f"trajout {repr_dir}/repr_complete{ext}",
        "run",
        "quit",
    ]
    with open(f"{repr_dir}/trjcat.cpptraj", "w") as f:
        f.write("\n".join(cmd_cpptraj))
    res_cpptraj = subprocess.run(
        f"cpptraj -i {repr_dir}/trjcat.cpptraj 1> {repr_dir}/trjcat.log \
                2>&1 {repr_dir}/trjcat.log --log {repr_dir}/trjcat.log",
        shell=True,
    )

    # Combining trajectories using cpptraj in pacsmd will cause error
    # So even returncode is 1, pacsmd will ignore
    # if res_cpptraj.returncode != 0:
    #     LOGGER.error("error occurred at cpptraj command")
    #     exit(1)

    # remove the repr trajectory from each cycle
    res_rm = subprocess.run(f"rm {repr_dir}/repr_cycle*", shell=True)
    if res_rm.returncode != 0:
        LOGGER.error(f"error occurred at rm command in cycle {cycle}")
        exit(1)
    LOGGER.info("genrepresent has been extracted successfully")


def genrepresent_desmond(settings: MDsettings) -> None:
    import os
    import shutil
    import subprocess

    from schrodinger.application.desmond import cms as cms_module
    from schrodinger.application.desmond.packages import topo

    # create the directory to store the repr trajectory
    repr_dir = make_reprdir(settings)

    # detect the last cycle
    last_cycle = detect_lastcycle(settings)

    # Concatenating frames by hand (slicing a loaded trajectory's Frame
    # objects in Python and calling traj.write_traj on the combined list)
    # produces a trajectory directory that write_traj does not error on,
    # but that later fails to open at all (open_file_read failed) once the
    # combined frame count is large enough to span multiple internal dtr
    # blob files - confirmed by reproducing this in complete isolation with
    # no PaCS-Toolkit code involved. trj_merge.py, schrodinger's own
    # trajectory tool, produces an equally multi-blob but genuinely
    # readable result for the same data - confirmed by a real round-trip
    # test - so both the per-cycle slicing and the final concatenation are
    # delegated to it here instead of doing either in raw Python.
    schrodinger_run = f"{os.environ['SCHRODINGER']}/run"

    segment_trjs = []
    first_cms_path = None
    for cycle in range(last_cycle, -1, -1):  # iteration until cycle 0
        cycle_dir = settings.each_cycle(_cycle=cycle)
        if cycle == last_cycle:
            selected_replica = 1
        with open(f"{cycle_dir}/summary/cv_ranked.log", "r") as f:
            for idx, line in enumerate(f):
                if idx == (selected_replica - 1):
                    line = line.strip()
                    (_, selected_replica, _, last_frame, _, _) = line.split(" ")
                    last_frame = int(last_frame)
                    selected_replica = int(selected_replica)
                    LOGGER.info(
                        f"cycle: {cycle}, replica: {selected_replica}, frame: {last_frame}"
                    )
                    break

        rep_dir = Path(settings.each_replica(_cycle=cycle, _replica=selected_replica))
        cms_path = f"{rep_dir}/{settings.trajectory}"
        if first_cms_path is None:
            first_cms_path = cms_path

        # last_frame == 0 means this cycle's winning replica is frame 0
        # itself (the cycle's own starting structure, carried over
        # unchanged - no sampled frame improved on it). tr[1:1] is an empty
        # slice, so there is nothing to contribute from this cycle - skip
        # it, since asking trj_merge.py to write a zero-frame trajectory
        # produces no output directory at all (write_traj's own empty-input
        # early return), which would otherwise crash the final concat step
        # with a missing-file error - confirmed by a real run on this exact
        # run's cycles 27-30, all of which plateaued at frame 0.
        if last_frame == 0:
            continue

        trj_path = topo.find_traj_path(cms_module.Cms(cms_path), str(rep_dir))
        if trj_path is None:
            LOGGER.error(f"no trajectory found associated with {cms_path}")
            exit(1)

        seg_base = f"{repr_dir}/cycle{cycle:03}_segment"
        res = subprocess.run(
            [
                schrodinger_run,
                "trj_merge.py",
                cms_path,
                trj_path,
                "-s",
                f"1:{last_frame + 1}:1",
                "-o",
                seg_base,
            ],
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            LOGGER.error(f"error occurred slicing cycle {cycle}: {res.stderr}")
            exit(1)
        segment_trjs.append(f"{seg_base}_trj")

    # concatenate the repr trajectory from all cycles (chronological order)
    segment_trjs = segment_trjs[::-1]
    repr_base = f"{repr_dir}/repr_complete"
    res = subprocess.run(
        [
            schrodinger_run,
            "trj_merge.py",
            first_cms_path,
            *segment_trjs,
            "-concat",
            "0",
            "1",
            "-o",
            repr_base,
        ],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        LOGGER.error(f"error occurred concatenating repr trajectory: {res.stderr}")
        exit(1)

    # trj_merge.py always names its output "{base}-out.cms" - rename to the
    # established repr_complete.cms convention
    shutil.move(f"{repr_base}-out.cms", f"{repr_dir}/repr_complete.cms")

    # clean up intermediate per-cycle segments
    for seg_trj in segment_trjs:
        shutil.rmtree(seg_trj, ignore_errors=True)
        seg_cms = seg_trj[: -len("_trj")] + "-out.cms"
        Path(seg_cms).unlink(missing_ok=True)

    LOGGER.info("genrepresent has been extracted successfully")


def load_frame_to_time(settings: MDsettings) -> Dict[int, float]:
    # Read correspondence between frame and time from file
    dir_0_1 = settings.each_replica(_cycle=0, _replica=1)
    # load frame to time
    # (no need to do "skiprows=1"
    # because it is recognized as a commment line by default)
    frame_time_array = np.loadtxt(
        f"{dir_0_1}/frame_time.tsv", comments="#", delimiter="\t", skiprows=0
    )
    frame_time_dict: Dict[int, float] = {}
    for frame, time in frame_time_array:
        frame_time_dict[int(frame)] = time
    return frame_time_dict


def detect_lastcycle(settings: MDsettings) -> int:
    # detect the last cycle
    # NOTE: last_cycle must default to settings.max_cycle, not 0 - if the
    # run completed every cycle through max_cycle with no missing
    # cv_ranked.log, the loop below never hits its break, and the old
    # default of 0 falsely triggered the "cv_ranked.log is not found" error
    # below even though the run genuinely finished. Confirmed by a real
    # run that completed both of its 2 cycles cleanly. This bug is
    # pre-existing and engine-agnostic (not desmond-specific).
    last_cycle = settings.max_cycle
    for cycle in range(1, settings.max_cycle + 1):
        cycle_dir = Path(settings.each_cycle(_cycle=cycle))
        if not (cycle_dir / "summary/cv_ranked.log").exists():
            last_cycle = cycle - 1
            break
    if last_cycle == 0:
        LOGGER.error("cv_ranked.log is not found")
        LOGGER.error("please check the simulation")
        exit(1)
    return last_cycle


def make_reprdir(settings: MDsettings) -> Path:
    # create the directory to store the repr trajectory
    repr_dir = Path(f"{settings.each_trial()}/genrepresent")
    if not repr_dir.exists():
        repr_dir.mkdir(parents=True)
    return repr_dir
