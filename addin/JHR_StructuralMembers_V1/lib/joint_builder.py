from __future__ import annotations

from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import addin_info, joint_geometry, member_metadata


JOINT_ATTRIBUTE_GROUP = "EI_JHR_StructuralJoint"
JOINT_TYPE = "straight_trim"
TANGENT_PLANE_NAME = "PLAN_JONCTION_TANGENTE"
REFERENCE_PLANE_NAME = "PLAN_JONCTION_APPUI"
CUT_PLANE_NAME = "PLAN_JONCTION_JEU"
SPLIT_FEATURE_NAME = "COUPE_JONCTION_DROITE"
REMOVE_FEATURE_NAME = "RETRAIT_EXCEDENT_JONCTION"
MINIMUM_REMAINING_LENGTH_CM = 0.1


@dataclass(frozen=True)
class JointEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: member_metadata.MemberMetadata
    secondary_metadata: member_metadata.MemberMetadata
    primary_body: object
    secondary_body: object
    secondary_curve: object
    support_vertex: object
    geometry: joint_geometry.StraightJointGeometry
    support_point: tuple
    cut_point: tuple
    gap_cm: float
    removed_length_cm: float
    remaining_length_cm: float
    preview_half_size_cm: float


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
            "La barre {} doit contenir exactement un corps avant la première jonction."
            .format(role)
        )
    body = bodies.item(0)
    if not body or not body.isValid:
        raise ValueError("Le corps de la barre {} n'est pas valide.".format(role))
    return body


def _body_proxy(body, occurrence):
    return body.createForAssemblyContext(occurrence) or body


def _body_vertices(body):
    return [body.vertices.item(index) for index in range(body.vertices.count)]


def _vertex_points(body):
    return [_point_tuple(vertex.geometry) for vertex in _body_vertices(body)]


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
        raise ValueError("Le chemin secondaire n'est ni une ligne ni un arc pris en charge.")
    evaluator = arc.worldGeometry.evaluator
    success, minimum, maximum = evaluator.getParameterExtents()
    if not success:
        raise RuntimeError("Fusion n'a pas pu lire les paramètres de l'arc secondaire.")
    success, start_point, end_point = evaluator.getEndPoints()
    if not success:
        raise RuntimeError("Fusion n'a pas pu lire les extrémités de l'arc secondaire.")
    success_start, start_tangent = evaluator.getTangent(minimum)
    success_end, end_tangent = evaluator.getTangent(maximum)
    if not success_start or not success_end:
        raise RuntimeError("Fusion n'a pas pu lire les tangentes de l'arc secondaire.")
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


def _analyze_secondary_curve(primary_line, secondary_curve):
    primary_start, primary_end = _line_endpoints(primary_line)
    secondary_endpoints, approaches = _curve_end_data(secondary_curve)
    candidates = []
    for index, endpoint in enumerate(secondary_endpoints):
        main_point, parameter = joint_geometry.closest_point_on_segment(
            endpoint,
            primary_start,
            primary_end,
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
            "Une extrémité de la barre secondaire doit rejoindre l'axe de la barre principale."
        )
    main_direction = joint_geometry.normalize(
        joint_geometry.subtract(primary_end, primary_start)
    )
    return joint_geometry.endpoint_joint_geometry(
        main_point,
        main_parameter,
        secondary_endpoints[endpoint_index],
        secondary_endpoints[1 - endpoint_index],
        endpoint_index,
        approaches[endpoint_index],
        main_direction,
        distance_cm,
    )


def _existing_joint(occurrence):
    return occurrence.component.attributes.itemByName(
        JOINT_ATTRIBUTE_GROUP,
        "joint_type",
    )


def _preview_half_size(secondary_points, approach_direction):
    if not secondary_points:
        return 10.0
    square = joint_geometry.plane_square((0.0, 0.0, 0.0), approach_direction, 1.0)
    first_axis = joint_geometry.normalize(
        joint_geometry.subtract(square[0], square[1])
    )
    second_axis = joint_geometry.normalize(
        joint_geometry.subtract(square[1], square[2])
    )
    first_spread = max(joint_geometry.dot(point, first_axis) for point in secondary_points) - min(
        joint_geometry.dot(point, first_axis) for point in secondary_points
    )
    second_spread = max(joint_geometry.dot(point, second_axis) for point in secondary_points) - min(
        joint_geometry.dot(point, second_axis) for point in secondary_points
    )
    return max(5.0, min(100.0, 0.65 * max(first_spread, second_spread)))


def evaluate_straight_joint(design, primary_occurrence, secondary_occurrence, gap_cm):
    if primary_occurrence == secondary_occurrence:
        raise ValueError("La barre principale et la barre secondaire doivent être différentes.")
    if gap_cm < 0.0:
        raise ValueError("Le jeu de jonction ne peut pas être négatif.")

    primary_metadata = _member_metadata(primary_occurrence, "principale")
    secondary_metadata = _member_metadata(secondary_occurrence, "secondaire")
    if _existing_joint(secondary_occurrence):
        raise ValueError(
            "La barre secondaire possède déjà une jonction créée par cette première version."
        )

    primary_line = _linked_curve(
        design,
        primary_metadata,
        "principale",
        allow_arc=False,
    )
    secondary_curve = _linked_curve(
        design,
        secondary_metadata,
        "secondaire",
        allow_arc=True,
    )
    geometry = _analyze_secondary_curve(primary_line, secondary_curve)

    primary_body = _single_body(primary_occurrence, "principale")
    secondary_body = _single_body(secondary_occurrence, "secondaire")
    primary_proxy = _body_proxy(primary_body, primary_occurrence)
    secondary_proxy = _body_proxy(secondary_body, secondary_occurrence)
    primary_vertices = _body_vertices(primary_proxy)
    primary_points = [_point_tuple(vertex.geometry) for vertex in primary_vertices]
    secondary_points = _vertex_points(secondary_proxy)
    support_index = joint_geometry.support_point_index(
        primary_points,
        geometry.approach_direction,
    )
    support_vertex = primary_vertices[support_index]
    support_point = primary_points[support_index]
    cut_point = joint_geometry.cut_point_from_support(
        support_point,
        geometry.approach_direction,
        gap_cm,
    )

    joint_projection = joint_geometry.dot(
        geometry.secondary_joint_endpoint,
        geometry.approach_direction,
    )
    cut_projection = joint_geometry.dot(cut_point, geometry.approach_direction)
    removed_length_cm = joint_projection - cut_projection
    remaining_length_cm = float(secondary_curve.length) - removed_length_cm
    if remaining_length_cm <= MINIMUM_REMAINING_LENGTH_CM:
        raise ValueError(
            "Le profil principal et le jeu demandé supprimeraient toute la barre secondaire."
        )
    if removed_length_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError(
            "Aucune surlongueur secondaire ne traverse l'enveloppe extérieure de la barre principale."
        )

    return JointEvaluation(
        primary_occurrence=primary_occurrence,
        secondary_occurrence=secondary_occurrence,
        primary_metadata=primary_metadata,
        secondary_metadata=secondary_metadata,
        primary_body=primary_body,
        secondary_body=secondary_body,
        secondary_curve=secondary_curve,
        support_vertex=support_vertex,
        geometry=geometry,
        support_point=support_point,
        cut_point=cut_point,
        gap_cm=float(gap_cm),
        removed_length_cm=removed_length_cm,
        remaining_length_cm=remaining_length_cm,
        preview_half_size_cm=_preview_half_size(
            secondary_points,
            geometry.approach_direction,
        ),
    )


def _world_plane_system(plane, occurrence):
    proxy = plane.createForAssemblyContext(occurrence) or plane
    origin, _, _, normal = proxy.transform.getAsCoordinateSystem()
    return _point_tuple(origin), _vector_tuple(normal)


def _add_tangent_plane(evaluation):
    component = evaluation.secondary_occurrence.component
    plane_input = component.constructionPlanes.createInput(
        evaluation.secondary_occurrence
    )
    fraction = adsk.core.ValueInput.createByReal(
        float(evaluation.geometry.secondary_joint_endpoint_index)
    )
    if not plane_input.setByDistanceOnPath(evaluation.secondary_curve, fraction):
        raise RuntimeError(
            "Fusion n'a pas pu créer le plan normal à la tangente de la barre secondaire."
        )
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu créer le plan tangent de la jonction.")
    plane.name = TANGENT_PLANE_NAME
    plane.isLightBulbOn = False
    return plane


def _add_reference_plane(evaluation, tangent_plane):
    component = evaluation.secondary_occurrence.component
    plane_input = component.constructionPlanes.createInput(
        evaluation.secondary_occurrence
    )
    if not plane_input.setByOffsetThroughPoint(
        tangent_plane,
        evaluation.support_vertex,
    ):
        raise RuntimeError(
            "Fusion n'a pas pu lier le plan de jonction au sommet de la barre principale."
        )
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu créer le plan d'appui de la jonction.")
    plane.name = REFERENCE_PLANE_NAME
    plane.isLightBulbOn = False
    return plane


def _add_cut_plane(evaluation, reference_plane):
    component = evaluation.secondary_occurrence.component
    reference_origin, reference_normal = _world_plane_system(
        reference_plane,
        evaluation.secondary_occurrence,
    )
    signed_offset = joint_geometry.signed_offset_between_planes(
        reference_origin,
        evaluation.cut_point,
        reference_normal,
    )
    plane_input = component.constructionPlanes.createInput(
        evaluation.secondary_occurrence
    )
    if not plane_input.setByOffset(
        reference_plane,
        adsk.core.ValueInput.createByReal(signed_offset),
    ):
        raise RuntimeError("Fusion n'a pas pu définir le jeu de la jonction.")
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu créer le plan de coupe de la jonction.")
    plane.name = CUT_PLANE_NAME
    plane.isLightBulbOn = False
    return plane


def _projection_center_for_body(body, occurrence, direction):
    proxy = _body_proxy(body, occurrence)
    return joint_geometry.body_projection_center(_vertex_points(proxy), direction)


def _add_attributes(evaluation):
    component = evaluation.secondary_occurrence.component
    attributes = component.attributes
    values = {
        "joint_type": JOINT_TYPE,
        "primary_component": evaluation.primary_occurrence.component.name,
        "primary_occurrence_token": evaluation.primary_occurrence.entityToken,
        "primary_source_curve_token": evaluation.primary_metadata.source_curve_token,
        "gap_mm": "{:.9f}".format(evaluation.gap_cm * 10.0).rstrip("0").rstrip("."),
        "extension_version": addin_info.VERSION,
    }
    for key, value in values.items():
        attributes.add(JOINT_ATTRIBUTE_GROUP, key, str(value))


def create_straight_joint(evaluation):
    """Coupe la secondaire sans modifier le corps de la barre principale."""
    created_entities = []
    component = evaluation.secondary_occurrence.component
    try:
        tangent_plane = _add_tangent_plane(evaluation)
        created_entities.append(tangent_plane)
        reference_plane = _add_reference_plane(evaluation, tangent_plane)
        created_entities.append(reference_plane)
        cut_plane = _add_cut_plane(evaluation, reference_plane)
        created_entities.append(cut_plane)

        split_features = component.features.splitBodyFeatures
        split_input = split_features.createInput(
            evaluation.secondary_body,
            cut_plane,
            True,
        )
        if not split_input:
            raise RuntimeError("Fusion n'a pas pu préparer la coupe de la barre secondaire.")
        split_feature = split_features.add(split_input)
        if not split_feature:
            raise RuntimeError("Fusion n'a pas pu couper la barre secondaire.")
        split_feature.name = SPLIT_FEATURE_NAME
        created_entities.append(split_feature)

        bodies = [component.bRepBodies.item(index) for index in range(component.bRepBodies.count)]
        if len(bodies) != 2:
            raise RuntimeError(
                "La coupe devait produire exactement deux morceaux, mais Fusion en retourne {}."
                .format(len(bodies))
            )
        excess_body = max(
            bodies,
            key=lambda body: _projection_center_for_body(
                body,
                evaluation.secondary_occurrence,
                evaluation.geometry.approach_direction,
            ),
        )
        remove_feature = component.features.removeFeatures.add(excess_body)
        if not remove_feature:
            raise RuntimeError("Fusion n'a pas pu retirer la surlongueur de la jonction.")
        remove_feature.name = REMOVE_FEATURE_NAME
        created_entities.append(remove_feature)

        _add_attributes(evaluation)
        return remove_feature
    except Exception:
        for entity in reversed(created_entities):
            if entity and entity.isValid:
                entity.deleteMe()
        raise
