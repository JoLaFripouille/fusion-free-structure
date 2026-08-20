from __future__ import annotations

import math
from dataclasses import dataclass


GEOMETRY_TOLERANCE_CM = 1e-6
JOINT_ENDPOINT_TOLERANCE_CM = 0.1
MINIMUM_JOIN_ANGLE_DEGREES = 5.0
PLANE_RELATION_TOLERANCE_CM = 1e-4
EXTENSION_MARGIN_CM = 0.05


def add(first, second):
    return tuple(a + b for a, b in zip(first, second))


def subtract(first, second):
    return tuple(a - b for a, b in zip(first, second))


def scale(vector, factor):
    return tuple(value * factor for value in vector)


def dot(first, second):
    return sum(a * b for a, b in zip(first, second))


def cross(first, second):
    ax, ay, az = first
    bx, by, bz = second
    return (
        ay * bz - az * by,
        az * bx - ax * bz,
        ax * by - ay * bx,
    )


def length(vector):
    return math.sqrt(dot(vector, vector))


def normalize(vector):
    magnitude = length(vector)
    if magnitude <= GEOMETRY_TOLERANCE_CM:
        raise ValueError("Une direction géométrique est nulle.")
    return scale(vector, 1.0 / magnitude)


def closest_point_on_segment(point, start, end):
    segment = subtract(end, start)
    squared_length = dot(segment, segment)
    if squared_length <= GEOMETRY_TOLERANCE_CM ** 2:
        raise ValueError("La barre principale possède un chemin de longueur nulle.")
    parameter = dot(subtract(point, start), segment) / squared_length
    parameter = min(1.0, max(0.0, parameter))
    return add(start, scale(segment, parameter)), parameter


def normal_plane_intersection_point(first_point, first_normal, second_point, second_normal):
    """Point de l'axe commun aux deux plans normaux, choisi près des deux stations."""
    first_normal = normalize(first_normal)
    second_normal = normalize(second_normal)
    axis = cross(first_normal, second_normal)
    squared_axis_length = dot(axis, axis)
    if squared_axis_length <= GEOMETRY_TOLERANCE_CM ** 2:
        raise ValueError("Les deux plans normaux sont parallèles.")
    first_constant = dot(first_normal, first_point)
    second_constant = dot(second_normal, second_point)
    point_on_axis = scale(
        add(
            scale(cross(second_normal, axis), first_constant),
            scale(cross(axis, first_normal), second_constant),
        ),
        1.0 / squared_axis_length,
    )
    midpoint = scale(add(first_point, second_point), 0.5)
    axis_direction = normalize(axis)
    return add(
        point_on_axis,
        scale(
            axis_direction,
            dot(subtract(midpoint, point_on_axis), axis_direction),
        ),
    )


@dataclass(frozen=True)
class StraightJointGeometry:
    main_point: tuple
    main_parameter: float
    secondary_joint_endpoint: tuple
    secondary_inner_endpoint: tuple
    secondary_joint_endpoint_index: int
    approach_direction: tuple
    main_direction: tuple
    plane_normal: tuple
    endpoint_distance_cm: float
    angle_degrees: float


@dataclass(frozen=True)
class MiterJointGeometry:
    joint_point: tuple
    primary_joint_endpoint: tuple
    primary_inner_endpoint: tuple
    primary_joint_endpoint_index: int
    primary_approach_direction: tuple
    secondary_joint_endpoint: tuple
    secondary_inner_endpoint: tuple
    secondary_joint_endpoint_index: int
    secondary_approach_direction: tuple
    endpoint_distance_cm: float
    angle_degrees: float
    plane_normal: tuple


def analyze_miter_joint(
    primary_start,
    primary_end,
    secondary_start,
    secondary_end,
    endpoint_tolerance_cm=JOINT_ENDPOINT_TOLERANCE_CM,
):
    """Valide deux lignes jointes par leurs extrémités et calcule leur plan bissecteur."""
    primary_endpoints = (primary_start, primary_end)
    secondary_endpoints = (secondary_start, secondary_end)
    candidates = []
    for primary_index, primary_endpoint in enumerate(primary_endpoints):
        for secondary_index, secondary_endpoint in enumerate(secondary_endpoints):
            candidates.append(
                (
                    length(subtract(primary_endpoint, secondary_endpoint)),
                    primary_index,
                    secondary_index,
                )
            )
    distance_cm, primary_index, secondary_index = min(candidates)
    if distance_cm > endpoint_tolerance_cm:
        raise ValueError(
            "Les deux barres doivent se rejoindre par leurs extrémités pour une coupe d'onglet."
        )

    primary_joint = primary_endpoints[primary_index]
    secondary_joint = secondary_endpoints[secondary_index]
    primary_inner = primary_endpoints[1 - primary_index]
    secondary_inner = secondary_endpoints[1 - secondary_index]
    primary_approach = normalize(subtract(primary_joint, primary_inner))
    secondary_approach = normalize(subtract(secondary_joint, secondary_inner))
    cosine = min(1.0, max(-1.0, dot(primary_approach, secondary_approach)))
    angle_degrees = math.degrees(math.acos(cosine))
    if min(angle_degrees, 180.0 - angle_degrees) < MINIMUM_JOIN_ANGLE_DEGREES:
        raise ValueError(
            "Les deux barres sont presque alignées ; aucun onglet fiable ne peut être créé."
        )

    # Les deux directions sont orientées depuis l'intérieur de chaque barre vers le raccord.
    # Leur différence est normale au plan qui laisse chaque barre d'un côté opposé.
    plane_normal = normalize(subtract(primary_approach, secondary_approach))
    joint_point = normal_plane_intersection_point(
        primary_joint,
        primary_approach,
        secondary_joint,
        secondary_approach,
    )
    return MiterJointGeometry(
        joint_point=joint_point,
        primary_joint_endpoint=primary_joint,
        primary_inner_endpoint=primary_inner,
        primary_joint_endpoint_index=primary_index,
        primary_approach_direction=primary_approach,
        secondary_joint_endpoint=secondary_joint,
        secondary_inner_endpoint=secondary_inner,
        secondary_joint_endpoint_index=secondary_index,
        secondary_approach_direction=secondary_approach,
        endpoint_distance_cm=distance_cm,
        angle_degrees=angle_degrees,
        plane_normal=plane_normal,
    )


def analyze_straight_joint(
    main_start,
    main_end,
    secondary_start,
    secondary_end,
    endpoint_tolerance_cm=JOINT_ENDPOINT_TOLERANCE_CM,
):
    """Valide une jonction de deux lignes dont une extrémité secondaire touche l'axe principal."""
    candidates = []
    for index, endpoint in enumerate((secondary_start, secondary_end)):
        main_point, parameter = closest_point_on_segment(
            endpoint,
            main_start,
            main_end,
        )
        candidates.append((length(subtract(endpoint, main_point)), index, main_point, parameter))
    distance_cm, endpoint_index, main_point, main_parameter = min(candidates)
    if distance_cm > endpoint_tolerance_cm:
        raise ValueError(
            "Une extrémité de la barre secondaire doit rejoindre l'axe de la barre principale."
        )

    secondary_endpoints = (secondary_start, secondary_end)
    joint_endpoint = secondary_endpoints[endpoint_index]
    inner_endpoint = secondary_endpoints[1 - endpoint_index]
    approach = normalize(subtract(joint_endpoint, inner_endpoint))
    main_direction = normalize(subtract(main_end, main_start))
    return endpoint_joint_geometry(
        main_point,
        main_parameter,
        joint_endpoint,
        inner_endpoint,
        endpoint_index,
        approach,
        main_direction,
        distance_cm,
    )


def endpoint_joint_geometry(
    main_point,
    main_parameter,
    joint_endpoint,
    inner_endpoint,
    endpoint_index,
    approach_direction,
    main_direction,
    endpoint_distance_cm,
):
    """Finalise une coupe droite à partir des tangentes locales des deux chemins."""
    approach = normalize(approach_direction)
    main_direction = normalize(main_direction)
    cosine = min(1.0, max(-1.0, abs(dot(main_direction, approach))))
    angle_degrees = math.degrees(math.acos(cosine))
    if angle_degrees < MINIMUM_JOIN_ANGLE_DEGREES:
        raise ValueError(
            "Les deux axes sont presque parallèles ; aucun plan de jonction fiable ne peut être calculé."
        )
    # La normale vise le côté de la principale d'où arrive la barre à ajuster.
    # Elle est la projection de l'axe intérieur secondaire sur le plan normal
    # à l'axe principal et reste donc valable pour tout angle non parallèle.
    secondary_interior_direction = scale(approach, -1.0)
    plane_normal = normalize(
        subtract(
            secondary_interior_direction,
            scale(
                main_direction,
                dot(secondary_interior_direction, main_direction),
            ),
        )
    )
    return StraightJointGeometry(
        main_point=main_point,
        main_parameter=main_parameter,
        secondary_joint_endpoint=joint_endpoint,
        secondary_inner_endpoint=inner_endpoint,
        secondary_joint_endpoint_index=endpoint_index,
        approach_direction=approach,
        main_direction=main_direction,
        plane_normal=plane_normal,
        endpoint_distance_cm=endpoint_distance_cm,
        angle_degrees=angle_degrees,
    )


def support_point_index(points, direction):
    if not points:
        raise ValueError("La barre principale ne contient aucun sommet exploitable.")
    return max(range(len(points)), key=lambda index: dot(points[index], direction))


def cut_point_from_support(support_point, plane_normal, gap_cm):
    if gap_cm < 0.0:
        raise ValueError("Le jeu de jonction ne peut pas être négatif.")
    return add(support_point, scale(normalize(plane_normal), gap_cm))


def plane_signed_distance(point, plane_point, plane_normal):
    return dot(subtract(point, plane_point), normalize(plane_normal))


def project_points_along_direction_to_plane(
    points,
    direction,
    plane_point,
    plane_normal,
):
    """Projette une section le long de son axe jusqu'au plan de contact."""
    if not points:
        raise ValueError("La section à projeter ne contient aucun point exploitable.")
    direction = normalize(direction)
    normal = normalize(plane_normal)
    rate = dot(direction, normal)
    if abs(rate) <= GEOMETRY_TOLERANCE_CM:
        raise ValueError(
            "La direction de la barre secondaire est parallèle au plan de contact."
        )
    projected = []
    for point in points:
        distance = plane_signed_distance(point, plane_point, normal)
        projected.append(add(point, scale(direction, -distance / rate)))
    return tuple(projected)


def axis_coverage_extensions(
    current_points,
    required_points,
    axis_direction,
    tolerance_cm=PLANE_RELATION_TOLERANCE_CM,
):
    """Retourne les prolongements nécessaires aux côtés négatif et positif d'un axe."""
    if not current_points:
        raise ValueError("La barre principale ne contient aucun point exploitable.")
    if not required_points:
        raise ValueError("La zone de jonction à couvrir est vide.")
    axis = normalize(axis_direction)
    current = tuple(dot(point, axis) for point in current_points)
    required = tuple(dot(point, axis) for point in required_points)
    negative_cm = max(0.0, min(current) - min(required))
    positive_cm = max(0.0, max(required) - max(current))
    if negative_cm <= tolerance_cm:
        negative_cm = 0.0
    if positive_cm <= tolerance_cm:
        positive_cm = 0.0
    return negative_cm, positive_cm


def body_plane_relation(
    body_points,
    plane_point,
    plane_normal,
    interior_point,
    tolerance_cm=PLANE_RELATION_TOLERANCE_CM,
):
    """Classe un corps par rapport au plan en orientant le côté intérieur positivement."""
    if not body_points:
        raise ValueError("Le corps ne contient aucun sommet exploitable.")
    interior_distance = plane_signed_distance(
        interior_point,
        plane_point,
        plane_normal,
    )
    if abs(interior_distance) <= tolerance_cm:
        raise ValueError("Le côté intérieur de la barre ne peut pas être déterminé.")
    interior_sign = 1.0 if interior_distance > 0.0 else -1.0
    distances = tuple(
        interior_sign * plane_signed_distance(point, plane_point, plane_normal)
        for point in body_points
    )
    minimum = min(distances)
    maximum = max(distances)
    if minimum < -tolerance_cm and maximum > tolerance_cm:
        relation = "overlap"
    elif minimum >= -tolerance_cm and minimum <= tolerance_cm:
        relation = "aligned"
    elif minimum > tolerance_cm:
        relation = "gap"
    else:
        relation = "outside"
    return relation, interior_sign, minimum, maximum


def extension_distance_to_plane(
    end_face_points,
    approach_direction,
    plane_point,
    plane_normal,
    interior_sign,
    margin_cm=EXTENSION_MARGIN_CM,
    tolerance_cm=PLANE_RELATION_TOLERANCE_CM,
):
    """Distance qui place toute la face d'extrémité au-delà du plan de coupe."""
    if not end_face_points:
        raise ValueError("La face d'extrémité ne contient aucun sommet exploitable.")
    approach = normalize(approach_direction)
    normal = normalize(plane_normal)
    rate = interior_sign * dot(approach, normal)
    if rate >= -GEOMETRY_TOLERANCE_CM:
        raise ValueError(
            "L'extrémité sélectionnée ne peut pas être prolongée vers le plan de jonction."
        )
    crossing_distances = []
    for point in end_face_points:
        distance = interior_sign * plane_signed_distance(point, plane_point, normal)
        crossing_distances.append(-distance / rate)
    crossing_distance_cm = max(crossing_distances)
    if crossing_distance_cm < -tolerance_cm:
        return 0.0
    return max(0.0, crossing_distance_cm) + margin_cm / abs(rate)


def signed_offset_between_planes(reference_point, target_point, plane_normal):
    return dot(subtract(target_point, reference_point), normalize(plane_normal))


def body_projection_center(points, direction):
    if not points:
        raise ValueError("Le corps ne contient aucun sommet exploitable.")
    projections = [dot(point, direction) for point in points]
    return (min(projections) + max(projections)) / 2.0


def plane_square(center, normal, half_size):
    if half_size <= 0.0:
        raise ValueError("La taille de l'aperçu de coupe doit être positive.")
    normal = normalize(normal)
    reference = (0.0, 0.0, 1.0) if abs(normal[2]) < 0.9 else (1.0, 0.0, 0.0)
    first_axis = normalize(cross(normal, reference))
    second_axis = normalize(cross(normal, first_axis))
    first = scale(first_axis, half_size)
    second = scale(second_axis, half_size)
    return (
        add(add(center, first), second),
        add(subtract(center, first), second),
        subtract(subtract(center, first), second),
        add(subtract(center, second), first),
    )
