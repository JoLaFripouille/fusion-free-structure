"""Couvre-joint extérieur et contreplaque biaise pour une aile UPN."""

from dataclasses import dataclass

from . import assembly_geometry as shapes, joint_geometry as geo


TOL = geo.PLANE_RELATION_TOLERANCE_CM
EDGE_MARGIN_CM = .1
THIN_EDGE_CM = .3


@dataclass(frozen=True)
class InclinedSeat:
    start_cm: float
    end_cm: float
    start_depth_cm: float
    end_depth_cm: float

    def depth_at(self, station):
        fraction = (station-self.start_cm)/(self.end_cm-self.start_cm)
        return self.start_depth_cm + fraction*(self.end_depth_cm-self.start_depth_cm)


@dataclass(frozen=True)
class WedgePlate(shapes.Plate):
    thickness_edges_cm: tuple = ()


def inclined_seats(bounds_mm, segments):
    """Retrouve les segments rectilignes tangents entre les congés des ailes."""
    bottom, back, top, toe = bounds_mm
    mid_height = (bottom+top)/2
    min_span = (toe-back)/4
    result = []
    for outside, sign in ((bottom, 1), (top, -1)):
        lines = []
        for p, q in segments:
            near, far = sorted((p, q), key=lambda point: point[1])
            depths = tuple(sign*(y-outside) for y in (near[0], far[0]))
            if (far[1]-near[1] > min_span
                    and TOL < min(depths) < max(depths) < abs(mid_height-outside)
                    and max(depths)-min(depths) > TOL):
                lines.append(InclinedSeat(near[1]*.1, far[1]*.1, depths[0]*.1, depths[1]*.1))
        if len(lines) != 1:
            raise ValueError("L’assise intérieure inclinée d’une aile UPN est introuvable dans le DXF.")
        result.append(lines[0])
    return tuple(result)


def wedge_row(seat, width_min, width_max, washer_radius):
    """Centre une rangée dans la largeur plane commune, avec appui de rondelle."""
    half_width = washer_radius + EDGE_MARGIN_CM
    low, high = max(width_min, seat.start_cm), min(width_max, seat.end_cm)
    if high-low < 2*half_width+2*TOL:
        raise ValueError("L’aile UPN ne laisse pas une assise biaise assez large pour la rondelle.")
    return (low+high)/2, half_width


def wedge_plate(cover, seat, station, half_width, section_centre, direction_sign, positions):
    """Tole à ébaucher puis biaiser, avec le plan d’écrou parallèle au couvre-joint."""
    depth_near, depth_far = (seat.depth_at(station+sign*half_width) for sign in (-direction_sign, direction_sign))
    nut_depth = max(depth_near, depth_far) + THIN_EDGE_CM
    edges = nut_depth-depth_near, nut_depth-depth_far
    support = geo.add(cover.point(0., direction_sign*(station-section_centre)), geo.scale(cover.normal, -nut_depth))
    length = max(x for x, _ in cover.outline) - min(x for x, _ in cover.outline)
    diameter = cover.holes[0][2]
    holes = tuple((x, 0., diameter) for x in positions)
    rectangle = shapes.rectangle(
        "Contreplaque biaise UPN", support, cover.u, cover.v, length, 2*half_width,
        max(edges), holes, finishable=False,
    )
    return WedgePlate(**vars(rectangle), thickness_edges_cm=edges), nut_depth


def trim_wedge(component, body, plate):
    """Usine la face inclinée après l’extrusion et le perçage de l’ébauche."""
    import adsk.core as core
    from . import angle_cleat_creator

    sketch = component.sketches.add(component.yZConstructionPlane)
    if not sketch:
        raise RuntimeError("Fusion a refusé l’esquisse d’usinage de la contreplaque.")
    sketch.name = "Coupe de l’assise biaise"
    low, high = (op(y for _, y in plate.outline) for op in (min, max))
    first, last = plate.thickness_edges_cm
    slope = (last-first)/(high-low)
    margin = .1
    top = max(first, last) + margin*(1+abs(slope))
    vertices = ((low-margin, first-slope*margin), (high+margin, last+slope*margin),
                (high+margin, top), (low-margin, top))
    points = [sketch.modelToSketchSpace(core.Point3D.create(0., y, z)) for y, z in vertices]
    lines = sketch.sketchCurves.sketchLines
    for start, end in zip(points, points[1:]+points[:1]):
        lines.addByTwoPoints(start, end).isFixed = True
    if sketch.profiles.count != 1:
        raise RuntimeError("Fusion n’a pas fermé le contour d’usinage biaise.")
    length = max(x for x, _ in plate.outline)-min(x for x, _ in plate.outline)
    angle_cleat_creator._extrude_symmetric_cuts(
        component, body, sketch.profiles.item(0), length+.4, "Assise inclinée UPN",
    )
    sketch.isVisible = False
    if component.bRepBodies.count != 1 or not component.bRepBodies.item(0).isSolid:
        raise RuntimeError("L’usinage biaise n’a pas conservé une contreplaque solide.")
    return component.bRepBodies.item(0)
