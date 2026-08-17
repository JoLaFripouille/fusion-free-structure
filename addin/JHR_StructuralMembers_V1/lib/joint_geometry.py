from __future__ import annotations

import math
from dataclasses import dataclass


GEOMETRY_TOLERANCE_CM = 1e-6
JOINT_ENDPOINT_TOLERANCE_CM = 0.1
MINIMUM_JOIN_ANGLE_DEGREES = 5.0
MAXIMUM_RIGHT_ANGLE_DEVIATION_DEGREES = 1.0


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


@dataclass(frozen=True)
class StraightJointGeometry:
    main_point: tuple
    main_parameter: float
    secondary_joint_endpoint: tuple
    secondary_inner_endpoint: tuple
    secondary_joint_endpoint_index: int
    approach_direction: tuple
    endpoint_distance_cm: float
    angle_degrees: float


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
            "Les deux barres sont presque parallèles ; la première jonction droite ne prend pas ce cas en charge."
        )
    if abs(90.0 - angle_degrees) > MAXIMUM_RIGHT_ANGLE_DEVIATION_DEGREES:
        raise ValueError(
            "La coupe droite actuelle exige des axes perpendiculaires. Utiliser la future coupe d'onglet pour cet angle."
        )
    return StraightJointGeometry(
        main_point=main_point,
        main_parameter=main_parameter,
        secondary_joint_endpoint=joint_endpoint,
        secondary_inner_endpoint=inner_endpoint,
        secondary_joint_endpoint_index=endpoint_index,
        approach_direction=approach,
        endpoint_distance_cm=endpoint_distance_cm,
        angle_degrees=angle_degrees,
    )


def support_point_index(points, direction):
    if not points:
        raise ValueError("La barre principale ne contient aucun sommet exploitable.")
    return min(range(len(points)), key=lambda index: dot(points[index], direction))


def cut_point_from_support(support_point, approach_direction, gap_cm):
    if gap_cm < 0.0:
        raise ValueError("Le jeu de jonction ne peut pas être négatif.")
    return add(support_point, scale(approach_direction, -gap_cm))


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
