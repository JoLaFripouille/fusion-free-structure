"""Copie bornée d'ensembles simples existants, sans téléchargement ni filetage créé."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import bolt_geometry, fastener_geometry as geo, joint_geometry as vec, timeline_groups


ATTRIBUTE_GROUP = "EI_JHR_FastenerV1"
EPSILON_CM = 0.00001


@dataclass
class Prototype:
    body: object
    layout: object
    origin: tuple
    axes: tuple


def point(value):
    return tuple(float(x) for x in value.asArray())


def prototype_body(entity):
    occurrence = adsk.fusion.Occurrence.cast(entity)
    if occurrence:
        if occurrence.bRepBodies.count != 1:
            raise ValueError("Choisir un ensemble simple contenant un seul corps solide direct.")
        entity = occurrence.bRepBodies.item(0)
    body = adsk.fusion.BRepBody.cast(entity)
    if not body or not body.isSolid or body.isTemporary:
        raise ValueError("Sélectionner le corps solide d'un ensemble existant complet.")
    body = body.nativeObject or body
    if body.faces.count > 200:
        raise ValueError("Le modèle est trop détaillé ; choisir une représentation simple.")
    return body


def size_from_name(body):
    text = body.parentComponent.name + " " + body.name
    match = re.search(r"\bM(\d+(?:[.,]\d+)?)\s*[x×]\s*(\d+(?:[.,]\d+)?)", text, re.I)
    return tuple(float(v.replace(",", ".")) for v in match.groups()) if match else None


def _face_interval(face, axis):
    stations = [vec.dot(point(v.geometry), axis) for v in face.vertices]
    if not stations:
        stations = [vec.dot(point(face.pointOnFace), axis)]
    return min(stations), max(stations)


def read_prototype(entity, diameter_mm, length_mm):
    body = prototype_body(entity)
    radius = float(diameter_mm) * 0.05
    shafts = [adsk.core.Cylinder.cast(f.geometry) for f in body.faces
              if adsk.core.Cylinder.cast(f.geometry)
              and abs(adsk.core.Cylinder.cast(f.geometry).radius - radius) < 0.002]
    if not shafts:
        raise ValueError("Le diamètre choisi ne correspond pas à la tige du modèle.")
    shaft_axis = vec.normalize(point(shafts[0].axis))
    tips = [f for f in body.faces if adsk.core.Plane.cast(f.geometry)
            and abs(f.area - math.pi * radius * radius) < max(1e-5, radius * radius * 0.001)
            and f.loops.count == 1
            and abs(vec.dot(point(adsk.core.Plane.cast(f.geometry).normal), shaft_axis)) > 0.9999]
    if len(tips) != 1:
        raise ValueError("L'extrémité plane de la vis n'est pas reconnue ; modèle refusé.")
    tip = tips[0]
    ok, normal = tip.evaluator.getNormalAtPoint(tip.pointOnFace)
    if not ok:
        raise ValueError("La direction de la vis n'est pas lisible.")
    axis = vec.normalize(point(normal))
    line_origin = point(shafts[0].origin)
    tip_station = vec.dot(point(tip.pointOnFace), axis)
    transverse_x, transverse_y, _ = bolt_geometry.perpendicular_axes(axis)
    cylinders, sides, wide = [], [], []
    for face in body.faces:
        lo, hi = _face_interval(face, axis)
        vertices = [point(v.geometry) for v in face.vertices]
        if not vertices:
            vertices = [point(face.pointOnFace)]
        transverse = [vec.subtract(vec.subtract(p, line_origin),
                                  vec.scale(axis, vec.dot(vec.subtract(p, line_origin), axis)))
                      for p in vertices]
        if max(vec.length(p) for p in transverse) > radius * 1.1:
            wide.append((lo, hi))
        cylinder = adsk.core.Cylinder.cast(face.geometry)
        if cylinder and abs(vec.dot(point(cylinder.axis), axis)) > 0.9999:
            delta = vec.subtract(point(cylinder.origin), line_origin)
            if vec.length(vec.subtract(delta, vec.scale(axis, vec.dot(delta, axis)))) < 0.002:
                cylinders.append((float(cylinder.radius), lo, hi))
        plane = adsk.core.Plane.cast(face.geometry)
        if plane and abs(vec.dot(point(plane.normal), axis)) < 0.0001:
            delta = vec.subtract(point(face.pointOnFace), line_origin)
            distance = vec.length(vec.subtract(delta, vec.scale(axis, vec.dot(delta, axis))))
            ok, side_normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
            if ok:
                angle = math.atan2(vec.dot(point(side_normal), transverse_y),
                                   vec.dot(point(side_normal), transverse_x))
                sides.append((lo, hi, distance, angle))
    layout, bearing_station = geo.recognize_sections(
        diameter_mm, length_mm, tip_station, cylinders, sides, wide)
    origin = vec.add(line_origin, vec.scale(axis, bearing_station - vec.dot(line_origin, axis)))
    return Prototype(body, layout, origin, bolt_geometry.perpendicular_axes(axis))


def _slot_walls(face, axis):
    """Only the two planes joined to axial edges of this selected cap."""
    result = {}
    for edge in face.edges:
        line = adsk.core.Line3D.cast(edge.geometry)
        if not line:
            continue
        direction = vec.normalize(vec.subtract(point(line.endPoint), point(line.startPoint)))
        if abs(vec.dot(direction, axis)) < 1. - geo.PARALLEL_TOLERANCE:
            continue
        for other in edge.faces:
            plane = adsk.core.Plane.cast(other.geometry)
            if other != face and plane and abs(vec.dot(point(plane.normal), axis)) < geo.PARALLEL_TOLERANCE:
                result[other.tempId] = other
    return result


def _slot_partner(face, cylinder):
    """Recognise an oblong by shared side walls, never by nearest cylinder."""
    axis = vec.normalize(point(cylinder.axis))
    walls = _slot_walls(face, axis)
    if not walls:
        return None
    if len(walls) != 2:
        raise ValueError("Contour d'oblong incomplet ; sélectionner une demi-face cylindrique intérieure.")
    first, second = (adsk.core.Plane.cast(f.geometry) for f in walls.values())
    normal = vec.normalize(point(first.normal))
    spacing = abs(vec.dot(vec.subtract(point(second.origin), point(first.origin)), normal))
    if (abs(vec.dot(normal, vec.normalize(point(second.normal)))) < 1. - geo.PARALLEL_TOLERANCE
            or abs(spacing - 2 * cylinder.radius) > geo.POSITION_TOLERANCE_CM):
        raise ValueError("Les parois choisies ne définissent pas un oblong simple.")
    candidates = {}
    for wall in walls.values():
        for edge in wall.edges:
            for other in edge.faces:
                cy = adsk.core.Cylinder.cast(other.geometry)
                if (other != face and cy and abs(cy.radius - cylinder.radius) < geo.POSITION_TOLERANCE_CM
                        and abs(vec.dot(point(cy.axis), axis)) > 1. - geo.PARALLEL_TOLERANCE
                        and set(_slot_walls(other, axis)) == set(walls)):
                    candidates[other.tempId] = cy
    if len(candidates) != 1:
        raise ValueError("Les deux extrémités de l'oblong ne sont pas identifiables sans ambiguïté.")
    partner = next(iter(candidates.values()))
    slot = geo.slot_from_caps(point(cylinder.origin), point(partner.origin), axis, cylinder.radius)
    if abs(vec.dot(slot.slot_axis, normal)) > geo.PARALLEL_TOLERANCE:
        raise ValueError("Les extrémités ne suivent pas les deux parois de l'oblong.")
    return slot


def read_hole(entity):
    edge = adsk.fusion.BRepEdge.cast(entity)
    face = adsk.fusion.BRepFace.cast(entity)
    circle = adsk.core.Circle3D.cast(edge.geometry) if edge else None
    arc = adsk.core.Arc3D.cast(edge.geometry) if edge else None
    cylinder = adsk.core.Cylinder.cast(face.geometry) if face else None
    candidates = list(edge.faces) if circle or arc else [face] if cylinder else []
    for candidate in candidates:
        cy = adsk.core.Cylinder.cast(candidate.geometry)
        if not cy:
            continue
        p = point(candidate.pointOnFace)
        axis = vec.normalize(point(cy.axis))
        radial = vec.subtract(vec.subtract(p, point(cy.origin)),
                              vec.scale(axis, vec.dot(vec.subtract(p, point(cy.origin)), axis)))
        ok, normal = candidate.evaluator.getNormalAtPoint(candidate.pointOnFace)
        if ok and vec.dot(radial, point(normal)) < 0:
            slot = _slot_partner(candidate, cy)
            if slot:
                return slot
            if arc:
                raise ValueError("Sélectionner un contour rond complet ou un oblong à deux parois parallèles.")
            return geo.Hole(point(circle.center) if circle else point(cy.origin),
                            axis, cy.radius * 2)
    raise ValueError("Choisir une arête circulaire, un arc ou une face cylindrique intérieure de perçage.")


def read_support(entity):
    face = adsk.fusion.BRepFace.cast(entity)
    plane = adsk.core.Plane.cast(face.geometry) if face else None
    if not plane:
        raise ValueError("Choisir une face d'appui plane.")
    return geo.SupportPlane(point(face.pointOnFace), point(plane.normal))


def read_countersink(entity):
    """Reconnaît une fraisure entre deux contours circulaires concentriques."""
    face = adsk.fusion.BRepFace.cast(entity)
    cone = adsk.core.Cone.cast(face.geometry) if face else None
    if not cone:
        raise ValueError("Choisir la face conique intérieure de la fraisure.")
    circles = [
        circle for edge in face.edges
        if (circle := adsk.core.Circle3D.cast(edge.geometry))
    ]
    if len(circles) != 2:
        raise ValueError("La fraisure doit avoir deux bords circulaires complets.")
    bore, opening = sorted(circles, key=lambda circle: circle.radius)
    center = point(opening.center)
    delta = vec.subtract(point(bore.center), center)
    depth = vec.length(delta)
    if depth <= geo.POSITION_TOLERANCE_CM or opening.radius - bore.radius <= geo.POSITION_TOLERANCE_CM:
        raise ValueError("La fraisure ne présente pas de profondeur ou de diamètre distinct.")
    axis = vec.scale(delta, 1 / depth)
    if abs(vec.dot(axis, point(cone.axis))) < 1 - geo.PARALLEL_TOLERANCE:
        raise ValueError("Les deux bords de la fraisure ne sont pas coaxiaux.")
    sample = face.pointOnFace
    axial_delta = vec.subtract(point(sample), center)
    radial = vec.subtract(axial_delta, vec.scale(axis, vec.dot(axial_delta, axis)))
    ok, normal = face.evaluator.getNormalAtPoint(sample)
    if not ok or vec.dot(radial, point(normal)) >= 0:
        raise ValueError("Sélectionner une fraisure intérieure, pas une tête de vis.")
    return geo.CountersunkHole(center, axis, 2 * bore.radius, 2 * opening.radius, depth)


def assembly_hardware(assembly):
    return [child for child in assembly.childOccurrences
            if child.component.attributes.itemByName(ATTRIBUTE_GROUP, "assembly_hardware")]


def existing_positions(root, prototype=None, *, ignored_assembly=None):
    """Détecte les poses dans VISSERIE à la racine et dans les assemblages JHR."""
    result = []
    prototype_component = prototype.body.parentComponent if prototype else None
    def visit(occurrence):
        component = occurrence.component
        marker = component.attributes.itemByName(ATTRIBUTE_GROUP, "configuration")
        if marker:
            local_origin, local_axis = (0., 0., 0.), (0., 0., 1.)
            grip = float(json.loads(marker.value)["grip_cm"])
            if not math.isfinite(grip) or grip <= 0:
                raise ValueError("Un ensemble JHR mémorise un serrage invalide.")
        elif prototype_component and component == prototype_component and component.bRepBodies.count == 1:
            local_origin, local_axis = prototype.origin, prototype.axes[2]
            grip = prototype.layout.grip_cm
        else:
            local_origin = local_axis = None
        if local_origin is not None:
            p = adsk.core.Point3D.create(*local_origin)
            z = adsk.core.Vector3D.create(*local_axis)
            p.transformBy(occurrence.transform2); z.transformBy(occurrence.transform2)
            axes = bolt_geometry.perpendicular_axes(point(z))
            result.append(geo.Placement(point(p), *axes, grip))
        for child in occurrence.childOccurrences:
            visit(child)
    for occurrence in root.occurrences:
        if occurrence == ignored_assembly:
            continue
        if occurrence.component.name.upper() == "VISSERIE":
            visit(occurrence)
        elif (occurrence.component.attributes.itemByName("EI_JHR_Assembly", "definition")
              or occurrence.component.attributes.itemByName("EI_JHR_BraceBay", "definition")
              or occurrence.component.attributes.itemByName("EI_JHR_AngleCleat", "assembly_index")):
            for child in assembly_hardware(occurrence):
                visit(child)
        elif occurrence.component.attributes.itemByName("EI_JHR_Guardrail", "definition"):
            for part in occurrence.childOccurrences:
                if part.component.attributes.itemByName("EI_JHR_Guardrail", "post_split"):
                    for child in assembly_hardware(part):
                        visit(child)
    return tuple(result)


def verify_clearance(design, assembly_occurrences):
    """Contrôle ciblé des volumes solides. Les surfaces d’appui peuvent coïncider."""
    selection = adsk.core.ObjectCollection.create()
    for occurrence in assembly_occurrences:
        selection.add(occurrence)
    request = design.createInterferenceInput(selection)
    request.areCoincidentFacesIncluded = False
    overlaps = design.analyzeInterference(request)
    if overlaps is None:
        raise RuntimeError("Fusion n’a pas pu contrôler les interférences de l’assemblage.")
    if overlaps.count:
        collision = overlaps.item(0)
        raise ValueError(f"Interférence entre {collision.entityOne.name} et {collision.entityTwo.name}.")


def _box(manager, lo, hi):
    return manager.createBox(adsk.core.OrientedBoundingBox3D.create(
        adsk.core.Point3D.create(*[(a + b) / 2 for a, b in zip(lo, hi)]),
        adsk.core.Vector3D.create(1, 0, 0), adsk.core.Vector3D.create(0, 1, 0),
        *[b - a for a, b in zip(lo, hi)]))


def _normalized_copy(manager, prototype):
    x, y, z = prototype.axes
    m = adsk.core.Matrix3D.create()
    assert m.setWithArray([*x, -vec.dot(x, prototype.origin),
                           *y, -vec.dot(y, prototype.origin),
                           *z, -vec.dot(z, prototype.origin), 0., 0., 0., 1.])
    body = manager.copy(prototype.body)
    assert manager.transform(body, m)
    return body


def adapted_copy(manager, normalized, layout, length_mm, grip_cm):
    plan = geo.adaptation_plan(layout, length_mm, grip_cm)
    bb = normalized.boundingBox
    margin = max(bb.maxPoint.x - bb.minPoint.x, bb.maxPoint.y - bb.minPoint.y, 1.0)
    lo = [bb.minPoint.x - margin, bb.minPoint.y - margin, bb.minPoint.z - margin]
    hi = [bb.maxPoint.x + margin, bb.maxPoint.y + margin,
          max(bb.maxPoint.z, plan["new_tip_cm"]) + abs(plan["grip_delta_cm"]) + margin]
    cut, delta = plan["cut_cm"], plan["grip_delta_cm"]
    left, right = manager.copy(normalized), manager.copy(normalized)
    intersection = adsk.fusion.BooleanTypes.IntersectionBooleanType
    union = adsk.fusion.BooleanTypes.UnionBooleanType
    assert manager.booleanOperation(left, _box(manager, lo, [hi[0], hi[1], cut + EPSILON_CM]), intersection)
    assert manager.booleanOperation(right, _box(manager, [lo[0], lo[1], cut - EPSILON_CM], hi), intersection)
    move = adsk.core.Matrix3D.create(); move.translation = adsk.core.Vector3D.create(0, 0, delta)
    assert manager.transform(right, move)
    if delta < 0:
        # Un grand raccourcissement ne doit pas remplir le logement d'une tête CHC.
        assert manager.booleanOperation(right, _box(manager, [lo[0], lo[1], cut - EPSILON_CM], hi), intersection)
    elif delta > EPSILON_CM:
        bridge = manager.createCylinderOrCone(
            adsk.core.Point3D.create(0, 0, cut - EPSILON_CM), layout.nominal_diameter_mm * .05,
            adsk.core.Point3D.create(0, 0, cut + delta + EPSILON_CM), layout.nominal_diameter_mm * .05)
        assert manager.booleanOperation(left, bridge, union)
    assert manager.booleanOperation(left, right, union)
    old_tip, new_tip = plan["old_tip_after_move_cm"], plan["new_tip_cm"]
    if old_tip > new_tip + EPSILON_CM:
        assert manager.booleanOperation(left, _box(manager, lo, [hi[0], hi[1], new_tip]), intersection)
    elif new_tip > old_tip + EPSILON_CM:
        extension = manager.createCylinderOrCone(
            adsk.core.Point3D.create(0, 0, old_tip - EPSILON_CM), layout.nominal_diameter_mm * .05,
            adsk.core.Point3D.create(0, 0, new_tip), layout.nominal_diameter_mm * .05)
        assert manager.booleanOperation(left, extension, union)
    if not left.isSolid or abs(left.boundingBox.maxPoint.z - new_tip) > .002:
        raise RuntimeError("La copie du modèle n'a pas la longueur attendue.")
    return left


def _frame_matrix(placement, parent_inverse=None):
    p = adsk.core.Point3D.create(*placement.origin)
    axes = [adsk.core.Vector3D.create(*v) for v in
            (placement.x_axis, placement.y_axis, placement.z_axis)]
    if parent_inverse:
        assert p.transformBy(parent_inverse)
        for axis in axes:
            assert axis.transformBy(parent_inverse)
    matrix = adsk.core.Matrix3D.create()
    assert matrix.setWithCoordinateSystem(p, *axes)
    return matrix


def create_fasteners(design, prototype, placements, diameter_mm, length_mm, head):
    """Prépare les copies avant d'ajouter un seul lot réversible ; ne sauvegarde pas."""
    geo.validate_parameters(prototype.layout, diameter_mm, length_mm, head)
    occupied = existing_positions(design.rootComponent, prototype)
    poses = [p for p in placements if not any(geo.same_position(p, q) for q in occupied)]
    if not poses:
        return {"created": 0, "occupied": len(placements)}
    manager = adsk.fusion.TemporaryBRepManager.get()
    normalized = _normalized_copy(manager, prototype)
    shapes = {}
    for pose in poses:
        key = round(pose.grip_cm, 6)
        if key not in shapes:
            shapes[key] = adapted_copy(manager, normalized, prototype.layout, length_mm, pose.grip_cm)
    root = design.rootComponent
    candidates = [o for o in root.occurrences if o.component.name.upper() == "VISSERIE"]
    if len(candidates) > 1:
        raise ValueError("Plusieurs groupes VISSERIE existent ; choisir d'abord un groupe unique.")
    timeline = design.timeline if design.designType == adsk.fusion.DesignTypes.ParametricDesignType else None
    start = timeline_groups.creation_start(timeline)
    vis = candidates[0] if candidates else root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    created_vis = not candidates
    if created_vis: vis.component.name = "VISSERIE"
    job = None
    try:
        job = vis.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        job.component.name = "POSE JHR - {} M{:g}x{:g}".format(head, diameter_mm, length_mm)
        canonical = {}
        inv = vis.transform2.copy(); assert inv.invert()
        for pose in poses:
            matrix = _frame_matrix(pose, inv)
            key = round(pose.grip_cm, 6)
            if key in canonical:
                assert job.component.occurrences.addExistingComponent(canonical[key], matrix)
                continue
            occurrence = job.component.occurrences.addNewComponent(matrix)
            component = occurrence.component
            component.name = geo.configuration_name(diameter_mm, length_mm, head, pose.grip_cm)
            component.description = "1 vis + 1 écrou hexagonal + 2 rondelles ; modèle existant réutilisé"
            if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
                feature = component.features.baseFeatures.add(); feature.name = "ENSEMBLE BOULONNERIE JHR"
                assert feature.startEdit()
                try:
                    body = component.bRepBodies.add(shapes[key], feature); assert body
                finally:
                    assert feature.finishEdit()
            else:
                body = component.bRepBodies.add(shapes[key]); assert body
            body.name = component.name
            body.appearance = prototype.body.appearance
            body.material = prototype.body.material
            component.attributes.add(ATTRIBUTE_GROUP, "configuration", json.dumps({
                "diameter_mm": diameter_mm, "length_mm": length_mm, "head": head,
                "grip_cm": pose.grip_cm, "screws": 1, "nuts": 1, "washers": 2}))
            canonical[key] = component
        if job.component.occurrences.count != len(poses):
            raise RuntimeError("Le nombre d'ensembles créés ne correspond pas aux perçages.")
    except Exception as error:
        clean = job is None or job.deleteMe()
        if created_vis and clean: clean = bool(vis.deleteMe())
        if not clean:
            raise RuntimeError("Insertion interrompue ; le nouveau lot JHR n'a pas pu être retiré : {}"
                               .format(error)) from error
        raise
    timeline_groups.group_creation(timeline, start, job.component.name)
    return {"created": len(poses), "occupied": len(placements) - len(poses)}
