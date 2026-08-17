from __future__ import annotations

import math
import unicodedata
from dataclasses import dataclass

from . import physical_materials


@dataclass(frozen=True)
class StructuralMaterialSpec:
    name: str
    grade: str
    standard: str
    maximum_thickness_mm: int
    density: str
    young_modulus: str
    poisson_ratio: float
    yield_strength: str
    tensile_strength: str


@dataclass(frozen=True)
class EnsureResult:
    existing_names: tuple[str, ...]
    created_names: tuple[str, ...]


REQUIRED_MATERIALS = (
    StructuralMaterialSpec(
        name="S235JR EN 10025-2 - t<=16 mm",
        grade="S235JR",
        standard="EN 10025-2:2019",
        maximum_thickness_mm=16,
        density="7850 kg/m^3",
        young_modulus="210 GPa",
        poisson_ratio=0.30,
        yield_strength="235 MPa",
        tensile_strength="360 MPa",
    ),
    StructuralMaterialSpec(
        name="S355J2 EN 10025-2 - t<=16 mm",
        grade="S355J2",
        standard="EN 10025-2:2019",
        maximum_thickness_mm=16,
        density="7850 kg/m^3",
        young_modulus="210 GPa",
        poisson_ratio=0.30,
        yield_strength="355 MPa",
        tensile_strength="470 MPa",
    ),
)


_PROPERTY_ALIASES = {
    "density": (
        "prismmaterialdensity",
        "density",
        "densite",
        "masse volumique",
    ),
    "young_modulus": (
        "prismmaterialyoungmodulus",
        "young modulus",
        "young",
        "elastic modulus",
        "module d elasticite",
        "module de young",
    ),
    "poisson_ratio": (
        "prismmaterialpoissonsratio",
        "prismmaterialpoissonratio",
        "poisson",
    ),
    "yield_strength": (
        "prismmaterialyieldstrength",
        "yield strength",
        "limite d elasticite",
        "limite elastique",
    ),
    "tensile_strength": (
        "prismmaterialtensilestrength",
        "ultimate tensile strength",
        "tensile strength",
        "resistance a la traction",
        "resistance ultime",
    ),
}


def _normalized(value):
    text = unicodedata.normalize("NFKD", str(value))
    plain = "".join(
        character for character in text if not unicodedata.combining(character)
    ).casefold()
    return " ".join(
        "".join(character if character.isalnum() else " " for character in plain).split()
    )


def _is_valid(entity):
    return bool(entity) and bool(getattr(entity, "isValid", True))


def _iter_collection(collection):
    for index in range(collection.count):
        yield collection.item(index)


def _find_exact_materials(materials, name):
    return tuple(
        material
        for material in _iter_collection(materials)
        if _is_valid(material) and str(material.name) == name
    )


def _property_fingerprint(material_property):
    return "{} {}".format(
        _normalized(getattr(material_property, "id", "")),
        _normalized(getattr(material_property, "name", "")),
    )


def _required_properties(material):
    properties = material.materialProperties
    if not properties:
        raise RuntimeError(
            "Le matériau de base '{}' ne contient aucune propriété physique."
            .format(material.name)
        )

    found = {}
    available = []
    for material_property in _iter_collection(properties):
        if not material_property:
            continue
        fingerprint = _property_fingerprint(material_property)
        available.append(
            "{} ({})".format(
                getattr(material_property, "name", "sans nom"),
                getattr(material_property, "id", "sans identifiant"),
            )
        )
        for key, aliases in _PROPERTY_ALIASES.items():
            if key not in found and any(alias in fingerprint for alias in aliases):
                found[key] = material_property

    missing = tuple(key for key in _PROPERTY_ALIASES if key not in found)
    if missing:
        raise RuntimeError(
            "Propriétés physiques introuvables pour '{}': {}. Propriétés disponibles: {}"
            .format(material.name, ", ".join(missing), "; ".join(available))
        )
    return found


def _expected_value(units_manager, material_property, expression, unitless_value=None):
    units = str(getattr(material_property, "units", "") or "")
    if not units:
        if unitless_value is None:
            raise RuntimeError(
                "La propriété '{}' ne fournit aucune unité exploitable."
                .format(material_property.name)
            )
        return float(unitless_value)
    parts = str(expression).split(maxsplit=1)
    if len(parts) != 2:
        raise RuntimeError(
            "La valeur physique '{}' ne contient pas une valeur et une unité."
            .format(expression)
        )
    source_value = float(parts[0])
    source_units = parts[1]
    value = float(units_manager.convert(source_value, source_units, units))
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(
            "Fusion ne peut pas convertir '{}' vers l'unité '{}' de la propriété '{}'."
            .format(expression, units, material_property.name)
        )
    return value


def _target_values(spec, properties, units_manager):
    return {
        "density": _expected_value(
            units_manager,
            properties["density"],
            spec.density,
        ),
        "young_modulus": _expected_value(
            units_manager,
            properties["young_modulus"],
            spec.young_modulus,
        ),
        "poisson_ratio": _expected_value(
            units_manager,
            properties["poisson_ratio"],
            str(spec.poisson_ratio),
            spec.poisson_ratio,
        ),
        "yield_strength": _expected_value(
            units_manager,
            properties["yield_strength"],
            spec.yield_strength,
        ),
        "tensile_strength": _expected_value(
            units_manager,
            properties["tensile_strength"],
            spec.tensile_strength,
        ),
    }


def _values_match(actual, expected):
    return math.isclose(float(actual), float(expected), rel_tol=1e-6, abs_tol=1e-12)


def _validate_material(material, spec, units_manager):
    properties = _required_properties(material)
    target_values = _target_values(spec, properties, units_manager)
    mismatches = []
    for key, target in target_values.items():
        actual = float(properties[key].value)
        if not _values_match(actual, target):
            mismatches.append(
                "{}={} attendu {}".format(properties[key].name, actual, target)
            )
    if mismatches:
        raise RuntimeError(
            "Le matériau existant '{}' ne correspond pas aux valeurs EI_JHR: {}. "
            "Il n'a pas été modifié."
            .format(spec.name, "; ".join(mismatches))
        )


def _configure_material(material, spec, units_manager):
    properties = _required_properties(material)
    target_values = _target_values(spec, properties, units_manager)
    for key, target in target_values.items():
        material_property = properties[key]
        if bool(getattr(material_property, "isReadOnly", False)):
            raise RuntimeError(
                "La propriété '{}' du matériau copié est en lecture seule."
                .format(material_property.name)
            )
        material_property.value = target

    material.description = (
        "Acier de construction {grade}, {standard}, épaisseur nominale t<={thickness} mm. "
        "Valeurs EI_JHR pour étude linéaire: rho={density}, E={young}, nu={poisson:.2f}, "
        "ReH min={yield_strength}, Rm min={tensile_strength}. "
        "Vérifier le certificat matière pour un calcul de justification."
    ).format(
        grade=spec.grade,
        standard=spec.standard,
        thickness=spec.maximum_thickness_mm,
        density=spec.density,
        young=spec.young_modulus,
        poisson=spec.poisson_ratio,
        yield_strength=spec.yield_strength,
        tensile_strength=spec.tensile_strength,
    )
    _validate_material(material, spec, units_manager)


def _base_material(material_libraries):
    choices = physical_materials.discover_steel_materials(material_libraries)
    choice = physical_materials.default_choice(choices)
    return physical_materials.resolve_material(material_libraries, choice)


def ensure_required_materials(design, material_libraries):
    """Crée les deux nuances EI_JHR dans le document actif, de façon idempotente."""
    if not design or not getattr(design, "materials", None):
        raise RuntimeError("Aucune conception Fusion active ne peut recevoir les matériaux EI_JHR.")

    existing = []
    missing = []
    for spec in REQUIRED_MATERIALS:
        matches = _find_exact_materials(design.materials, spec.name)
        if len(matches) > 1:
            raise RuntimeError(
                "Le document contient plusieurs matériaux nommés '{}'."
                .format(spec.name)
            )
        if matches:
            _validate_material(matches[0], spec, design.unitsManager)
            existing.append(spec.name)
        else:
            missing.append(spec)

    if not missing:
        return EnsureResult(tuple(existing), ())

    base_material = _base_material(material_libraries)
    _required_properties(base_material)
    created_materials = []
    try:
        for spec in missing:
            material = design.materials.addByCopy(base_material, spec.name)
            if not _is_valid(material):
                raise RuntimeError(
                    "Fusion n'a pas pu créer le matériau '{}'.".format(spec.name)
                )
            created_materials.append(material)
            _configure_material(material, spec, design.unitsManager)
    except Exception:
        for material in reversed(created_materials):
            if _is_valid(material) and not bool(getattr(material, "isUsed", False)):
                material.deleteMe()
        raise

    return EnsureResult(
        tuple(existing),
        tuple(material.name for material in created_materials),
    )
