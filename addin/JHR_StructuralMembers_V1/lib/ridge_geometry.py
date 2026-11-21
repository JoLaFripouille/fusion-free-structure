"""Deux platines verticales et leurs jarrets, calculés en centimètres."""

from dataclasses import dataclass, replace
from math import isfinite, sqrt

from . import assembly_geometry as shapes, joint_geometry as geo


VERTICAL_AXES = ((0., 0., 1.), (0., 1., 0.))
TOL = geo.PLANE_RELATION_TOLERANCE_CM


@dataclass(frozen=True)
class RidgeBeam:
    """Les bornes de section sont prises depuis l’ancrage du chemin."""

    endpoint: tuple
    interior_axis: tuple
    height_axis: tuple
    across_axis: tuple
    width_limits: tuple
    height_limits: tuple
    length: float


@dataclass(frozen=True)
class RidgeCut:
    point: tuple
    interior_normal: tuple


@dataclass(frozen=True)
class RidgePlan:
    plates: tuple
    cuts: tuple
    bolt_centres: tuple
    bolt_axis: tuple


def _ridge_plane(beams, axes):
    candidates = []
    for up in VERTICAL_AXES:
        drops = tuple(-geo.dot(axis, up) for axis in axes)
        horizontal = tuple(geo.add(axis, geo.scale(up, drop)) for axis, drop in zip(axes, drops))
        runs = tuple(geo.length(direction) for direction in horizontal)
        if min(runs) <= TOL:
            continue
        first, second = (geo.scale(direction, 1. / run) for direction, run in zip(horizontal, runs))
        if geo.length(geo.add(first, second)) <= TOL:
            across = geo.cross(up, first)
            if any(geo.length(geo.cross(geo.normalize(beam.across_axis), across)) > TOL for beam in beams):
                continue
            slopes = tuple(drop / run for drop, run in zip(drops, runs))
            height_alignment = min(abs(geo.dot(geo.normalize(beam.height_axis), up)) for beam in beams)
            candidates.append((height_alignment, up, first, slopes))
    if not candidates:
        raise ValueError("Les axes des deux poutres doivent former des versants opposés dans un même plan vertical Y ou Z.")
    _, up, normal, slopes = max(candidates, key=lambda candidate: candidate[0])
    if min(slopes) < -1e-12:
        raise ValueError("Les deux poutres doivent être horizontales ou descendre depuis le faîtage.")
    return up, normal


def _haunch(root, axis, up, normal, section_width, dims, label):
    # La cote de délardement part du pied de l’aile, sur la face verticale de la platine.
    web, _ = shapes.haunch(root, axis, up, section_width, 0., dims)
    rise, reach = dims["drop"], dims["reach"]
    heel_ratio = -geo.dot(up, normal) / geo.dot(axis, normal)
    heel_x = -rise * heel_ratio
    if reach <= heel_x + TOL:
        raise ValueError("Allonger le jarret pour conserver une semelle inclinée côté poutre.")
    web = replace(web, name=f"Âme de jarret {label}",
                  outline=tuple((x + heel_ratio*y, y) for x, y in web.outline))

    # La section longitudinale garde une épaisseur constante et se termine sur la platine.
    run = reach - heel_x
    thickness = dims["flange"]
    normal_offset = thickness * sqrt(run**2 + rise**2)
    heel_bottom = -rise - normal_offset / reach
    toe_bottom = -normal_offset / run
    across = geo.cross(axis, up)
    width = dims["flange_width"]
    sole = shapes.Plate(
        f"Semelle de jarret {label}", geo.add(root, geo.scale(across, -width/2)), axis, up,
        ((heel_x, -rise), (reach, 0.), (reach, toe_bottom), (heel_ratio*heel_bottom, heel_bottom)),
        width,
    )
    return (web, sole), sole.point(heel_ratio*heel_bottom, heel_bottom)


def _beam_plates(beam, axis, cut, across, model_up, dims, double, label):
    x_axis = geo.normalize(beam.across_axis)
    height_axis = geo.normalize(beam.height_axis)
    sign = 1. if geo.dot(height_axis, model_up) > 0 else -1.
    up = geo.scale(height_axis, sign)
    if (geo.length(geo.cross(x_axis, across)) > TOL or
            geo.length(geo.cross(up, geo.cross(x_axis, axis))) > TOL):
        raise ValueError("Orienter les âmes des deux sections dans le plan des pentes du faîtage.")
    left, right = beam.width_limits
    low, high = sorted(value*sign for value in beam.height_limits)
    if right-left <= TOL or high-low <= TOL or beam.length <= TOL:
        raise ValueError("Les dimensions de la section ou de la poutre sont insuffisantes.")
    centre = geo.add(beam.endpoint, geo.scale(x_axis, (left+right)/2))
    sections = tuple(geo.add(centre, geo.scale(up, level)) for level in (low, high))
    roots = geo.project_points_along_direction_to_plane(sections, axis, cut.point, cut.interior_normal)
    if any(geo.dot(geo.subtract(root, beam.endpoint), axis) >= beam.length-TOL for root in roots):
        raise ValueError("La coupe de faîtage dépasse l’extrémité opposée d’une poutre.")
    plates, height_points = [], list(roots)
    haunches = [(roots[0], up, "inférieur")]
    if double:
        haunches.append((roots[1], geo.scale(up, -1), "supérieur"))
    for root, local_up, side in haunches:
        parts, heel = _haunch(root, axis, local_up, cut.interior_normal, right-left,
                              dims, f"{side} {label}")
        if any(geo.dot(geo.subtract(part.point(x, y), beam.endpoint), axis) > beam.length+TOL
               for part in parts for x, y in part.outline):
            raise ValueError("Le jarret dépasse l’extrémité opposée de la poutre.")
        plates.extend(parts)
        height_points.append(heel)
    return plates, height_points, tuple(geo.add(beam.endpoint, geo.scale(x_axis, x))
                                        for x in (left, right))


def plan_ridge(joint_point, first, second, dims, double=False, washer_radius=0.):
    """Produit les tôles, les plans de coupe et le perçage commun aux deux platines."""
    beams = (first, second)
    if any(geo.length(geo.subtract(beam.endpoint, joint_point)) > geo.JOINT_ENDPOINT_TOLERANCE_CM
           for beam in beams):
        raise ValueError("Les deux poutres doivent se rejoindre par leurs extrémités.")
    if (any(not isfinite(value) or value < 0 for value in dims.values()) or
            not isfinite(washer_radius) or washer_radius < 0 or dims["thickness"] <= 0):
        raise ValueError("Les dimensions de l’assemblage doivent être finies et positives.")
    axes = tuple(geo.normalize(beam.interior_axis) for beam in beams)
    up, normal = _ridge_plane(beams, axes)
    across = geo.cross(up, normal)
    cuts = tuple(RidgeCut(geo.add(joint_point, geo.scale(n, dims["thickness"])), n)
                 for n in (normal, geo.scale(normal, -1.)))
    haunches, heights, widths = [], [], []
    for beam, axis, cut, label in zip(beams, axes, cuts, ("1", "2")):
        parts, height_points, width_points = _beam_plates(beam, axis, cut, across, up, dims, double, label)
        haunches.extend(parts)
        heights.extend(geo.dot(geo.subtract(point, joint_point), up) for point in height_points)
        widths.extend(geo.dot(geo.subtract(point, joint_point), across) for point in width_points)

    min_width, min_height = max(widths)-min(widths), max(heights)-min(heights)
    diameter = dims["hole"]
    clearance = max(diameter/2, washer_radius)
    edge = max(1.5*diameter, clearance + .1)
    gauge = (dims["gauge"] or min_width + 2*(clearance + .1)) if diameter else 0.
    width = dims["width"] or max(min_width, gauge + 2*edge)
    height = dims["height"] or min_height + 2*edge
    if width < min_width-TOL or height < min_height-TOL:
        raise ValueError("Les platines doivent couvrir les deux sections et les jarrets.")
    holes = ()
    if diameter:
        if gauge - min_width <= 2*clearance or width - gauge <= 2*clearance:
            raise ValueError("Écarter les colonnes pour dégager les ailes et ménager l’appui sur les platines.")
        rows = shapes.bolt_rows(dims["rows"], -height/2+edge, height/2-edge,
                               2*clearance+.1, span=dims["pitch"])
        holes = tuple((x, y, diameter) for x in (-gauge/2, gauge/2) for y in rows)
    elif washer_radius:
        raise ValueError("Prévoir des perçages pour poser les boulons.")

    centre = geo.add(joint_point, geo.add(geo.scale(across, (max(widths)+min(widths))/2),
                                         geo.scale(up, (max(heights)+min(heights))/2)))
    first_plate = shapes.rectangle("Platine d’about de faîtage 1", centre, across, up,
                                   width, height, dims["thickness"], holes)
    second_plate = shapes.rectangle("Platine d’about de faîtage 2", centre, geo.scale(across, -1.), up,
                                    width, height, dims["thickness"], holes)
    centres = tuple(first_plate.point(x, y) for x, y, _ in holes)
    return RidgePlan((first_plate, second_plate, *haunches), cuts, centres, normal)
