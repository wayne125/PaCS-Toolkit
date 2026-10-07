import numpy as np
from pacs.utils.genfeature.genfeat import GenFeatureCore
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


def cal_feature(
    trj_path: str,
    topology: str,
    selection: str,
) -> np.ndarray:
    import mdtraj as md

    trj = md.load(
        f"{trj_path}",
        top=topology,
    )
    return trj.atom_slice(trj.topology.select(selection)).xyz


def cal_feature_trial(
    trial: int,
    trj_filename: str,
    topology: str,
    output_directory: str,
    n_parallel: int,
    selection: str,
) -> None:
    gen_core = GenFeatureCore(
        trial=trial,
        trj_filename=trj_filename,
        output_directory=output_directory,
        n_parallel=n_parallel,
    )

    gen_core.prepare()
    gen_core.cal_parallel(cal_feature, topology, selection)


def cal_feature_desmond(
    trj_path: str,
    selection: str,
) -> np.ndarray:
    from schrodinger.application.desmond.packages import traj_util, topo

    _, cms_model, tr = traj_util.read_cms_and_traj(trj_path)
    aids = cms_model.select_atom(selection)
    if cms_model.need_msys:
        gids = topo.aids2gids(cms_model, aids, include_pseudoatoms=True)
    else:
        gids = cms_model.convert_to_gids(aids, with_pseudo=True)
    return np.array([fr.pos(gids) for fr in tr])


def cal_feature_trial_desmond(
    trial: int,
    trj_filename: str,
    output_directory: str,
    n_parallel: int,
    selection: str,
) -> None:
    gen_core = GenFeatureCore(
        trial=trial,
        trj_filename=trj_filename,
        output_directory=output_directory,
        n_parallel=n_parallel,
    )

    gen_core.prepare()
    gen_core.cal_parallel(cal_feature_desmond, selection)
