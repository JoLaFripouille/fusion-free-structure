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
        name="S275JR EN 10025-2 - t<=16 mm",
        grade="S275JR",
        standard="EN 10025-2:2019",
        maximum_thickness_mm=16,
        density="7850 kg/m^3",
        young_modulus="210 GPa",
        poisson_ratio=0.30,
        yield_strength="275 MPa",
        tensile_strength="410 MPa",
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


def _normalized_units(units):
    return (
        str(units)
        .strip()
        .casefold()
        .replace("³", "^3")
        .replace("²", "^2")
        .replace(" ", "")
    )


def _physical_value_in_property_units(property_key, expression, property_units):
    parts = str(expression).split(maxsplit=1)
    if len(parts) != 2:
        raise RuntimeError(
            "La valeur physique '{}' ne contient pas une valeur et une unité."
            .format(expression)
        )
    source_value = float(parts[0])
    source_units = _normalized_units(parts[1])
    target_units = _normalized_units(property_units)

    if property_key == "density":
        if source_units not in ("kg/m^3", "kg/m3"):
            raise RuntimeError("La densité source '{}' n'est pas prise en charge.".format(expression))
        density_factors = {
            "kg/m^3": 1.0,
            "kg/m3": 1.0,
            "kilogrampercubicmeter": 1.0,
            "kg/cm^3": 1e-6,
            "kg/cm3": 1e-6,
            "kilogrampercubiccentimeter": 1e-6,
            "kg/mm^3": 1e-9,
            "kg/mm3": 1e-9,
            "kilogrampercubicmillimeter": 1e-9,
            "g/cm^3": 1e-3,
            "g/cm3": 1e-3,
            "grampercubiccentimeter": 1e-3,
            "g/mm^3": 1e-6,
            "g/mm3": 1e-6,
            "grampercubicmillimeter": 1e-6,
            "lbm/in^3": 3.6127292000084e-5,
            "lbmass/in^3": 3.6127292000084e-5,
            "lb/in^3": 3.6127292000084e-5,
            "poundmasspercubicinch": 3.6127292000084e-5,
        }
        if target_units in density_factors:
            return source_value * density_factors[target_units]

    if property_key in ("young_modulus", "yield_strength", "tensile_strength"):
        pressure_to_mpa = {
            "pa": 1e-6,
            "pascal": 1e-6,
            "kpa": 1e-3,
            "kilopascal": 1e-3,
            "mpa": 1.0,
            "megapascal": 1.0,
            "gpa": 1e3,
            "gigapascal": 1e3,
            "n/m^2": 1e-6,
            "n/m2": 1e-6,
            "newtonpersquaremeter": 1e-6,
            "n/mm^2": 1.0,
            "n/mm2": 1.0,
            "newtonpersquaremillimeter": 1.0,
            "psi": 0.006894757293168,
            "poundforcepersquareinch": 0.006894757293168,
            "ksi": 6.894757293168,
            "kilopoundforcepersquareinch": 6.894757293168,
        }
        if source_units not in pressure_to_mpa:
            raise RuntimeError("La pression source '{}' n'est pas prise en charge.".format(expression))
        if target_units in pressure_to_mpa:
            value_mpa = source_value * pressure_to_mpa[source_units]
            return value_mpa / pressure_to_mpa[target_units]

    raise RuntimeError(
        "L'unité Fusion '{}' de la propriété '{}' n'est pas encore prise en charge."
        .format(property_units, property_key)
    )


def _expected_value(units_manager, material_property, expression, property_key, unitless_value=None):
    if property_key == "poisson_ratio" and unitless_value is not None:
        return float(unitless_value)
    units = str(getattr(material_property, "units", "") or "")
    if not units:
        if unitless_value is None:
            raise RuntimeError(
                "La propriété '{}' ne fournit aucune unité exploitable."
                .format(material_property.name)
            )
        return float(unitless_value)
    value = float(
        _physical_value_in_property_units(property_key, expression, units)
    )
    if not math.isfinite(value) or value < 0:
        raise RuntimeError(
            "La conversion de '{}' vers l'unité '{}' de la propriété '{}' est invalide."
            .format(expression, units, material_property.name)
        )
    return value


def _target_values(spec, properties, units_manager):
    return {
        "density": _expected_value(
            units_manager,
            properties["density"],
            spec.density,
            "density",
        ),
        "young_modulus": _expected_value(
            units_manager,
            properties["young_modulus"],
            spec.young_modulus,
            "young_modulus",
        ),
        "poisson_ratio": _expected_value(
            units_manager,
            properties["poisson_ratio"],
            str(spec.poisson_ratio),
            "poisson_ratio",
            spec.poisson_ratio,
        ),
        "yield_strength": _expected_value(
            units_manager,
            properties["yield_strength"],
            spec.yield_strength,
            "yield_strength",
        ),
        "tensile_strength": _expected_value(
            units_manager,
            properties["tensile_strength"],
            spec.tensile_strength,
            "tensile_strength",
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


def _set_and_validate_material_name(material, expected_name):
    material.name = expected_name
    actual_name = str(material.name)
    if actual_name != expected_name:
        raise RuntimeError(
            "Fusion a conservé le nom '{}' au lieu de '{}'."
            .format(actual_name, expected_name)
        )


def _base_material(material_libraries):
    choices = physical_materials.discover_steel_materials(material_libraries)
    choice = physical_materials.default_choice(choices)
    return physical_materials.resolve_material(material_libraries, choice)


def ensure_required_materials(design, material_libraries):
    """Crée les nuances EI_JHR requises dans le document actif, sans doublon."""
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
            _set_and_validate_material_name(material, spec.name)
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
