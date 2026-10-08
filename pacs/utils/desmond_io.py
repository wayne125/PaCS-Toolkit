def fix_trajectory_property(cms_path: str, trj_dir_name: str) -> None:
    """Point a .cms file's embedded trajectory reference at trj_dir_name.

    traj_util.read_cms_and_traj() locates a trajectory via the
    s_chorus_trajectory_file property on the FULL_SYSTEM CT, not by
    filename convention (confirmed by reading topo.find_traj_path's
    source). cms.Cms.write() does NOT persist a value set through the
    high-level cms_model.property[...] accessor for this property -
    confirmed by a real round-trip test, the write silently keeps the
    original value. The property must be patched on the raw FULL_SYSTEM
    CT structure directly and rewritten with structure.StructureWriter -
    the same pattern schrodinger's own watermap.py stage uses internally.
    """
    from schrodinger import structure
    from schrodinger.application.desmond import constants

    sts = list(structure.StructureReader(cms_path))
    for st in sts:
        if st.property.get(constants.CT_TYPE) == constants.CT_TYPE.VAL.FULL_SYSTEM:
            st.property["s_chorus_trajectory_file"] = trj_dir_name
    with structure.StructureWriter(cms_path) as writer:
        for st in sts:
            writer.append(st)
