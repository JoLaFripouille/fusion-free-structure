"""Préparation et coupe d'un croisement de deux cornières continues."""

from dataclasses import dataclass
from math import hypot, isfinite, radians, sin, sqrt

from . import joint_geometry as geo


ATTRIBUTE_GROUP = "EI_JHR_CrossingBrace"
TOL = geo.PLANE_RELATION_TOLERANCE_CM


@dataclass(frozen=True)
class CrossingCut:
    centre: tuple
    axis: tuple
    fraction: float
    half_gap_cm: float
    profile_radius_cm: float
    branches: tuple


def _envelope(member, axis, normal):
    """Dégagement transversal et rayon du rectangle de coupe autour de l’ancrage."""
    across = geo.cross(normal, axis)
    xmin, ymin, xmax, ymax = member.bounds
    ax, ay = member.anchor
    offset_x = ((xmin-ax)*.1, (xmax-ax)*.1)
    offset_y = ((ymin-ay)*.1, (ymax-ay)*.1)
    a, b = (geo.dot(direction, across) for direction in (member.section_x, member.section_y))
    half_width = max(abs(x*a+y*b) for x in offset_x for y in offset_y)
    radius = hypot(max(map(abs, offset_x)), max(map(abs, offset_y)))
    return half_width, radius


def plan(members, clearance_cm):
    """Calcule deux coupes d’équerre par barre à partir du croisement des axes."""
    if len(members) != 2 or any(not member.family.startswith("Corniere") for member in members):
        raise ValueError("Sélectionner deux cornières continues.")
    if not isfinite(clearance_cm) or clearance_cm < 0.:
        raise ValueError("Le jeu entre cornières doit être positif ou nul.")
    endpoints = tuple(
        (tuple(line.startPoint.asArray()), tuple(line.endPoint.asArray()))
        for line in (member.curve.worldGeometry for member in members)
    )
    spans = tuple(geo.subtract(end, start) for start, end in endpoints)
    lengths = tuple(geo.length(span) for span in spans)
    u, v = (geo.normalize(span) for span in spans)
    cosine = geo.dot(u, v)
    sine = geo.length(geo.cross(u, v))
    if sine < sin(radians(geo.MINIMUM_JOIN_ANGLE_DEGREES)):
        raise ValueError("Les cornières forment un angle trop faible pour un gousset central.")
    normal = geo.scale(geo.cross(u, v), 1./sine)
    q = geo.subtract(endpoints[1][0], endpoints[0][0])
    if abs(geo.dot(q, normal)) > TOL:
        raise ValueError("Les axes des deux cornières doivent se croiser dans le même plan.")
    along_u, along_v = geo.dot(q, u), geo.dot(q, v)
    stations = ((along_u-cosine*along_v)/sine**2, (cosine*along_u-along_v)/sine**2)
    envelopes = tuple(_envelope(member, axis, normal) for member, axis in zip(members, (u, v)))
    cuts = []
    for index, axis in enumerate((u, v)):
        start, end = endpoints[index]
        length, station = lengths[index], stations[index]
        width, radius = envelopes[index]
        other_width = envelopes[1-index][0]
        half_gap = (other_width + abs(cosine)*width + clearance_cm)/sine
        if min(station, length-station) <= half_gap+TOL:
            raise ValueError(f"Le croisement ou le dégagement sort de la cornière {index+1}.")
        centre = geo.add(start, geo.scale(axis, station))
        shift = geo.scale(axis, half_gap)
        cuts.append(CrossingCut(
            centre, axis, station/length, half_gap, radius,
            ((geo.subtract(centre, shift), start), (geo.add(centre, shift), end)),
        ))
    return tuple(cuts)


def is_branch(body):
    return bool(body.attributes.itemByName(ATTRIBUTE_GROUP, "branch"))


def branch_endpoints(body, occurrence, curve):
    """Reporte les abouts physiques du solide choisi sur l’axe du profil continu."""
    from . import joint_builder as joints

    start, end = joints._line_endpoints(curve)
    axis = geo.normalize(geo.subtract(end, start))
    projections = [geo.dot(geo.subtract(point, start), axis)
                   for point in joints._body_sample_points(body, occurrence)]
    if not projections or max(projections)-min(projections) <= TOL:
        raise ValueError("Les abouts physiques de la branche sont introuvables.")
    return tuple(geo.add(start, geo.scale(axis, distance))
                 for distance in (min(projections), max(projections)))


def create(member, cut, created_entities):
    """Retire le milieu du profil existant et renvoie ses deux corps conservés."""
    import adsk.core as core
    from . import angle_cleat_creator, joint_builder as joints

    occurrence = member.occurrence
    component = occurrence.component
    body = joints._single_body(occurrence, "à couper au croisement")
    physical = branch_endpoints(body, occurrence, member.curve)
    before = tuple(geo.dot(geo.subtract(point, cut.centre), cut.axis) for point in physical)
    if before[0] >= -cut.half_gap_cm-TOL or before[1] <= cut.half_gap_cm+TOL:
        raise ValueError("La matière de la cornière ne passe plus de part et d’autre de la coupe.")
    plane = joints._add_path_plane(component, occurrence, member.curve, cut.fraction,
                                   "Station centrale du croisement")
    created_entities.append(plane)
    joints._validate_plane_match(plane, occurrence, cut.centre, cut.axis)
    sketch = component.sketches.add(plane)
    if not sketch:
        raise RuntimeError("Fusion a refusé l’esquisse de coupe du croisement.")
    created_entities.append(sketch)
    sketch.name = "Dégagement du croisement"
    radius = cut.profile_radius_cm+.2
    sketch.sketchCurves.sketchLines.addTwoPointRectangle(
        core.Point3D.create(-radius, -radius, 0.), core.Point3D.create(radius, radius, 0.),
    )
    if sketch.profiles.count != 1:
        raise RuntimeError("Le contour du dégagement n'est pas fermé.")
    feature = angle_cleat_creator._extrude_symmetric_cuts(
        component, body, sketch.profiles.item(0), 2*cut.half_gap_cm, "Coupe centrale de la cornière",
    )
    created_entities.append(feature)
    sketch.isVisible = False
    if component.bRepBodies.count != 2:
        raise RuntimeError("La coupe centrale doit produire exactement deux branches solides.")
    branches = []
    for remaining in component.bRepBodies:
        ends = branch_endpoints(remaining, occurrence, member.curve)
        stations = tuple(geo.dot(geo.subtract(point, cut.centre), cut.axis) for point in ends)
        branches.append((stations, remaining))
    branches.sort(key=lambda item: item[0])
    for index, ((low, high), remaining) in enumerate(branches):
        expected = (before[0], -cut.half_gap_cm) if index == 0 else (cut.half_gap_cm, before[1])
        if not remaining.isSolid or max(abs(low-expected[0]), abs(high-expected[1])) > TOL:
            raise RuntimeError("Une branche a perdu son alignement ou sa longueur après la coupe.")
        marker = remaining.attributes.add(ATTRIBUTE_GROUP, "branch", str(index))
        created_entities.append(marker)
    return tuple(remaining for _, remaining in branches)
