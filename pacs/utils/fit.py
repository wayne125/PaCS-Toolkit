import multiprocessing as mp
from pathlib import Path

from pacs.models.settings import MDsettings
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


def fit(settings: MDsettings, trj_file: str, out_file: str) -> None:
    if settings.analyzer == "mdtraj":
        fit_mdtraj(settings, trj_file, out_file)
    elif settings.analyzer == "desmond":
        fit_desmond(settings, trj_file, out_file)
    else:
        raise NotImplementedError


def fit_trial(settings: MDsettings, trj_file: str, out_file: str) -> None:
    job_list = []
    for path in Path(".").glob(f"./trial{settings.trial:03}/cycle*/replica*"):
        if not Path(f"{path}/{trj_file}").exists():
            LOGGER.error(f"trajectory file {path}/{trj_file} is not found.")
            exit(1)
        p = mp.Process(target=fit, args=(settings, f"{path}/{trj_file}", out_file))
        p.start()
        job_list.append(p)

        if len(job_list) == settings.n_parallel:
            for proc in job_list:
                proc.join()
            for proc in job_list:
                if proc.exitcode != 0:
                    LOGGER.error("error occurred at child process")
                    exit(1)
            for proc in job_list:
                proc.close()
            job_list = []

    if len(job_list) != 0:
        for proc in job_list:
            proc.join()
        for proc in job_list:
            if proc.exitcode != 0:
                LOGGER.error("error occurred at child process")
                exit(1)
        for proc in job_list:
            proc.close()
        job_list = []


def fit_mdtraj(settings: MDsettings, trj_file: str, out_file: str) -> None:
    import mdtraj as md

    ext = Path(trj_file).suffix
    parent = Path(trj_file).parent
    stem = Path(trj_file).stem
    fit_trj_file = (
        f"{parent}/{stem}_fit{ext}" if out_file is None else f"{parent}/{out_file}"
    )

    ref_structure = settings.reference
    trj_selection = settings.selection1
    ref_selection = settings.selection2

    trj = md.load(trj_file, top=settings.top_mdtraj)
    ref = md.load(ref_structure)
    fit_trj = trj.superpose(
        ref,
        atom_indices=trj.top.select(trj_selection),
        ref_atom_indices=ref.top.select(ref_selection),
    )

    fit_trj.save(fit_trj_file)
    LOGGER.info(f"a new trajectory file is saved as {fit_trj_file}")


def fit_desmond(settings: MDsettings, trj_file: str, out_file: str) -> None:
    import numpy as np
    from schrodinger.application.desmond.packages import traj, traj_util, topo
    from schrodinger.comparison.atom_mapper import align_pos
    from schrodinger.structure import StructureReader
    from schrodinger.structutils.analyze import evaluate_asl

    ext = Path(trj_file).suffix
    parent = Path(trj_file).parent
    stem = Path(trj_file).stem
    fit_trj_dir = (
        f"{parent}/{stem}_fit_trj" if out_file is None else f"{parent}/{out_file}"
    )

    ref_structure = settings.reference
    trj_selection = settings.selection1
    ref_selection = settings.selection2

    msys_model, cms_model, tr = traj_util.read_cms_and_traj(trj_file)
    fit_aids = cms_model.select_atom(trj_selection)
    if cms_model.need_msys:
        fit_gids = topo.aids2gids(cms_model, fit_aids, include_pseudoatoms=True)
    else:
        fit_gids = cms_model.convert_to_gids(fit_aids, with_pseudo=True)

    ref_st = next(StructureReader(str(ref_structure)))
    ref_aids = evaluate_asl(ref_st, ref_selection)
    fit_ref_pos = np.array([ref_st.atom[i].xyz for i in ref_aids])

    fitted_frames = []
    for fr in tr:
        full_pos = fr.pos()
        fit_pos = full_pos[fit_gids]
        aligned_pos = align_pos(full_pos, fit_pos, fit_ref_pos)
        new_fr = fr.copy()
        # traj.Frame has no setPos() - confirmed by reading the real method
        # (only `pos(i=None)` exists, a getter). pos() returns the frame's
        # own live position array when cached, so in-place slice assignment
        # mutates it directly - confirmed by a real test (mutation persists
        # across subsequent pos() calls, and the original frame, copied
        # beforehand, is unaffected).
        new_fr.pos()[:] = aligned_pos
        fitted_frames.append(new_fr)

    traj.write_traj(fitted_frames, fit_trj_dir)
    LOGGER.info(f"a new trajectory directory is saved as {fit_trj_dir}")
