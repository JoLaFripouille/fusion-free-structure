"""Placement de boulonnerie réutilisée ; aucun accès Fusion dans ce module."""
from __future__ import annotations

import math
from dataclasses import dataclass

from . import bolt_geometry, bolt_specs, joint_geometry as vec


POSITION_TOLERANCE_CM = 0.001  # 0,01 mm, également pour les deux arêtes d'un trou.
PARALLEL_TOLERANCE = 1e-4


@dataclass(frozen=True)
class PrototypeLayout:
    nominal_diameter_mm: float
    length_mm: float
    head: str
    head_washer_cm: float
    nut_washer_cm: float
    nut_height_cm: float
    grip_cm: float
    projection_cm: float | None = None

    @property
    def designation(self):
        return "M{:g}".format(self.nominal_diameter_mm)

    @property
    def minimum_projection_cm(self):
        if self.projection_cm is not None:
            value = float(self.projection_cm)
            if not math.isfinite(value) or value < 0:
                raise ValueError("Le dépassement doit être positif ou nul et fini.")
            return value
        available = [s for s in bolt_specs.BOLT_SPECS
                     if abs(s.nominal_diameter_mm - self.nominal_diameter_mm) < 0.01]
        return available[0].thread_projection_mm * 0.1 if available else 0.0


@dataclass(frozen=True)
class Hole:
    center: tuple
    axis: tuple
    diameter_cm: float


@dataclass(frozen=True)
class Slot:
    """Oblong défini par ses deux demi-cercles, posé au milieu par défaut."""
    center: tuple
    axis: tuple
    diameter_cm: float
    slot_axis: tuple
    center_distance_cm: float

    @property
    def length_cm(self):
        return self.diameter_cm + self.center_distance_cm


@dataclass(frozen=True)
class CountersunkHole(Hole):
    """Le centre est à l'ouverture et l'axe pointe vers le fond de la fraisure."""

    opening_diameter_cm: float
    depth_cm: float

    def head_depth(self, shaft_diameter_cm):
        return self.depth_cm * (
            (self.opening_diameter_cm - shaft_diameter_cm)
            / (self.opening_diameter_cm - self.diameter_cm)
        )


def slot_from_caps(first_center, second_center, axis, radius_cm):
    first, second = _point(first_center), _point(second_center)
    shaft = vec.normalize(_point(axis))
    radius = _positive(radius_cm, "Le rayon de l'oblong")
    delta = vec.subtract(second, first)
    # Surface-cylinder origins are arbitrary along their axes; remove that
    # axial displacement before reconstructing the capsule centre.
    delta = vec.subtract(delta, vec.scale(shaft, vec.dot(delta, shaft)))
    distance = vec.length(delta)
    if distance <= POSITION_TOLERANCE_CM:
        raise ValueError("Les deux extrémités de l'oblong sont confondues.")
    return Slot(vec.add(first, vec.scale(delta, .5)), shaft, 2 * radius,
                vec.scale(delta, 1 / distance), distance)


@dataclass(frozen=True)
class SupportPlane:
    point: tuple
    normal: tuple


@dataclass(frozen=True)
class Placement:
    origin: tuple
    x_axis: tuple
    y_axis: tuple
    z_axis: tuple
    grip_cm: float
    countersink: CountersunkHole | None = None


def _positive(value, label):
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise ValueError("{} doit être positif et fini.".format(label))
    return result


def _point(value):
    result = tuple(float(x) for x in value)
    if len(result) != 3 or not all(math.isfinite(x) for x in result):
        raise ValueError("Un point ou une direction est invalide.")
    return result


def validate_parameters(layout, diameter_mm, length_mm, head):
    diameter_mm = _positive(diameter_mm, "Le diamètre")
    length_mm = _positive(length_mm, "La longueur")
    if head not in ("H", "CHC", "TBHC", "TF"):
        raise ValueError("Choisir une tête H, fraisée, cylindrique CHC ou bombée TBHC.")
    if abs(diameter_mm - layout.nominal_diameter_mm) > 0.02:
        raise ValueError("Choisir un ensemble modèle M{:g} ; le modèle sélectionné est M{:g}."
                         .format(diameter_mm, layout.nominal_diameter_mm))
    if head != layout.head:
        raise ValueError("Le modèle sélectionné a une tête {} ; sélectionner un ensemble {}."
                         .format(layout.head, head))
    return diameter_mm, length_mm, head


def same_position(first, second, tolerance_cm=POSITION_TOLERANCE_CM):
    alignment = vec.dot(first.z_axis, second.z_axis)
    if abs(alignment) < 1.0 - PARALLEL_TOLERANCE:
        return False
    delta = vec.subtract(second.origin, first.origin)
    station = vec.dot(delta, first.z_axis)
    if vec.length(vec.subtract(delta, vec.scale(first.z_axis, station))) > tolerance_cm:
        return False
    if vec.length(delta) <= tolerance_cm:
        return True
    other_end = station + alignment * second.grip_cm
    overlap = min(first.grip_cm, max(station, other_end)) - max(0.0, min(station, other_end))
    return overlap > tolerance_cm


def plan_placements(holes, head_plane, nut_plane, layout, diameter_mm,
                    length_mm, head, occupied=(), reverse=False):
    """Projette les trous choisis sur les appuis ; ne cherche pas dans le modèle."""
    validate_parameters(layout, diameter_mm, length_mm, head)
    if reverse:
        head_plane, nut_plane = nut_plane, head_plane
    hp, np = _point(head_plane.point), _point(nut_plane.point)
    hn, nn = vec.normalize(_point(head_plane.normal)), vec.normalize(_point(nut_plane.normal))
    if abs(vec.dot(hn, nn)) < 1.0 - PARALLEL_TOLERANCE:
        raise ValueError("Les deux faces d'appui doivent être parallèles.")
    holes = tuple(holes)
    if not holes:
        raise ValueError("Sélectionner au moins un perçage rond ou oblong.")
    if len(holes) > 100:
        raise ValueError("Traiter au maximum 100 perçages par pose.")
    result, ignored = [], 0
    for hole in holes:
        center, axis = _point(hole.center), vec.normalize(_point(hole.axis))
        if abs(vec.dot(hn, axis)) < 1.0 - PARALLEL_TOLERANCE:
            raise ValueError("Un perçage n'est pas perpendiculaire aux appuis choisis.")
        bolt_specs.validate_hole_diameter(layout, _positive(hole.diameter_cm, "Le trou"))
        # Les pointOnFace peuvent être très éloignés sur les mêmes plans.
        # Intersecter chaque axe avec chaque appui, sans projeter np - hp sur l'axe.
        offset = vec.dot(vec.subtract(hp, center), hn) / vec.dot(axis, hn)
        origin = vec.add(center, vec.scale(axis, offset))
        spacing = vec.dot(vec.subtract(np, origin), nn) / vec.dot(axis, nn)
        if spacing < 0:
            axis, spacing = vec.scale(axis, -1.0), -spacing
        if spacing <= POSITION_TOLERANCE_CM:
            raise ValueError("Les deux appuis sont confondus ; choisir les faces extérieures.")
        minimum = (layout.head_washer_cm + spacing + layout.nut_washer_cm
                   + layout.nut_height_cm + layout.minimum_projection_cm)
        if length_mm * 0.1 + POSITION_TOLERANCE_CM < minimum:
            raise ValueError("Vis trop courte pour ce serrage : longueur minimale {:g} mm."
                             .format(math.ceil(minimum * 10.0)))
        x_axis, y_axis, z_axis = bolt_geometry.perpendicular_axes(axis)
        seat = hole if isinstance(hole, CountersunkHole) else None
        if head == "TF":
            if not seat:
                raise ValueError("Sélectionner la face conique de chaque fraisure.")
            if vec.length(vec.subtract(origin, seat.center)) > POSITION_TOLERANCE_CM:
                raise ValueError("L'appui côté tête doit correspondre à l'ouverture de la fraisure.")
            if vec.dot(z_axis, seat.axis) < 1 - PARALLEL_TOLERANCE:
                raise ValueError("La tête fraisée doit être tournée vers l'ouverture du trou.")
            if seat.head_depth(diameter_mm * .1) >= spacing:
                raise ValueError("La tête fraisée dépasse l'épaisseur de l'assemblage.")
        item = Placement(origin, x_axis, y_axis, z_axis, spacing, seat if head == "TF" else None)
        if any(same_position(item, prior) for prior in tuple(occupied) + tuple(result)):
            ignored += 1
        else:
            result.append(item)
    return tuple(result), ignored


def modeled_washer_options(head, *, tapped=False, head_washer=None, nut_washer=None):
    """Résout la composition en conservant les valeurs par défaut historiques."""
    head_available = head != "TF"
    nut_available = not tapped
    if head_washer and not head_available:
        raise ValueError("La tête fraisée doit porter directement dans la fraisure.")
    if nut_washer and not nut_available:
        raise ValueError("La pose en trou taraudé ne comporte pas de rondelle côté écrou.")
    return (head_available if head_washer is None else bool(head_washer),
            nut_available if nut_washer is None else bool(nut_washer))


def plan_modeled_fasteners(holes, head_plane, nut_plane, diameter_mm,
                          length_mm=None, projection_mm=5., occupied=(), reverse=False,
                          head="H", *, head_washer=None, nut_washer=None):
    """Planifie la vis, l'écrou et les rondelles choisies.

    Le dépassement demandé est mesuré après la face extérieure de l'écrou.
    Aucune validation de résistance ou de couverture d'un oblong n'est déduite.
    """
    diameter = _positive(diameter_mm, "Le diamètre")
    projection = float(projection_mm)
    if not math.isfinite(projection) or projection < 0:
        raise ValueError("Le dépassement doit être positif ou nul et fini.")
    spec, _ = bolt_specs.modeled_spec(diameter, head)
    head_washer, nut_washer = modeled_washer_options(head, head_washer=head_washer, nut_washer=nut_washer)
    washer_cm = spec.washer_thickness_mm * .1
    layout = PrototypeLayout(diameter, length_mm or 1., head,
                             washer_cm if head_washer else 0.,
                             washer_cm if nut_washer else 0.,
                             spec.nut_height_mm * .1, 1., projection * .1)
    holes = tuple(holes)
    # Reuse the established support intersection and duplicate checks. A first
    # pass obtains grips without choosing a physical screw length yet.
    poses, ignored = plan_placements(holes, head_plane, nut_plane, layout,
                                     diameter, 1e6, head, occupied, reverse)
    if not poses:
        return spec, (), ignored, length_mm
    minimum = max((p.grip_cm + layout.head_washer_cm + layout.nut_washer_cm
                   + layout.nut_height_cm + layout.minimum_projection_cm) * 10
                  for p in poses)
    chosen = (math.ceil((minimum - 1e-8) / bolt_geometry.LENGTH_STEP_MM)
              * bolt_geometry.LENGTH_STEP_MM) if length_mm is None else _positive(length_mm, "La longueur")
    poses, ignored = plan_placements(holes, head_plane, nut_plane, layout,
                                     diameter, chosen, head, occupied, reverse)
    return spec, poses, ignored, chosen


def adaptation_plan(layout, length_mm, grip_cm):
    """Bornes de la copie du prototype ; la tête et les rondelles ne sont pas redessinées."""
    _positive(length_mm, "La longueur")
    _positive(grip_cm, "Le serrage")
    tip = length_mm * 0.1 - layout.head_washer_cm
    nut_top = grip_cm + layout.nut_washer_cm + layout.nut_height_cm
    if tip + POSITION_TOLERANCE_CM < nut_top + layout.minimum_projection_cm:
        raise ValueError("La longueur choisie ne laisse pas passer l'écrou.")
    return {
        "cut_cm": min(layout.grip_cm, grip_cm) / 2.0,
        "grip_delta_cm": grip_cm - layout.grip_cm,
        "old_tip_after_move_cm": layout.length_mm * 0.1 - layout.head_washer_cm
                                 + grip_cm - layout.grip_cm,
        "new_tip_cm": tip,
    }


def configuration_name(diameter_mm, length_mm, head, grip_cm, *, head_washer=None, nut_washer=None):
    tapped = head.endswith("-Taraudage")
    head_kind = head.removesuffix("-Taraudage")
    head_washer, nut_washer = modeled_washer_options(head_kind, tapped=tapped,
                                                    head_washer=head_washer, nut_washer=nut_washer)
    if tapped:
        suffix = " + 1 RONDELLE" if head_washer else ""
        return "VIS {} M{:g}x{:g} - TARAUDAGE{}".format(head_kind, diameter_mm, length_mm, suffix)
    if head_washer and nut_washer:
        washers = "2 RONDELLES"
    elif head_washer:
        washers = "1 RONDELLE SOUS TETE"
    elif nut_washer:
        washers = "1 RONDELLE" if head == "TF" else "1 RONDELLE SOUS ECROU"
    else:
        washers = "0 RONDELLE"
    return "BOULON {} M{:g}x{:g} - SERRAGE {:g} mm - 1 ECROU + {}".format(
        head, diameter_mm, length_mm, round(grip_cm * 10.0, 3), washers)


def _six_hex_sides(planes):
    angles = []
    for angle in sorted(p[3] % (2 * math.pi) for p in planes):
        if not angles or angle - angles[-1] > 0.0005:
            angles.append(angle)
    if len(angles) > 1 and angles[0] + 2 * math.pi - angles[-1] < 0.0005:
        angles.pop()
    if len(angles) != 6:
        return False
    gaps = [((angles[(i + 1) % 6] - angles[i]) % (2 * math.pi)) for i in range(6)]
    return all(abs(gap - math.pi / 3) < 0.01 for gap in gaps)


def recognize_sections(diameter_mm, length_mm, tip_station, cylinders,
                       side_planes, wide_faces):
    """Reconnaissance bornée d'un ensemble simple déjà dessiné.

    Cylindres : (rayon, début axial, fin axiale), plans latéraux :
    (début, fin, distance radiale, angle de normale), grandes faces : (début, fin).
    Toutes les dimensions sont en cm dans le repère de la vis.
    Aucun diamètre de rondelle ou d'écrou n'est créé à partir d'un nom.
    """
    diameter_mm = _positive(diameter_mm, "Le diamètre du modèle")
    length_mm = _positive(length_mm, "La longueur du modèle")
    radius, tolerance = diameter_mm * 0.05, 0.005
    under_head = tip_station - length_mm * 0.1
    rings = sorted(set(tuple(round(v, 7) for v in row) for row in cylinders))
    head_rings = [c for c in rings if c[0] > radius * 1.05
                  and abs(c[1] - under_head) < tolerance
                  and 0.03 < c[2] - c[1] < diameter_mm * 0.06]
    if len(head_rings) != 1:
        raise ValueError("Rondelle sous tête non reconnue ; choisir un ensemble complet "
                         "et renseigner sa longueur de vis réelle.")
    hr = head_rings[0]
    other_rings = [c for c in rings if abs(c[0] - hr[0]) < tolerance
                   and abs((c[2] - c[1]) - (hr[2] - hr[1])) < tolerance
                   and c[1] > hr[2] + POSITION_TOLERANCE_CM]
    if len(other_rings) != 1:
        raise ValueError("La rondelle côté écrou n'est pas reconnue dans ce modèle.")
    nr = other_rings[0]
    outer_hex = [p for p in side_planes if p[1] <= under_head + tolerance
                 and p[2] > radius * 1.1]
    socket_hex = [p for p in side_planes if p[1] <= under_head + tolerance
                  and p[2] < radius * 1.1]
    round_head = [c for c in rings if c[0] > radius * 1.1
                  and c[2] <= under_head + tolerance and c[2] - c[1] > tolerance]
    if _six_hex_sides(outer_hex) and not round_head:
        head = "H"
    elif round_head and _six_hex_sides(socket_hex):
        head = "CHC"
    else:
        raise ValueError("Tête H ou CHC non reconnue géométriquement ; modèle refusé.")
    nut_sides = [p for p in side_planes if p[0] >= nr[2] - tolerance
                 and p[2] > radius * 1.1]
    nut_faces = [p for p in wide_faces if p[0] >= nr[2] - tolerance]
    if not _six_hex_sides(nut_sides) or not nut_faces:
        raise ValueError("Un écrou hexagonal complet est requis dans le modèle.")
    nut_height = max(p[1] for p in nut_faces) - nr[2]
    if nut_height <= tolerance or max(p[1] for p in nut_faces) > tip_station + tolerance:
        raise ValueError("Écrou ou extrémité de vis incohérent dans le modèle.")
    layout = PrototypeLayout(diameter_mm, length_mm, head, hr[2] - hr[1],
                             nr[2] - nr[1], nut_height, nr[1] - hr[2])
    return layout, hr[2]
