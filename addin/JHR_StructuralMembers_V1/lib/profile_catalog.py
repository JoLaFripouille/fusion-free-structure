from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from pathlib import Path

from . import anchors, dxf_geometry


MM_TO_CM = 0.1
GEOGRAPHIC_CATEGORY_ID = "Zones_geographiques"
GEOGRAPHIC_CATEGORY_LABEL = "Zones géographiques"
DEFAULT_REGION_ID = "Europe"
DEFAULT_FAMILY_ID = "IPE"
DEFAULT_DXF_FILENAME = "IPE_100.dxf"

REGION_LABELS = {
    "Europe": "Europe",
}

REGION_ORDER = {
    region_id: index
    for index, region_id in enumerate(("Europe",))
}

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
    category_id: str
    category_label: str
    region_id: str
    region_label: str
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
        return self.anchor_mm(anchors.DEFAULT_ANCHOR_CODE)

    def anchor_mm(self, anchor_code):
        return anchors.point_for_bounds(self.bounds_mm, anchor_code)

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
        return self.import_offset_cm_for_anchor(anchors.DEFAULT_ANCHOR_CODE)

    def import_offset_cm_for_anchor(self, anchor_code):
        anchor_x, anchor_y = self.anchor_mm(anchor_code)
        return (-anchor_x * MM_TO_CM, -anchor_y * MM_TO_CM)


def library_candidates(addin_root=None):
    root = Path(addin_root) if addin_root else Path(__file__).resolve().parents[1]
    return (
        root / "profiles",
        root.parent.parent / "profiles",
    )


def resolve_library_root(addin_root=None):
    for candidate in library_candidates(addin_root):
        if candidate.is_dir() and any(candidate.rglob("*.dxf")):
            return candidate
    raise FileNotFoundError(
        "Le dossier relatif profiles contenant la bibliothèque DXF est introuvable."
    )


def discover_profiles(addin_root=None):
    library_root = resolve_library_root(addin_root)
    profiles = []
    catalog_directories = []
    for family_directory in library_root.rglob("*"):
        if not family_directory.is_dir() or not any(family_directory.glob("*.dxf")):
            continue
        directory_parts = family_directory.relative_to(library_root).parts
        if len(directory_parts) == 1:
            # Compatibilité V1.9.7 et antérieures : profiles/<famille>.
            region_id = DEFAULT_REGION_ID
        elif len(directory_parts) == 2:
            # Compatibilité avec la transition : profiles/<zone>/<famille>.
            region_id = directory_parts[0]
        elif (
            len(directory_parts) == 3
            and directory_parts[0] == GEOGRAPHIC_CATEGORY_ID
        ):
            region_id = directory_parts[1]
        else:
            continue
        catalog_directories.append((region_id, family_directory))

    for region_id, family_directory in catalog_directories:
        region_label = REGION_LABELS.get(region_id, region_id.replace("_", " "))
        family_id = family_directory.name
        family_label = FAMILY_LABELS.get(family_id, family_id.replace("_", " "))
        for dxf_path in family_directory.glob("*.dxf"):
            profiles.append(ProfileDefinition(
                category_id=GEOGRAPHIC_CATEGORY_ID,
                category_label=GEOGRAPHIC_CATEGORY_LABEL,
                region_id=region_id,
                region_label=region_label,
                family_id=family_id,
                family_label=family_label,
                section_label=_section_label(family_id, dxf_path.stem),
                dxf_path=dxf_path,
                relative_path=(
                    Path("profiles") / dxf_path.relative_to(library_root)
                ).as_posix(),
            ))
    profiles.sort(key=lambda profile: (
        profile.category_label.casefold(),
        REGION_ORDER.get(profile.region_id, len(REGION_ORDER)),
        profile.region_label.casefold(),
        FAMILY_ORDER.get(profile.family_id, len(FAMILY_ORDER)),
        profile.family_label.casefold(),
        _natural_numbers(profile.section_label),
    ))
    if not profiles:
        raise FileNotFoundError("La bibliothèque DXF ne contient aucun profil.")
    return tuple(profiles)


def category_options(profiles):
    options = []
    seen = set()
    for profile in profiles:
        if profile.category_id not in seen:
            options.append((profile.category_id, profile.category_label))
            seen.add(profile.category_id)
    return tuple(options)


def category_label(category_id):
    if category_id == GEOGRAPHIC_CATEGORY_ID:
        return GEOGRAPHIC_CATEGORY_LABEL
    return str(category_id).replace("_", " ")


def region_options(profiles, category_id=None):
    options = []
    seen = set()
    for profile in profiles:
        if category_id is not None and profile.category_id != category_id:
            continue
        if profile.region_id not in seen:
            options.append((profile.region_id, profile.region_label))
            seen.add(profile.region_id)
    return tuple(options)


def family_options(profiles, region_id=None, category_id=None):
    options = []
    seen = set()
    for profile in profiles:
        if category_id is not None and profile.category_id != category_id:
            continue
        if region_id is not None and profile.region_id != region_id:
            continue
        if profile.family_id not in seen:
            options.append((profile.family_id, profile.family_label))
            seen.add(profile.family_id)
    return tuple(options)


def profiles_for_family(profiles, family_id, region_id=None, category_id=None):
    return tuple(
        profile
        for profile in profiles
        if profile.family_id == family_id
        and (region_id is None or profile.region_id == region_id)
        and (category_id is None or profile.category_id == category_id)
    )


def default_profile(profiles):
    for profile in profiles:
        if (
            profile.region_id == DEFAULT_REGION_ID
            and profile.family_id == DEFAULT_FAMILY_ID
            and profile.dxf_path.name == DEFAULT_DXF_FILENAME
        ):
            return profile
    return profiles[0]


def profile_from_labels(
    profiles,
    family_label,
    section_label,
    region_label=None,
    category_label=None,
):
    for profile in profiles:
        if (
            profile.family_label == family_label
            and profile.section_label == section_label
            and (region_label is None or profile.region_label == region_label)
            and (category_label is None or profile.category_label == category_label)
        ):
            return profile
    raise ValueError(
        "Le profil sélectionné ({}, {}, {}, {}) n'existe pas dans la bibliothèque."
        .format(
            category_label or "catégorie non précisée",
            region_label or "zone non précisée",
            family_label,
            section_label,
        )
    )


def resolve_profile_source(profile_source, addin_root=None):
    """Résout un chemin actuel ou antérieur sans sortir de la bibliothèque."""
    root = Path(addin_root) if addin_root else Path(__file__).resolve().parents[1]
    relative_path = Path(str(profile_source).replace("\\", "/"))
    relative_candidates = [relative_path]
    parts = relative_path.parts
    if len(parts) == 3 and parts[0] == "profiles":
        relative_candidates.append(
            Path("profiles")
            / GEOGRAPHIC_CATEGORY_ID
            / DEFAULT_REGION_ID
            / parts[1]
            / parts[2]
        )
    elif len(parts) == 4 and parts[0] == "profiles":
        relative_candidates.append(
            Path("profiles")
            / GEOGRAPHIC_CATEGORY_ID
            / parts[1]
            / parts[2]
            / parts[3]
        )

    base_roots = (root, root.parent.parent)
    candidates = [
        base_root / relative_candidate
        for relative_candidate in relative_candidates
        for base_root in base_roots
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return candidates[0]
