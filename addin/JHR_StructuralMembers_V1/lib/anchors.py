from __future__ import annotations

from dataclasses import dataclass


DEFAULT_ANCHOR_CODE = "C"


@dataclass(frozen=True)
class AnchorDefinition:
    code: str
    label: str
    row: int
    column: int


ANCHOR_DEFINITIONS = (
    AnchorDefinition("TL", "Haut gauche", 0, 0),
    AnchorDefinition("TC", "Haut centre", 0, 1),
    AnchorDefinition("TR", "Haut droite", 0, 2),
    AnchorDefinition("ML", "Milieu gauche", 1, 0),
    AnchorDefinition("C", "Centre", 1, 1),
    AnchorDefinition("MR", "Milieu droite", 1, 2),
    AnchorDefinition("BL", "Bas gauche", 2, 0),
    AnchorDefinition("BC", "Bas centre", 2, 1),
    AnchorDefinition("BR", "Bas droite", 2, 2),
)

_ANCHORS_BY_CODE = {anchor.code: anchor for anchor in ANCHOR_DEFINITIONS}


def definition(anchor_code):
    try:
        return _ANCHORS_BY_CODE[anchor_code]
    except KeyError as error:
        raise ValueError("Point d'ancrage inconnu : {}.".format(anchor_code)) from error


def point_for_bounds(bounds_mm, anchor_code):
    """Calcule un point de la grille 3 × 3 sur l'enveloppe du profil."""
    anchor = definition(anchor_code)
    min_x, min_y, max_x, max_y = bounds_mm
    x_values = (min_x, (min_x + max_x) / 2.0, max_x)
    y_values = (max_y, (min_y + max_y) / 2.0, min_y)
    return x_values[anchor.column], y_values[anchor.row]


def label(anchor_code):
    return definition(anchor_code).label
