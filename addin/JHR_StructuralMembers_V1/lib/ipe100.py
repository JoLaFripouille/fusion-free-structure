from __future__ import annotations

import math


PROFILE_NAME = "IPE 100"
ANCHOR_NAME = "C"
WIDTH_MM = 55.0
HEIGHT_MM = 100.0
MM_TO_CM = 0.1

# Contour validé de Bibliotheque_Acier/IPE/IPE_100.dxf.
# Chaque sommet porte le bulge du segment qui part de ce sommet.
VERTICES_MM = (
    (-27.5, 0.0, 0.0),
    (27.5, 0.0, 0.0),
    (27.5, 5.7, 0.0),
    (9.05, 5.7, -0.41421356237309503),
    (2.05, 12.7, 0.0),
    (2.05, 87.3, -0.41421356237309503),
    (9.05, 94.3, 0.0),
    (27.5, 94.3, 0.0),
    (27.5, 100.0, 0.0),
    (-27.5, 100.0, 0.0),
    (-27.5, 94.3, 0.0),
    (-9.05, 94.3, -0.41421356237309503),
    (-2.05, 87.3, 0.0),
    (-2.05, 12.7, -0.41421356237309503),
    (-9.05, 5.7, 0.0),
    (-27.5, 5.7, 0.0),
)


def _arc_from_bulge(start, end, bulge):
    x1, y1 = start
    x2, y2 = end
    dx, dy = x2 - x1, y2 - y1
    chord = math.hypot(dx, dy)
    if chord <= 0:
        raise ValueError("Segment d'arc de longueur nulle")
    sweep = 4.0 * math.atan(bulge)
    center_offset = chord / (2.0 * math.tan(sweep / 2.0))
    midpoint_x, midpoint_y = (x1 + x2) / 2.0, (y1 + y2) / 2.0
    left_x, left_y = -dy / chord, dx / chord
    center = (midpoint_x + left_x * center_offset, midpoint_y + left_y * center_offset)
    radius = math.hypot(x1 - center[0], y1 - center[1])
    return center, radius, sweep


def segments_mm(anchor=(0.0, 50.0)):
    """Retourne le contour ordonné, centré sur l'ancrage de section choisi."""
    anchor_x, anchor_y = anchor
    points = [(x - anchor_x, y - anchor_y, bulge) for x, y, bulge in VERTICES_MM]
    result = []
    for index, (x1, y1, bulge) in enumerate(points):
        x2, y2, _ = points[(index + 1) % len(points)]
        start, end = (x1, y1), (x2, y2)
        if abs(bulge) < 1e-12:
            result.append({"type": "LINE", "start": start, "end": end})
        else:
            center, radius, sweep = _arc_from_bulge(start, end, bulge)
            result.append({
                "type": "ARC",
                "start": start,
                "end": end,
                "center": center,
                "radius": radius,
                "sweep": sweep,
            })
    return result


def segments_cm(anchor=(0.0, 50.0)):
    converted = []
    for segment in segments_mm(anchor):
        item = dict(segment)
        for key in ("start", "end", "center"):
            if key in item:
                item[key] = tuple(value * MM_TO_CM for value in item[key])
        if "radius" in item:
            item["radius"] *= MM_TO_CM
        converted.append(item)
    return converted
