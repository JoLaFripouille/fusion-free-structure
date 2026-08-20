from __future__ import annotations

import math
from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import addin_info, joint_geometry, joint_records, member_metadata


JOINT_ATTRIBUTE_GROUP = joint_records.ATTRIBUTE_GROUP
STRAIGHT_JOINT_TYPE = "axis_envelope_trim"
MITER_JOINT_TYPE = "miter_trim"
PRIMARY_STATION_PLANE_NAME = "PLAN_JONCTION_STATION_REFERENCE"
SECONDARY_STATION_PLANE_NAME = "PLAN_JONCTION_STATION_AJUSTER"
JOINT_AXIS_NAME = "AXE_INTERSECTION_JONCTION"
ORIENTATION_PLANE_NAME = "PLAN_ORIENTATION_JONCTION"
REFERENCE_PLANE_NAME = "PLAN_JONCTION_ENVELOPPE"
CUT_PLANE_NAME = "PLAN_JONCTION_FINAL"
SUPPORT_POINT_NAME = "POINT_ENVELOPPE_JONCTION"
EXTEND_FEATURE_NAME = "PROLONGEMENT_VERS_JONCTION"
SPLIT_FEATURE_NAME = "COUPE_JONCTION"
REMOVE_FEATURE_NAME = "RETRAIT_EXCEDENT_JONCTION"
MITER_FIRST_PATH_PLANE_NAME = "PLAN_ONGLET_AXE_1"
MITER_SECOND_PATH_PLANE_NAME = "PLAN_ONGLET_AXE_2"
MITER_AXIS_NAME = "AXE_INTERSECTION_ONGLET"
MITER_PLANE_NAME = "PLAN_COUPE_ONGLET"
MITER_SPLIT_FEATURE_NAME = "COUPE_ONGLET"
MITER_REMOVE_FEATURE_NAME = "RETRAIT_EXCEDENT_ONGLET"
FACE_ALIGNMENT_TOLERANCE = 0.995
EDGE_STROKE_TOLERANCE_CM = 1e-5


@dataclass(frozen=True)
class EndTreatment:
    occurrence: object
    body: object
    curve: object
    endpoint_index: int
    joint_endpoint: tuple
    inner_point: tuple
    approach_direction: tuple
    relation: str
    interior_sign: float
    extension_face: object
    extension_cm: float

    @property
    def requires_split(self):
        return self.relation in ("overlap", "gap")


@dataclass(frozen=True)
class JointEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: member_metadata.MemberMetadata
    secondary_metadata: member_metadata.MemberMetadata
    primary_body: object
    secondary_body: object
    primary_curve: object
    secondary_curve: object
    support_edge: object
    support_fraction: float
    geometry: joint_geometry.StraightJointGeometry
    support_point: tuple
    cut_point: tuple
    cut_normal: tuple
    gap_cm: float
    treatment: EndTreatment
    preview_half_size_cm: float

    @property
    def preview_normal(self):
        return self.cut_normal


@dataclass(frozen=True)
class MiterEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: member_metadata.MemberMetadata
    secondary_metadata: member_metadata.MemberMetadata
    primary_body: object
    secondary_body: object
    primary_curve: object
    secondary_curve: object
    geometry: joint_geometry.MiterJointGeometry
    first_treatment: EndTreatment
    second_treatment: EndTreatment
    cut_point: tuple
    cut_normal: tuple
    preview_half_size_cm: float

    @property
    def preview_normal(self):
        return self.cut_normal


def _point_tuple(point):
    return (float(point.x), float(point.y), float(point.z))


def _vector_tuple(vector):
    return (float(vector.x), float(vector.y), float(vector.z))


def _attribute_values(component):
    values = {}
    for key in member_metadata.ATTRIBUTE_KEYS:
        attribute = component.attributes.itemByName(member_metadata.ATTRIBUTE_GROUP, key)
        if attribute:
            values[key] = attribute.value
    return values


def _member_metadata(occurrence, role):
    if not occurrence or not occurrence.isValid:
        raise ValueError("La barre {} n'est pas un composant valide.".format(role))
    try:
        return member_metadata.parse_member_attributes(
            _attribute_values(occurrence.component)
        )
    except ValueError as error:
        raise ValueError(
            "La barre {} n'a pas été créée par Profil acier ou ses informations sont incomplètes : {}"
            .format(role, error)
        ) from error


def _linked_curve(design, metadata, role, allow_arc):
    accepted_types = ("line", "arc") if allow_arc else ("line",)
    if metadata.source_curve_type not in accepted_types:
        raise ValueError(
            "La barre {} doit être créée sur {}."
            .format(role, "une ligne ou un arc" if allow_arc else "une ligne droite")
        )
    entities = design.findEntityByToken(metadata.source_curve_token)
    for entity in entities:
        curve = adsk.fusion.SketchLine.cast(entity)
        if allow_arc and not curve:
            curve = adsk.fusion.SketchArc.cast(entity)
        if curve and curve.isValid:
            return curve.nativeObject if curve.nativeObject else curve
    raise ValueError(
        "Le chemin de squelette lié à la barre {} est introuvable.".format(role)
    )


def _single_body(occurrence, role):
    bodies = occurrence.component.bRepBodies
    if bodies.count != 1:
        raise ValueError(
            "La barre {} doit contenir exactement un corps pour recevoir une jonction."
            .format(role)
        )
    body = bodies.item(0)
    if not body or not body.isValid:
        raise ValueError("Le corps de la barre {} n'est pas valide.".format(role))
    return body


def _body_proxy(body, occurrence):
    return body.createForAssemblyContext(occurrence) or body


def _curve_stroke_points(curve):
    evaluator = curve.evaluator
    success, minimum, maximum = evaluator.getParameterExtents()
    if not success:
        return ()
    success, points = evaluator.getStrokes(
        minimum,
        maximum,
        EDGE_STROKE_TOLERANCE_CM,
    )
    if not success:
        return ()
    return tuple(_point_tuple(point) for point in points)


def _edge_points(edge):
    points = list(_curve_stroke_points(edge.geometry))
    if not points:
        for index in range(edge.vertices.count):
            points.append(_point_tuple(edge.vertices.item(index).geometry))
    return tuple(points)


def _face_points(face):
    points = []
    for index in range(face.edges.count):
        points.extend(_edge_points(face.edges.item(index)))
    if face.pointOnFace:
        points.append(_point_tuple(face.pointOnFace))
    return tuple(points)


def _body_sample_points(body, occurrence):
    proxy = _body_proxy(body, occurrence)
    points = []
    for index in range(proxy.edges.count):
        points.extend(_edge_points(proxy.edges.item(index)))
    for index in range(proxy.faces.count):
        face = proxy.faces.item(index)
        if face.pointOnFace:
            points.append(_point_tuple(face.pointOnFace))
    if not points:
        for index in range(proxy.vertices.count):
            points.append(_point_tuple(proxy.vertices.item(index).geometry))
    return tuple(points)


def _body_support_reference(body, occurrence, direction):
    proxy = _body_proxy(body, occurrence)
    best = None
    for index in range(proxy.edges.count):
        edge = proxy.edges.item(index)
        evaluator = edge.geometry.evaluator
        success, minimum, maximum = evaluator.getParameterExtents()
        if not success or abs(maximum - minimum) <= joint_geometry.GEOMETRY_TOLERANCE_CM:
            continue
        points = _curve_stroke_points(edge.geometry)
        for point_tuple in points:
            projection = joint_geometry.dot(point_tuple, direction)
            if best is not None and projection <= best[0]:
                continue
            point = adsk.core.Point3D.create(*point_tuple)
            parameter_ok, parameter = evaluator.getParameterAtPoint(point)
            if not parameter_ok:
                continue
            fraction = (parameter - minimum) / (maximum - minimum)
            best = (projection, point_tuple, edge, min(1.0, max(0.0, fraction)))
    if best is None:
        raise ValueError("L'enveloppe de la barre de référence est introuvable.")
    _, point, edge, fraction = best
    return point, edge, fraction


def _line_endpoints(line):
    geometry = line.worldGeometry
    return _point_tuple(geometry.startPoint), _point_tuple(geometry.endPoint)


def _curve_end_data(curve):
    line = adsk.fusion.SketchLine.cast(curve)
    if line:
        start, end = _line_endpoints(line)
        direction = joint_geometry.normalize(joint_geometry.subtract(end, start))
        return (start, end), (
            joint_geometry.scale(direction, -1.0),
            direction,
        )

    arc = adsk.fusion.SketchArc.cast(curve)
    if not arc:
        raise ValueError("Le chemin à ajuster n'est ni une ligne ni un arc pris en charge.")
    evaluator = arc.worldGeometry.evaluator
    success, minimum, maximum = evaluator.getParameterExtents()
    if not success:
        raise RuntimeError("Fusion n'a pas pu lire les paramètres de l'arc.")
    success, start_point, end_point = evaluator.getEndPoints()
    if not success:
        raise RuntimeError("Fusion n'a pas pu lire les extrémités de l'arc.")
    success_start, start_tangent = evaluator.getTangent(minimum)
    success_end, end_tangent = evaluator.getTangent(maximum)
    if not success_start or not success_end:
        raise RuntimeError("Fusion n'a pas pu lire les tangentes de l'arc.")
    return (
        (_point_tuple(start_point), _point_tuple(end_point)),
        (
            joint_geometry.scale(
                joint_geometry.normalize(_vector_tuple(start_tangent)),
                -1.0,
            ),
            joint_geometry.normalize(_vector_tuple(end_tangent)),
        ),
    )


def _analyze_adjusted_curve(reference_line, adjusted_curve):
    reference_start, reference_end = _line_endpoints(reference_line)
    adjusted_endpoints, approaches = _curve_end_data(adjusted_curve)
    candidates = []
    for index, endpoint in enumerate(adjusted_endpoints):
        main_point, parameter = joint_geometry.closest_point_on_segment(
            endpoint,
            reference_start,
            reference_end,
        )
        candidates.append(
            (
                joint_geometry.length(joint_geometry.subtract(endpoint, main_point)),
                index,
                main_point,
                parameter,
            )
        )
    distance_cm, endpoint_index, main_point, main_parameter = min(candidates)
    if distance_cm > joint_geometry.JOINT_ENDPOINT_TOLERANCE_CM:
        raise ValueError(
            "Une extrémité de la barre à ajuster doit rejoindre l'axe de la barre de référence."
        )
    main_direction = joint_geometry.normalize(
        joint_geometry.subtract(reference_end, reference_start)
    )
    return joint_geometry.endpoint_joint_geometry(
        main_point,
        main_parameter,
        adjusted_endpoints[endpoint_index],
        adjusted_endpoints[1 - endpoint_index],
        endpoint_index,
        approaches[endpoint_index],
        main_direction,
        distance_cm,
    )


def _planar_end_face(body, occurrence, approach_direction, joint_endpoint):
    proxy = _body_proxy(body, occurrence)
    approach = joint_geometry.normalize(approach_direction)
    candidates = []
    for index in range(proxy.faces.count):
        face = proxy.faces.item(index)
        if not adsk.core.Plane.cast(face.geometry):
            continue
        point = face.pointOnFace
        success, normal = face.evaluator.getNormalAtPoint(point)
        if not success:
            continue
        normal_tuple = joint_geometry.normalize(_vector_tuple(normal))
        alignment = joint_geometry.dot(normal_tuple, approach)
        if alignment < FACE_ALIGNMENT_TOLERANCE:
            continue
        station_error = abs(
            joint_geometry.dot(
                joint_geometry.subtract(_point_tuple(point), joint_endpoint),
                approach,
            )
        )
        candidates.append((station_error, -alignment, face))
    if not candidates:
        raise ValueError(
            "La face d'extrémité à prolonger est introuvable. "
            "La barre peut néanmoins recevoir une coupe si elle traverse déjà le plan."
        )
    _, _, proxy_face = min(candidates, key=lambda item: (item[0], item[1]))
    native_face = proxy_face.nativeObject if proxy_face.nativeObject else proxy_face
    return native_face, _face_points(proxy_face)


def _evaluate_treatment(
    occurrence,
    body,
    curve,
    endpoint_index,
    joint_endpoint,
    inner_point,
    approach_direction,
    cut_point,
    cut_normal,
):
    body_points = _body_sample_points(body, occurrence)
    relation, interior_sign, _, _ = joint_geometry.body_plane_relation(
        body_points,
        cut_point,
        cut_normal,
        inner_point,
    )
    if relation == "outside":
        raise ValueError(
            "Le corps se trouve entièrement du mauvais côté du plan de jonction. "
            "Vérifier l'extrémité et l'orientation du chemin."
        )
    extension_face = None
    extension_cm = 0.0
    if relation in ("overlap", "gap"):
        extension_face, face_points = _planar_end_face(
            body,
            occurrence,
            approach_direction,
            joint_endpoint,
        )
        extension_cm = joint_geometry.extension_distance_to_plane(
            face_points,
            approach_direction,
            cut_point,
            cut_normal,
            interior_sign,
        )
        if extension_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
            extension_face = None
    return EndTreatment(
        occurrence=occurrence,
        body=body,
        curve=curve,
        endpoint_index=endpoint_index,
        joint_endpoint=joint_endpoint,
        inner_point=inner_point,
        approach_direction=approach_direction,
        relation=relation,
        interior_sign=interior_sign,
        extension_face=extension_face,
        extension_cm=extension_cm,
    )


def evaluate_straight_joint(design, primary_occurrence, secondary_occurrence, gap_cm):
    if primary_occurrence == secondary_occurrence:
        raise ValueError("Les deux barres sélectionnées doivent être différentes.")
    if gap_cm < 0.0:
        raise ValueError("Le jeu de jonction ne peut pas être négatif.")

    primary_metadata = _member_metadata(primary_occurrence, "de référence")
    secondary_metadata = _member_metadata(secondary_occurrence, "à ajuster")
    primary_curve = _linked_curve(
        design,
        primary_metadata,
        "de référence",
        allow_arc=False,
    )
    secondary_curve = _linked_curve(
        design,
        secondary_metadata,
        "à ajuster",
        allow_arc=True,
    )
    geometry = _analyze_adjusted_curve(primary_curve, secondary_curve)

    primary_body = _single_body(primary_occurrence, "de référence")
    secondary_body = _single_body(secondary_occurrence, "à ajuster")
    support_point, support_edge, support_fraction = _body_support_reference(
        primary_body,
        primary_occurrence,
        geometry.plane_normal,
    )
    cut_point = joint_geometry.cut_point_from_support(
        support_point,
        geometry.plane_normal,
        gap_cm,
    )
    treatment = _evaluate_treatment(
        secondary_occurrence,
        secondary_body,
        secondary_curve,
        geometry.secondary_joint_endpoint_index,
        geometry.secondary_joint_endpoint,
        geometry.secondary_inner_endpoint,
        geometry.approach_direction,
        cut_point,
        geometry.plane_normal,
    )
    return JointEvaluation(
        primary_occurrence=primary_occurrence,
        secondary_occurrence=secondary_occurrence,
        primary_metadata=primary_metadata,
        secondary_metadata=secondary_metadata,
        primary_body=primary_body,
        secondary_body=secondary_body,
        primary_curve=primary_curve,
        secondary_curve=secondary_curve,
        support_edge=support_edge,
        support_fraction=support_fraction,
        geometry=geometry,
        support_point=support_point,
        cut_point=cut_point,
        cut_normal=geometry.plane_normal,
        gap_cm=float(gap_cm),
        treatment=treatment,
        preview_half_size_cm=50.0,
    )


def evaluate_miter_joint(design, primary_occurrence, secondary_occurrence):
    if primary_occurrence == secondary_occurrence:
        raise ValueError("Les deux barres de l'onglet doivent être différentes.")
    primary_metadata = _member_metadata(primary_occurrence, "1")
    secondary_metadata = _member_metadata(secondary_occurrence, "2")
    primary_curve = _linked_curve(design, primary_metadata, "1", allow_arc=False)
    secondary_curve = _linked_curve(design, secondary_metadata, "2", allow_arc=False)
    primary_start, primary_end = _line_endpoints(primary_curve)
    secondary_start, secondary_end = _line_endpoints(secondary_curve)
    geometry = joint_geometry.analyze_miter_joint(
        primary_start,
        primary_end,
        secondary_start,
        secondary_end,
    )
    primary_body = _single_body(primary_occurrence, "1")
    secondary_body = _single_body(secondary_occurrence, "2")
    first_treatment = _evaluate_treatment(
        primary_occurrence,
        primary_body,
        primary_curve,
        geometry.primary_joint_endpoint_index,
        geometry.primary_joint_endpoint,
        geometry.primary_inner_endpoint,
        geometry.primary_approach_direction,
        geometry.joint_point,
        geometry.plane_normal,
    )
    second_treatment = _evaluate_treatment(
        secondary_occurrence,
        secondary_body,
        secondary_curve,
        geometry.secondary_joint_endpoint_index,
        geometry.secondary_joint_endpoint,
        geometry.secondary_inner_endpoint,
        geometry.secondary_approach_direction,
        geometry.joint_point,
        geometry.plane_normal,
    )
    return MiterEvaluation(
        primary_occurrence=primary_occurrence,
        secondary_occurrence=secondary_occurrence,
        primary_metadata=primary_metadata,
        secondary_metadata=secondary_metadata,
        primary_body=primary_body,
        secondary_body=secondary_body,
        primary_curve=primary_curve,
        secondary_curve=secondary_curve,
        geometry=geometry,
        first_treatment=first_treatment,
        second_treatment=second_treatment,
        cut_point=geometry.joint_point,
        cut_normal=geometry.plane_normal,
        preview_half_size_cm=50.0,
    )


def _world_plane_system(plane, occurrence):
    proxy = plane.createForAssemblyContext(occurrence) or plane
    origin, _, _, normal = proxy.transform.getAsCoordinateSystem()
    return _point_tuple(origin), _vector_tuple(normal)


def _world_axis_direction(axis, occurrence):
    proxy = axis.createForAssemblyContext(occurrence) or axis
    return _vector_tuple(proxy.geometry.direction)


def _add_path_plane(component, occurrence, curve, fraction, name):
    plane_input = component.constructionPlanes.createInput(occurrence)
    if not plane_input.setByDistanceOnPath(
        curve,
        adsk.core.ValueInput.createByReal(float(fraction)),
    ):
        raise RuntimeError("Fusion n'a pas pu créer un plan normal au chemin.")
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu ajouter un plan normal au chemin.")
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def _add_intersection_axis(component, occurrence, first_plane, second_plane, name):
    axis_input = component.constructionAxes.createInput(occurrence)
    if not axis_input.setByTwoPlanes(first_plane, second_plane):
        raise RuntimeError("Fusion n'a pas pu définir l'axe commun aux deux directions.")
    axis = component.constructionAxes.add(axis_input)
    if not axis:
        raise RuntimeError("Fusion n'a pas pu créer l'axe commun aux deux directions.")
    axis.name = name
    axis.isLightBulbOn = False
    return axis


def _signed_plane_angle(reference_normal, target_normal, axis_direction):
    reference = joint_geometry.normalize(reference_normal)
    axis = joint_geometry.normalize(axis_direction)
    target = joint_geometry.normalize(target_normal)
    candidates = []
    for candidate in (target, joint_geometry.scale(target, -1.0)):
        candidates.append(
            math.atan2(
                joint_geometry.dot(axis, joint_geometry.cross(reference, candidate)),
                joint_geometry.dot(reference, candidate),
            )
        )
    return min(candidates, key=abs)


def _create_angle_plane(component, occurrence, axis, reference_plane, angle, name):
    plane_input = component.constructionPlanes.createInput(occurrence)
    if not plane_input.setByAngle(
        axis,
        adsk.core.ValueInput.createByReal(float(angle)),
        reference_plane,
    ):
        raise RuntimeError("Fusion n'a pas pu définir l'orientation du plan de coupe.")
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu créer le plan de coupe orienté.")
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def _add_oriented_plane(
    component,
    occurrence,
    axis,
    reference_plane,
    target_normal,
    name,
    created_entities,
    target_point=None,
):
    _, reference_normal = _world_plane_system(reference_plane, occurrence)
    axis_direction = _world_axis_direction(axis, occurrence)
    angle = _signed_plane_angle(reference_normal, target_normal, axis_direction)
    plane = _create_angle_plane(
        component,
        occurrence,
        axis,
        reference_plane,
        angle,
        name,
    )
    _, actual_normal = _world_plane_system(plane, occurrence)
    alignment = abs(
        joint_geometry.dot(
            joint_geometry.normalize(actual_normal),
            joint_geometry.normalize(target_normal),
        )
    )
    if alignment < 0.9999:
        plane.deleteMe()
        plane = _create_angle_plane(
            component,
            occurrence,
            axis,
            reference_plane,
            -angle,
            name,
        )
        _, actual_normal = _world_plane_system(plane, occurrence)
        alignment = abs(
            joint_geometry.dot(
                joint_geometry.normalize(actual_normal),
                joint_geometry.normalize(target_normal),
            )
        )
    if alignment < 0.9999:
        plane.deleteMe()
        raise RuntimeError("Fusion a orienté le plan de coupe dans une direction inattendue.")
    if target_point is not None:
        actual_origin, actual_normal = _world_plane_system(plane, occurrence)
        position_error = abs(
            joint_geometry.plane_signed_distance(
                target_point,
                actual_origin,
                actual_normal,
            )
        )
        if position_error > 1e-3:
            plane.deleteMe()
            raise RuntimeError(
                "Le plan Fusion ne passe pas par le même point que la prévisualisation."
            )
    created_entities.append(plane)
    return plane


def _add_offset_through_point(component, occurrence, plane, point_entity, name):
    plane_input = component.constructionPlanes.createInput(occurrence)
    if not plane_input.setByOffsetThroughPoint(plane, point_entity):
        raise RuntimeError("Fusion n'a pas pu positionner le plan sur l'enveloppe réelle.")
    result = component.constructionPlanes.add(plane_input)
    if not result:
        raise RuntimeError("Fusion n'a pas pu créer le plan d'enveloppe.")
    result.name = name
    result.isLightBulbOn = False
    return result


def _add_support_point(evaluation, created_entities):
    component = evaluation.secondary_occurrence.component
    point_input = component.constructionPoints.createInput(
        evaluation.secondary_occurrence
    )
    if not point_input.setByDistanceOnPath(
        evaluation.support_edge,
        adsk.core.ValueInput.createByReal(evaluation.support_fraction),
    ):
        raise RuntimeError("Fusion n'a pas pu lier le point d'enveloppe au profil de référence.")
    point = component.constructionPoints.add(point_input)
    if not point:
        raise RuntimeError("Fusion n'a pas pu créer le point d'enveloppe de la jonction.")
    point.name = SUPPORT_POINT_NAME
    point.isLightBulbOn = False
    created_entities.append(point)
    return point


def _add_offset_to_point(component, occurrence, plane, target_point, name):
    reference_origin, reference_normal = _world_plane_system(plane, occurrence)
    offset = joint_geometry.signed_offset_between_planes(
        reference_origin,
        target_point,
        reference_normal,
    )
    plane_input = component.constructionPlanes.createInput(occurrence)
    if not plane_input.setByOffset(
        plane,
        adsk.core.ValueInput.createByReal(offset),
    ):
        raise RuntimeError("Fusion n'a pas pu appliquer le jeu de jonction.")
    result = component.constructionPlanes.add(plane_input)
    if not result:
        raise RuntimeError("Fusion n'a pas pu créer le plan final de jonction.")
    result.name = name
    result.isLightBulbOn = False
    return result


def _validate_plane_match(plane, occurrence, target_point, target_normal):
    actual_origin, actual_normal = _world_plane_system(plane, occurrence)
    alignment = abs(
        joint_geometry.dot(
            joint_geometry.normalize(actual_normal),
            joint_geometry.normalize(target_normal),
        )
    )
    position_error = abs(
        joint_geometry.plane_signed_distance(
            target_point,
            actual_origin,
            actual_normal,
        )
    )
    if alignment < 0.9999 or position_error > 1e-3:
        raise RuntimeError(
            "Le plan final ne correspond pas exactement au plan affiché en prévisualisation."
        )


def _add_direct_cut_plane(evaluation, created_entities):
    component = evaluation.secondary_occurrence.component
    occurrence = evaluation.secondary_occurrence
    reference_station = _add_path_plane(
        component,
        occurrence,
        evaluation.primary_curve,
        evaluation.geometry.main_parameter,
        PRIMARY_STATION_PLANE_NAME,
    )
    created_entities.append(reference_station)
    adjusted_station = _add_path_plane(
        component,
        occurrence,
        evaluation.secondary_curve,
        evaluation.geometry.secondary_joint_endpoint_index,
        SECONDARY_STATION_PLANE_NAME,
    )
    created_entities.append(adjusted_station)
    axis = _add_intersection_axis(
        component,
        occurrence,
        reference_station,
        adjusted_station,
        JOINT_AXIS_NAME,
    )
    created_entities.append(axis)
    orientation_plane = _add_oriented_plane(
        component,
        occurrence,
        axis,
        reference_station,
        evaluation.cut_normal,
        ORIENTATION_PLANE_NAME,
        created_entities,
    )
    support_point = _add_support_point(evaluation, created_entities)
    envelope_plane = _add_offset_through_point(
        component,
        occurrence,
        orientation_plane,
        support_point,
        REFERENCE_PLANE_NAME,
    )
    created_entities.append(envelope_plane)
    cut_plane = _add_offset_to_point(
        component,
        occurrence,
        envelope_plane,
        evaluation.cut_point,
        CUT_PLANE_NAME,
    )
    created_entities.append(cut_plane)
    _validate_plane_match(
        cut_plane,
        occurrence,
        evaluation.cut_point,
        evaluation.cut_normal,
    )
    return cut_plane


def _add_miter_cut_plane(evaluation, occurrence, created_entities):
    component = occurrence.component
    first_plane = _add_path_plane(
        component,
        occurrence,
        evaluation.primary_curve,
        evaluation.geometry.primary_joint_endpoint_index,
        MITER_FIRST_PATH_PLANE_NAME,
    )
    created_entities.append(first_plane)
    second_plane = _add_path_plane(
        component,
        occurrence,
        evaluation.secondary_curve,
        evaluation.geometry.secondary_joint_endpoint_index,
        MITER_SECOND_PATH_PLANE_NAME,
    )
    created_entities.append(second_plane)
    axis = _add_intersection_axis(
        component,
        occurrence,
        first_plane,
        second_plane,
        MITER_AXIS_NAME,
    )
    created_entities.append(axis)
    return _add_oriented_plane(
        component,
        occurrence,
        axis,
        first_plane,
        evaluation.cut_normal,
        MITER_PLANE_NAME,
        created_entities,
        target_point=evaluation.cut_point,
    )


def _create_extension_feature(treatment, direction):
    body = _single_body(treatment.occurrence, "à prolonger")
    extension_face, _ = _planar_end_face(
        body,
        treatment.occurrence,
        treatment.approach_direction,
        treatment.joint_endpoint,
    )
    component = treatment.occurrence.component
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        extension_face,
        adsk.fusion.FeatureOperations.JoinFeatureOperation,
    )
    if not extrude_input:
        raise RuntimeError("Fusion n'a pas pu préparer le prolongement de la barre.")
    extrude_input.creationOccurrence = treatment.occurrence
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(treatment.extension_cm)
    )
    if not extrude_input.setOneSideExtent(extent, direction):
        raise RuntimeError("Fusion n'a pas pu orienter le prolongement de la barre.")
    feature = extrudes.add(extrude_input)
    if not feature:
        raise RuntimeError("Fusion n'a pas pu créer le prolongement de la barre.")
    return feature


def _remaining_end_extension(treatment, cut_point, cut_normal):
    body = _single_body(treatment.occurrence, "à contrôler après prolongement")
    _, face_points = _planar_end_face(
        body,
        treatment.occurrence,
        treatment.approach_direction,
        treatment.joint_endpoint,
    )
    return joint_geometry.extension_distance_to_plane(
        face_points,
        treatment.approach_direction,
        cut_point,
        cut_normal,
        treatment.interior_sign,
    )


def _extend_body(treatment, cut_point, cut_normal, created_entities):
    if treatment.extension_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        return None
    failures = []
    directions = (
        ("positive", adsk.fusion.ExtentDirections.PositiveExtentDirection),
        ("négative", adsk.fusion.ExtentDirections.NegativeExtentDirection),
    )
    for label, direction in directions:
        feature = None
        accepted = False
        try:
            feature = _create_extension_feature(treatment, direction)
            remaining_cm = _remaining_end_extension(
                treatment,
                cut_point,
                cut_normal,
            )
            if remaining_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
                feature.name = EXTEND_FEATURE_NAME
                created_entities.append(feature)
                accepted = True
                return feature
            failures.append(
                "direction {}: {:.3f} mm encore manquants"
                .format(label, remaining_cm * 10.0)
            )
        except Exception as error:
            failures.append("direction {}: {}".format(label, error))
        finally:
            if feature and feature.isValid and not accepted:
                feature.deleteMe()
    raise RuntimeError(
        "Fusion n'a pas pu prolonger toute la face au-delà du plan de coupe ({})"
        .format(" ; ".join(failures))
    )


def _projection_center(body, occurrence, plane_point, plane_normal, interior_sign):
    points = _body_sample_points(body, occurrence)
    values = [
        interior_sign
        * joint_geometry.plane_signed_distance(point, plane_point, plane_normal)
        for point in points
    ]
    return (min(values) + max(values)) / 2.0


def _validate_body_crosses_plane(treatment, cut_point, cut_normal):
    """Confirme sur le corps courant que le plan final peut réellement le séparer."""
    body = _single_body(treatment.occurrence, "à contrôler")
    relation, interior_sign, minimum, maximum = joint_geometry.body_plane_relation(
        _body_sample_points(body, treatment.occurrence),
        cut_point,
        cut_normal,
        treatment.inner_point,
    )
    if interior_sign != treatment.interior_sign:
        raise RuntimeError(
            "Le côté intérieur de la barre a changé pendant la préparation de la jonction."
        )
    if relation != "overlap":
        raise RuntimeError(
            "Le corps ne traverse pas le plan final après préparation "
            "(état={}, intervalle={:.3f} à {:.3f} mm)."
            .format(relation, minimum * 10.0, maximum * 10.0)
        )


def _split_and_keep_interior(
    treatment,
    cut_plane,
    cut_point,
    cut_normal,
    split_name,
    remove_name,
    created_entities,
):
    if not treatment.requires_split:
        return ()
    component = treatment.occurrence.component
    _validate_body_crosses_plane(treatment, cut_point, cut_normal)
    body = _single_body(treatment.occurrence, "à couper")
    split_features = component.features.splitBodyFeatures
    split_input = split_features.createInput(body, cut_plane, True)
    if not split_input:
        raise RuntimeError("Fusion n'a pas pu préparer la séparation au plan calculé.")
    split_feature = split_features.add(split_input)
    if not split_feature:
        raise RuntimeError(
            "Fusion n'a pas pu séparer la barre. Le prolongement ou le plan ne traverse pas le corps."
        )
    split_feature.name = split_name
    created_entities.append(split_feature)

    bodies = [component.bRepBodies.item(index) for index in range(component.bRepBodies.count)]
    if len(bodies) < 2:
        raise RuntimeError("La séparation n'a produit aucun excédent distinct à retirer.")
    keep_index = max(
        range(len(bodies)),
        key=lambda index: _projection_center(
            bodies[index],
            treatment.occurrence,
            cut_point,
            cut_normal,
            treatment.interior_sign,
        ),
    )
    remove_features = []
    for index, candidate in enumerate(bodies):
        if index == keep_index:
            continue
        remove_feature = component.features.removeFeatures.add(candidate)
        if not remove_feature:
            raise RuntimeError("Fusion n'a pas pu retirer un excédent de la jonction.")
        remove_feature.name = remove_name
        created_entities.append(remove_feature)
        remove_features.append(remove_feature)
    return tuple(remove_features)


def _add_record(occurrence, payload):
    attributes = occurrence.component.attributes
    existing = attributes.itemsByGroup(JOINT_ATTRIBUTE_GROUP)
    name = joint_records.next_record_name(attribute.name for attribute in existing)
    attribute = attributes.add(
        JOINT_ATTRIBUTE_GROUP,
        name,
        joint_records.encode_record(payload),
    )
    if not attribute:
        raise RuntimeError("Fusion n'a pas pu enregistrer la traçabilité de la jonction.")
    return attribute


def _direct_record(evaluation):
    return {
        "joint_type": STRAIGHT_JOINT_TYPE,
        "endpoint_index": evaluation.geometry.secondary_joint_endpoint_index,
        "reference_component": evaluation.primary_occurrence.component.name,
        "reference_occurrence_token": evaluation.primary_occurrence.entityToken,
        "reference_source_curve_token": evaluation.primary_metadata.source_curve_token,
        "adjusted_source_curve_token": evaluation.secondary_metadata.source_curve_token,
        "angle_deg": evaluation.geometry.angle_degrees,
        "gap_mm": evaluation.gap_cm * 10.0,
        "initial_relation": evaluation.treatment.relation,
        "extension_mm": evaluation.treatment.extension_cm * 10.0,
        "extension_version": addin_info.VERSION,
    }


def _miter_record(evaluation, treatment, peer_occurrence, peer_metadata):
    return {
        "joint_type": MITER_JOINT_TYPE,
        "endpoint_index": treatment.endpoint_index,
        "peer_component": peer_occurrence.component.name,
        "peer_occurrence_token": peer_occurrence.entityToken,
        "peer_source_curve_token": peer_metadata.source_curve_token,
        "angle_deg": evaluation.geometry.angle_degrees,
        "initial_relation": treatment.relation,
        "extension_mm": treatment.extension_cm * 10.0,
        "extension_version": addin_info.VERSION,
    }


def create_straight_joint(evaluation):
    """Ajuste la seconde barre à l'enveloppe orientée de la première."""
    created_entities = []
    created_attributes = []
    try:
        cut_plane = _add_direct_cut_plane(evaluation, created_entities)
        _extend_body(
            evaluation.treatment,
            evaluation.cut_point,
            evaluation.cut_normal,
            created_entities,
        )
        _split_and_keep_interior(
            evaluation.treatment,
            cut_plane,
            evaluation.cut_point,
            evaluation.cut_normal,
            SPLIT_FEATURE_NAME,
            REMOVE_FEATURE_NAME,
            created_entities,
        )
        created_attributes.append(
            _add_record(evaluation.secondary_occurrence, _direct_record(evaluation))
        )
        return tuple(created_entities)
    except Exception:
        for attribute in reversed(created_attributes):
            if attribute and attribute.isValid:
                attribute.deleteMe()
        for entity in reversed(created_entities):
            if entity and entity.isValid:
                entity.deleteMe()
        raise


def create_miter_joint(evaluation):
    """Ajuste symétriquement les deux barres au même plan d'onglet."""
    created_entities = []
    created_attributes = []
    try:
        first_plane = _add_miter_cut_plane(
            evaluation,
            evaluation.primary_occurrence,
            created_entities,
        )
        _extend_body(
            evaluation.first_treatment,
            evaluation.cut_point,
            evaluation.cut_normal,
            created_entities,
        )
        _split_and_keep_interior(
            evaluation.first_treatment,
            first_plane,
            evaluation.cut_point,
            evaluation.cut_normal,
            MITER_SPLIT_FEATURE_NAME,
            MITER_REMOVE_FEATURE_NAME,
            created_entities,
        )
        second_plane = _add_miter_cut_plane(
            evaluation,
            evaluation.secondary_occurrence,
            created_entities,
        )
        _extend_body(
            evaluation.second_treatment,
            evaluation.cut_point,
            evaluation.cut_normal,
            created_entities,
        )
        _split_and_keep_interior(
            evaluation.second_treatment,
            second_plane,
            evaluation.cut_point,
            evaluation.cut_normal,
            MITER_SPLIT_FEATURE_NAME,
            MITER_REMOVE_FEATURE_NAME,
            created_entities,
        )
        created_attributes.append(
            _add_record(
                evaluation.primary_occurrence,
                _miter_record(
                    evaluation,
                    evaluation.first_treatment,
                    evaluation.secondary_occurrence,
                    evaluation.secondary_metadata,
                ),
            )
        )
        created_attributes.append(
            _add_record(
                evaluation.secondary_occurrence,
                _miter_record(
                    evaluation,
                    evaluation.second_treatment,
                    evaluation.primary_occurrence,
                    evaluation.primary_metadata,
                ),
            )
        )
        return tuple(created_entities)
    except Exception:
        for attribute in reversed(created_attributes):
            if attribute and attribute.isValid:
                attribute.deleteMe()
        for entity in reversed(created_entities):
            if entity and entity.isValid:
                entity.deleteMe()
        raise
