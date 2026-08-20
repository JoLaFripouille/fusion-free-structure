from __future__ import annotations

from . import dxf_geometry, joint_geometry


def read_r12_polyline_vertices(dxf_path):
    """Lit les sommets de la première POLYLINE 2D d'un DXF ASCII R12."""
    for entity in dxf_geometry.read_r12_entities(dxf_path):
        if entity["type"] == "POLYLINE":
            return entity["vertices"]
    raise ValueError("Le DXF ne contient pas de POLYLINE exploitable pour l'aperçu.")


def tessellate_profile_cm(dxf_path, anchor_mm=(0.0, 50.0), max_angle_deg=7.5):
    """Compatibilité V1.2 : retourne le premier contour visuel du DXF."""
    return tessellate_profile_contours_cm(dxf_path, anchor_mm, max_angle_deg)[0]


def tessellate_profile_contours_cm(dxf_path, anchor_mm=None, max_angle_deg=7.5):
    """Approxime tous les contours pour l'aperçu, sans modifier le DXF final."""
    contours = dxf_geometry.tessellate_profile_contours_mm(dxf_path, max_angle_deg)
    if anchor_mm is None:
        min_x, min_y, max_x, max_y = dxf_geometry.profile_bounds_mm(dxf_path)
        anchor_mm = ((min_x + max_x) / 2.0, (min_y + max_y) / 2.0)
    anchor_x, anchor_y = anchor_mm
    return [
        [
            ((x - anchor_x) * 0.1, (y - anchor_y) * 0.1)
            for x, y in contour
        ]
        for contour in contours
    ]


def build_swept_side_mesh(profile_points, frames):
    """Construit les coordonnées et triangles d'une enveloppe visuelle ouverte."""
    if len(profile_points) < 3 or len(frames) < 2:
        raise ValueError("L'aperçu exige un contour et au moins deux repères de chemin.")

    coordinates = []
    for origin, x_axis, y_axis in frames:
        for profile_x, profile_y in profile_points:
            coordinates.extend((
                origin[0] + profile_x * x_axis[0] + profile_y * y_axis[0],
                origin[1] + profile_x * x_axis[1] + profile_y * y_axis[1],
                origin[2] + profile_x * x_axis[2] + profile_y * y_axis[2],
            ))

    profile_count = len(profile_points)
    triangles = []
    for frame_index in range(len(frames) - 1):
        first = frame_index * profile_count
        second = (frame_index + 1) * profile_count
        for point_index in range(profile_count):
            next_index = (point_index + 1) % profile_count
            a = first + point_index
            b = first + next_index
            c = second + next_index
            d = second + point_index
            triangles.extend((a, b, c, a, c, d))
    return coordinates, triangles


def build_wire_indices(profile_count, frame_count):
    """Dessine les sections extrêmes, la section médiane et quelques génératrices."""
    if profile_count < 3 or frame_count < 2:
        return []
    indices = []
    section_frames = sorted({0, frame_count // 2, frame_count - 1})
    for frame_index in section_frames:
        base = frame_index * profile_count
        for point_index in range(profile_count):
            indices.extend((base + point_index, base + (point_index + 1) % profile_count))

    rail_step = max(1, profile_count // 12)
    for point_index in range(0, profile_count, rail_step):
        for frame_index in range(frame_count - 1):
            indices.extend((
                frame_index * profile_count + point_index,
                (frame_index + 1) * profile_count + point_index,
            ))
    return indices


def build_circle_wire(center, first_axis, second_axis, radius, segments=32):
    """Construit un cercle 3D fermé pour matérialiser un futur perçage."""
    import math

    if radius <= 0.0 or segments < 8:
        raise ValueError("Le cercle d'aperçu du perçage est invalide.")
    coordinates = []
    for index in range(segments):
        angle = 2.0 * math.pi * index / segments
        first = radius * math.cos(angle)
        second = radius * math.sin(angle)
        coordinates.extend(
            (
                center[0] + first_axis[0] * first + second_axis[0] * second,
                center[1] + first_axis[1] * first + second_axis[1] * second,
                center[2] + first_axis[2] * first + second_axis[2] * second,
            )
        )
    indices = []
    for index in range(segments):
        indices.extend((index, (index + 1) % segments))
    return coordinates, indices


def build_cylinder_wire(origin, axis, radius, length, segments=24):
    """Construit deux cercles reliés pour prévisualiser un cylindre orienté."""
    if radius <= 0.0 or length <= 0.0 or segments < 8:
        raise ValueError("Le cylindre d'aperçu est invalide.")
    z_axis = joint_geometry.normalize(axis)
    reference = (
        (0.0, 0.0, 1.0)
        if abs(joint_geometry.dot(z_axis, (0.0, 0.0, 1.0))) < 0.9
        else (1.0, 0.0, 0.0)
    )
    first_axis = joint_geometry.normalize(
        joint_geometry.cross(reference, z_axis)
    )
    second_axis = joint_geometry.normalize(
        joint_geometry.cross(z_axis, first_axis)
    )
    end = joint_geometry.add(origin, joint_geometry.scale(z_axis, length))
    first_coordinates, first_indices = build_circle_wire(
        origin,
        first_axis,
        second_axis,
        radius,
        segments,
    )
    second_coordinates, second_indices = build_circle_wire(
        end,
        first_axis,
        second_axis,
        radius,
        segments,
    )
    coordinates = first_coordinates + second_coordinates
    indices = list(first_indices)
    indices.extend(index + segments for index in second_indices)
    rail_step = max(1, segments // 6)
    for index in range(0, segments, rail_step):
        indices.extend((index, index + segments))
    return coordinates, indices
