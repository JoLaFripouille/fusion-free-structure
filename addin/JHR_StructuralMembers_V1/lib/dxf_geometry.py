from __future__ import annotations

import math
from pathlib import Path


SUPPORTED_ENTITY_TYPES = {"LINE", "ARC", "CIRCLE", "POLYLINE"}
CONNECT_TOLERANCE_MM = 1e-5


def _pairs(dxf_path):
    lines = Path(dxf_path).read_text(encoding="ascii").splitlines()
    return [
        (lines[index].strip(), lines[index + 1].strip())
        for index in range(0, len(lines) - 1, 2)
    ]


def _values_to_dict(values):
    result = {}
    for code, value in values:
        result.setdefault(code, []).append(value)
    return result


def _number(data, code, default=None):
    values = data.get(code)
    if not values:
        if default is not None:
            return default
        raise ValueError("Le code DXF {} est absent.".format(code))
    return float(values[0])


def read_r12_entities(dxf_path):
    """Lit les entités 2D utilisées par la bibliothèque DXF ASCII R12."""
    pairs = _pairs(dxf_path)
    start = None
    for index in range(len(pairs) - 1):
        if pairs[index] == ("0", "SECTION") and pairs[index + 1] == ("2", "ENTITIES"):
            start = index + 2
            break
    if start is None:
        raise ValueError("Le DXF ne contient pas de section ENTITIES.")

    entities = []
    index = start
    while index < len(pairs):
        code, entity_type = pairs[index]
        if code == "0" and entity_type == "ENDSEC":
            break
        if code != "0":
            index += 1
            continue

        if entity_type == "POLYLINE":
            index += 1
            header_values = []
            while index < len(pairs) and pairs[index][0] != "0":
                header_values.append(pairs[index])
                index += 1

            vertices = []
            while index < len(pairs):
                marker = pairs[index]
                if marker == ("0", "SEQEND"):
                    index += 1
                    while index < len(pairs) and pairs[index][0] != "0":
                        index += 1
                    break
                if marker != ("0", "VERTEX"):
                    break
                index += 1
                vertex_values = []
                while index < len(pairs) and pairs[index][0] != "0":
                    vertex_values.append(pairs[index])
                    index += 1
                vertex_data = _values_to_dict(vertex_values)
                vertices.append((
                    _number(vertex_data, "10"),
                    _number(vertex_data, "20"),
                    _number(vertex_data, "42", 0.0),
                ))

            header = _values_to_dict(header_values)
            flags = int(_number(header, "70", 0.0))
            entities.append({
                "type": "POLYLINE",
                "vertices": vertices,
                "closed": bool(flags & 1),
            })
            continue

        index += 1
        entity_values = []
        while index < len(pairs) and pairs[index][0] != "0":
            entity_values.append(pairs[index])
            index += 1
        if entity_type not in SUPPORTED_ENTITY_TYPES:
            raise ValueError("Entité DXF non prise en charge : {}.".format(entity_type))
        data = _values_to_dict(entity_values)
        if entity_type == "LINE":
            entities.append({
                "type": "LINE",
                "start": (_number(data, "10"), _number(data, "20")),
                "end": (_number(data, "11"), _number(data, "21")),
            })
        elif entity_type == "ARC":
            entities.append({
                "type": "ARC",
                "center": (_number(data, "10"), _number(data, "20")),
                "radius": _number(data, "40"),
                "start_angle": math.radians(_number(data, "50")),
                "end_angle": math.radians(_number(data, "51")),
            })
        elif entity_type == "CIRCLE":
            entities.append({
                "type": "CIRCLE",
                "center": (_number(data, "10"), _number(data, "20")),
                "radius": _number(data, "40"),
            })

    if not entities:
        raise ValueError("Le DXF ne contient aucune géométrie 2D exploitable.")
    return entities


def _arc_data(start, end, bulge):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0:
        raise ValueError("Arc DXF de longueur nulle.")
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


def _positive_arc_sweep(start_angle, end_angle):
    sweep = (end_angle - start_angle) % (2.0 * math.pi)
    return 2.0 * math.pi if math.isclose(sweep, 0.0, abs_tol=1e-12) else sweep


def _sample_arc(center, radius, start_angle, sweep, max_angle):
    subdivisions = max(1, int(math.ceil(abs(sweep) / max_angle)))
    return [
        (
            center[0] + radius * math.cos(start_angle + sweep * step / subdivisions),
            center[1] + radius * math.sin(start_angle + sweep * step / subdivisions),
        )
        for step in range(subdivisions + 1)
    ]


def _polyline_points(entity, max_angle):
    vertices = entity["vertices"]
    if len(vertices) < 2:
        raise ValueError("Une POLYLINE contient moins de deux sommets.")
    closed = entity["closed"] or _points_close(vertices[0][:2], vertices[-1][:2])

    segment_count = len(vertices) if entity["closed"] else len(vertices) - 1
    points = []
    for index in range(segment_count):
        x1, y1, bulge = vertices[index]
        x2, y2, _ = vertices[(index + 1) % len(vertices)]
        if abs(bulge) < 1e-12:
            segment = [(x1, y1), (x2, y2)]
        else:
            center, radius, start_angle, sweep = _arc_data((x1, y1), (x2, y2), bulge)
            segment = _sample_arc(center, radius, start_angle, sweep, max_angle)
        points.extend(segment if not points else segment[1:])
    if closed and _points_close(points[0], points[-1]):
        points.pop()
    return points


def _entity_segment(entity, max_angle):
    if entity["type"] == "LINE":
        return [entity["start"], entity["end"]]
    if entity["type"] == "ARC":
        sweep = _positive_arc_sweep(entity["start_angle"], entity["end_angle"])
        return _sample_arc(
            entity["center"],
            entity["radius"],
            entity["start_angle"],
            sweep,
            max_angle,
        )
    raise ValueError("Cette entité ne constitue pas un segment raccordable.")


def _points_close(first, second, tolerance=CONNECT_TOLERANCE_MM):
    return math.hypot(first[0] - second[0], first[1] - second[1]) <= tolerance


def _connect_segments(segments):
    remaining = [list(segment) for segment in segments]
    contours = []
    while remaining:
        contour = remaining.pop(0)
        while not _points_close(contour[-1], contour[0]):
            match_index = None
            reverse = False
            for index, segment in enumerate(remaining):
                if _points_close(contour[-1], segment[0]):
                    match_index = index
                    break
                if _points_close(contour[-1], segment[-1]):
                    match_index = index
                    reverse = True
                    break
            if match_index is None:
                raise ValueError("Les lignes et arcs du DXF ne forment pas un contour fermé.")
            segment = remaining.pop(match_index)
            if reverse:
                segment.reverse()
            contour.extend(segment[1:])
        contour.pop()
        if len(contour) < 3:
            raise ValueError("Un contour DXF contient moins de trois points.")
        contours.append(contour)
    return contours


def tessellate_profile_contours_mm(dxf_path, max_angle_deg=7.5):
    """Retourne tous les contours fermés, uniquement pour l'affichage."""
    max_angle = math.radians(max_angle_deg)
    contours = []
    segments = []
    for entity in read_r12_entities(dxf_path):
        if entity["type"] == "POLYLINE":
            points = _polyline_points(entity, max_angle)
            is_closed = entity["closed"] or _points_close(
                entity["vertices"][0][:2],
                entity["vertices"][-1][:2],
            )
            if is_closed:
                contours.append(points)
            else:
                segments.append(points)
        elif entity["type"] == "CIRCLE":
            contours.append(_sample_arc(
                entity["center"],
                entity["radius"],
                0.0,
                2.0 * math.pi,
                max_angle,
            )[:-1])
        else:
            segments.append(_entity_segment(entity, max_angle))
    if segments:
        contours.extend(_connect_segments(segments))
    if not contours:
        raise ValueError("Aucun contour fermé n'a été détecté dans le DXF.")
    return contours


def _angle_on_sweep(angle, start_angle, sweep):
    if sweep >= 0:
        return (angle - start_angle) % (2.0 * math.pi) <= sweep + 1e-12
    return (start_angle - angle) % (2.0 * math.pi) <= -sweep + 1e-12


def _arc_extreme_points(center, radius, start_angle, sweep):
    angles = [start_angle, start_angle + sweep]
    for angle in (0.0, math.pi / 2.0, math.pi, 3.0 * math.pi / 2.0):
        if _angle_on_sweep(angle, start_angle, sweep):
            angles.append(angle)
    return [
        (center[0] + radius * math.cos(angle), center[1] + radius * math.sin(angle))
        for angle in angles
    ]


def profile_bounds_mm(dxf_path):
    """Calcule les limites exactes des lignes, arcs, cercles et bulges."""
    points = []
    for entity in read_r12_entities(dxf_path):
        entity_type = entity["type"]
        if entity_type == "LINE":
            points.extend((entity["start"], entity["end"]))
        elif entity_type == "ARC":
            points.extend(_arc_extreme_points(
                entity["center"],
                entity["radius"],
                entity["start_angle"],
                _positive_arc_sweep(entity["start_angle"], entity["end_angle"]),
            ))
        elif entity_type == "CIRCLE":
            center_x, center_y = entity["center"]
            radius = entity["radius"]
            points.extend((
                (center_x - radius, center_y),
                (center_x + radius, center_y),
                (center_x, center_y - radius),
                (center_x, center_y + radius),
            ))
        elif entity_type == "POLYLINE":
            vertices = entity["vertices"]
            segment_count = len(vertices) if entity["closed"] else len(vertices) - 1
            for index in range(segment_count):
                x1, y1, bulge = vertices[index]
                x2, y2, _ = vertices[(index + 1) % len(vertices)]
                if abs(bulge) < 1e-12:
                    points.extend(((x1, y1), (x2, y2)))
                else:
                    center, radius, start_angle, sweep = _arc_data((x1, y1), (x2, y2), bulge)
                    points.extend(_arc_extreme_points(center, radius, start_angle, sweep))
    if not points:
        raise ValueError("Impossible de calculer les limites du profil DXF.")
    xs = [point[0] for point in points]
    ys = [point[1] for point in points]
    return min(xs), min(ys), max(xs), max(ys)
