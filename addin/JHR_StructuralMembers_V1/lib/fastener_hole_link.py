"""Liaison d’une fixation JHR à l’ouverture circulaire de son perçage."""

import adsk.core
import adsk.fusion

from . import fastener_creator as creator, fastener_geometry as geometry, joint_geometry as vec


TOLERANCE = geometry.POSITION_TOLERANCE_CM


def _aligned(first, second):
    return abs(vec.dot(vec.normalize(first), vec.normalize(second))) >= 1. - geometry.PARALLEL_TOLERANCE


def _near(first, second):
    return vec.length(vec.subtract(first, second)) <= TOLERANCE


def _on_axis(point, origin, axis):
    return vec.length(vec.cross(vec.subtract(point, origin), vec.normalize(axis))) <= TOLERANCE


def _circle(edge):
    return adsk.core.Circle3D.cast(edge.geometry)


def _add_distinct(candidates, edge):
    if not any(edge == candidate for candidate in candidates):
        candidates.append(edge)


def _as_brep(entity):
    return adsk.fusion.BRepEdge.cast(entity), adsk.fusion.BRepFace.cast(entity)


def _round_bore_openings(entity):
    edge, face = _as_brep(entity)
    candidates = tuple(edge.faces) if edge else (face,) if face else ()
    for candidate in candidates:
        if adsk.core.Cylinder.cast(candidate.geometry):
            yield from candidate.edges


def source_for_pose(selected_entities, placement, head_kind):
    """Retrouve l’ouverture circulaire sélectionnée au niveau d’appui de la tête."""
    candidates = []
    slot_selected = False
    for entity in selected_entities:
        try:
            hole = creator.read_countersink(entity) if head_kind == "TF" else creator.read_hole(entity)
        except ValueError:
            continue
        if not _aligned(hole.axis, placement.z_axis):
            continue
        if isinstance(hole, geometry.Slot):
            slot_selected = True
            continue
        if not _on_axis(hole.center, placement.origin, placement.z_axis):
            continue
        if head_kind == "TF":
            edges = adsk.fusion.BRepFace.cast(entity).edges
            diameter = hole.opening_diameter_cm
        else:
            edges = _round_bore_openings(entity)
            diameter = hole.diameter_cm
        for edge in edges:
            ring = _circle(edge)
            if (ring and abs(ring.radius * 2 - diameter) <= TOLERANCE
                    and _near(creator.point(ring.center), placement.origin)
                    and _aligned(creator.point(ring.normal), placement.z_axis)):
                _add_distinct(candidates, edge)
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise ValueError("Plusieurs ouvertures circulaires coïncident avec l’appui de la tête.")
    if slot_selected:
        raise ValueError("La liaison d’une fixation à un trou oblong n’est pas disponible.")
    raise ValueError("Sélectionner le trou rond ou la fraisure qui débouche sur la face d’appui de la tête.")


def _fastener_geometry(fastener_occurrence, placement):
    joint_geometry = adsk.fusion.JointGeometry
    key = adsk.fusion.JointKeyPointTypes.CenterKeyPoint
    rings = []
    for body in fastener_occurrence.bRepBodies:
        for edge in body.edges:
            circle = _circle(edge)
            if (circle and _near(creator.point(circle.center), placement.origin)
                    and _aligned(creator.point(circle.normal), placement.z_axis)):
                rings.append((circle.radius, edge))
    if rings:
        return joint_geometry.createByCurve(max(rings, key=lambda ring: ring[0])[1], key)
    origin = fastener_occurrence.component.originConstructionPoint
    return joint_geometry.createByPoint(origin.createForAssemblyContext(fastener_occurrence))


def _validate_geometry(joint_geometry, placement):
    return (joint_geometry
            and _near(creator.point(joint_geometry.origin), placement.origin)
            and _aligned(creator.point(joint_geometry.primaryAxisVector), placement.z_axis))


def _verify_pose(occurrence, placement, source):
    origin, _, _, axis = occurrence.transform2.getAsCoordinateSystem()
    if (not _near(creator.point(origin), placement.origin)
            or vec.dot(vec.normalize(creator.point(axis)), vec.normalize(placement.z_axis))
            < 1. - geometry.PARALLEL_TOLERANCE):
        raise RuntimeError("La liaison a déplacé ou retourné la fixation.")
    ring = _circle(source) if source.isValid else None
    if (not ring or not _near(creator.point(ring.center), placement.origin)
            or not _aligned(creator.point(ring.normal), placement.z_axis)):
        raise RuntimeError("La liaison a déplacé la pièce percée.")


def bind(design, fastener_occurrence, placement, selected_entity):
    """Crée un joint rigide dont la référence reste l’arête du perçage."""
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise ValueError("Enregistrer l’historique de conception pour lier une fixation à son trou.")
    if design.snapshots.hasPendingSnapshot:
        raise ValueError("Capturer ou rétablir la position en cours avant de lier la fixation.")
    head_kind = "TF" if placement.countersink else "H"
    edge = adsk.fusion.BRepEdge.cast(selected_entity)
    if not edge or not _circle(edge):
        edge = source_for_pose((selected_entity,), placement, head_kind)
    source = adsk.fusion.JointGeometry.createByCurve(edge, adsk.fusion.JointKeyPointTypes.CenterKeyPoint)
    local = _fastener_geometry(fastener_occurrence, placement)
    if not _validate_geometry(source, placement) or not _validate_geometry(local, placement):
        raise ValueError("Fusion ne reconnaît pas les repères du trou et de la fixation sur le plan d’appui.")

    joints = design.rootComponent.joints
    grounded = fastener_occurrence.isGroundToParent
    joint = None
    try:
        if grounded:
            fastener_occurrence.isGroundToParent = False
        joint_input = joints.createInput(local, source)
        if not joint_input or not joint_input.setAsRigidJointMotion():
            raise RuntimeError("Fusion a refusé le joint rigide de la fixation.")
        # Le joint Fusion place les normales face à face par défaut.
        joint_input.isFlipped = vec.dot(creator.point(local.primaryAxisVector),
                                        creator.point(source.primaryAxisVector)) > 0.
        joint = joints.add(joint_input)
        if not joint or joint.healthState != adsk.fusion.FeatureHealthStates.HealthyFeatureHealthState:
            raise RuntimeError("Fusion a refusé la liaison de la fixation au trou.")
        _verify_pose(fastener_occurrence, placement, edge)
        joint.name = "JHR · Fixation liée au trou"
        return joint
    except Exception:
        if joint and joint.isValid and not joint.deleteMe():
            raise RuntimeError("Fusion n’a pas pu retirer le joint de fixation interrompu.")
        if design.snapshots.hasPendingSnapshot:
            design.snapshots.revertPendingSnapshot()
        if grounded and fastener_occurrence.isValid:
            fastener_occurrence.isGroundToParent = True
        raise
