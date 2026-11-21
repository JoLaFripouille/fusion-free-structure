"""Édition des assemblages JHR sans remplacer leurs profils sources."""

from dataclasses import dataclass, field
import json
from math import atan2, isclose, pi
from uuid import uuid4

import adsk.core as core
import adsk.fusion as fusion

from . import assembly_catalog as catalogue, assembly_geometry as shapes
from . import assembly_operations as assemblies, joint_geometry as geo


@dataclass(frozen=True)
class EditTarget:
    group: object
    template: catalogue.Template
    occurrences: tuple
    parameters_mm: dict
    alternate: bool
    writable: bool
    reason: str
    original: str


@dataclass(frozen=True)
class Revision:
    target: EditTarget
    plan: assemblies.AssemblyPlan
    parts: tuple


@dataclass
class Journal:
    design: object
    marker: object
    original: str
    undo: list = field(default_factory=list)
    position_snapshots: list = field(default_factory=list)

    def rollback(self):
        errors = []
        for restore in reversed(self.undo):
            try:
                restore()
            except Exception as error:
                errors.append(str(error))
        self.undo.clear()
        self.design.timeline.moveToEnd()
        if self.marker.value != self.original:
            self.marker.value = self.original
        if errors:
            raise RuntimeError("Restauration du pied incomplète : " + " · ".join(errors))


def _marker(group):
    marker = group.component.attributes.itemByName(assemblies.ATTRIBUTE_GROUP, "definition")
    if not marker:
        raise ValueError("La définition de l’assemblage JHR est introuvable.")
    return marker


def read(design, entity):
    """Retrouve le type, les rôles et les valeurs existantes depuis une tôle ou le groupe."""
    group = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
    while group and not group.component.attributes.itemByName(assemblies.ATTRIBUTE_GROUP, "definition"):
        group = group.assemblyContext
    if not group:
        raise ValueError("Sélectionner le groupe d’un assemblage à platines JHR ou l’une de ses tôles.")

    marker = _marker(group)
    original = marker.value
    payload = json.loads(original)
    template = catalogue.template_for(payload["kind"])
    tokens = payload.get("members", ())
    if len(tokens) != len(template.roles):
        raise ValueError("Les profils sources de cet assemblage sont incomplets.")

    occurrences = []
    for token, role in zip(tokens, template.roles):
        matches = [occurrence for item in design.findEntityByToken(token)
                   if (occurrence := fusion.Occurrence.cast(item)) and occurrence.isValid]
        if len(matches) != 1:
            raise ValueError(f"Profil source introuvable ou ambigu : {role}.")
        occurrences.append(matches[0])

    settings = catalogue.recorded_parameters(template, payload.get("parameters_mm", {}))
    params = {f.key: settings.get(f.key, f.default)
              for _, fields in template.groups for f in fields}
    link = payload.get("shear_link") or payload.get("end_plate_link") or payload.get("splice_link") or {}
    alternate = bool(link.get("alternate", payload.get("alternate", False)))
    reason = ""
    if template.family != "Pieds de poteau":
        from ..commands.remove_assembly import target_group

        try:
            target_group(design, group)
        except (ValueError, RuntimeError) as error:
            reason = str(error)
        if not reason and not link and "alternate" not in payload:
            for candidate in (False, True):
                plan = assemblies.evaluate(design, template.key, tuple(occurrences), params, candidate,
                                           check_material=False)
                if assemblies._plates_match(group, plan.plates):
                    alternate = candidate
                    break
            else:
                reason = "Le côté de montage d’origine de cet assemblage est introuvable."
    elif payload.get("base_end_index") not in (0, 1):
        reason = "Ce pied ancien ne comporte pas de liaison d’extrémité enregistrée."
    elif _component_instances(design, group.component) != 1:
        reason = "Le pied doit être une occurrence unique dans la conception."
    else:
        member = assemblies._member(design, occurrences[0], template.roles[0])
        start, end = assemblies.joints._line_endpoints(member.curve)
        alternate = payload["base_end_index"] != int(end[2] < start[2])
    return EditTarget(group, template, tuple(occurrences), params, alternate, not reason, reason, original)


def _component_instances(design, component):
    return design.rootComponent.allOccurrencesByComponent(component).count


def _use_hardware(target, settings):
    payload = json.loads(target.original)
    return bool(payload.get("base_anchor_hardware") or not target.parameters_mm.get("anchor_diameter")
                and settings.get("anchor_diameter"))


def evaluate(design, target, parameters_mm, alternate=None, *, preview_support=False):
    """Prépare le nouvel état mécanique et l’aperçu du pied sans créer d’entités."""
    if not target.writable:
        raise ValueError(target.reason)
    if target.template.family != "Pieds de poteau":
        side = target.alternate if alternate is None else alternate
        return assemblies.evaluate(design, target.template.key, target.occurrences, parameters_mm, side,
                                   check_material=False, preview_support=preview_support)
    if alternate is not None and alternate != target.alternate:
        raise ValueError("Le remplacement d’un pied d’une extrémité à l’autre changerait sa liaison.")
    dimensions = shapes.dimensions(target.template, parameters_mm)
    settings = {field.key: dimensions[field.key] * (10 if field.unit == "mm" else 1)
                for _, fields in target.template.groups for field in fields}
    member = assemblies._member(design, target.occurrences[0], target.template.roles[0])
    stored = json.loads(target.original)
    flush = bool(stored.get("base_flush"))
    pieces = assemblies._base(member, dimensions, stored["base_end_index"], target.template.key,
                              include_anchor_hardware=_use_hardware(target, settings), flush_to_skeleton=flush)
    plates = tuple(shapes.finish_rectangle(plate, dimensions.get("chamfer", 0.), dimensions.get("corner_radius", 0.))
                   if plate.finishable else plate for plate in pieces)
    return assemblies.AssemblyPlan(target.template, (member,), settings, plates,
                                   alternate=target.alternate, base_flush=flush)


def prepare_refresh(design, group):
    """Capture la géométrie d’origine avant de modifier la section ou l’orientation du poteau."""
    target = read(design, group)
    if not target.writable:
        raise ValueError(target.reason)
    plan = evaluate(design, target, target.parameters_mm)
    parts = tuple(group.childOccurrences)
    if not assemblies._plates_match(group, plan.plates):
        raise ValueError("Le pied ne correspond plus aux positions enregistrées. Contrôler sa liaison avant édition.")
    for part, shape in zip(parts, plan.plates):
        if not _solid_matches(part, shape):
            raise ValueError(f"{part.component.name} a été retouché. Contrôler le pied avant édition.")
    return Revision(target, plan, parts)


def refresh(design, revision):
    """Recalcule un pied après changement du poteau et retourne un journal réversible."""
    target = revision.target
    plan = evaluate(design, target, target.parameters_mm)
    return _apply(design, revision, plan)


def apply(design, target, plan):
    """Applique une édition du formulaire avec le groupe et sa liaison d’origine."""
    if _marker(target.group).value != target.original:
        raise ValueError("Cet assemblage a changé depuis l’ouverture du formulaire.")
    if plan.support_errors:
        raise assemblies.support_error(plan.support_errors)
    from . import assembly_copy

    if target.template.family != "Pieds de poteau":
        return assembly_copy.rebuild_linked(design, target, plan)
    revision = prepare_refresh(design, target.group)
    latest = evaluate(design, target, plan.settings_mm, plan.alternate)
    return assembly_copy.apply_master_settings(design, revision, latest)


def _rebuild(design, target, plan):
    from ..commands.remove_assembly import remove
    from . import purlin_connections

    if not target.writable:
        raise ValueError(target.reason)
    if plan.settings_mm == target.parameters_mm and plan.alternate == target.alternate:
        return target.group
    record = json.loads(target.original)
    parent = target.group.assemblyContext
    # Suppression et recréation restent dans la même transaction native de la commande.
    remove(design, target.group)
    if target.template.key == "shear_plate" and (record.get("purlin_connection") or record.get("joint_records")):
        main, purlin = target.occurrences
        batch = purlin_connections.evaluate_batch(design, (main,), (purlin,), plan.settings_mm, allow_bars=True,
                                                  alternate=plan.alternate,
                                                  cope_clearances_cm=record.get("cope_clearances_cm"))
        groups = purlin_connections.create_batch(design, batch, parent=parent)
        if len(groups) != 1:
            raise RuntimeError("Fusion n’a pas régénéré le raccord de la panne.")
        return groups[0]
    return assemblies.create(design, assemblies.evaluate(
        design, target.template.key, target.occurrences, plan.settings_mm, plan.alternate,
    ), parent=parent)


def _piece_family(name):
    # Les pièces d’un même type gardent leur place quand seul le diamètre change.
    return name.split(" M", 1)[0].split(" Ø", 1)[0]


def _profile_features(body, plate):
    return (
        body.faces.count == len(plate.outline) + len(plate.holes) + 2
        and isclose(body.volume, _profile_area(plate) * plate.thickness_cm, rel_tol=1e-4, abs_tol=1e-5)
    )


def _profile_area(plate):
    # Les contours arrondis sont échantillonnés uniquement pour la lecture préalable.
    # La géométrie appliquée utilise de vrais arcs et vérifie les boucles de l’esquisse.
    contour = plate.display_outline()
    edge_area = abs(sum(a[0]*b[1] - a[1]*b[0] for a, b in zip(contour, contour[1:] + contour[:1]))) / 2
    return edge_area - sum(pi * diameter**2 / 4 for _, _, diameter in plate.holes)


def _solid_matches(part, plate):
    bodies = part.component.bRepBodies
    if bodies.count != 1 or not bodies.item(0).isSolid:
        return False
    body = bodies.item(0)
    if plate.arcs:
        # Les arcs peuvent être regroupés sur une seule face cylindrique par Fusion.
        return isclose(body.volume, _profile_area(plate) * plate.thickness_cm, rel_tol=.01, abs_tol=1e-5)
    return _profile_features(body, plate)


def _matrix(plate):
    matrix = core.Matrix3D.create()
    matrix.setWithCoordinateSystem(core.Point3D.create(*plate.origin), core.Vector3D.create(*plate.u),
                                   core.Vector3D.create(*plate.v), core.Vector3D.create(*plate.normal))
    return matrix


def _replace_profile(component, plate, journal):
    sketch = component.sketches.add(component.xYConstructionPlane)
    journal.undo.append(lambda: _remove_sketch(sketch))
    sketch.name = "Contour et perçages — édition"
    points = [core.Point3D.create(x, y, 0) for x, y in plate.outline]
    arcs = dict(plate.arcs)
    for index, (start, end) in enumerate(zip(points, points[1:] + points[:1])):
        if index in arcs:
            middle = core.Point3D.create(*arcs[index], 0)
            sketch.sketchCurves.sketchArcs.addByThreePoints(start, middle, end).isFixed = True
        else:
            sketch.sketchCurves.sketchLines.addByTwoPoints(start, end).isFixed = True
    for x, y, diameter in plate.holes:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(core.Point3D.create(x, y, 0), diameter/2).isFixed = True
    profile = max(sketch.profiles, key=lambda region: region.profileLoops.count, default=None)
    if not profile or profile.profileLoops.count != 1 + len(plate.holes):
        raise RuntimeError("Le nouveau contour et ses perçages ne forment pas un profil unique.")
    sketch.isVisible = False
    return profile


def _remove_sketch(sketch):
    if sketch.isValid and not sketch.deleteMe():
        raise RuntimeError("L’esquisse d’édition est restée dans la conception.")


def _roll_before(feature):
    if not feature.timelineObject.rollTo(True):
        raise RuntimeError("Impossible de revenir avant l’extrusion de la tôle.")


def _restore_profile(design, feature, profile):
    group = feature.timelineObject.parentGroup
    collapsed = bool(group and group.isCollapsed)
    if collapsed:
        group.isCollapsed = False
    try:
        _roll_before(feature)
        feature.profile = profile
    finally:
        design.timeline.moveToEnd()
        if group and group.isValid and group.isCollapsed != collapsed:
            group.isCollapsed = collapsed


def _modify_part(design, part, old, new, journal):
    if (old.outline, old.arcs, old.holes, old.thickness_cm, old.name) == (
        new.outline, new.arcs, new.holes, new.thickness_cm, new.name,
    ):
        return
    component = part.component
    feature = component.features.extrudeFeatures.itemByName("Épaisseur de la tôle")
    if not feature or not feature.isParametric or component.features.count != 1 or _component_instances(design, component) != 1:
        raise ValueError(f"La géométrie de {component.name} a été retouchée ou est réutilisée.")
    extent = fusion.DistanceExtentDefinition.cast(feature.extentOne)
    if not extent:
        raise ValueError(f"L’épaisseur de {component.name} ne correspond plus à une extrusion droite.")
    if (old.outline, old.arcs, old.holes) != (new.outline, new.arcs, new.holes):
        group = feature.timelineObject.parentGroup
        collapsed = bool(group and group.isCollapsed)
        if collapsed:
            group.isCollapsed = False
        try:
            prior = feature.profile
            _roll_before(feature)
            sketch_profile = _replace_profile(component, new, journal)
            journal.undo.append(lambda: _restore_profile(design, feature, prior))
            feature.profile = sketch_profile
        finally:
            design.timeline.moveToEnd()
            if group and group.isValid and group.isCollapsed != collapsed:
                group.isCollapsed = collapsed

    if old.thickness_cm != new.thickness_cm:
        parameter = fusion.DistanceExtentDefinition.cast(feature.extentOne).distance
        expression = parameter.expression
        journal.undo.append(lambda: setattr(parameter, "expression", expression))
        parameter.value = new.thickness_cm
    if feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState or not _solid_matches(part, new):
        raise RuntimeError(f"La géométrie du nouveau solide est invalide : {new.name}.")
    if old.name != new.name:
        if component.name == old.name:
            journal.undo.append(lambda: setattr(component, "name", old.name))
            component.name = new.name
        body = component.bRepBodies.item(0)
        if body.name == old.name:
            journal.undo.append(lambda: setattr(body, "name", old.name))
            body.name = new.name


def _matches_matrix(occurrence, matrix):
    actual = occurrence.transform2.getAsCoordinateSystem()
    return all(geo.length(geo.subtract(got.asArray(), wanted.asArray())) <= assemblies.TOL
               for got, wanted in zip(actual, matrix.getAsCoordinateSystem()))


def _assert_placements(placements):
    failed = [child.component.name for child, matrix in placements if not _matches_matrix(child, matrix)]
    if failed:
        raise RuntimeError("Fusion n’a pas conservé la position ou l’orientation de : " + ", ".join(failed))


def _rotation_matches(placements, rotation):
    for child, wanted in placements:
        before = child.transform2.getAsCoordinateSystem()
        for coordinate, expected in zip(before, wanted.getAsCoordinateSystem()):
            coordinate.transformBy(rotation)
            if geo.length(geo.subtract(coordinate.asArray(), expected.asArray())) > assemblies.TOL:
                return False
    return True


def _rotate_linked_group(design, group, placements, journal):
    """Utilise la liaison du pied si toutes les pièces suivent une rotation rigide."""
    if not placements:
        return False
    first, wanted = placements[0]
    _, old_u, _, old_normal = first.transform2.getAsCoordinateSystem()
    _, new_u, _, new_normal = wanted.getAsCoordinateSystem()
    if (geo.length(geo.subtract(old_u.asArray(), new_u.asArray())) <= assemblies.TOL
            or design.snapshots.hasPendingSnapshot):
        return False
    joints = [joint for joint in design.rootComponent.joints if joint.name.startswith("Liaison au squelette – ")
              and (joint.occurrenceOne == group or joint.occurrenceTwo == group)]
    if len(joints) != 1 or not joints[0].angle:
        return False
    joint = joints[0]
    input_frame = (joint.geometryTwoTransform if joint.occurrenceOne == group
                   else joint.geometryOneTransform)
    if not input_frame:
        return False
    pivot, _, _, axis = input_frame.getAsCoordinateSystem()
    normal = axis.asArray()
    if any(abs(geo.dot(normal, vector.asArray())) < 1 - assemblies.TOL for vector in (old_normal, new_normal)):
        return False
    angle = atan2(geo.dot(normal, geo.cross(old_u.asArray(), new_u.asArray())),
                  geo.dot(old_u.asArray(), new_u.asArray()))
    if abs(angle) <= assemblies.TOL:
        return False
    rotation = core.Matrix3D.create()
    if not rotation.setToRotation(angle, axis, pivot) or not _rotation_matches(placements, rotation):
        return False

    parameter = joint.angle
    original, value = parameter.expression, parameter.value
    for delta in (angle, -angle):
        try:
            parameter.value = value + delta
            if all(_matches_matrix(child, matrix) for child, matrix in placements):
                journal.undo.append(lambda: setattr(parameter, "expression", original))
                return True
        except RuntimeError:
            pass
        parameter.expression = original
    raise RuntimeError("La rotation mesurée n’a pas été appliquée par la liaison du pied.")


def _move_parts(design, placements, journal, *, base_plate=None):
    if not placements:
        return
    snapshots = design.snapshots
    if snapshots.hasPendingSnapshot:
        raise ValueError("Valider ou annuler les déplacements en cours avant de repositionner le pied.")

    before = [(child, child.transform2.copy(), desired) for child, desired in placements]

    def restore():
        for occurrence, matrix, _ in before:
            occurrence.transform2 = matrix

    captured = False
    try:
        # Le setter travaille sur le proxy racine, dont le repère est celui du plan.
        # transformOccurrences laisse parfois intacte une pièce qui pivote sur place.
        for occurrence, _, matrix in before:
            if occurrence == base_plate and occurrence.isGroundToParent:
                # Fusion ancre la première pièce à sa position de création.
                # La liaison du pied au squelette reste portée par le groupe.
                occurrence.isGroundToParent = False
                journal.undo.append(lambda part=occurrence: setattr(part, "isGroundToParent", True))
            occurrence.transform2 = matrix
        _assert_placements(placements)
        if snapshots.hasPendingSnapshot:
            snapshot = snapshots.add()
            if not snapshot:
                raise RuntimeError("Fusion n’a pas conservé le déplacement des pièces.")
            journal.undo.append(lambda: _delete_owned(snapshot, "Le repositionnement n’a pas été annulé."))
            captured = True
            snapshot.name = f"JHR · Position du pied · {uuid4().hex}"
            journal.position_snapshots.append(snapshot.name)
        else:
            journal.undo.append(restore)
        _assert_placements(placements)
    except Exception:
        if snapshots.hasPendingSnapshot:
            snapshots.revertPendingSnapshot()
        elif not captured and (not journal.undo or journal.undo[-1] is not restore):
            # Si une erreur précède la capture, il peut s’agir d’un placement
            # direct que Fusion n’a pas marqué comme transformée en attente.
            restore()
        raise


def _delete_owned(entity, message):
    if entity.isValid and not entity.deleteMe():
        raise RuntimeError(message)


def _check_piece_layout(old_plates, new_plates):
    if len(new_plates) < len(old_plates) or any(
        _piece_family(old.name) != _piece_family(new.name) for old, new in zip(old_plates, new_plates)
    ):
        raise ValueError("Cette modification retirerait ou remplacerait des pièces liées du pied.")


def _apply(design, revision, plan):
    target = revision.target
    marker = _marker(target.group)
    if marker.value != target.original:
        raise ValueError("La définition du pied a changé pendant l’opération.")
    old_plates, new_plates = revision.plan.plates, plan.plates
    _check_piece_layout(old_plates, new_plates)
    journal = Journal(design, marker, target.original)
    try:
        for child, before, after in zip(revision.parts, old_plates, new_plates):
            _modify_part(design, child, before, after, journal)
        placements = tuple((child, _matrix(plate)) for child, plate in zip(revision.parts, new_plates))
        changed = tuple((child, matrix) for child, matrix in placements if not _matches_matrix(child, matrix))
        if changed and not _rotate_linked_group(design, target.group, placements, journal):
            _move_parts(design, changed, journal, base_plate=revision.parts[0])
        if len(new_plates) > len(old_plates):
            reverse = target.group.transform2.copy()
            if not reverse.invert():
                raise RuntimeError("Le repère du pied ne peut pas être inversé.")
            material = plan.members[0].body.material
            for plate in new_plates[len(old_plates):]:
                child = assemblies._create_plate(target.group.component, assemblies._local_plate(plate, reverse),
                                                  material if plate.inherit_material else None)
                journal.undo.append(lambda child=child: _delete_owned(child, "La pièce ajoutée n’a pas été retirée."))
        if not assemblies._plates_match(target.group, new_plates):
            raise RuntimeError("Les pièces déplacées ne correspondent pas au pied recalculé.")
        if plan.base_flush:
            from . import base_seat_trim

            base_seat_trim.verify_plate_seat(plan.members[0], plan.plates[0])
        record = json.loads(target.original)
        if journal.position_snapshots:
            record.setdefault("position_snapshots", []).extend(journal.position_snapshots)
        if revision.plan.settings_mm != plan.settings_mm or journal.undo:
            record["parameters_mm"] = plan.settings_mm
            record["origin"] = plan.plates[0].origin
            if _use_hardware(target, plan.settings_mm):
                record["base_anchor_hardware"] = True
        record["reference_state"] = [assemblies._reference_state(member) for member in plan.members]
        serialized = json.dumps(record)
        if json.loads(serialized) != json.loads(target.original):
            marker.value = serialized
        return journal
    except Exception:
        journal.rollback()
        raise
