import dataclasses
from pathlib import Path
from typing import List

from pacs.mdrun.exporter.superExporter import SuperExporter
from pacs.models.settings import MDsettings, Snapshot
from pacs.utils.logger import generate_logger

LOGGER = generate_logger(__name__)


@dataclasses.dataclass
class eDesmond(SuperExporter):
    def export_each(
        self,
        settings: MDsettings,
        cycle: int,
        replica_rank: int,
        results: List[Snapshot],
    ) -> None:
        if settings.analyzer == "desmond":
            self.export_by_desmond(settings, cycle, replica_rank, results)
        else:
            raise NotImplementedError

    def export_by_desmond(
        self,
        settings: MDsettings,
        cycle: int,
        replica_rank: int,
        results: List[Snapshot],
    ) -> None:
        # Desmond-native frame extraction path using Schrodinger Python API
        # NOTE: This code must be run under $SCHRODINGER/run python3, not plain python3
        # API documentation source: schrodinger_api_2026-3/api/schrodinger.application.desmond.packages.traj.md
        # and schrodinger_api_2026-3/api/schrodinger.application.desmond.packages.topo.md
        
        from schrodinger.application.desmond.packages import traj_util, topo

        from_dir = settings.each_replica(
            _cycle=cycle, _replica=results[replica_rank].replica
        )
        out_dir = settings.each_replica(_cycle=cycle + 1, _replica=replica_rank + 1)
        
        # Load the cms model and trajectory
        # The .cms file contains the path to the associated .dtr trajectory file
        # NOTE: multisim always names its output "{JOBNAME}-out{ext}"
        # regardless of the -o flag's value - confirmed against a real run
        # (JOBNAME is fixed to "prd" by DESMOND.run_md). It is not "prd.cms".
        cms_path = f"{from_dir}/prd-out{settings.structure_extension}"
        
        # Use traj_util.read_cms_and_traj to load both the cms model and trajectory
        # This is the recommended approach as it handles the .cms -> .dtr path association
        msys_model, cms_model, tr = traj_util.read_cms_and_traj(cms_path)
        
        # Get the selected frame
        selected_frame = tr[results[replica_rank].frame]
        
        # Handle centering if requested
        # NOTE: The Schrodinger trajectory API (traj.Frame) does not have a built-in
        # centering method equivalent to mdtraj's image_molecules or gromacs trjconv.
        # For Desmond, centering would need to be implemented manually using the
        # frame's box information and coordinate transformations.
        # This is left as unimplemented for now - users should ensure their
        # trajectories are properly centered during the MD run.
        if settings.centering:
            # Unimplemented: centering in Schrodinger trajectory API
            # The equivalent would require:
            # 1. Selecting atoms via ASL (settings.centering_selection)
            # 2. Computing center of mass of selected atoms
            # 3. Translating all coordinates so the COM is at the box center
            # 4. Unwrapping/wrapping as needed
            # This can be added later using schrodinger.application.desmond.packages.analysis.Com
            # and manual coordinate manipulation via frame.pos() and frame.box
            LOGGER.warning(
                "centering is not yet implemented for desmond exporter. "
                "Trajectory coordinates are used as-is."
            )
        
        # Update the cms_model with the selected frame's coordinates and
        # write it out as the input for the next cycle.
        # NOTE: topo.update_cms (not Cms.update_with_frame) is the function
        # compatible with a cms_model loaded via traj_util.read_cms_and_traj
        # (i.e. topo.read_cms): it reads cms_model.particle2gid, which that
        # load path populates. Cms.update_with_frame expects id_maps
        # populated the newer FEP/titration way and raises
        # `TypeError: unsupported operand type(s) for +: 'NoneType' and 'int'`
        # on a standard (non-FEP) system with virtual sites/pseudoatoms -
        # confirmed against a real completed Desmond job (152306-atom
        # system with TIP4P-style pseudoatoms). Do not pre-`.reduce()` the
        # frame either - topo.update_cms indexes the frame's raw gid-space
        # arrays itself.
        topo.update_cms(cms_model, selected_frame, update_pseudoatoms=True)
        
        # Ensure output directory exists
        Path(out_dir).mkdir(parents=True, exist_ok=True)
        
        # Write the updated cms file
        output_cms = f"{out_dir}/input{settings.structure_extension}"
        cms_model.write(output_cms)
