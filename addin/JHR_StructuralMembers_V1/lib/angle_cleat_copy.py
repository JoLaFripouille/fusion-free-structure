"""Réglages persistants et reprise des attaches par cornières."""
from dataclasses import dataclass
import json

import adsk.fusion as fusion

from . import angle_cleat_builder, angle_cleat_creator, angle_cleat_geometry
from . import assembly_geometry, bolt_specs, fastener_creator, profile_catalog
from .assembly_catalog import Field, Template


_ROLES = ("Poutre principale", "Poutre secondaire")
_GEOMETRY = ("Cornières", (
    Field("height", "Hauteur des cornières", 100),
    Field("vertical_offset", "Déport vertical", 0, signed=True),
))
_HOLES = ("Perçages", (
    Field("hole", "Diamètre du trou", 18),
    Field("rows", "Nombre de rangées", 2, unit="", max_count=6),
    Field("pitch", "Pas vertical", 40),
    Field("primary_gauge", "Axe des trous côté poutre principale", 30),
    Field("secondary_gauge", "Axe des trous côté poutre secondaire", 30),
))
TEMPLATES = (
    Template("double_angle", "Cornières", "Assemblage par cornières", _ROLES, (_GEOMETRY, _HOLES)),
    Template("opposed_double_angle", "Cornières", "Cornières opposées",
             (*_ROLES, "Poutre secondaire opposée"), (_GEOMETRY, _HOLES)),
)
DEFINITION_ATTRIBUTE = "definition"


@dataclass(frozen=True)
class AngleCleatSource:
    group: object
    template: Template
    occurrences: tuple
    parameters_mm: dict
    original: str | None
    alternate: bool = False
    writable: bool = True
    reason: str = ""


@dataclass(frozen=True)
class AngleCleatPlan:
    template: Template
    evaluation: object
    settings_mm: dict
    plates: tuple
    fasteners: tuple
    alternate: bool = False


def _definition(group):
    return group.component.attributes.itemByName(angle_cleat_creator.ATTRIBUTE_GROUP, DEFINITION_ATTRIBUTE)


def find_group(entity):
    group = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
    while group:
        if group.component.attributes.itemByName(angle_cleat_creator.ATTRIBUTE_GROUP, "assembly_index"):
            return group
        group = group.assemblyContext


def store_definition(group, evaluations, model_bolts):
    first = evaluations[0]
    pattern = first.hole_pattern
    members = (first.primary_occurrence, *(plan.secondary_occurrence for plan in evaluations))
    settings = {
        "profile": first.angle_profile.relative_path,
        "bolt": first.bolt_spec.designation,
        "model_bolts": bool(model_bolts),
        "height": 10. * first.cleat_height_cm,
        "vertical_offset": 10. * first.vertical_offset_cm,
        "hole": 10. * pattern.diameter_cm,
        "rows": pattern.row_count,
        "pitch": 10. * pattern.pitch_cm,
        "primary_gauge": 10. * pattern.primary_gauge_cm,
        "secondary_gauge": 10. * pattern.secondary_gauge_cm,
    }
    definition = {"kind": TEMPLATES[len(evaluations)-1].key,
                  "members": [item.entityToken for item in members], "parameters_mm": settings}
    marker = group.component.attributes.add(angle_cleat_creator.ATTRIBUTE_GROUP, DEFINITION_ATTRIBUTE,
                                            json.dumps(definition))
    if not marker:
        raise RuntimeError("Fusion n’a pas enregistré les réglages des cornières.")


def _member_matches(design, token):
    return [occurrence for entity in design.findEntityByToken(token) or ()
            if (occurrence := fusion.Occurrence.cast(entity)) and occurrence.isValid
            and occurrence in design.rootComponent.occurrences]


def _required_member(candidates, role):
    if len(candidates) != 1:
        raise ValueError(f"{role} : le profil de l’assemblage est introuvable ou ambigu.")
    return candidates[0]


def _legacy_settings(design, group):
    parts = []
    for child in group.childOccurrences:
        attributes = child.component.attributes

        def value(key):
            attribute = attributes.itemByName(angle_cleat_creator.ATTRIBUTE_GROUP, key)
            return attribute.value if attribute else None

        if value("assembly_type") != "double_angle_cleat":
            continue
        settings = {key: value(attribute) for key, attribute in (
            ("profile", "profile_source"), ("height", "height_mm"),
            ("vertical_offset", "vertical_offset_mm"), ("hole", "hole_diameter_mm"),
            ("rows", "hole_rows"), ("pitch", "hole_pitch_mm"),
            ("primary_gauge", "primary_gauge_mm"), ("secondary_gauge", "secondary_gauge_mm"),
        )}
        parts.append((value("primary_component"), value("secondary_component"), settings, child.component.name))
    primary_names = {primary for primary, _, _, _ in parts}
    secondary_names = {secondary for _, secondary, _, _ in parts}
    if len(parts) not in (2, 4) or len(primary_names) != 1 or len(secondary_names) != len(parts) // 2:
        raise ValueError("Les profils de cet ancien assemblage par cornières ne sont pas identifiables.")

    ordered_names = []
    seeds = []
    for side in range(1, len(secondary_names) + 1):
        candidates = parts if len(parts) == 2 else [
            part for part in parts if f" · face {side} " in part[3]
        ]
        if (len(candidates) != 2 or candidates[0][:3] != candidates[1][:3]
                or candidates[0][1] in ordered_names):
            raise ValueError("L’ordre d’origine des cornières opposées est introuvable.")
        ordered_names.append(candidates[0][1])
        seeds.append(candidates[0][2])

    diameters = set()
    for hardware in fastener_creator.assembly_hardware(group):
        for lot in hardware.childOccurrences:
            for bolt in lot.childOccurrences:
                marker = bolt.component.attributes.itemByName(fastener_creator.ATTRIBUTE_GROUP, "configuration")
                if marker:
                    diameters.add(json.loads(marker.value)["diameter_mm"])
    if len(diameters) != 1:
        raise ValueError("Le diamètre du boulon de cet ancien montage n’est pas enregistré.")

    settings = seeds[0].copy()
    if any(value is None for value in settings.values()):
        raise ValueError("Les réglages de cet ancien assemblage par cornières sont incomplets.")
    for key in settings.keys() - {"profile"}:
        settings[key] = int(settings[key]) if key == "rows" else float(settings[key])
    diameter, = diameters
    settings.update(bolt=f"M{diameter:g}", model_bolts=True)
    names = (next(iter(primary_names)), *ordered_names)
    members = tuple(_required_member(
        [occ for occ in design.rootComponent.occurrences if occ.component.name == name], role,
    ) for name, role in zip(names, TEMPLATES[len(ordered_names)-1].roles))
    return members, settings


def read(design, entity):
    group = find_group(entity)
    if not group:
        raise ValueError("Sélectionner une pièce d’un assemblage par cornières.")
    marker = _definition(group)
    original = marker.value if marker else None
    if marker:
        payload = json.loads(original)
        tokens = payload["members"]
        if len(tokens) not in (2, 3):
            raise ValueError("Les profils de l’assemblage par cornières sont incomplets.")
        if payload.get("kind") != TEMPLATES[len(tokens)-2].key:
            raise ValueError("Le type de l’assemblage par cornières ne correspond plus à ses profils.")
        members = tuple(_required_member(_member_matches(design, token), role)
                        for token, role in zip(tokens, TEMPLATES[len(tokens)-2].roles))
        settings = payload["parameters_mm"]
    else:
        members, settings = _legacy_settings(design, group)
    from ..commands.remove_assembly import target_group

    reason = ""
    try:
        target_group(design, group)
    except (ValueError, RuntimeError) as error:
        reason = str(error)
    return AngleCleatSource(group, TEMPLATES[len(members)-2], members, settings, original,
                           writable=not reason, reason=reason)


def evaluate(design, source, targets, settings=None):
    if len(targets) != len(source.template.roles):
        raise ValueError("Sélectionner les poutres cibles dans l’ordre indiqué.")
    settings = {**source.parameters_mm, **(settings or {})}
    if type(settings["model_bolts"]) is not bool:
        raise ValueError("Le choix de modéliser les boulons doit être vrai ou faux.")
    dimensions = {key: value for key, value in settings.items() if key not in ("profile", "bolt", "model_bolts")}
    dims = assembly_geometry.dimensions(source.template, dimensions)
    profiles = angle_cleat_builder.equal_angle_profiles(profile_catalog.discover_profiles())
    profile = next((item for item in profiles if item.relative_path == settings["profile"]), None)
    if profile is None:
        raise ValueError("La section de cornière n’est plus disponible dans le catalogue.")
    bolt = bolt_specs.bolt_spec_by_designation(settings["bolt"])
    opposed = len(targets) == 3
    calculate = (angle_cleat_builder.evaluate_opposed_double_angle_preview if opposed else
                 angle_cleat_builder.evaluate_double_angle_preview)
    native = calculate(design, *targets, profile, dims["height"], dims["vertical_offset"],
                       dims["hole"], dims["rows"], dims["pitch"], dims["primary_gauge"], dims["secondary_gauge"], bolt)
    sides = (native.first, native.opposite) if opposed else (native,)
    plates = []
    for side in sides:
        outline, = side.angle_contours_cm
        if outline[0] == outline[-1]:
            outline = outline[:-1]
        for placement in side.placements:
            frame = angle_cleat_geometry.rigid_frame_for_placement(placement)
            plates.append(assembly_geometry.Plate(
                f"{side.angle_profile.designation} · {placement.side}", frame.origin, frame.x_axis,
                frame.y_axis, outline, side.cleat_height_cm,
            ))
    fasteners = ((native.bolt_placements, bolt.nominal_diameter_mm, None),) if settings["model_bolts"] else ()
    return AngleCleatPlan(source.template, native, settings, tuple(plates), fasteners)


def evaluate_edit(design, source, settings, alternate=False):
    if not source.writable:
        raise ValueError(source.reason)
    if alternate:
        raise ValueError("Le sens d’un assemblage par cornières est déterminé par ses poutres.")
    return evaluate(design, source, source.occurrences, settings)


def apply_edit(design, source, plan):
    from . import assembly_copy

    return assembly_copy._rebuild_settings(design, source, plan, (plan.settings_mm, plan.alternate),
                                           read, evaluate_edit, reconfigure)


def create_copy(design, plan):
    if hasattr(plan.evaluation, "opposite"):
        result = angle_cleat_creator.create_opposed_double_angle_assembly(
            design.rootComponent, plan.evaluation, model_bolts=plan.settings_mm["model_bolts"],
        )
        return result.group
    result = angle_cleat_creator.create_double_angle_assembly(
        design.rootComponent, plan.evaluation, model_bolts=plan.settings_mm["model_bolts"],
    )
    return result.group


def reconfigure(design, source, plan):
    from ..commands.remove_assembly import remove

    marker = _definition(source.group)
    if (marker.value if marker else None) != source.original:
        raise ValueError("Les réglages des cornières ont changé depuis l’ouverture de la commande.")
    if plan.settings_mm == source.parameters_mm:
        return source.group
    remove(design, source.group)
    return create_copy(design, evaluate(design, source, source.occurrences, plan.settings_mm))
