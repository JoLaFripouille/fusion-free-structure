"""Repère et axes du contreventement à partir des deux faces porteuses."""

from dataclasses import dataclass
from math import isfinite

from . import joint_geometry as geo


Vector = tuple[float, float, float]
Diagonal = tuple[Vector, Vector]


@dataclass(frozen=True)
class SupportFace:
    """Face intérieure, avec ses niveaux bas et haut projetés sur la verticale."""

    origin: Vector
    normal: Vector
    low: float
    high: float


@dataclass(frozen=True)
class BayFrame:
    up: Vector
    across: Vector
    normal: Vector
    corners: tuple[Vector, Vector, Vector, Vector]
    diagonals: tuple[Diagonal, Diagonal]


def plan(first: SupportFace, second: SupportFace, up: Vector, pilot: Vector, *,
         bottom_cm: float = 0., top_cm: float = 0.,
         setback_cm: float | tuple[float, float] = 0., offset_cm: float = 0.) -> BayFrame:
    """Calcule le X dans le repère réel du portique. Toutes les longueurs sont en cm."""
    left_setback, right_setback = setback_cm if isinstance(setback_cm, tuple) else (setback_cm, setback_cm)
    if not all(isfinite(value) for value in (bottom_cm, top_cm, left_setback, right_setback, offset_cm)):
        raise ValueError("Les retraits et le déport doivent avoir une valeur finie.")
    if min(bottom_cm, top_cm, left_setback, right_setback) < 0.:
        raise ValueError("Les retraits du bas, du haut et des faces doivent être positifs ou nuls.")

    up = geo.normalize(up)
    inward, opposite = (geo.normalize(face.normal) for face in (first, second))
    if max(abs(geo.dot(direction, up)) for direction in (inward, opposite)) > geo.GEOMETRY_TOLERANCE_CM:
        raise ValueError("Les deux faces porteuses doivent être verticales.")
    if geo.length(geo.add(inward, opposite)) > geo.GEOMETRY_TOLERANCE_CM:
        raise ValueError("Sélectionner deux faces planes, parallèles et opposées.")

    # Orthogonalise le repère avant de projeter les cotes sur ses trois axes.
    across = geo.normalize(geo.subtract(inward, geo.scale(up, geo.dot(inward, up))))
    normal = geo.cross(across, up)
    left_face = geo.dot(first.origin, across)
    right_face = geo.dot(second.origin, across)
    left = left_face + left_setback
    right = right_face - right_setback
    if right_face - left_face <= geo.PLANE_RELATION_TOLERANCE_CM:
        raise ValueError("Sélectionner les faces des poteaux qui se regardent dans la travée.")
    if right - left <= geo.PLANE_RELATION_TOLERANCE_CM:
        raise ValueError("Les retraits des cornières dépassent l’espace entre les deux faces.")

    levels = tuple((face.low+bottom_cm, face.high-top_cm) for face in (first, second))
    if any(top-bottom <= geo.PLANE_RELATION_TOLERANCE_CM for bottom, top in levels):
        raise ValueError("Les retraits du bas et du haut dépassent la hauteur de l’une des faces.")

    plane = geo.scale(normal, geo.dot(pilot, normal) + offset_cm)
    left_base = geo.add(plane, geo.scale(across, left))
    right_base = geo.add(plane, geo.scale(across, right))
    left_bottom, left_top = (geo.add(left_base, geo.scale(up, height)) for height in levels[0])
    right_bottom, right_top = (geo.add(right_base, geo.scale(up, height)) for height in levels[1])
    return BayFrame(
        up, across, normal,
        (left_bottom, left_top, right_bottom, right_top),
        ((left_bottom, right_top), (left_top, right_bottom)),
    )
