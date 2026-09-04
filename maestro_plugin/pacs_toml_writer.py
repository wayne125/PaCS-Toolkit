"""Pure functions for building and serializing PaCS-MD Desmond input.toml
settings. No Maestro dependency - importable and testable standalone."""

from typing import Any, Dict, Optional

SUPPORTED_ANALYZER_TYPES = ("target", "rmsd")


_SECTION_KEYS = [
    (
        "basic",
        [
            "trial",
            "max_cycle",
            "n_replica",
            "n_parallel",
            "centering",
            "centering_selection",
            "working_dir",
        ],
    ),
    (
        "simulator",
        [
            "simulator",
            "structure",
            "topology",
            "mdconf",
            "msj_file",
            "trajectory_extension",
            "desmond_host",
            "desmond_maxjob",
            "desmond_lic",
        ],
    ),
    (
        "analyzer",
        ["type", "threshold", "analyzer", "reference", "selection1", "selection2"],
    ),
    ("postprocess", ["rmmol", "rmfile"]),
]


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    return f'"{value}"'


def settings_dict_to_toml(settings: Dict[str, Any]) -> str:
    lines = []
    for header, keys in _SECTION_KEYS:
        present = [k for k in keys if k in settings]
        if not present:
            continue
        lines.append(f"## {header}")
        for key in present:
            lines.append(f"{key} = {_format_value(settings[key])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def build_settings_dict(
    *,
    structure_cms: str,
    msj_file: str,
    mdconf: str,
    working_dir: str,
    analyzer_type: str,
    threshold: float,
    reference: str,
    selection1: str,
    selection2: str,
    n_replica: int = 1,
    max_cycle: int = 1,
    n_parallel: int = 1,
    trial: int = 1,
    centering: bool = True,
    centering_selection: str = "protein",
    desmond_host: str = "localhost",
    desmond_maxjob: int = 1,
    desmond_lic: Optional[str] = None,
    rmmol: bool = False,
    rmfile: bool = False,
) -> Dict[str, Any]:
    if analyzer_type not in SUPPORTED_ANALYZER_TYPES:
        raise ValueError(
            f"analyzer_type must be one of {SUPPORTED_ANALYZER_TYPES}, "
            f"got {analyzer_type!r}"
        )

    settings: Dict[str, Any] = {
        "trial": trial,
        "max_cycle": max_cycle,
        "n_replica": n_replica,
        "n_parallel": n_parallel,
        "centering": centering,
        "centering_selection": centering_selection,
        "working_dir": working_dir,
        "simulator": "desmond",
        "structure": structure_cms,
        "topology": structure_cms,
        "mdconf": mdconf,
        "msj_file": msj_file,
        "trajectory_extension": ".dtr",
        "desmond_host": desmond_host,
        "desmond_maxjob": desmond_maxjob,
        "type": analyzer_type,
        "threshold": threshold,
        "analyzer": "desmond",
        "reference": reference,
        "selection1": selection1,
        "selection2": selection2,
        "rmmol": rmmol,
        "rmfile": rmfile,
    }
    if desmond_lic:
        settings["desmond_lic"] = desmond_lic
    return settings
