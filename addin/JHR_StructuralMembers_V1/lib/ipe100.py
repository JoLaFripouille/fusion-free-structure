from __future__ import annotations

from pathlib import Path


PROFILE_NAME = "IPE 100"
PROFILE_FAMILY = "IPE"
DXF_FILENAME = "IPE_100.dxf"
ANCHOR_NAME = "C"
WIDTH_MM = 55.0
HEIGHT_MM = 100.0
MM_TO_CM = 0.1

# Le DXF validé est centré horizontalement, mais son origine se trouve au
# milieu de la face inférieure. Cet offset place l'ancrage C sur l'origine de
# l'esquisse sans modifier ni reconstruire le contour importé.
IMPORT_OFFSET_CM = (0.0, -HEIGHT_MM * MM_TO_CM / 2.0)


def dxf_candidates(addin_root=None):
    """Retourne les emplacements relatifs acceptés pour la bibliothèque."""
    root = Path(addin_root) if addin_root else Path(__file__).resolve().parents[1]
    relative_profile = Path("profiles") / PROFILE_FAMILY / DXF_FILENAME
    return (
        root / relative_profile,
        root.parent.parent / relative_profile,
    )


def resolve_dxf_path(addin_root=None):
    """Trouve le DXF dans une installation autonome ou dans le dépôt."""
    for candidate in dxf_candidates(addin_root):
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(
        "Le profil relatif profiles/{}/{} est introuvable dans l'installation."
        .format(PROFILE_FAMILY, DXF_FILENAME)
    )
