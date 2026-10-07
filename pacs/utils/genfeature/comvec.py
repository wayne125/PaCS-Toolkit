import numpy as np
from pacs.utils.genfeature.genfeat import GenFeatureCore
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


def cal_feature(
    trj_path: str,
    topology: str,
    reference: str,
    selection_fit_trj: str,
    selection_fit_ref: str,
    selection1: str,
    selection2: str,
) -> np.ndarray:
    import mdtraj as md

    trj = md.load(
        f"{trj_path}",
        top=topology,
    )
    ref = md.load(reference)
    trj.superpose(
        ref,
        0,
        atom_indices=trj.top.select(selection_fit_trj),
        ref_atom_indices=ref.top.select(selection_fit_ref),
    )
    com1 = md.compute_center_of_mass(trj.atom_slice(trj.topology.select(selection1)))
    com2 = md.compute_center_of_mass(trj.atom_slice(trj.topology.select(selection2)))
    return np.array([com1[i] - com2[i] for i in range(len(com1))])


def cal_feature_trial(
    trial: int,
    trj_filename: str,
    topology: str,
    output_directory: str,
    n_parallel: int,
    reference: str,
    selection_fit_trj: str,
    selection_fit_ref: str,
    selection1: str,
    selection2: str,
) -> None:
    gen_core = GenFeatureCore(
        trial=trial,
        trj_filename=trj_filename,
        output_directory=output_directory,
        n_parallel=n_parallel,
    )

    gen_core.prepare()
    gen_core.cal_parallel(
        cal_feature,
        topology,
        reference,
        selection_fit_trj,
        selection_fit_ref,
        selection1,
        selection2,
    )


def cal_feature_desmond(
    trj_path: str,
    reference: str,
    selection_fit_trj: str,
    selection_fit_ref: str,
    selection1: str,
    selection2: str,
) -> np.ndarray:
    import numpy as np
    from schrodinger.application.desmond.packages import analysis, traj_util
    from schrodinger.structure import StructureReader
    from schrodinger.structutils.analyze import evaluate_asl

    msys_model, cms_model, tr = traj_util.read_cms_and_traj(trj_path)
    fit_aids = cms_model.select_atom(selection_fit_trj)
    aids1 = cms_model.select_atom(selection1)
    aids2 = cms_model.select_atom(selection2)

    ref_st = next(StructureReader(str(reference)))
    fit_ref_aids = evaluate_asl(ref_st, selection_fit_ref)
    fit_ref_pos = np.array([ref_st.atom[i].xyz for i in fit_ref_aids])

    align1 = analysis.PosAlign(msys_model, cms_model, aids1, fit_aids, fit_ref_pos)
    align2 = analysis.PosAlign(msys_model, cms_model, aids2, fit_aids, fit_ref_pos)
    pos1_per_frame, pos2_per_frame = analysis.analyze(tr, align1, align2)

    masses1 = np.array([cms_model.atom[i].atomic_weight for i in aids1])
    masses2 = np.array([cms_model.atom[i].atomic_weight for i in aids2])

    com_vecs = []
    for p1, p2 in zip(pos1_per_frame, pos2_per_frame):
        com1 = np.average(p1, axis=0, weights=masses1)
        com2 = np.average(p2, axis=0, weights=masses2)
        com_vecs.append(com1 - com2)
    return np.array(com_vecs)


def cal_feature_trial_desmond(
    trial: int,
    trj_filename: str,
    output_directory: str,
    n_parallel: int,
    reference: str,
    selection_fit_trj: str,
    selection_fit_ref: str,
    selection1: str,
    selection2: str,
) -> None:
    gen_core = GenFeatureCore(
        trial=trial,
        trj_filename=trj_filename,
        output_directory=output_directory,
        n_parallel=n_parallel,
    )

    gen_core.prepare()
    gen_core.cal_parallel(
        cal_feature_desmond,
        reference,
        selection_fit_trj,
        selection_fit_ref,
        selection1,
        selection2,
    )
