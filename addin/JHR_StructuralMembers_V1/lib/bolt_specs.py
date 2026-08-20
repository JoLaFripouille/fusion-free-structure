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
