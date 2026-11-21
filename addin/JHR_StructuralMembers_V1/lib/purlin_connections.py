"""Apparie les abouts des pannes avec les poutres choisies et prépare les plats d’âme."""
from dataclasses import dataclass
from math import radians, sin
import json

from . import assembly_placement, joint_geometry as geometry

KIND = "shear_plate"


@dataclass(frozen=True)
class Axis:
    occurrence: object
    start: tuple
    end: tuple


@dataclass(frozen=True)
class Batch:
    plans: tuple
    existing_count: int
    unmatched: tuple
    cope_plans: tuple
    cope_clearances_cm: tuple

    @property
    def cope_count(self):
        return sum(plan is not None for plan in self.cope_plans)


def match_ends(beam_axes, purlin_axes):
    """Trouve au plus une poutre par about, selon la tolérance de la jonction JHR."""
    beams = [(axis, geometry.normalize(geometry.subtract(axis.end, axis.start))) for axis in beam_axes]
    pairs, unmatched = [], []
    orthogonality_limit = sin(radians(.1))
    for purlin in purlin_axes:
        direction = geometry.normalize(geometry.subtract(purlin.end, purlin.start))
        matches = []
        for index, point in enumerate((purlin.start, purlin.end), start=1):
            supports = []
            for beam, axis in beams:
                if abs(geometry.dot(direction, axis)) > orthogonality_limit:
                    continue
                closest, _ = geometry.closest_point_on_segment(point, beam.start, beam.end)
                if geometry.length(geometry.subtract(point, closest)) <= geometry.JOINT_ENDPOINT_TOLERANCE_CM:
                    supports.append(beam.occurrence)
            if len(supports) > 1:
                names = ", ".join(beam.name for beam in supports)
                raise ValueError(f"{purlin.occurrence.name}, about {index} — plusieurs poutres possibles ({names}).")
            if supports:
                if supports[0] in matches:
                    raise ValueError(f"Les deux abouts de {purlin.occurrence.name} désignent la même poutre.")
                matches.append(supports[0])
        if not matches:
            unmatched.append(purlin.occurrence)
        pairs.extend((beam, purlin.occurrence) for beam in matches)
    return tuple(pairs), tuple(unmatched)


def _existing_pairs(design, attribute_group):
    for attr in design.findAttributes(attribute_group, "definition"):
        definition = json.loads(attr.value)
        tokens = definition.get("members", ())
        if len(tokens) == 2:
            first, second = (design.findEntityByToken(token) for token in tokens)
            yield definition["kind"], first, second


def _angle_cleat_pairs(design, attribute_group):
    pairs = set()
    for primary in design.findAttributes(attribute_group, "primary_component"):
        secondary = primary.parent.attributes.itemByName(attribute_group, "secondary_component")
        if secondary and primary.value and secondary.value:
            pairs.add(frozenset((primary.value, secondary.value)))
    return pairs


def _axes(design, occurrences, expected_role, caption, allow_bars):
    from . import joint_builder, member_metadata

    allowed_roles = (expected_role, "BARRE") if allow_bars else (expected_role,)
    axes = []
    for occurrence in occurrences:
        if not occurrence or not occurrence.isValid or occurrence not in design.rootComponent.occurrences:
            raise ValueError(f"Sélectionner les profils « {caption} » dans le composant racine.")
        metadata = joint_builder._member_metadata(occurrence, caption)
        if member_metadata.role_for(occurrence.component) not in allowed_roles:
            raise ValueError(f"{occurrence.name} — fonction attendue « {caption} ». Utiliser Modifier un profil.")
        curve = joint_builder._linked_curve(design, metadata, caption, allow_arc=False)
        axes.append(Axis(occurrence, *joint_builder._line_endpoints(curve)))
    return axes


def _interferes(design, beam, purlin):
    import adsk.core as core

    selection = core.ObjectCollection.create()
    selection.add(beam)
    selection.add(purlin)
    request = design.createInterferenceInput(selection)
    request.areCoincidentFacesIncluded = False
    overlaps = design.analyzeInterference(request)
    if overlaps is None:
        raise RuntimeError("Fusion n’a pas pu contrôler le chevauchement des deux profils.")
    return overlaps.count > 0


def _prepare_cope(design, beam, purlin, clearances_cm):
    from . import cope_builder, cope_creator

    cope = cope_builder.evaluate_profile_cope(design, beam, purlin, *clearances_cm)
    cope_creator.ensure_endpoint_available(cope)
    if cope.primary_extensions:
        raise ValueError("Le grugeage exige de prolonger la poutre porteuse. Ajuster sa longueur avant le lot.")
    return cope


def evaluate_batch(design, beams, purlins, settings_mm=None, *, allow_bars=False, alternate=False,
                   cope_clearances_cm=None):
    """Valide les appuis et les perçages du lot, sans modifier la conception."""
    from . import angle_cleat_creator, assembly_operations, default_settings

    if not beams or not purlins:
        raise ValueError("Sélectionner les poutres porteuses et les pannes.")
    if any(beam in purlins for beam in beams):
        raise ValueError("Un profil ne peut pas être à la fois poutre porteuse et panne dans le même lot.")
    beam_axes = _axes(design, beams, "POUTRE", "Poutre", allow_bars)
    purlin_axes = _axes(design, purlins, "PANNE", "Panne", allow_bars)
    pairs, unmatched = match_ends(beam_axes, purlin_axes)
    records = tuple(_existing_pairs(design, assembly_operations.ATTRIBUTE_GROUP)) if pairs else ()
    cleats = _angle_cleat_pairs(design, angle_cleat_creator.ATTRIBUTE_GROUP) if pairs else set()
    if cope_clearances_cm is None:
        defaults, _ = default_settings.load_or_factory()
        cope_clearances_cm = tuple(value * default_settings.MM_TO_CM for value in (
            defaults.cope_ih_vertical_mm, defaults.cope_ih_longitudinal_mm, defaults.cope_ih_support_mm,
        ))
    plans, cope_plans, existing_count = [], [], 0
    for beam, purlin in pairs:
        if frozenset((beam.component.name, purlin.component.name)) in cleats:
            raise ValueError(f"{purlin.name} → {beam.name} — les profils sont déjà assemblés par cornières.")
        prior = [kind for kind, first, second in records
                 if (beam in first and purlin in second) or (purlin in first and beam in second)]
        if any(kind != KIND for kind in prior):
            raise ValueError(f"{purlin.name} → {beam.name} — un autre assemblage relie déjà ces profils.")
        if prior:
            existing_count += 1
            continue
        try:
            plan = assembly_operations.evaluate(design, KIND, (beam, purlin), settings_mm, alternate)
            cope = _prepare_cope(design, beam, purlin, cope_clearances_cm) if _interferes(design, beam, purlin) else None
        except (ValueError, FileNotFoundError, RuntimeError) as error:
            raise ValueError(f"{purlin.name} → {beam.name} — {error}") from error
        plans.append(plan)
        cope_plans.append(cope)
    return Batch(tuple(plans), existing_count, unmatched, tuple(cope_plans), cope_clearances_cm)


def create_batch(design, batch, *, parent=assembly_placement.DEFAULT_PARENT):
    """Applique le lot dans la transaction de la commande Fusion."""
    from . import assembly_operations, cope_creator, joint_records, timeline_groups

    changed_purlins, groups = [], []
    for plan, cope in zip(batch.plans, batch.cope_plans):
        beam, purlin = (member.occurrence for member in plan.members)
        already_modified = purlin in changed_purlins
        start = timeline_groups.creation_start(design.timeline)
        try:
            with timeline_groups.defer_grouping():
                previous_records = set()
                if cope:
                    if already_modified:
                        cope = _prepare_cope(design, beam, purlin, batch.cope_clearances_cm)
                    previous_records = {item.name for item in purlin.component.attributes.itemsByGroup(
                        joint_records.ATTRIBUTE_GROUP,
                    )}
                    cope_creator.create_profile_cope(cope)
                if cope or already_modified:
                    plan = assembly_operations.evaluate(design, KIND, (beam, purlin), plan.settings_mm, plan.alternate)
                group = assembly_operations.create(design, plan, parent=parent)
                marker = group.component.attributes.itemByName(assembly_operations.ATTRIBUTE_GROUP, "definition")
                record = json.loads(marker.value)
                record["purlin_connection"] = True
                record["cope_clearances_cm"] = batch.cope_clearances_cm
                if cope:
                    record["joint_records"] = [
                        {"member": purlin.entityToken, "name": item.name}
                        for item in purlin.component.attributes.itemsByGroup(joint_records.ATTRIBUTE_GROUP)
                        if item.name not in previous_records
                    ]
                marker.value = json.dumps(record)
            timeline_groups.group_creation(design.timeline, start, group.component.name)
            groups.append(group)
        except Exception as error:
            raise RuntimeError(f"Raccord de {purlin.name} sur {beam.name} interrompu. {error}") from error
        changed_purlins.append(purlin)
    return tuple(groups)
