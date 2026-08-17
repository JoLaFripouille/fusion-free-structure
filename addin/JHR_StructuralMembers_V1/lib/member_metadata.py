from __future__ import annotations

import math
import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from . import anchors


ATTRIBUTE_GROUP = "EI_JHR_StructuralMember"
ATTRIBUTE_KEYS = (
    "profile",
    "profile_category",
    "profile_region",
    "profile_family",
    "profile_source",
    "steel_grade",
    "material_name",
    "material_id",
    "material_library_name",
    "material_library_id",
    "material_source_id",
    "material_property_count",
    "anchor",
    "rotation_deg",
    "flip_x",
    "flip_y",
    "source_curve_token",
    "source_line_token",
    "source_curve_type",
    "extension_version",
)


@dataclass(frozen=True)
class MemberMetadata:
    profile: str
    profile_category: str
    profile_region: str
    profile_family: str
    profile_source: str
    steel_grade: str
    material_name: str
    material_id: str
    material_library_name: str
    material_library_id: str
    material_source_id: str
    material_property_count: int
    anchor: str
    rotation_deg: float
    flip_x: bool
    flip_y: bool
    source_curve_token: str
    source_curve_type: str
    extension_version: str

    @property
    def has_physical_material_metadata(self):
        return bool(
            self.material_name
            and self.material_id
            and self.material_library_name
            and self.material_library_id
            and self.material_source_id
        )


def _required_text(values, key, label):
    value = str(values.get(key, "")).strip()
    if not value:
        raise ValueError("Information manquante : {}.".format(label))
    return value


def _optional_text(values, key):
    return str(values.get(key, "")).strip()


def _material_metadata(values):
    keys = (
        "material_name",
        "material_id",
        "material_library_name",
        "material_library_id",
        "material_source_id",
        "material_property_count",
    )
    has_any_value = any(_optional_text(values, key) for key in keys)
    legacy_grade = _optional_text(values, "steel_grade")
    if not has_any_value:
        display_name = legacy_grade or "Non renseigné"
        return display_name, display_name, "", "", "", "", 0

    material_name = _required_text(values, "material_name", "matériau Fusion")
    material_id = _required_text(values, "material_id", "identifiant du matériau Fusion")
    library_name = _required_text(
        values,
        "material_library_name",
        "bibliothèque du matériau Fusion",
    )
    library_id = _required_text(
        values,
        "material_library_id",
        "identifiant de la bibliothèque Fusion",
    )
    source_id = _optional_text(values, "material_source_id") or material_id
    count_source = _required_text(
        values,
        "material_property_count",
        "nombre de propriétés physiques",
    )
    try:
        property_count = int(count_source)
    except ValueError as error:
        raise ValueError(
            "Nombre de propriétés physiques invalide : {}.".format(count_source)
        ) from error
    if property_count < 1:
        raise ValueError("Le matériau enregistré ne contient aucune propriété physique.")
    return (
        legacy_grade or material_name,
        material_name,
        material_id,
        library_name,
        library_id,
        source_id,
        property_count,
    )


def _boolean(values, key, default=False):
    source = str(values.get(key, str(default))).strip().lower()
    if source == "true":
        return True
    if source == "false":
        return False
    raise ValueError("Valeur booléenne invalide pour {} : {}.".format(key, source))


def _rotation_degrees(values):
    source = str(values.get("rotation_deg", "0")).strip()
    try:
        value = float(source)
    except ValueError as error:
        raise ValueError("Angle de rotation invalide : {}.".format(source)) from error
    if not math.isfinite(value):
        raise ValueError("L'angle de rotation doit être un nombre fini.")
    return value


def _relative_profile_source(values):
    source = _required_text(values, "profile_source", "fichier DXF source")
    path = PurePosixPath(source.replace("\\", "/"))
    if path.is_absolute() or re.match(r"^[A-Za-z]:", source) or ".." in path.parts:
        raise ValueError("Le chemin du DXF source n'est pas relatif à la bibliothèque.")
    return path.as_posix()


def parse_member_attributes(values):
    """Valide les attributs persistés sans dépendre de l'API Fusion."""
    anchor = _required_text(values, "anchor", "point d'ancrage")
    anchors.definition(anchor)
    source_token = str(values.get("source_curve_token", "")).strip()
    if not source_token:
        source_token = _required_text(values, "source_line_token", "liaison au squelette")
    (
        steel_grade,
        material_name,
        material_id,
        material_library_name,
        material_library_id,
        material_source_id,
        material_property_count,
    ) = _material_metadata(values)

    return MemberMetadata(
        profile=_required_text(values, "profile", "profil"),
        profile_category=(
            _optional_text(values, "profile_category") or "Zones_geographiques"
        ),
        profile_region=_optional_text(values, "profile_region") or "Europe",
        profile_family=_required_text(values, "profile_family", "famille"),
        profile_source=_relative_profile_source(values),
        steel_grade=steel_grade,
        material_name=material_name,
        material_id=material_id,
        material_library_name=material_library_name,
        material_library_id=material_library_id,
        material_source_id=material_source_id,
        material_property_count=material_property_count,
        anchor=anchor,
        rotation_deg=_rotation_degrees(values),
        flip_x=_boolean(values, "flip_x"),
        flip_y=_boolean(values, "flip_y"),
        source_curve_token=source_token,
        source_curve_type=str(values.get("source_curve_type", "line")).strip() or "line",
        extension_version=str(values.get("extension_version", "ancienne")).strip() or "ancienne",
    )


def format_rotation_degrees(value):
    if abs(value) < 5e-10:
        value = 0.0
    return ("{:.9f}".format(value)).rstrip("0").rstrip(".")
