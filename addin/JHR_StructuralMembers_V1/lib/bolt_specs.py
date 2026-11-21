from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoltSpec:
    designation: str
    strength_class: str
    nominal_diameter_mm: float
    recommended_hole_mm: float
    head_across_flats_mm: float
    head_height_mm: float
    nut_across_flats_mm: float
    nut_height_mm: float
    washer_inner_diameter_mm: float
    washer_outer_diameter_mm: float
    washer_thickness_mm: float
    thread_projection_mm: float = 5.0

    @property
    def display_label(self):
        return "{} — classe {} — trou Ø{} mm".format(
            self.designation,
            self.strength_class,
            _format_number(self.recommended_hole_mm),
        )


def _format_number(value):
    number = float(value)
    return str(int(number)) if number.is_integer() else "{:g}".format(number)


BOLT_SPECS = (
    BoltSpec("M12", "8.8", 12.0, 14.0, 18.0, 7.5, 18.0, 10.0, 13.0, 24.0, 2.5),
    BoltSpec("M16", "8.8", 16.0, 18.0, 24.0, 10.0, 24.0, 13.0, 17.0, 30.0, 3.0),
    BoltSpec("M20", "8.8", 20.0, 22.0, 30.0, 12.5, 30.0, 16.0, 21.0, 37.0, 3.0),
    BoltSpec("M24", "8.8", 24.0, 26.0, 36.0, 15.0, 36.0, 19.0, 25.0, 44.0, 4.0),
)

# Petits diamètres réservés à la pose manuelle. Le choix des assemblages
# de charpente continue d'utiliser BOLT_SPECS.
_SMALL_SOCKET_SPECS = {
    4: BoltSpec("M4", "", 4, 4.5, 7, 2.8, 7, 3.2, 4.3, 9, .8),
    5: BoltSpec("M5", "", 5, 5.5, 8, 3.5, 8, 4.7, 5.3, 10, 1),
    6: BoltSpec("M6", "", 6, 6.6, 10, 4, 10, 5.2, 6.4, 12, 1.6),
    8: BoltSpec("M8", "", 8, 9, 13, 5.3, 13, 6.8, 8.4, 16, 1.6),
    10: BoltSpec("M10", "", 10, 11, 16, 6.4, 16, 8.4, 10.5, 20, 2),
}


@dataclass(frozen=True)
class SocketHead:
    diameter_mm: float
    height_mm: float
    flats_mm: float
    depth_mm: float
    crown_mm: float = 0.


# Dimensions de présentation selon les fiches ISO 4762 et ISO 7380-1.
_SOCKET_HEADS = {
    "CHC": {  # Ø tête, hauteur, clé, profondeur d'empreinte
        4: SocketHead(7, 4, 3, 2), 5: SocketHead(8.5, 5, 4, 2.5),
        6: SocketHead(10, 6, 5, 3), 8: SocketHead(13, 8, 6, 4),
        10: SocketHead(16, 10, 8, 5), 12: SocketHead(18, 12, 10, 6),
        16: SocketHead(24, 16, 14, 8), 20: SocketHead(30, 20, 17, 10),
        24: SocketHead(36, 24, 19, 12),
    },
    "TBHC": {  # Dernière cote : diamètre du méplat supérieur
        4: SocketHead(7.6, 2.2, 2.5, 1.3, 3.8),
        5: SocketHead(9.5, 2.75, 3, 1.56, 5),
        6: SocketHead(10.5, 3.3, 4, 2.08, 6),
        8: SocketHead(14, 4.4, 5, 2.6, 7.7),
        10: SocketHead(17.5, 5.5, 6, 3.12, 10),
        12: SocketHead(21, 6.6, 8, 4.16, 12),
        16: SocketHead(28, 8.8, 10, 5.2, 16),
    },
}


def modeled_spec(diameter_mm, head):
    if head in _SOCKET_HEADS:
        sizes = _SOCKET_HEADS[head]
        if diameter_mm not in sizes:
            available = ", ".join(f"M{value}" for value in sizes)
            raise ValueError(f"Diamètres disponibles pour la tête {head} : {available}.")
        spec = _SMALL_SOCKET_SPECS.get(diameter_mm) or bolt_spec_by_designation(f"M{diameter_mm:g}")
        return spec, sizes[diameter_mm]
    if head not in ("H", "TF"):
        raise ValueError("Choisir une tête H, fraisée, cylindrique CHC ou bombée TBHC.")
    return bolt_spec_by_designation(f"M{diameter_mm:g}"), None


def default_bolt_spec():
    return bolt_spec_by_designation("M16")


def bolt_spec_by_designation(designation):
    wanted = str(designation).strip().upper()
    for spec in BOLT_SPECS:
        if spec.designation == wanted:
            return spec
    raise ValueError("Le diamètre de boulon '{}' n'est pas disponible.".format(designation))


def bolt_spec_from_label(label):
    text = str(label).strip()
    for spec in BOLT_SPECS:
        if text == spec.display_label:
            return spec
    raise ValueError("Le boulon sélectionné n'existe plus dans la liste.")


def validate_hole_diameter(spec, hole_diameter_cm):
    hole_mm = float(hole_diameter_cm) * 10.0
    if hole_mm <= spec.nominal_diameter_mm:
        raise ValueError(
            "Le trou Ø{:.3f} mm est trop petit pour le boulon {}."
            .format(hole_mm, spec.designation)
        )
    return hole_mm
