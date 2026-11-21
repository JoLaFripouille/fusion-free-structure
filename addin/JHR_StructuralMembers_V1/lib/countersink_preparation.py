"""Fraisure native concentrique à un perçage existant."""
from __future__ import annotations

from dataclasses import dataclass

from . import bolt_specs, fastener_geometry as geometry, joint_geometry as vec


# Enveloppe 90° ISO 10642 (Fabory) et M24 90° Aspen Fasteners ME672-2430X90.
_OPENING_MM = {12: 26.88, 16: 33.6, 20: 40.32, 24: 39.}
_TOLERANCE = geometry.POSITION_TOLERANCE_CM


@dataclass(frozen=True)
class Preparation:
    hole: geometry.CountersunkHole
    head_face: object
    opening_edge: object
    wall_depth_cm: float
    backing_face: object | None


def _dimensions(diameter_mm, bore_cm, wall_depth_cm):
    spec, _ = bolt_specs.modeled_spec(diameter_mm, "TF")
    opening_cm = _OPENING_MM[spec.nominal_diameter_mm] * .1
    depth_cm = (opening_cm - bore_cm) / 2
    if depth_cm <= _TOLERANCE:
        raise ValueError("Le perçage est trop large pour la tête fraisée choisie.")
    if wall_depth_cm <= depth_cm + _TOLERANCE:
        raise ValueError("La paroi est trop mince pour cette fraisure à 90°.")
    return opening_cm, depth_cm


def _same_face(first, second):
    return first == second or (first.tempId == second.tempId and first.body == second.body)


def _rings(wall, hole):
    import adsk.core as core
    from .fastener_creator import point

    for edge in wall.edges:
        circle = core.Circle3D.cast(edge.geometry)
        if not circle or abs(2 * circle.radius - hole.diameter_cm) > _TOLERANCE:
            continue
        center = point(circle.center)
        if vec.length(vec.cross(vec.subtract(center, hole.center), hole.axis)) <= _TOLERANCE:
            yield edge, center


def _flat_neighbors(edge, axis):
    import adsk.core as core
    from .fastener_creator import point

    for face in edge.faces:
        plane = core.Plane.cast(face.geometry)
        if plane and abs(vec.dot(vec.normalize(point(plane.normal)), axis)) >= 1 - geometry.PARALLEL_TOLERANCE:
            yield face


def _faces_outward(face, axis):
    from .fastener_creator import point

    ok, normal = face.evaluator.getNormalAtPoint(face.pointOnFace)
    return ok and vec.dot(point(normal), axis) >= 1 - geometry.PARALLEL_TOLERANCE


def plan(entity, head_face, diameter_mm):
    """Mesure le perçage et le matériau avant d'ajouter une fraisure."""
    import adsk.core as core
    import adsk.fusion as fusion
    from . import fastener_creator as creator

    edge = fusion.BRepEdge.cast(entity)
    face = fusion.BRepFace.cast(entity)
    if not (edge and core.Circle3D.cast(edge.geometry) or face and core.Cylinder.cast(face.geometry)):
        raise ValueError("Sélectionner le bord rond du perçage ou sa paroi cylindrique intérieure.")
    if head_face is not None and not fusion.BRepFace.cast(head_face):
        raise ValueError("La face d’appui sous tête doit être plane.")
    hole = creator.read_hole(entity)
    if not isinstance(hole, geometry.Hole):
        raise ValueError("La préparation automatique exige un perçage rond complet.")
    walls = [face] if face else [neighbor for neighbor in edge.faces if core.Cylinder.cast(neighbor.geometry)]
    if len(walls) != 1:
        raise ValueError("La paroi cylindrique du perçage doit être identifiable sans ambiguïté.")
    rings = list(_rings(walls[0], hole))
    if len(rings) != 2:
        raise ValueError("Sélectionner un perçage cylindrique limité par deux bords circulaires complets.")

    seats = []
    for rim, center in rings:
        for seat in _flat_neighbors(rim, hole.axis):
            selected = _same_face(seat, head_face) if head_face is not None else edge == rim
            if selected:
                seats.append((seat, rim, center))
    if len(seats) != 1:
        raise ValueError("Choisir le bord rond côté tête ou la face plane où débouche ce perçage.")
    seat, opening_edge, center = seats[0]
    back_edge, back_center = next((rim, center) for rim, center in rings if rim != opening_edge)
    inward = vec.subtract(back_center, center)
    wall_depth_cm = vec.length(inward)
    if wall_depth_cm <= _TOLERANCE:
        raise ValueError("Le perçage ne présente pas de profondeur mesurable.")
    axis = vec.scale(inward, 1 / wall_depth_cm)
    if not _faces_outward(seat, vec.scale(axis, -1)):
        raise ValueError("Sélectionner la face extérieure du côté tête.")
    opening_cm, depth_cm = _dimensions(diameter_mm, hole.diameter_cm, wall_depth_cm)
    exits = [face for face in _flat_neighbors(back_edge, axis) if _faces_outward(face, axis)]
    backing_face = exits[0] if len(exits) == 1 else None
    return Preparation(geometry.CountersunkHole(center, axis, hole.diameter_cm, opening_cm, depth_cm),
                       seat, opening_edge, wall_depth_cm, backing_face)


def bore_face(preparation, countersink_face):
    """Retrouve la paroi d'origine au fond de la fraisure mesurée."""
    import adsk.core as core
    from . import fastener_creator as creator

    hole = preparation.hole
    throat = vec.add(hole.center, vec.scale(hole.axis, hole.depth_cm))
    for edge in countersink_face.edges:
        circle = core.Circle3D.cast(edge.geometry)
        if not circle or vec.length(vec.subtract(creator.point(circle.center), throat)) > _TOLERANCE:
            continue
        for face in edge.faces:
            if not core.Cylinder.cast(face.geometry):
                continue
            ends = [vec.dot(vec.subtract(center, hole.center), hole.axis) for _, center in _rings(face, hole)]
            if (len(ends) == 2 and abs(min(ends) - hole.depth_cm) <= _TOLERANCE
                    and abs(max(ends) - preparation.wall_depth_cm) <= _TOLERANCE):
                return face
    raise RuntimeError("La partie cylindrique du perçage a changé pendant la fraisure.")


def apply(design, preparation):
    """Ajoute le perçage et renvoie sa face conique résolue dans le contexte initial."""
    import adsk.core as core
    import adsk.fusion as fusion
    from . import fastener_creator as creator

    hole = preparation.hole
    seat = preparation.head_face
    occurrence = seat.assemblyContext
    native_seat = seat.nativeObject or seat
    native_edge = preparation.opening_edge.nativeObject or preparation.opening_edge
    body = native_seat.body
    holes = body.parentComponent.features.holeFeatures
    value = core.ValueInput.createByReal
    angle = core.ValueInput.createByString
    entry = holes.createCountersinkInput(value(hole.diameter_cm), value(hole.opening_diameter_cm), angle("90 deg"))
    # La partie droite est déjà percée. Une courte portée cylindrique suffit
    # pour définir la fonction sans atteindre le fond du perçage d'origine.
    cut_depth = min(hole.depth_cm + .05, (hole.depth_cm + preparation.wall_depth_cm) / 2)
    if (not entry or not entry.setPositionAtCenter(native_seat, native_edge)
            or not entry.setDistanceExtent(value(cut_depth))):
        raise RuntimeError("Fusion a refusé la fraisure concentrique au perçage.")
    entry.tipAngle = angle("180 deg")
    entry.participantBodies = [body]
    feature = holes.add(entry)
    if not feature:
        raise RuntimeError("Fusion n’a pas créé la fraisure.")
    try:
        if feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
            raise RuntimeError(f"La fraisure est en erreur : {feature.errorOrWarningMessage}")
        feature.name = f"JHR - Fraisure 90° Ø{hole.opening_diameter_cm * 10:g}"
        stock = body.createForAssemblyContext(occurrence) if occurrence else body
        for face in stock.faces:
            if not core.Cone.cast(face.geometry):
                continue
            try:
                measured = creator.read_countersink(face)
            except ValueError:
                continue
            if (vec.length(vec.subtract(measured.center, hole.center)) <= _TOLERANCE
                    and vec.dot(measured.axis, hole.axis) >= 1 - geometry.PARALLEL_TOLERANCE
                    and abs(measured.opening_diameter_cm - hole.opening_diameter_cm) <= _TOLERANCE
                    and abs(measured.diameter_cm - hole.diameter_cm) <= _TOLERANCE
                    and abs(measured.depth_cm - hole.depth_cm) <= _TOLERANCE):
                bore_face(preparation, face)
                return face, (feature,)
        raise RuntimeError("La fraisure à 90° n’a pas pu être mesurée sur toute sa circonférence.")
    except Exception:
        feature.deleteMe()
        raise
