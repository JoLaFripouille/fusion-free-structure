from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

from . import dxf_geometry


MM_TO_CM = 0.1
DEFAULT_FAMILY_ID = "IPE"
DEFAULT_DXF_FILENAME = "IPE_100.dxf"

FAMILY_LABELS = {
    "IPE": "IPE",
    "HEA": "HEA",
    "HEB": "HEB",
    "IPN": "IPN",
    "UPN": "UPN",
    "UPE": "UPE",
    "Corniere_Egale": "Cornière égale",
    "Corniere_Inegale": "Cornière inégale",
    "Te_Egal": "Té égal",
    "Tube_Carre": "Tube carré",
    "Tube_Rectangulaire": "Tube rectangulaire",
    "Tube_Rond": "Tube rond",
}

FAMILY_ORDER = {
    family_id: index
    for index, family_id in enumerate((
        "IPE",
        "HEA",
        "HEB",
        "IPN",
        "UPN",
        "UPE",
        "Corniere_Egale",
        "Corniere_Inegale",
        "Te_Egal",
        "Tube_Carre",
        "Tube_Rectangulaire",
        "Tube_Rond",
    ))
}


def _natural_numbers(value):
    numbers = tuple(float(number) for number in re.findall(r"\d+(?:\.\d+)?", value))
    return numbers, value.casefold()


def _section_label(family_id, stem):
    prefix = family_id + "_"
    source = stem[len(prefix):] if stem.startswith(prefix) else stem
    if "_ep" not in source:
        return source.replace("x", " × ")

    dimensions, thickness = source.rsplit("_ep", 1)
    dimensions = dimensions.replace("x", " × ")
    if family_id == "Tube_Rond":
        dimensions = "Ø " + dimensions
    return "{} — ép. {} mm".format(dimensions, thickness)


@functools.lru_cache(maxsize=64)
def _cached_bounds(path_text):
    return dxf_geometry.profile_bounds_mm(Path(path_text))


@dataclass(frozen=True)
class ProfileDefinition:
    family_id: str
    family_label: str
    section_label: str
    dxf_path: Path
    relative_path: str

    @property
    def designation(self):
        return "{} {}".format(self.family_label, self.section_label)

    @property
    def component_token(self):
        return re.sub(r"[^A-Z0-9]+", "", self.dxf_path.stem.upper())

    @property
    def bounds_mm(self):
        return _cached_bounds(str(self.dxf_path))

    @property
    def center_mm(self):
        min_x, min_y, max_x, max_y = self.bounds_mm
        return ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)

    @property
    def width_mm(self):
        min_x, _, max_x, _ = self.bounds_mm
        return max_x - min_x

    @property
    def height_mm(self):
        _, min_y, _, max_y = self.bounds_mm
        return max_y - min_y

    @property
    def import_offset_cm(self):
        center_x, center_y = self.center_mm
        return (-center_x * MM_TO_CM, -center_y * MM_TO_CM)


def library_candidates(addin_root=None):
    root = Path(addin_root) if addin_root else Path(__file__).resolve().parents[1]
    return (
        root / "profiles",
        root.parent.parent / "profiles",
    )


def resolve_library_root(addin_root=None):
    for candidate in library_candidates(addin_root):
        if candidate.is_dir() and any(candidate.glob("*/*.dxf")):
            return candidate
    raise FileNotFoundError(
        "Le dossier relatif profiles contenant la bibliothèque DXF est introuvable."
    )


def discover_profiles(addin_root=None):
    library_root = resolve_library_root(addin_root)
    profiles = []
    for family_directory in library_root.iterdir():
        if not family_directory.is_dir():
            continue
        family_id = family_directory.name
        family_label = FAMILY_LABELS.get(family_id, family_id.replace("_", " "))
        for dxf_path in family_directory.glob("*.dxf"):
            profiles.append(ProfileDefinition(
                family_id=family_id,
                family_label=family_label,
                section_label=_section_label(family_id, dxf_path.stem),
                dxf_path=dxf_path,
                relative_path=(Path("profiles") / family_id / dxf_path.name).as_posix(),
            ))
    profiles.sort(key=lambda profile: (
        FAMILY_ORDER.get(profile.family_id, len(FAMILY_ORDER)),
        profile.family_label.casefold(),
        _natural_numbers(profile.section_label),
    ))
    if not profiles:
        raise FileNotFoundError("La bibliothèque DXF ne contient aucun profil.")
    return tuple(profiles)


def family_options(profiles):
    options = []
    seen = set()
    for profile in profiles:
        if profile.family_id not in seen:
            options.append((profile.family_id, profile.family_label))
            seen.add(profile.family_id)
    return tuple(options)


def profiles_for_family(profiles, family_id):
    return tuple(profile for profile in profiles if profile.family_id == family_id)


def default_profile(profiles):
    for profile in profiles:
        if (
            profile.family_id == DEFAULT_FAMILY_ID
            and profile.dxf_path.name == DEFAULT_DXF_FILENAME
        ):
            return profile
    return profiles[0]


def profile_from_labels(profiles, family_label, section_label):
    for profile in profiles:
        if profile.family_label == family_label and profile.section_label == section_label:
            return profile
    raise ValueError(
        "Le profil sélectionné ({}, {}) n'existe pas dans la bibliothèque."
        .format(family_label, section_label)
    )
