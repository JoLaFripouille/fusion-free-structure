"""Goussets de contreventement, calculés en centimètres."""

from dataclasses import dataclass
from itertools import combinations
from math import atan2, hypot, isfinite, radians, tau

from . import joint_geometry as geo
from .assembly_geometry import DimensionError, Plate


TOL = geo.PLANE_RELATION_TOLERANCE_CM


@dataclass(frozen=True)
class GussetArm:
    """Axe médian de la bande pleine, orienté de la jonction vers l’extérieur."""

    near: tuple
    far: tuple
    normal: tuple
    clear_width_cm: float
    thickness_cm: float
    flanges_bound_plate: bool = False
    bearing_offsets_cm: tuple[float, float] | None = None


@dataclass(frozen=True)
class GussetPlan:
    plate: Plate
    centres_by_arm: tuple  # Points mondiaux sur la face d’appui, ordre de sélection.
    arm_order: tuple       # Indices trigonométriques dans le repère de la tôle.


def support_weld(arm, normal, origin, section_axes, outer, web, *,
                 thickness_cm, face=0, position=0, offset_cm=0.):
    """Pose perpendiculaire à l’aile ou à l’une des faces exposées de l’âme."""
    alignments = tuple(geo.dot(normal, axis) for axis in section_axes)
    across = max(range(2), key=lambda index: abs(alignments[index])) if face == 0 else int(face)-1
    alignment = alignments[across]
    if abs(alignment) < 1.-TOL:
        raise ValueError("Le plan de la cornière doit être perpendiculaire à la face d’appui choisie.")
    face_axis = section_axes[1-across]
    span_axis = section_axes[across]
    face_bounds = outer[1] if across == 0 else web[0]
    span_bounds = outer[0] if across == 0 else web[1]
    positive_face = geo.dot(geo.subtract(arm.far, origin), face_axis) >= sum(face_bounds)/2
    face_level = face_bounds[int(positive_face)]
    natural_face = geo.dot(geo.subtract(arm.near, origin), span_axis) + alignment*arm.thickness_cm/2
    centre = sum(web[across])/2
    if position == 0:
        start = natural_face
    else:
        centre += offset_cm if position == 2 else 0.
        start = centre - alignment*thickness_cm/2
        if abs(start-natural_face) > TOL:
            raise ValueError("Aligner la face de la cornière sur la position choisie du gousset.")
    stop = start+alignment*thickness_cm
    low, high = span_bounds
    if min(start, stop) < low+TOL or max(start, stop) > high-TOL:
        feature = "l’aile du porteur" if across == 0 else "la zone libre de l’âme entre les congés"
        raise ValueError(f"Le chant du gousset déborde de {feature}.")
    offset = geo.add(geo.scale(span_axis, start), geo.scale(face_axis, face_level))
    inside = geo.scale(face_axis, -.02 if positive_face else .02)
    return offset, inside


def brace_clearance(points, weld_point, outward):
    return min(geo.dot(geo.subtract(point, weld_point), outward) for point in points)


def brace_end_shift(clearance, wanted, axis, outward):
    rate = geo.dot(axis, outward)
    if rate <= .05:
        raise ValueError("La cornière est presque parallèle à l’appui. Le jeu d’about ne peut pas être réglé.")
    return (wanted-clearance)/rate


def _turn(a, b, c):
    return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])


def _hull(points):
    def chain(ordered):
        vertices = []
        for point in ordered:
            while len(vertices) >= 2 and _turn(vertices[-2], vertices[-1], point) <= TOL ** 2:
                vertices.pop()
            vertices.append(point)
        return vertices[:-1]

    points = sorted(set(points))
    return tuple(chain(points) + chain(reversed(points)))


def _clip_rectangle(points, directions):
    """Conserve quatre chants d’équerre et coupe les coins suivant les diagonales."""
    x, y = zip(*points)
    outline = ((min(x), min(y)), (max(x), min(y)), (max(x), max(y)), (min(x), max(y)))
    for direction in directions:
        limit = max(geo.dot(point, direction) for point in points)
        distances = tuple(geo.dot(point, direction)-limit for point in outline)
        sides = tuple(0. if abs(distance) <= TOL else distance for distance in distances)
        clipped = []
        for a, b, sa, sb in zip(outline, outline[1:] + outline[:1], sides, sides[1:] + sides[:1]):
            if sa <= 0.:
                clipped.append(a)
            if sa*sb < 0.:
                clipped.append(geo.add(a, geo.scale(geo.subtract(b, a), sa/(sa-sb))))
        outline = tuple(clipped)
    if len(outline) != 8:
        raise ValueError("Les dimensions et les angles des cornières ne permettent pas de conserver quatre coins coupés.")
    return outline


def _straight_edge_scallops(outline, centres, depth, edge_distance, washer_radius):
    """Évide les quatre chants, en gardant les coupes d’angle et les appuis des rondelles."""
    key = ("scallop_depth_mm",)
    if not isfinite(depth) or depth < 0.:
        raise DimensionError(key, "La profondeur de l’arrondi doit être positive.")
    arcs = []
    for index, (a, b) in enumerate(zip(outline, outline[1:] + outline[:1])):
        delta = geo.subtract(b, a)
        if min(map(abs, delta)) > TOL:
            continue
        half = hypot(*delta)/2
        if depth >= half-TOL:
            raise DimensionError(key, "La profondeur dépasse la moitié du chant droit le plus court.")
        u = geo.normalize(delta)
        inward = (-u[1], u[0])
        middle = geo.scale(geo.add(a, b), .5)
        radius = (half**2+depth**2)/(2*depth)
        centre = geo.add(middle, geo.scale(inward, depth-radius))
        cosine = (radius-depth)/radius
        for hole in centres:
            radial = geo.subtract(hole, centre)
            distance = hypot(*radial)
            clearance = (distance-radius if geo.dot(radial, inward) >= cosine*distance else
                         min(hypot(*geo.subtract(hole, p)) for p in (a, b)))
            if clearance < max(edge_distance, washer_radius)+TOL:
                raise DimensionError(key, "L’évidement approche trop d’un perçage ou de sa rondelle.")
        arcs.append((index, geo.add(middle, geo.scale(inward, depth))))
    if len(arcs) != 4:
        raise DimensionError(key, "Les quatre chants droits du contour sont introuvables.")
    return tuple(arcs)


def _check_web_clearance(outline, foot, direction, width, length, arm_number):
    """Contrôle le contour au droit de la barre, entre ses deux extrémités."""
    across = (-direction[1], direction[0])
    local = tuple((geo.dot(geo.subtract(point, foot), direction),
                   geo.dot(geo.subtract(point, foot), across)) for point in outline)
    offsets = [y for x, y in local if 0 <= x <= length]
    for (x1, y1), (x2, y2) in zip(local, local[1:] + local[:1]):
        for station in (0, length):
            if min(x1, x2) < station < max(x1, x2):
                offsets.append(y1 + (y2 - y1) * (station - x1) / (x2 - x1))
    if any(abs(offset) >= width / 2 - TOL for offset in offsets):
        raise ValueError(f"Le contour du gousset rencontre une aile ou un congé de la diagonale {arm_number}.")


def supported_gusset(arms, weld_edge, *, thickness_cm, hole_diameter_cm, rows,
                     end_distance_cm, pitch_cm, edge_distance_cm, pad_width_cm=0.,
                     washer_radius_cm=0., alternate=False, weld_length_cm=0.):
    """Gousset de 1 à 3 diagonales, avec un chant soudé sur l’aile du profil porteur."""
    arms = tuple(arms)
    if not 1 <= len(arms) <= 3:
        raise ValueError("Sélectionner une à trois diagonales pour le gousset d’extrémité.")
    dimensions = (thickness_cm, hole_diameter_cm, end_distance_cm, pitch_cm, edge_distance_cm)
    if (any(not isfinite(value) or value <= 0 for value in dimensions)
            or any(not isfinite(value) or value < 0
                   for value in (pad_width_cm, washer_radius_cm, weld_length_cm))):
        raise ValueError("Les cotes du gousset et des perçages sont incompatibles.")
    radius = max(hole_diameter_cm / 2, washer_radius_cm)
    half_pad = pad_width_cm / 2 if pad_width_cm else edge_distance_cm
    if rows not in (2, 3) or min(edge_distance_cm, half_pad) <= radius + TOL:
        raise ValueError("Le nombre de trous, la distance au chant ou la largeur du gousset est incompatible.")
    if half_pad + TOL < edge_distance_cm or end_distance_cm + TOL < edge_distance_cm or pitch_cm <= 2*radius + TOL:
        raise ValueError("Vérifier le recul, l’entraxe et la largeur autour des trous.")
    normal = geo.scale(geo.normalize(arms[0].normal), -1 if alternate else 1)
    origin, end = weld_edge
    length = geo.length(geo.subtract(end, origin))
    u = geo.normalize(geo.subtract(end, origin))
    if abs(geo.dot(normal, u)) > TOL:
        raise ValueError("Le chant à souder doit suivre le plan des diagonales.")
    v = geo.cross(normal, u)
    if geo.dot(geo.subtract(arms[0].far, origin), v) < 0:
        origin, u, v = end, geo.scale(u, -1), geo.scale(v, -1)

    pads, centres, roots = [], [], []
    last = end_distance_cm + (int(rows)-1)*pitch_cm
    for index, arm in enumerate(arms, 1):
        if abs(geo.dot(normal, geo.normalize(arm.normal))) < 1.-TOL:
            raise ValueError("Les faces d’appui des diagonales doivent être parallèles.")
        if edge_distance_cm > arm.clear_width_cm/2 + TOL:
            raise ValueError(f"La face pleine de la diagonale {index} est trop étroite.")
        delta = geo.subtract(arm.far, arm.near)
        if geo.length(delta) < last+edge_distance_cm-TOL:
            raise ValueError(f"Les perçages dépassent la diagonale {index}.")
        axis = geo.normalize(delta)
        face = geo.add(arm.near, geo.scale(normal, arm.thickness_cm/2))
        offset = geo.subtract(face, origin)
        if abs(geo.dot(axis, normal)) > TOL or abs(geo.dot(offset, normal)) > TOL:
            raise ValueError("Les faces d’appui et le chant du gousset doivent être coplanaires.")
        x, y = geo.dot(offset, u), geo.dot(offset, v)
        dx, dy = geo.dot(axis, u), geo.dot(axis, v)
        if dy <= .05 or y < -TOL:
            raise ValueError("Les diagonales doivent partir de l’aile vers le même côté.")
        root = x-y*dx/dy
        # L’assise couvre la projection de la bande boulonnée et s’évase au porteur.
        spread = max(half_pad/dy, half_pad*2)
        roots.append((root, spread))
        local_axis, foot = (dx, dy), (x, y)
        centres.append(tuple(geo.add(foot, geo.scale(local_axis, end_distance_cm+i*pitch_cm))
                             for i in range(int(rows))))
        width = geo.scale((-dy, dx), half_pad)
        for station in (end_distance_cm-edge_distance_cm, last+edge_distance_cm):
            centre = geo.add(foot, geo.scale(local_axis, station))
            pads.extend((geo.add(centre, width), geo.subtract(centre, width)))
    if len(arms) == 1:
        direction = 1. if dx >= 0. else -1.
        arm = arms[0]
        bearing = arm.bearing_offsets_cm or (-arm.clear_width_cm/2, arm.clear_width_cm/2)
        if geo.dot(normal, arm.normal) < 0:
            bearing = (-bearing[1], -bearing[0])
        low, high = sorted(direction*offset for offset in bearing)
        low = min(low, -half_pad)
        high = max(high+.1, half_pad)
        slant = abs(dx)
        station = last+edge_distance_cm
        # Le chant en bout coupe la pleine largeur de l'aile à 90° de la cornière.
        # Le coin côté retour doit aussi laisser la distance au chant au dernier trou.
        if slant > TOL:
            station = max(station, last+(edge_distance_cm+dy*low)/slant)
        weld_diagonal = direction*root-high/dy
        weld_return = direction*x+slant*station-dy*low
        if weld_length_cm:
            extension = (weld_length_cm-(weld_return-weld_diagonal))/(dy+1/dy)
            if extension < -TOL:
                raise ValueError("Le chant demandé est trop court pour couvrir toute l’aile de la cornière.")
            low -= extension
            high += extension
            weld_diagonal = direction*root-high/dy
            weld_return = direction*x+slant*station-dy*low
        tip_origin = (direction*x+slant*station, y+dy*station)
        across = (-dy, slant)
        tip_return = geo.add(tip_origin, geo.scale(across, low))
        tip_diagonal = geo.add(tip_origin, geo.scale(across, high))
        if tip_return[1] <= TOL:
            raise ValueError("Le bout d’équerre à la cornière rencontre le profil porteur.")
        points = ((weld_diagonal, 0.), (weld_return, 0.), tip_return, tip_diagonal)
        outline = tuple((direction*px, py) for px, py in points)
        if direction < 0:
            outline = tuple(reversed(outline))
    else:
        weld_start = min(root-spread for root, spread in roots)
        weld_end = max(root+spread for root, spread in roots)
        if weld_length_cm:
            middle = (weld_start+weld_end)/2
            weld_start, weld_end = middle-weld_length_cm/2, middle+weld_length_cm/2
        if any(y < -TOL for _, y in pads):
            raise ValueError("Le gousset descend dans l’aile du profil porteur.")
        outline = _hull(pads+[(weld_start, 0.), (weld_end, 0.)])
    weld = [x for x, y in outline if abs(y) <= TOL]
    if min(weld) < -TOL or max(weld) > length+TOL:
        raise ValueError("Le chant à souder dépasse l’about du profil porteur.")
    outline = tuple((max(0., min(length, x)), 0.) if abs(y) <= TOL else (x, y) for x, y in outline)
    all_centres = tuple(point for group in centres for point in group)
    if any(hypot(*geo.subtract(a, b)) <= 2*radius+TOL for a, b in combinations(all_centres, 2)):
        raise ValueError("Des perçages ou appuis de rondelle se touchent.")
    for a, b in zip(outline, outline[1:] + outline[:1]):
        if any(hypot(*geo.subtract(hole, geo.closest_point_on_segment(hole, a, b)[0]))+TOL
               < edge_distance_cm for hole in all_centres):
            raise ValueError("Un perçage est trop près d’un chant du gousset.")
    plate = Plate("Gousset d’extrémité", origin, u, v, outline, thickness_cm,
                  tuple((*point, hole_diameter_cm) for point in all_centres))
    return GussetPlan(plate, tuple(tuple(plate.point(*point) for point in group) for group in centres),
                      tuple(range(len(arms))))


def central_gusset(arms, *, thickness_cm, hole_diameter_cm, rows, end_distance_cm,
                   pitch_cm, edge_distance_cm, pad_width_cm=0., washer_radius_cm=0., alternate=False,
                   level_outline=False, bearing_vertical=None, scallop_depth_cm=0.):
    """Relie quatre faces d’appui coplanaires par un contour convexe.

    Les reculs et les distances au chant se mesurent depuis les axes des trous.
    La normale de la première diagonale désigne le côté d'appui de référence.
    """
    arms = tuple(arms)
    if len(arms) != 4:
        raise ValueError("Sélectionner quatre diagonales pour le gousset central.")
    dimensions = (thickness_cm, hole_diameter_cm, end_distance_cm, pitch_cm, edge_distance_cm)
    if (any(not isfinite(value) or value <= 0 for value in dimensions)
            or any(not isfinite(value) or value < 0 for value in (pad_width_cm, washer_radius_cm))):
        raise ValueError("Les cotes du gousset et des perçages sont incompatibles.")
    if rows not in (2, 3):
        raise ValueError("Choisir deux ou trois trous par diagonale.")
    radius = max(hole_diameter_cm / 2, washer_radius_cm)
    pad_half_width = pad_width_cm / 2 if pad_width_cm else edge_distance_cm
    if edge_distance_cm <= radius + TOL or pad_half_width + TOL < edge_distance_cm:
        raise ValueError("Augmenter la distance au chant ou la largeur des extrémités du gousset.")
    if pitch_cm <= 2 * radius + TOL:
        raise ValueError("L’entraxe doit séparer les perçages et leurs appuis.")
    if end_distance_cm + TOL < edge_distance_cm:
        raise ValueError("Le premier perçage est trop près de l’extrémité d’une diagonale.")

    for arm in arms:
        if (any(len(vector) != 3 or not all(isfinite(coord) for coord in vector)
                for vector in (arm.near, arm.far, arm.normal))
                or any(not isfinite(value) or value <= 0 for value in (arm.clear_width_cm, arm.thickness_cm))):
            raise ValueError("Les points d’axe, normales ou sections des diagonales sont invalides.")

    normal = geo.scale(geo.normalize(arms[0].normal), -1 if alternate else 1)
    lengths = tuple(geo.length(geo.subtract(arm.far, arm.near)) for arm in arms)
    last = end_distance_cm + (int(rows) - 1) * pitch_cm
    for index, (arm, length) in enumerate(zip(arms, lengths), start=1):
        if last + edge_distance_cm > length + TOL:
            raise ValueError(f"Le recul, l’entraxe et le nombre de trous dépassent la diagonale {index}.")
        if arm.clear_width_cm / 2 + TOL < edge_distance_cm:
            raise ValueError(f"La bande pleine de la diagonale {index} est trop étroite pour les perçages.")

    def contact(point, arm):
        return geo.add(point, geo.scale(normal, arm.thickness_cm / 2))

    support = tuple(contact(arm.near, arm) for arm in arms)
    origin = tuple(sum(coord) / 4 for coord in zip(*support))
    if any(geo.length(geo.cross(normal, geo.normalize(arm.normal))) > TOL for arm in arms):
        raise ValueError("Les normales d’appui des quatre diagonales doivent être parallèles.")
    if any(abs(geo.dot(geo.subtract(contact(point, arm), origin), normal)) > TOL
           for arm in arms for point in (arm.near, arm.far)):
        raise ValueError("Les quatre faces d’appui doivent être coplanaires du même côté.")

    directions = tuple(geo.normalize(geo.cross(geo.cross(normal, geo.subtract(arm.far, arm.near)), normal))
                       for arm in arms)
    if level_outline or bearing_vertical:
        vertical = geo.cross(geo.cross(normal, bearing_vertical or (0., 0., 1.)), normal)
        if geo.length(vertical) < TOL:
            u = geo.normalize(geo.cross(geo.cross(normal, (1., 0., 0.)), normal))
        else:
            u = geo.normalize(geo.cross(vertical, normal))
    else:
        u = directions[0]
    v = geo.cross(normal, u)

    def local(vector):
        return geo.dot(vector, u), geo.dot(vector, v)

    feet = tuple(local(geo.subtract(point, origin)) for point in support)
    axes = tuple(local(direction) for direction in directions)
    if any(geo.dot(foot, axis) < -TOL for foot, axis in zip(feet, axes)):
        raise ValueError("Les extrémités proches doivent se trouver au centre et les axes partir vers l’extérieur.")
    angles = tuple(atan2(axis[1], axis[0]) % tau for axis in axes)
    order = tuple(sorted(range(4), key=angles.__getitem__))
    gaps = tuple((angles[b] - angles[a]) % tau for a, b in zip(order, order[1:] + order[:1]))
    if min(gaps) < radians(geo.MINIMUM_JOIN_ANGLE_DEGREES) or max(gaps) >= tau / 2:
        raise ValueError("Les axes doivent former quatre branches distinctes autour du gousset.")

    pads, centres = [], []
    for foot, axis, arm in zip(feet, axes, arms):
        first_point = geo.add(foot, geo.scale(axis, end_distance_cm))
        centres.append(tuple(geo.add(first_point, geo.scale(axis, index * pitch_cm))
                             for index in range(int(rows))))
        low, high = -pad_half_width, pad_half_width
        if bearing_vertical and arm.bearing_offsets_cm:
            bearing = arm.bearing_offsets_cm
            if geo.dot(normal, arm.normal) < 0:
                bearing = (-bearing[1], -bearing[0])
            low, high = min(low, bearing[0]), max(high, bearing[1])
        across = (-axis[1], axis[0])
        for station in (end_distance_cm - edge_distance_cm, last + edge_distance_cm):
            pad_centre = geo.add(foot, geo.scale(axis, station))
            pads.extend(geo.add(pad_centre, geo.scale(across, offset)) for offset in (low, high))

    all_centres = tuple(point for group in centres for point in group)
    if any(hypot(*geo.subtract(a, b)) <= 2 * radius + TOL for a, b in combinations(all_centres, 2)):
        raise ValueError("Des perçages ou des appuis de deux diagonales se touchent.")
    if bearing_vertical:
        outline = _clip_rectangle(pads, axes)
    elif level_outline:
        xs, ys = zip(*all_centres)
        xmin, xmax = min(xs)-pad_half_width, max(xs)+pad_half_width
        ymin, ymax = min(ys)-pad_half_width, max(ys)+pad_half_width
        outline = ((xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax))
    else:
        outline = _hull(pads)
    for a, b in zip(outline, outline[1:] + outline[:1]):
        edge_length = hypot(*geo.subtract(b, a))
        if any(_turn(a, b, hole) / edge_length + TOL < edge_distance_cm for hole in all_centres):
            raise ValueError("Un perçage est trop près du chant du gousset.")
    for index, (arm, foot, axis, length) in enumerate(zip(arms, feet, axes, lengths), start=1):
        if arm.flanges_bound_plate:
            _check_web_clearance(outline, foot, axis, arm.clear_width_cm, length, index)

    arcs = (_straight_edge_scallops(outline, all_centres, scallop_depth_cm, edge_distance_cm, radius)
            if scallop_depth_cm else ())
    plate = Plate("Gousset central", origin, u, v, outline, thickness_cm,
                  tuple((*point, hole_diameter_cm) for point in all_centres), arcs)
    return GussetPlan(plate, tuple(tuple(plate.point(*point) for point in group) for group in centres), order)
