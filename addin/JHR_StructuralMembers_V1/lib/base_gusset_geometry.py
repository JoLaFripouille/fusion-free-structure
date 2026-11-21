"""Goussets de pied et contrôles d’encombrement dans le repère de la platine."""

from math import hypot

from . import assembly_geometry as shapes, joint_geometry as geo


TOL = geo.GEOMETRY_TOLERANCE_CM


def _footprint_fits(dimensions, x_range, y_range):
    a, b = dimensions["width"]/2, dimensions["height"]/2
    bevel, radius = dimensions["chamfer"], dimensions["corner_radius"]
    for x in x_range:
        for y in y_range:
            x, y = abs(x), abs(y)
            if x > a + TOL or y > b + TOL:
                return False
            if bevel and x + y > a + b - bevel + TOL:
                return False
            if radius and hypot(max(0., x-a+radius), max(0., y-b+radius)) > radius + TOL:
                return False
    return True


def _closest_hole(x_range, y_range, holes):
    gap = float("inf")
    for x, y, diameter in holes:
        dx = max(x_range[0] - x, 0., x - x_range[1])
        dy = max(y_range[0] - y, 0., y - y_range[1])
        gap = min(gap, hypot(dx, dy) - diameter/2)
    return gap


def foot_gussets(plate, section_width, section_height, dims, flange_faces=(), *, anchor_washers=False):
    """Prépare deux goussets d’âme et quatre prolongements d’ailes, si activés."""
    if not (dims.get("gusset") or dims.get("flange_gusset")):
        return ()
    offsets = dims["offset_x"], dims["offset_y"]
    centre = plate.point(-offsets[0], -offsets[1])
    postward = geo.scale(plate.normal, -1)
    half_section = section_width/2, section_height/2
    plate_half = dims["width"]/2, dims["height"]/2
    plate_axes = plate.u, plate.v
    holes = plate.holes
    clearance = dims.get("hole_gusset_clearance", 0.)
    if anchor_washers and (anchor := dims.get("anchor_diameter")):
        washer = shapes.base_anchor_washer_diameter(anchor)
        holes = tuple((x, y, max(diameter, washer)) for x, y, diameter in holes)
    groups = (
        (1, "gusset", "Gousset de pied", ((0., section_width),)),
        (0, "flange_gusset", "Gousset d’aile de pied", flange_faces),
    )
    gussets = []
    for axis, key, name, faces in groups:
        thickness = dims.get(key, 0.)
        if not thickness:
            continue
        height = dims[key + "_height"]
        chamfer = dims.get(key + "_chamfer", 0.)
        flat = dims.get(key + "_flat", 0.)
        if not faces:
            raise ValueError(f"{name} : les chants des ailes sont introuvables.")
        for side in (-1, 1):
            available = plate_half[axis] - half_section[axis] + side * offsets[axis]
            width = dims.get(key + "_width", 0.) or available
            if width <= TOL or height <= TOL or width > available + TOL:
                raise shapes.DimensionError((key + "_width", key + "_height"),
                                            f"{name} · Le débord de platine ou les dimensions sont insuffisants.")
            if chamfer and chamfer >= min(width, height) - TOL:
                raise shapes.DimensionError((key + "_chamfer",),
                                            f"{name} · Réduire le chanfrein de soudure pour conserver les deux appuis.")
            if flat and flat >= min(width, height) - TOL:
                raise shapes.DimensionError((key + "_flat",),
                                            f"{name} · Le méplat doit être inférieur à la largeur et à la hauteur.")
            outline = [(chamfer, 0.), (width, 0.)]
            if flat:
                outline.extend(((width, flat), (flat, height)))
            outline.append((0., height))
            if chamfer:
                outline.append((0., chamfer))
            outward = geo.scale(plate_axes[axis], side)
            thickness_axis = geo.cross(outward, postward)
            edge = geo.add(centre, geo.scale(outward, half_section[axis]))
            along = 1 - axis
            for station, bearing in faces:
                if thickness > bearing + TOL:
                    raise shapes.DimensionError((key,), f"{name} · L’épaisseur dépasse le chant d’appui du poteau.")
                longitudinal = tuple(sorted((side*half_section[axis] - offsets[axis],
                                             side*(half_section[axis]+width) - offsets[axis])))
                transverse = station - offsets[along]
                transversal = (transverse-thickness/2, transverse+thickness/2)
                x_range, y_range = ((longitudinal, transversal) if axis == 0 else (transversal, longitudinal))
                if not _footprint_fits(dims, x_range, y_range):
                    raise shapes.DimensionError((key + "_width", "chamfer", "corner_radius"),
                                                f"{name} · Le gousset déborde du contour de la platine.")
                gap = _closest_hole(x_range, y_range, holes)
                if gap <= TOL or gap + TOL < clearance:
                    adjustment = ("Ajuster les cotes de perçage X/Y, la platine ou la largeur du gousset."
                                  if dims.get("hole_position", 0)
                                  else "Ajuster les entraxes X/Y ou la largeur du gousset.")
                    detail = ("un perçage ou une rondelle rencontre le gousset." if gap <= TOL
                              else f"jeu de {gap*10:.2f} mm, minimum demandé {clearance*10:g} mm.")
                    fields = ("hole_edge_x", "hole_edge_y", "gauge", "pitch", "hole_gusset_clearance")
                    raise shapes.DimensionError(fields, f"{name} · {detail.capitalize()} {adjustment}")
                origin = geo.add(edge, geo.scale(plate_axes[along], station))
                origin = geo.add(origin, geo.scale(thickness_axis, -thickness/2))
                gussets.append(shapes.Plate(name, origin, outward, postward, tuple(outline), thickness))
    return tuple(gussets)
