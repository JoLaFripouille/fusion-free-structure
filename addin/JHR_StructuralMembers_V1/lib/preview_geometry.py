from __future__ import annotations

import math


def read_r12_polyline_vertices(dxf_path):
    """Lit les sommets de la première POLYLINE 2D d'un DXF ASCII R12."""
    lines = dxf_path.read_text(encoding="ascii").splitlines()
    pairs = [
        (lines[index].strip(), lines[index + 1].strip())
        for index in range(0, len(lines) - 1, 2)
    ]
    vertices = []
    current = None
    inside_polyline = False
    for code, value in pairs:
        if code == "0":
            if current:
                vertices.append((current["x"], current["y"], current.get("bulge", 0.0)))
                current = None
            if value == "POLYLINE" and not inside_polyline:
                inside_polyline = True
            elif value == "VERTEX" and inside_polyline:
                current = {}
            elif value == "SEQEND" and inside_polyline:
                break
        elif current is not None:
            if code == "10":
                current["x"] = float(value)
            elif code == "20":
                current["y"] = float(value)
            elif code == "42":
                current["bulge"] = float(value)
    if current:
        vertices.append((current["x"], current["y"], current.get("bulge", 0.0)))
    if len(vertices) < 3:
        raise ValueError("Le DXF ne contient pas de POLYLINE fermée exploitable pour l'aperçu.")
    return vertices


def _arc_data(start, end, bulge):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0:
        raise ValueError("Arc DXF de longueur nulle")
    sweep = 4.0 * math.atan(bulge)
    center_offset = chord / (2.0 * math.tan(sweep / 2.0))
    midpoint_x = (x1 + x2) / 2.0
    midpoint_y = (y1 + y2) / 2.0
    left_x, left_y = -dy / chord, dx / chord
    center = (
        midpoint_x + left_x * center_offset,
        midpoint_y + left_y * center_offset,
    )
    radius = math.hypot(x1 - center[0], y1 - center[1])
    start_angle = math.atan2(y1 - center[1], x1 - center[0])
    return center, radius, start_angle, sweep


def tessellate_profile_cm(dxf_path, anchor_mm=(0.0, 50.0), max_angle_deg=7.5):
    """Approxime visuellement le contour DXF sans modifier la géométrie finale."""
    vertices = read_r12_polyline_vertices(dxf_path)
    max_angle = math.radians(max_angle_deg)
    anchor_x, anchor_y = anchor_mm
    points_mm = []
    for index, (x1, y1, bulge) in enumerate(vertices):
        x2, y2, _ = vertices[(index + 1) % len(vertices)]
        if abs(bulge) < 1e-12:
            points_mm.append((x1 - anchor_x, y1 - anchor_y))
            continue

        center, radius, start_angle, sweep = _arc_data((x1, y1), (x2, y2), bulge)
        subdivisions = max(1, int(math.ceil(abs(sweep) / max_angle)))
        for step in range(subdivisions):
            angle = start_angle + sweep * step / subdivisions
            points_mm.append((
                center[0] + radius * math.cos(angle) - anchor_x,
                center[1] + radius * math.sin(angle) - anchor_y,
            ))
    return [(x * 0.1, y * 0.1) for x, y in points_mm]


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
