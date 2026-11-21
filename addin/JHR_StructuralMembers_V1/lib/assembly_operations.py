"""Mesure les supports Fusion, prépare puis crée un assemblage JHR."""
from dataclasses import dataclass, replace
from itertools import product
import json

import adsk.core as core
import adsk.fusion as fusion

from . import (
    anchors, angle_cleat_creator, assembly_catalog, assembly_geometry as shapes, assembly_placement,
    base_gusset_geometry, bolt_specs, cope_builder, cope_geometry, crossing_braces, dxf_geometry, fastener_creator, fastener_geometry,
    gusset_geometry, joint_builder as joints, joint_geometry as geo, profile_catalog,
    ridge_geometry, simple_fastener_creator, upn_splice,
)

ATTRIBUTE_GROUP = "EI_JHR_Assembly"
TOL = 1e-4


@dataclass(frozen=True)
class Member:
    occurrence: object
    body: object
    curve: object
    family: str
    source: object
    section_x: tuple
    section_y: tuple
    bounds: tuple
    anchor: tuple
    axis_ends: tuple = ()


@dataclass(frozen=True)
class Drilling:
    member: Member
    centres: tuple
    axis: tuple
    diameter: float
    span: float


@dataclass(frozen=True)
class BraceEnd:
    member: Member
    face: object
    plane_point: tuple
    plane_normal: tuple
    plane_offset: float
    axis: tuple
    far_station: float
    weld_point: tuple
    outward: tuple
    clearance: float


@dataclass(frozen=True)
class AssemblyPlan:
    template: object
    members: tuple
    settings_mm: dict
    plates: tuple
    drilling: tuple = ()
    trim: object = None
    fasteners: tuple = ()
    ridge_trim: tuple = ()
    alternate: bool = False
    crossing: tuple = ()
    brace_ends: tuple = ()
    brace_gaps_cm: tuple = ()
    base_flush: bool = False
    support_errors: tuple = ()


def _member(design, occurrence, role, body=None, *, allow_nested=False):
    root = design.rootComponent
    if not occurrence or not occurrence.isValid:
        raise ValueError(f"Sélectionner {role} parmi les profils JHR.")
    candidates = root.allOccurrences if allow_nested and occurrence.assemblyContext else root.occurrences
    if occurrence not in candidates:
        raise ValueError(f"Sélectionner {role} parmi les profils JHR à la racine.")
    metadata = joints._member_metadata(occurrence, role)
    curve = joints._linked_curve(design, metadata, role, allow_arc=False)
    source = profile_catalog.resolve_profile_source(metadata.profile_source)
    bounds = tuple(dxf_geometry.profile_bounds_mm(source))
    anchor = anchors.point_for_bounds(bounds, metadata.anchor)
    x, y = cope_builder._profile_axes(curve, metadata)
    return Member(occurrence, body if body else joints._single_body(occurrence, role), curve,
                  metadata.profile_family, source, x, y, bounds, anchor)


def _brace_member(design, occurrence, role, support):
    bodies = list(occurrence.component.bRepBodies)
    if len(bodies) == 1:
        return _member(design, occurrence, role)
    if len(bodies) != 2 or not all(crossing_braces.is_branch(body) for body in bodies):
        raise ValueError("Choisir une cornière ou une branche issue d’un croisement JHR.")
    start, end = joints._line_endpoints(support.curve)
    candidates = []
    for body in bodies:
        member = _member(design, occurrence, role, body)
        axis_ends = crossing_braces.branch_endpoints(body, occurrence, member.curve)
        distance = min(geo.length(geo.subtract(p, geo.closest_point_on_segment(p, start, end)[0]))
                       for p in axis_ends)
        candidates.append((distance, replace(member, axis_ends=axis_ends)))
    candidates.sort(key=lambda candidate: candidate[0])
    if candidates[1][0]-candidates[0][0] < TOL:
        raise ValueError("Les deux branches sont à égale distance du profil porteur.")
    return candidates[0][1]


def _range(member, axis):
    return tuple((member.bounds[index] - member.anchor[axis]) * .1 for index in (axis, axis+2))


def _base(post, dims, end_index, kind, *, include_anchor_hardware=True, flush_to_skeleton=False):
    if kind == "base_ih" and post.family not in cope_builder.I_H_FAMILIES:
        raise ValueError("Ce pied attend un profil IPE, HEA ou HEB.")
    if kind == "base_angle" and not post.family.startswith("Corniere"):
        raise ValueError("Ce pied attend une cornière.")
    if kind == "base_tube" and not post.family.casefold().startswith("tube"):
        raise ValueError("Ce pied attend un tube.")
    ends = joints._line_endpoints(post.curve)
    near, far = ends[end_index], ends[1-end_index]
    normal = geo.normalize(geo.subtract(near, far))
    t = dims["thickness"]
    if flush_to_skeleton:
        if t >= geo.length(geo.subtract(near, far)) - TOL:
            raise ValueError("L’épaisseur de la platine doit être inférieure à la longueur de l’ébauche.")
        center = geo.subtract(near, geo.scale(normal, t))
    else:
        face, points = joints._planar_end_face(post.body, post.occurrence, normal, near)
        if not face or not points:
            raise ValueError("Extrémité plane du poteau introuvable.")
        center = geo.add(near, geo.scale(normal, geo.dot(geo.subtract(points[0], near), normal)))
    u, v = post.section_x, post.section_y
    reverse_y = geo.dot(geo.cross(u, v), normal) < 0
    if reverse_y:
        v = geo.scale(v, -1)
    x_range, y_range = _range(post, 0), _range(post, 1)
    center = geo.add(center, geo.scale(post.section_x, sum(x_range) / 2))
    center = geo.add(center, geo.scale(post.section_y, sum(y_range) / 2))
    section_w, section_h = x_range[1]-x_range[0], y_range[1]-y_range[0]
    dims = shapes.base_plate_dimensions(dims, section_w, section_h, reverse_y=reverse_y)
    w, h, dx, dy = (dims[key] for key in ("width", "height", "offset_x", "offset_y"))
    if w + TOL < section_w + 2*abs(dx) or h + TOL < section_h + 2*abs(dy):
        raise ValueError("La platine doit couvrir l’enveloppe du poteau.")
    holes = shapes.base_holes(dims)
    if any(abs(x+dx) - d/2 <= section_w/2 and abs(y+dy) - d/2 <= section_h/2 for x, y, d in holes):
        raise shapes.DimensionError(("hole_edge_x", "hole_edge_y", "gauge", "pitch"),
                                    "Un perçage tombe sous l’enveloppe du poteau.")
    if include_anchor_hardware and (diameter := dims.get("anchor_diameter", 0.)):
        washer_radius = shapes.base_anchor_washer_diameter(diameter) / 2
        if any(geo.length((max(0, abs(x+dx)-section_w/2), max(0, abs(y+dy)-section_h/2))) < washer_radius-TOL
               for x, y, _ in holes):
            raise shapes.DimensionError(("hole_edge_x", "hole_edge_y", "gauge", "pitch"),
                                        "Une rondelle d’ancrage empiète sur l’enveloppe du poteau.")
    plate_center = geo.add(center, geo.add(geo.scale(u, dx), geo.scale(v, dy)))
    finish = max(dims["chamfer"], dims["corner_radius"])
    if w/2+h/2-section_w/2-section_h/2-abs(dx)-abs(dy) < finish:
        key = "chamfer" if dims["chamfer"] else "corner_radius"
        raise shapes.DimensionError((key,), "La finition des angles passe sous le poteau.")
    plates = [shapes.rectangle("Platine de pied", plate_center, u, v, w, h, t, holes)]
    flange_faces = ()
    if dims.get("flange_gusset"):
        section = _i_geometry(post)
        inner = _inner_flange_levels(post, section)
        outer = (section.min_y_mm, section.max_y_mm)
        sign = geo.dot(v, post.section_y)
        mid = sum(outer)/2
        flange_faces = tuple((sign*((edge+face)/2-mid)*.1, abs(edge-face)*.1)
                             for edge, face in zip(outer, inner))
    plates.extend(base_gusset_geometry.foot_gussets(
        plates[0], section_w, section_h, dims, flange_faces,
        anchor_washers=include_anchor_hardware,
    ))
    if dims["shim"]:
        shim_origin = geo.add(plate_center, geo.scale(normal, t))
        plates.extend(shapes.fork_shims(
            shim_origin, u, v, w, h, dims["shim"], holes, dims["shim_clearance"],
            dims["shim_gap"], dims["shim_inset"], finish,
        ))
    plates.extend(shapes.base_fixings(plates[0], dims, include_hardware=include_anchor_hardware))
    if flush_to_skeleton:
        # La platine et sa grille sont symétriques en v. Placer son esquisse au
        # niveau de l’ébauche permet ensuite d’extruder vers le poteau.
        plates[0] = replace(plates[0], origin=geo.add(plate_center, geo.scale(normal, t)),
                            v=geo.scale(v, -1))
    return tuple(plates)


def _i_geometry(member):
    if member.family not in cope_builder.I_H_FAMILIES:
        raise ValueError("Cet assemblage accepte des profils IPE, HEA ou HEB.")
    return cope_geometry.analyze_i_profile_dxf(member.source)


def _perpendicular(main, secondary):
    evaluation = joints._analyze_adjusted_curve(main.curve, secondary.curve)
    if abs(evaluation.angle_degrees - 90.0) > .1:
        raise ValueError("Ce modèle attend des axes perpendiculaires.")
    return evaluation


def _inner_flange_levels(member, section):
    """Retrouve les faces intérieures planes dans le contour exact du profil."""
    levels = set()
    mid = (section.min_y_mm + section.max_y_mm)/2
    for contour in dxf_geometry.tessellate_profile_contours_mm(member.source):
        for (ax, ay), (bx, by) in zip(contour, contour[1:]+contour[:1]):
            if abs(ay-by) < TOL and abs(bx-ax) > section.width_mm/16:
                if section.min_y_mm+TOL < ay < section.max_y_mm-TOL:
                    levels.add(ay)
    bottom, top = (sorted(y for y in levels if y < mid), sorted(y for y in levels if y > mid))
    if not bottom or not top:
        raise ValueError("Les deux faces intérieures des ailes ne sont pas identifiables.")
    return bottom[0], top[-1]


def _stiffeners(post, section, support, up, heights, stations, post_start, main_axis, thickness, clearance):
    bottom, top = _inner_flange_levels(post, section)
    lower_relief = max(0, section.web_min_y_mm-bottom)*.1
    upper_relief = max(0, top-section.web_max_y_mm)*.1
    low, high = ((level-post.anchor[1])*.1 for level in (bottom, top))
    low, high = low+clearance, high-clearance
    if high-low <= lower_relief+upper_relief+TOL:
        raise shapes.DimensionError(("stiffener_clearance",), "Le jeu réduit trop la hauteur utile du raidisseur.")
    u, v = post.section_x, post.section_y
    normal = geo.cross(u, v)
    x0, x1 = ((value-post.anchor[0])*.1 for value in (section.web_min_x_mm, section.web_max_x_mm))
    left, right = _range(post, 0)
    levels = [geo.dot(geo.subtract(geo.add(support, geo.scale(up, height)), post_start), main_axis)
              for height in heights]
    ordered = sorted(levels)
    if any(high-low < thickness+TOL for low, high in zip(ordered, ordered[1:])):
        raise shapes.DimensionError(("stiffener",), "Réduire l’épaisseur pour séparer les raidisseurs.")
    plates = []
    for station in levels:
        if station <= stations[0]+thickness/2 or station >= stations[1]-thickness/2:
            raise shapes.DimensionError(("stiffener",), "Un raidisseur déborde de l’extrémité du poteau.")
        centre = geo.add(post_start, geo.scale(main_axis, station))
        origin = geo.add(centre, geo.scale(normal, -thickness/2))
        for web_edge, flange_edge, sign in ((x0, left, -1), (x1, right, 1)):
            heel = web_edge+sign*clearance
            tip = flange_edge-sign*max(.1, clearance)
            if sign*(tip-heel) <= max(lower_relief, upper_relief)+TOL:
                raise shapes.DimensionError(("stiffener_clearance",), "Le jeu réduit trop la largeur utile du raidisseur.")
            contour = [(heel, low+lower_relief), (heel+sign*lower_relief, low),
                       (tip, low), (tip, high),
                       (heel+sign*upper_relief, high), (heel, high-upper_relief)]
            outline = tuple(point for i, point in enumerate(contour) if point != contour[i-1])
            plates.append(shapes.Plate("Raidisseur d’âme du poteau", origin, u, v, outline, thickness))
    return tuple(plates)


def _fastener_plan(centres, normal, thickness, support_thickness, hole, spec):
    head_point = geo.add(centres[0], geo.scale(normal, thickness))
    nut_point = geo.add(centres[0], geo.scale(normal, -support_thickness))
    _, positions, _, length = fastener_geometry.plan_modeled_fasteners(
        [fastener_geometry.Hole(centre, normal, hole) for centre in centres],
        fastener_geometry.SupportPlane(head_point, normal),
        fastener_geometry.SupportPlane(nut_point, normal), spec.nominal_diameter_mm,
    )
    return positions, spec.nominal_diameter_mm, length


def _end_plate(design, post, beam, dims, with_haunch, raked=False, *, preview_support=False):
    root = design.rootComponent
    for member in (post, beam):
        occurrence = member.occurrence
        cursor = occurrence
        while cursor:
            if cursor.isReferencedComponent:
                raise ValueError(f"{occurrence.name} : modifier le profil dans son fichier Fusion source.")
            cursor = cursor.assemblyContext
        if root.allOccurrencesByComponent(occurrence.component).count != 1:
            raise ValueError(f"{occurrence.name} : le perçage ou la coupe toucherait plusieurs occurrences.")
    post_shape, beam_shape = _i_geometry(post), _i_geometry(beam)
    thickness = dims["thickness"]
    if thickness <= 0:
        raise ValueError("Saisir une épaisseur positive pour la platine d’about.")
    trim = joints.evaluate_straight_joint(design, post.occurrence, beam.occurrence, thickness,
                                         allow_support_end=True)
    paths = trim.geometry
    if not raked and abs(paths.angle_degrees - 90.) > .1:
        raise ValueError("Choisir About d’arbalétrier sur poteau pour un raccord en biais.")
    direction = trim.cut_normal
    if abs(geo.dot(direction, post.section_y)) < .995:
        raise ValueError("Sélectionner un raccord côté aile du poteau.")
    if not raked and abs(geo.dot(beam.section_y, paths.main_direction)) < .995:
        raise ValueError("La hauteur de la poutre doit suivre l’axe du poteau.")
    vertical = max((1, 2), key=lambda index: abs(paths.main_direction[index]))
    up = paths.main_direction if paths.main_direction[vertical] >= 0 else geo.scale(paths.main_direction, -1)
    if not raked:
        up = beam.section_y if geo.dot(beam.section_y, up) >= 0 else geo.scale(beam.section_y, -1)
    across = geo.cross(up, direction)
    end = paths.secondary_joint_endpoint
    section_y = beam.section_y
    if raked:
        slope = geo.dot(paths.approach_direction, direction)
        if abs(slope) < .5 or abs(geo.dot(across, beam.section_x)) < .999:
            raise ValueError("Le profil de l’arbalétrier doit suivre le plan du poteau et de la pente.")
        projection = geo.scale(paths.approach_direction, 1/slope)
        cut_origin = geo.add(end, geo.scale(projection, geo.dot(geo.subtract(trim.cut_point, end), direction)))
        section_y = geo.subtract(section_y, geo.scale(projection, geo.dot(section_y, direction)))
    else:
        cut_origin = geo.add(end, geo.scale(direction, geo.dot(geo.subtract(trim.cut_point, end), direction)))
    support = geo.add(cut_origin, geo.scale(direction, -thickness))
    profile_width = _range(beam, 0)
    vertical_scale = geo.dot(up, section_y)
    low, high = sorted(val * vertical_scale for val in _range(beam, 1))
    beam_width = profile_width[1] - profile_width[0]
    support = geo.add(support, geo.scale(beam.section_x, sum(profile_width)/2))
    diameter = dims["hole"]
    margin = max(1.5 * diameter, 1.0)
    min_z = low - (dims["drop"] + dims["flange"] if with_haunch else 0)
    flange_levels = _inner_flange_levels(beam, beam_shape)
    inner_low, inner_high = sorted(
        (level-beam.anchor[1])*.1*vertical_scale for level in flange_levels)
    top = high - dims["top_setback"]
    if top <= inner_high+TOL:
        raise ValueError("Le retrait haut doit laisser une partie de l’aile supérieure sur la platine.")
    bolt = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}") if dims["bolt"] else None
    if bolt and not diameter:
        raise ValueError("Prévoir des perçages pour poser les boulons.")
    washer_radius = bolt.washer_outer_diameter_mm*.05 if bolt else 0
    clearance = max(diameter/2, washer_radius) + .1
    haunch = ()
    if with_haunch:
        origin = geo.add(support, geo.scale(direction, thickness))
        haunch = shapes.haunch(origin, direction, up, beam_width, low, dims)
    stiffener_levels = []
    if dims["stiffener"]:
        levels = ((low+inner_low)/2, (high+inner_high)/2)
        positions = ("stiffener_lower", "stiffener_upper")
        if vertical_scale < 0.:
            levels, positions = levels[::-1], positions[::-1]
        stiffener_levels.extend(level for key, level in zip(positions, levels) if dims[key])
        if haunch and dims["stiffener_haunch"]:
            sole = haunch[1]
            heel = min(geo.dot(geo.subtract(sole.point(x, y), support), up) for x, y in sole.outline)
            stiffener_levels.append(heel + geo.dot(sole.normal, up)*sole.thickness_cm/2)
        if not stiffener_levels:
            raise shapes.DimensionError(("stiffener",), "Cocher au moins un emplacement de raidisseur.")
    min_gauge = max(beam_width, dims["flange_width"] + 2*clearance + .1) if with_haunch else beam_width
    if raked:
        min_gauge += 2*clearance + .1
    post_start, _ = joints._line_endpoints(post.curve)
    face_x = _range(post, 0)
    centre_x = geo.dot(geo.subtract(support, post_start), post.section_x)
    bearing_half_width = min(centre_x-face_x[0], face_x[1]-centre_x)
    width = dims["width"] or min(min_gauge + 2*max(margin, clearance+.1), 2*bearing_half_width)
    if not dims["width"] and width < beam_width-TOL:
        raise shapes.DimensionError(("width",), "L’aile du poteau ne couvre pas la largeur de la poutre à cet emplacement.")
    height = dims["height"] or top-min_z + 2*margin
    bottom = top-height
    gauge = dims["gauge"] or width - 2*margin
    if width < beam_width - TOL or bottom > min_z+TOL:
        raise ValueError("La platine doit couvrir la section et, le cas échéant, le jarret.")
    center_y = (bottom+top)/2
    center = geo.add(support, geo.scale(up, center_y))
    if diameter and not dims["gauge"]:
        gauge = min(gauge, 2*(bearing_half_width-clearance-TOL))
    original_stations = tuple(geo.dot(geo.subtract(p, post_start), paths.main_direction)
                              for p in joints._line_endpoints(post.curve))
    plate_points = tuple(geo.add(support, geo.scale(up, height)) for height in (bottom, top))
    plate_stations = tuple(geo.dot(geo.subtract(p, post_start), paths.main_direction) for p in plate_points)
    stations = min(*original_stations, *plate_stations), max(*original_stations, *plate_stations)
    trim = replace(trim, primary_extensions=joints._primary_extensions_to_cover(
        post.occurrence, post.body, post.curve, paths, plate_points,
    ))
    holes = ()
    if diameter:
        if gauge <= 2*clearance or width-gauge <= 2*clearance:
            raise ValueError("Écarter les deux colonnes ou augmenter la largeur de platine.")
        if raked and gauge < min_gauge-TOL:
            raise ValueError("Écarter les colonnes de boulons au-delà de l’enveloppe de l’arbalétrier.")
        blocked = []
        if gauge/2-clearance < beam_width/2:
            blocked.extend(((low-clearance, inner_low+clearance),
                            (inner_high-clearance, high+clearance)))
        if dims["stiffener"]:
            keepout = dims["stiffener"]/2 + clearance
            blocked.extend((level-keepout, level+keepout) for level in stiffener_levels)
        if with_haunch:
            if gauge/2-clearance < dims["flange_width"]/2:
                raise ValueError("Écarter les deux colonnes de boulons pour dégager la semelle du jarret.")
            under = int(dims["rows"])//2
            if under < 1:
                raise ValueError("Prévoir au moins deux rangées pour répartir la fixation entre l’IPE et le jarret.")
            rows = shapes.bolt_rows(under, min_z+clearance, low-clearance,
                                   2*clearance, blocked, dims["pitch"])
            rows += shapes.bolt_rows(dims["rows"]-under, low+clearance, top-clearance,
                                    2*clearance, blocked, dims["pitch"])
        else:
            row_min, row_max = low+clearance, top-clearance
            rows = shapes.bolt_rows(dims["rows"], row_min, row_max,
                                   2*clearance, blocked, dims["pitch"])
        holes = tuple((x, y-center_y, diameter) for x in (-gauge/2, gauge/2) for y in rows)
    plate = shapes.rectangle("Platine d’about", center, across, up, width, height, thickness, holes)
    direction_on_post = geo.dot(direction, post.section_y)
    lower_flange, upper_flange = _inner_flange_levels(post, post_shape)
    flange = ((post_shape.max_y_mm-upper_flange) if direction_on_post > 0 else
              (lower_flange-post_shape.min_y_mm)) * .1
    post_root = max(post_shape.web_min_y_mm-lower_flange, upper_flange-post_shape.web_max_y_mm)*.1
    # Coupe bornée à l’aile en sélectionnant sa face d’appui.
    drilling, fasteners = (), ()
    support_errors = []
    if holes:
        centres = tuple(plate.point(x, y) for x, y, _ in holes)
        web_limits = tuple((x-post.anchor[0])*.1 for x in (post_shape.web_min_x_mm, post_shape.web_max_x_mm))
        for index, position in enumerate(centres, 1):
            delta = geo.subtract(position, post_start)
            along, x = geo.dot(delta, paths.main_direction), geo.dot(delta, post.section_x)
            rad = clearance if bolt else diameter/2
            if not (face_x[0]+rad < x < face_x[1]-rad and stations[0]+rad < along < stations[1]-rad):
                support_errors.append((index, "déborde de l’aile du poteau"))
            elif web_limits[0]-post_root-rad < x < web_limits[1]+post_root+rad:
                support_errors.append((index, "rencontre l’âme ou le congé du poteau"))
        if support_errors and not preview_support:
            raise support_error(support_errors)
        drilling = (Drilling(post, centres, direction, diameter, 2*flange+.2),)
        if bolt:
            fasteners = _fastener_plan(centres, direction, thickness, flange, diameter, bolt)
    plates = (plate, *haunch)
    if stiffener_levels:
        plates += _stiffeners(post, post_shape, support, up, stiffener_levels, stations, post_start,
                              paths.main_direction, dims["stiffener"], dims["stiffener_clearance"])
    return plates, drilling, trim, fasteners, tuple(support_errors)


def support_error(errors):
    details = " · ".join(f"N°{index} {message}" for index, message in errors)
    return shapes.DimensionError(("gauge", "pitch"), "Fixations sur le poteau. " + details + ".")


def _shear_plate(main, beam, dims, other_side, *, check_material=True):
    main_shape, section = _i_geometry(main), _i_geometry(beam)
    paths = _perpendicular(main, beam)
    if abs(geo.dot(main.section_y, beam.section_y)) < .995:
        raise ValueError("Aligner les hauteurs des deux profils.")
    direction = paths.plane_normal
    direction_to_web = geo.dot(direction, main.section_x)
    if abs(direction_to_web) < .995:
        raise ValueError("Le plat doit être monté sur l’âme de la poutre principale.")
    normal = geo.cross(direction, beam.section_y)
    up = beam.section_y
    if geo.dot(normal, beam.section_x) * (-1 if other_side else 1) < 0:
        up, normal = geo.scale(up, -1), geo.scale(normal, -1)
    origin = cope_geometry.web_face_cut_point(main_shape, main.anchor, paths.secondary_joint_endpoint,
                                             main.section_x, direction, 0.0)
    side = geo.dot(normal, beam.section_x)
    web_side = section.web_max_x_mm if side > 0 else section.web_min_x_mm
    other_web = section.web_min_x_mm if side > 0 else section.web_max_x_mm
    origin = geo.add(origin, geo.scale(beam.section_x, (web_side-beam.anchor[0])*.1))
    mid_y = (section.web_min_y_mm + section.web_max_y_mm)/2
    origin = geo.add(origin, geo.scale(beam.section_y, (mid_y-beam.anchor[1])*.1))
    width, height, thickness = (dims[key] for key in ("width", "height", "thickness"))
    primary_clear = (main_shape.web_max_y_mm-main_shape.web_min_y_mm)*.1
    if height > min(primary_clear, (section.web_max_y_mm-section.web_min_y_mm)*.1) - TOL:
        raise ValueError("Le plat d’âme dépasse la hauteur libre des profils.")
    diameter = dims["hole"]
    columns = shapes.pitch_series(dims["columns"], dims["column_step"])
    columns = tuple(dims["gauge"] - columns[-1] + x for x in columns)
    rows = shapes.pitch_series(dims["rows"], dims["pitch"])
    holes = tuple((x, y, diameter) for x in columns for y in rows) if diameter else ()
    plate = shapes.rectangle("Plat d’âme soudé", origin, direction, up, width, height, thickness, holes, width/2)
    if not holes:
        if dims["bolt"]:
            raise ValueError("Prévoir des perçages pour poser les boulons.")
        return (plate,), (), ()
    # Les centres sont contrôlés contre l’âme existante avant toute écriture.
    centres = tuple(plate.point(x, y) for x, y, _ in holes)
    secondary_web = abs(other_web-web_side)*.1
    if check_material:
        proxy = joints._body_proxy(beam.body, beam.occurrence)
        for center in centres:
            point = geo.add(center, geo.scale(normal, -secondary_web/2))
            if proxy.pointContainment(core.Point3D.create(*point)) != fusion.PointContainment.PointInsidePointContainment:
                raise ValueError("Les perçages ne tombent pas dans l’âme secondaire. Vérifier le grugeage et le jeu.")
    fasteners = ()
    nominal = dims["bolt"]*10
    if nominal:
        spec = bolt_specs.bolt_spec_by_designation(f"M{nominal:g}")
        rim = spec.washer_outer_diameter_mm*.05
        horizontal_step = dims["column_step"] if len(columns) > 1 else width
        vertical_step = dims["pitch"] if len(rows) > 1 else height
        if not rim < min(columns[0], width-columns[-1], height/2-rows[-1],
                         horizontal_step/2, vertical_step/2):
            raise ValueError("L’appui des rondelles déborde du plat ou les rondelles se touchent.")
        fasteners = _fastener_plan(centres, normal, thickness, secondary_web, diameter, spec)
    return (plate,), (Drilling(beam, centres, normal, diameter, 2*secondary_web+.2),), fasteners


def _splice_section(member, covers):
    if member.family not in ("UPN", "UPE"):
        section = _i_geometry(member)
        return member, section, _inner_flange_levels(member, section) if covers else ()
    a, b, c, d = member.bounds
    middle = (a+c)/2
    segments = [(p, q) for contour in dxf_geometry.tessellate_profile_contours_mm(member.source)
                for p, q in zip(contour, contour[1:]+contour[:1])]
    web = sorted((p[1], min(p[0], q[0]), max(p[0], q[0])) for p, q in segments
                 if abs(p[1]-q[1]) < TOL and min(p[0], q[0]) < middle < max(p[0], q[0]))
    if len(web) != 2:
        raise ValueError("Les deux faces planes de l’âme du U sont introuvables.")
    outer, inner = web
    section = cope_geometry.IProfileGeometry(b, a, d, c, outer[0], inner[0], inner[1], inner[2])
    canonical = replace(member, section_x=member.section_y, section_y=member.section_x,
                        bounds=(b, a, d, c), anchor=(member.anchor[1], member.anchor[0]))
    levels = ()
    if covers and member.family == "UPN":
        from . import upn_splice

        levels = upn_splice.inclined_seats(member.bounds, segments)
    elif covers:
        inside = sorted({p[0] for p, q in segments if abs(p[0]-q[0]) < TOL and
                         abs(p[1]-q[1]) > (d-b)/4 and a+TOL < p[0] < c-TOL})
        if len(inside) != 2:
            raise ValueError("Les deux assises intérieures des ailes du UPE sont introuvables.")
        levels = tuple(inside)
    return canonical, section, levels


def _upn_splice_covers(members, dims, section, seats, center, axis, positions, spec):
    first = members[0]
    origin = geo.add(center, geo.scale(first.section_x, sum(_range(first, 0))/2))
    height_limit = _range(first, 1)
    width = dims["cover_width"] or section.width_mm*.1
    if width > section.width_mm*.1+TOL:
        raise ValueError("Le couvre-joint dépasse de l’aile UPN.")
    length, thickness, diameter = dims["width"], dims["cover_thickness"], dims["hole"]
    radius = max(diameter/2, spec.washer_outer_diameter_mm*.05 if spec else 0.)
    if spec:
        # Décaler les axes d’ailes longitudinalement par rapport aux boulons de l’âme.
        room = length/2-positions[-1]-radius-.1
        shift = min(dims["column_step"]/2, room)
        if shift <= radius+TOL:
            raise ValueError("Allonger le couvre-joint pour décaler les boulons d’aile de ceux de l’âme.")
        positions = tuple(position+shift for position in positions)
    transverse_centre = (section.min_x_mm+section.max_x_mm)*.05
    sides = sorted(((height_limit[1], first.section_y, seats[1]),
                    (height_limit[0], geo.scale(first.section_y, -1), seats[0])),
                   key=lambda side: side[1][2], reverse=True)
    plates, drills, fasteners = [], [], []
    for index, (height, normal, seat) in enumerate(sides[:int(dims["flange_covers"])]):
        support = geo.add(origin, geo.scale(first.section_y, height))
        transverse = geo.cross(normal, axis)
        sign = geo.dot(first.section_x, transverse)
        holes = ()
        if diameter:
            station, half_width = upn_splice.wedge_row(seat, transverse_centre-width/2,
                                                      transverse_centre+width/2, radius)
            holes = tuple((i*x, sign*(station-transverse_centre), diameter)
                          for i in (-1, 1) for x in positions)
        label = "Couvre-joint dessus" if index == 0 else "Couvre-joint dessous"
        cover = shapes.rectangle(label, support, axis, transverse, length, width, thickness, holes)
        plates.append(cover)
        if not holes:
            continue
        wedge, nut_depth = upn_splice.wedge_plate(cover, seat, station, half_width, transverse_centre,
                                                sign, tuple(x for x, _, _ in holes))
        plates.append(wedge)
        centres = tuple(cover.point(x, y) for x, y, _ in holes)
        half = len(centres)//2
        for member, group in zip(members, (centres[:half], centres[half:])):
            proxy = joints._body_proxy(member.body, member.occurrence)
            mid_flange = geo.scale(normal, -seat.depth_at(station)/2)
            if any(proxy.pointContainment(core.Point3D.create(*geo.add(p, mid_flange)))
                   != fusion.PointContainment.PointInsidePointContainment for p in group):
                raise ValueError("Un perçage du couvre-joint tombe hors de la matière d’une aile UPN.")
            drills.append(Drilling(member, group, normal, diameter, 2*nut_depth+.2))
        if spec:
            fasteners.append(_fastener_plan(centres, normal, thickness, nut_depth, diameter, spec))
    return tuple(plates), tuple(drills), tuple(fasteners)


def _splice_covers(members, dimensions, section, flange_levels, center, axis, positions, spec,
                   *, check_material=True):
    count = int(dimensions["flange_covers"])
    if not count:
        return (), (), ()
    first = members[0]
    if first.family == "UPN":
        return _upn_splice_covers(members, dimensions, section, flange_levels, center, axis, positions, spec)
    origin = geo.add(center, geo.scale(first.section_x, sum(_range(first, 0))/2))
    height_limit = _range(first, 1)
    inner_bottom, inner_top = flange_levels
    flange_thickness = ((section.max_y_mm-inner_top)*.1, (inner_bottom-section.min_y_mm)*.1)
    roots = max(section.web_min_y_mm-inner_bottom, inner_top-section.web_max_y_mm)*.1
    width = dimensions["cover_width"] or section.width_mm*.1
    length, thickness = dimensions["width"], dimensions["cover_thickness"]
    if width > section.width_mm*.1+TOL:
        raise ValueError("Le couvre-joint dépasse de l’aile.")
    diameter = dimensions["hole"]
    radius = spec.washer_outer_diameter_mm*.05 if spec else diameter/2
    centre_section_x = (section.min_x_mm+section.max_x_mm)*.05
    left_edge, right_edge = (centre_section_x-width/2+radius+.2, centre_section_x+width/2-radius-.2)
    faces = ((left_edge, min(right_edge, section.web_min_x_mm*.1-roots-radius-.1)),
             (max(left_edge, section.web_max_x_mm*.1+roots+radius+.1), right_edge))
    stations = [a if side == 0 else b for side, (a,b) in enumerate(faces) if b >= a]
    if diameter and not stations:
        raise ValueError("Le couvre-joint ne laisse pas d’appui aux trous hors du congé de l’âme.")
    if len(stations) == 1:
        a,b = next(interval for interval in faces if interval[1] >= interval[0])
        stations = [a,b] if b-a > 2*radius+.2 else [(a+b)/2]
    # Utiliser les vrais plans extérieurs des ailes, y compris un profil tourné sur son chemin.
    sides = sorted(((height_limit[1], first.section_y, flange_thickness[0]),
                    (height_limit[0], geo.scale(first.section_y, -1), flange_thickness[1])),
                   key=lambda side: side[1][2], reverse=True)
    plates, drills, fasteners = [], [], []
    for index, (station, normal, flange) in enumerate(sides[:count]):
        support = geo.add(origin, geo.scale(first.section_y, station))
        transverse = geo.cross(normal, axis)
        sign = geo.dot(first.section_x, transverse)
        holes = tuple((i*x, sign*(y-centre_section_x), diameter)
                      for i in (-1, 1) for x in positions for y in stations) if diameter else ()
        plate = shapes.rectangle("Couvre-joint " + ("dessus" if index == 0 else "dessous"),
                                 support, axis, transverse, length, width, thickness, holes)
        plates.append(plate)
        if holes:
            centres = tuple(plate.point(x, y) for x, y, _ in holes)
            half = len(centres)//2
            for member, group in zip(members, (centres[:half], centres[half:])):
                if check_material:
                    proxy = joints._body_proxy(member.body, member.occurrence)
                    if any(proxy.pointContainment(core.Point3D.create(*geo.add(p, geo.scale(normal, -flange/2))))
                           != fusion.PointContainment.PointInsidePointContainment for p in group):
                        raise ValueError("Un perçage du couvre-joint tombe hors de la matière d’une aile.")
                drills.append(Drilling(member, group, normal, diameter, 2*flange+.2))
            if spec:
                fasteners.append(_fastener_plan(centres, normal, thickness, flange, diameter, spec))
    return tuple(plates), tuple(drills), tuple(fasteners)


def _nearest_ends(first, second):
    ends = [joints._line_endpoints(member.curve) for member in (first, second)]
    indices = min(product((0, 1), repeat=2), key=lambda pair: geo.length(
        geo.subtract(ends[0][pair[0]], ends[1][pair[1]]),
    ))
    return ends, indices


def _splice_web(first, second, dims, alternate, *, check_material=True):
    first, section, flange_levels = _splice_section(first, dims["flange_covers"])
    second, _, _ = _splice_section(second, dims["flange_covers"])
    (start, stop), (end_a, end_b) = _nearest_ends(first, second)
    a, b = start[end_a], stop[end_b]
    axis = geo.normalize(geo.subtract(a, start[1-end_a]))
    next_axis = geo.normalize(geo.subtract(stop[1-end_b], b))
    displacement = geo.subtract(b, a)
    if (first.source != second.source or geo.dot(axis, next_axis) < .99999 or
            geo.length(geo.cross(axis, displacement)) > .01 or
            abs(geo.dot(first.section_y, second.section_y)) < .99999):
        raise ValueError("Sélectionner deux profils identiques, alignés bout à bout.")
    if first.family in ("UPN", "UPE") and geo.dot(first.section_x, second.section_x) < .99999:
        raise ValueError("Les deux U doivent présenter leurs âmes du même côté.")

    boundary = []
    for member, endpoint, out in ((first, a, axis), (second, b, geo.scale(axis, -1))):
        _, points = joints._planar_end_face(member.body, member.occurrence, out, endpoint)
        if not points:
            raise ValueError("Un about plan est introuvable pour l’éclissage.")
        boundary.append(geo.dot(points[0], axis))
    gap = boundary[1]-boundary[0]
    if gap < -TOL:
        raise ValueError("Les extrémités des poutres se recouvrent.")
    center = geo.add(a, geo.scale(axis, sum(boundary)/2 - geo.dot(a, axis)))
    web_limits = tuple((x-first.anchor[0])*.1 for x in (section.web_min_x_mm, section.web_max_x_mm))
    pitch_heights = ((section.web_min_y_mm+section.web_max_y_mm)/2-first.anchor[1])*.1
    if first.anchor != second.anchor:
        raise ValueError("Appliquer le même ancrage aux deux sections.")
    up = first.section_y if not alternate else geo.scale(first.section_y, -1)
    center_web = geo.add(center, geo.scale(first.section_y, pitch_heights))
    normal = geo.cross(axis, up)
    signed = geo.dot(first.section_x, normal)
    x_low, x_high = sorted(value*signed for value in web_limits)
    web_depth = x_high-x_low
    front = geo.add(center_web, geo.scale(normal, x_high))
    back = geo.add(center_web, geo.scale(normal, x_low))
    width, thickness = (dims[key] for key in ("width", "thickness"))
    clear_height = (section.web_max_y_mm-section.web_min_y_mm)*.1
    height = dims["height"] or min(9.5, clear_height-.02)
    if height > clear_height - TOL:
        raise ValueError("Les éclisses ne tiennent pas entre les congés des ailes.")
    diameter = dims["hole"]
    axial = shapes.pitch_series(dims["columns"], dims["column_step"])
    positions = tuple(gap/2 + dims["end_dist"] + item-axial[0] for item in axial)
    rows = shapes.pitch_series(dims["rows"], dims["pitch"])
    holes = tuple((sign*x, y, diameter) for sign in (-1, 1) for x in positions for y in rows) if diameter else ()
    copies = int(dims["copies"])
    main = shapes.rectangle("Éclisse côté 2" if alternate else "Éclisse côté 1",
                            front, axis, up, width, height, thickness, holes)
    plates = (main,)
    if copies == 2:
        plates += (shapes.rectangle("Éclisse côté opposé", back, geo.scale(axis, -1), up,
                                   width, height, thickness, holes),)
    drill = []
    all_centres = []
    if holes:
        half = len(holes)//2
        for member, sub in zip((first, second), (holes[:half], holes[half:])):
            centres = tuple(main.point(x, y) for x, y, _ in sub)
            if check_material:
                proxy = joints._body_proxy(member.body, member.occurrence)
                for point in centres:
                    sample = geo.add(point, geo.scale(normal, -web_depth/2))
                    if proxy.pointContainment(core.Point3D.create(*sample)) != fusion.PointContainment.PointInsidePointContainment:
                        raise ValueError("Un perçage sort de l’âme de l’une des poutres.")
            all_centres.extend(centres)
            drill.append(Drilling(member, centres, normal, diameter, 2*web_depth+.2))
    fasteners, spec = (), None
    if dims["bolt"]:
        if not holes:
            raise ValueError("Prévoir des perçages pour poser les boulons.")
        spec = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}")
        radius = spec.washer_outer_diameter_mm*.05
        if radius >= min(dims["end_dist"], width/2-positions[-1], height/2-rows[-1]):
            raise ValueError("L’appui des rondelles déborde des éclisses ou d’un about.")
        if len(axial) > 1 and dims["column_step"] <= 2*radius or len(rows) > 1 and dims["pitch"] <= 2*radius:
            raise ValueError("Augmenter l’entraxe pour laisser passer les rondelles.")
        fasteners = (_fastener_plan(all_centres, normal, thickness, web_depth+(copies-1)*thickness, diameter, spec),)
    covers, cover_drills, cover_bolts = _splice_covers(
        (first, second), dims, section, flange_levels, center, axis, positions, spec,
        check_material=check_material,
    )
    return plates+covers, tuple(drill)+cover_drills, fasteners+cover_bolts


def _brace_arm(member, near, far):
    is_i = member.family in cope_builder.I_H_FAMILIES
    mm = .1
    bearing = None
    if is_i:
        shape = _i_geometry(member)
        thickness = shape.web_max_x_mm-shape.web_min_x_mm
        width = shape.web_max_y_mm-shape.web_min_y_mm
        x = (shape.web_min_x_mm+shape.web_max_x_mm)/2
        y = (shape.web_min_y_mm+shape.web_max_y_mm)/2
        normal = member.section_x
    elif member.family.startswith("Corniere"):
        shape = cope_geometry.analyze_single_flange_profile_dxf(member.source)
        thickness = shape.flange_thickness_mm
        left = (shape.min_x_mm, shape.web_min_x_mm-shape.negative_root_radius_mm)
        right = (shape.web_max_x_mm+shape.positive_root_radius_mm, shape.max_x_mm)
        lo, hi = max((left, right), key=lambda edges: edges[1]-edges[0])
        width, x, y = hi-lo, (lo+hi)/2, shape.min_y_mm+thickness/2
        normal = geo.scale(member.section_y, -1)
        across = geo.cross(normal, geo.normalize(geo.subtract(far, near)))
        direction = geo.dot(across, member.section_x)
        bearing = tuple(sorted((edge-x)*mm*direction for edge in (shape.min_x_mm, shape.max_x_mm)))
    else:
        raise ValueError("Le gousset attend des diagonales I/H ou en cornière.")
    offset = geo.add(geo.scale(member.section_x, (x-member.anchor[0])*mm),
                     geo.scale(member.section_y, (y-member.anchor[1])*mm))
    return gusset_geometry.GussetArm(geo.add(near, offset), geo.add(far, offset),
                                    normal, width*mm, thickness*mm, is_i, bearing)


def _end_gusset(support, members, dims, alternate, *, check_material=True):
    section = _i_geometry(support)
    start, end = joints._line_endpoints(support.curve)
    arms = []
    for member in members:
        if not member.family.startswith("Corniere"):
            raise ValueError("Choisir des diagonales en cornière.")
        ends = member.axis_ends or joints._line_endpoints(member.curve)
        near, far = sorted(ends, key=lambda point: geo.length(geo.subtract(
            point, geo.closest_point_on_segment(point, start, end)[0],
        )))
        arms.append(_brace_arm(member, near, far))
    normal = geo.scale(geo.normalize(arms[0].normal), -1 if alternate else 1)
    web = tuple(tuple((side-support.anchor[index])*.1 for side in limits)
                for index, limits in enumerate(((section.web_min_x_mm, section.web_max_x_mm),
                                                (section.web_min_y_mm, section.web_max_y_mm))))
    offset, inside = gusset_geometry.support_weld(
        arms[0], normal, start, (support.section_x, support.section_y),
        (_range(support, 0), _range(support, 1)), web, thickness_cm=dims["thickness"],
        face=dims["weld_face"], position=dims["weld_position"], offset_cm=dims["weld_offset"],
    )
    weld_edge = geo.add(start, offset), geo.add(end, offset)
    arms, adjustments, gaps = _brace_ends(members, arms, weld_edge[0],
                                         geo.scale(geo.normalize(inside), -1.), dims["weld_gap"])
    bolt = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}") if dims["bolt"] else None
    shape = gusset_geometry.supported_gusset(
        arms, weld_edge, thickness_cm=dims["thickness"], hole_diameter_cm=dims["hole"], rows=dims["rows"],
        end_distance_cm=dims["end_dist"], pitch_cm=dims["pitch"], edge_distance_cm=dims["edge"],
        pad_width_cm=dims["pad"], washer_radius_cm=bolt.washer_outer_diameter_mm*.05 if bolt else 0.,
        alternate=alternate, weld_length_cm=dims["weld_length"],
    )
    weld = sorted(x for x, y in shape.plate.outline if abs(y) < TOL)
    proxy = joints._body_proxy(support.body, support.occurrence)
    middle = geo.scale(normal, dims["thickness"]/2)
    for station in (weld[0]+.01, sum(weld)/len(weld), weld[-1]-.01):
        point = geo.add(shape.plate.point(station, 0.), geo.add(middle, inside))
        if proxy.pointContainment(core.Point3D.create(*point)) != fusion.PointContainment.PointInsidePointContainment:
            raise ValueError("Le chant du gousset ne porte pas sur la face réelle du profil.")
    return (*_brace_hardware(members, arms, shape, dims, bolt,
                             check_material=check_material and not adjustments), adjustments, gaps)


def _brace_ends(members, arms, weld_point, outward, clearance):
    if clearance < 0. and abs(clearance+.1) > TOL:
        raise ValueError("Saisir un jeu positif ou nul, ou −1 pour garder l’about.")
    result, adjustments, gaps = [], [], []
    for member, arm in zip(members, arms):
        points = joints._body_sample_points(member.body, member.occurrence)
        gap = gusset_geometry.brace_clearance(points, weld_point, outward)
        gaps.append(gap if clearance < 0. else clearance)
        if clearance < 0.:
            result.append(arm)
            continue
        axis = geo.normalize(geo.subtract(arm.far, arm.near))
        shift = gusset_geometry.brace_end_shift(gap, clearance, axis, outward)
        if abs(shift) <= TOL:
            result.append(arm)
            continue
        if member.occurrence.component.bRepBodies.count != 1:
            raise ValueError("Régler l’about sur une cornière à corps unique, avant le croisement en X.")
        face, points_on_face = joints._planar_end_face(member.body, member.occurrence, geo.scale(axis, -1.), arm.near)
        proxy = face.createForAssemblyContext(member.occurrence)
        plane = core.Plane.cast((proxy or face).geometry)
        if not plane:
            raise ValueError("La face d’about de la cornière doit être plane.")
        normal = geo.normalize(plane.normal.asArray())
        if abs(geo.dot(normal, axis)) < .9999:
            raise ValueError("Le réglage du jeu attend une cornière coupée d’équerre à son bout.")
        displacement = geo.scale(axis, shift)
        plane_point = geo.add(points_on_face[0], displacement)
        far = max(geo.dot(point, axis) for point in points)
        if far-geo.dot(plane_point, axis) <= TOL:
            raise ValueError("Le jeu demandé dépasse l’about opposé de la cornière.")
        actual_near = geo.dot(geo.subtract(plane_point, arm.near), axis)
        result.append(replace(arm, near=geo.add(arm.near, geo.scale(axis, actual_near))))
        adjustments.append(BraceEnd(member, face, plane_point, normal, geo.dot(displacement, normal),
                                    axis, far, weld_point, outward, clearance))
    return tuple(result), tuple(adjustments), tuple(gaps)


def _adjust_brace_end(adjustment, created):
    member = adjustment.member
    component = member.occurrence.component
    plane = joints._add_face_offset_plane(component, member.occurrence, adjustment.face,
                                          adjustment.plane_offset, "Jeu au porteur")
    created.append(plane)
    try:
        joints._validate_plane_match(plane, member.occurrence, adjustment.plane_point, adjustment.plane_normal)
    except RuntimeError:
        # Fusion peut orienter un plan d’offset à l’opposé de la normale géométrique de la face.
        reflected = geo.subtract(adjustment.plane_point,
                                 geo.scale(adjustment.plane_normal, 2*adjustment.plane_offset))
        joints._validate_plane_match(plane, member.occurrence, reflected, adjustment.plane_normal)
        if not plane.deleteMe():
            raise RuntimeError("Fusion n’a pas pu retirer le plan d’offset inversé.")
        created.pop()
        plane = joints._add_face_offset_plane(component, member.occurrence, adjustment.face,
                                              -adjustment.plane_offset, "Jeu au porteur")
        created.append(plane)
        joints._validate_plane_match(plane, member.occurrence, adjustment.plane_point, adjustment.plane_normal)
    source, target = core.ObjectCollection.create(), core.ObjectCollection.create()
    source.add(adjustment.face)
    target.add(plane)
    features = component.features.replaceFaceFeatures
    feature_input = features.createInput(source, False, target)
    feature = features.add(feature_input) if feature_input else None
    if not feature:
        raise RuntimeError("Fusion n’a pas ajusté l’about de la cornière.")
    created.append(feature)
    feature.name = "Ajustage de l’about au gousset"
    body = joints._single_body(member.occurrence, "cornière après ajustage")
    points = joints._body_sample_points(body, member.occurrence)
    gap = gusset_geometry.brace_clearance(points, adjustment.weld_point, adjustment.outward)
    far = max(geo.dot(point, adjustment.axis) for point in points)
    if abs(gap-adjustment.clearance) > .001 or abs(far-adjustment.far_station) > .001:
        raise RuntimeError("Le jeu obtenu ou la position de l’autre bout ne correspond pas au calcul.")
    return body


def _central_gusset(members, dims, alternate, *, check_material=True):
    endpoints = [joints._line_endpoints(member.curve) for member in members]

    def sum_spans(indices):
        ends = [points[index] for index, points in zip(indices, endpoints)]
        middle = tuple(sum(axis)/len(ends) for axis in zip(*ends))
        return sum(geo.length(geo.subtract(point, middle))**2 for point in ends)

    joint_ends = min(product((0, 1), repeat=4), key=sum_spans)
    arms = tuple(_brace_arm(member, end[index], end[1-index])
                 for member, end, index in zip(members, endpoints, joint_ends))
    shape, bolt = _central_shape(arms, dims, alternate)
    return _brace_hardware(members, arms, shape, dims, bolt, check_material=check_material)


def _central_shape(arms, dims, alternate, level_outline=False, *, bearing_vertical=None, scallop_depth_cm=0.):
    bolt = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}") if dims["bolt"] else None
    shape = gusset_geometry.central_gusset(
        arms, thickness_cm=dims["thickness"], hole_diameter_cm=dims["hole"], rows=dims["rows"],
        end_distance_cm=dims["end_dist"], pitch_cm=dims["pitch"], edge_distance_cm=dims["edge"],
        pad_width_cm=dims["pad"], washer_radius_cm=bolt.washer_outer_diameter_mm*.05 if bolt else 0.,
        alternate=alternate, level_outline=level_outline, bearing_vertical=bearing_vertical,
        scallop_depth_cm=scallop_depth_cm,
    )
    return shape, bolt


def _crossing_gusset(members, dims, alternate, *, check_material=True):
    cuts = crossing_braces.plan(members, dims["cross_gap"])
    arms = tuple(_brace_arm(member, near, far) for member, cut in zip(members, cuts)
                 for near, far in cut.branches)
    shape, bolt = _central_shape(arms, dims, alternate, level_outline=True)
    plates, drills, fasteners = _brace_hardware(
        tuple(member for member in members for _ in range(2)), arms, shape, dims, bolt,
        check_material=check_material,
    )
    merged = tuple(replace(first, centres=first.centres+second.centres)
                   for first, second in zip(drills[::2], drills[1::2]))
    return plates, merged, fasteners, cuts


def _brace_hardware(members, arms, shape, dims, bolt, *, check_material=True):
    normal = shape.plate.normal
    drills, fasteners = [], []
    for member, arm, centres in zip(members, arms, shape.centres_by_arm):
        if check_material:
            proxy = joints._body_proxy(member.body, member.occurrence)
            for centre in centres:
                sample = geo.add(centre, geo.scale(normal, -arm.thickness_cm/2))
                if proxy.pointContainment(core.Point3D.create(*sample)) != fusion.PointContainment.PointInsidePointContainment:
                    raise ValueError("Un perçage sort de la face d’appui d’une diagonale.")
        drills.append(Drilling(member, centres, normal, dims["hole"], 2*arm.thickness_cm+.2))
        if bolt:
            fasteners.append(_fastener_plan(centres, normal, dims["thickness"], arm.thickness_cm, dims["hole"], bolt))
    return (shape.plate,), tuple(drills), tuple(fasteners)


def _ridge(design, members, dims, double):
    for member in members:
        _i_geometry(member)
    cut = joints.evaluate_miter_joint(design, *(member.occurrence for member in members), allow_aligned=True)
    treatments = cut.first_treatment, cut.second_treatment
    beams = []
    for member, t in zip(members, treatments):
        path = geo.subtract(t.inner_point, t.joint_endpoint)
        beams.append(ridge_geometry.RidgeBeam(
            t.joint_endpoint, geo.normalize(path), member.section_y, member.section_x,
            _range(member, 0), _range(member, 1), geo.length(path),
        ))
    spec = bolt_specs.bolt_spec_by_designation(f"M{dims['bolt']*10:g}") if dims["bolt"] else None
    result = ridge_geometry.plan_ridge(cut.geometry.joint_point, *beams, dims, double=double,
                                      washer_radius=spec.washer_outer_diameter_mm*.05 if spec else 0.)
    if any(abs(geo.dot(cut.cut_normal, target.interior_normal)) < .99999 for target in result.cuts):
        raise ValueError("L’application du faîtage demande pour l’instant deux pentes symétriques.")
    hardware = ()
    if spec:
        hardware = (_fastener_plan(result.bolt_centres, result.bolt_axis, dims["thickness"],
                                   dims["thickness"], dims["hole"], spec),)
    return result.plates, hardware, (cut, result.cuts)


def _apply_ridge_trim(ridge, created):
    evaluation, targets = ridge
    geometry = evaluation.geometry
    aligned = geo.length(geo.cross(geometry.primary_approach_direction,
                                   geometry.secondary_approach_direction)) <= geo.GEOMETRY_TOLERANCE_CM
    for treatment, target in zip((evaluation.first_treatment, evaluation.second_treatment), targets):
        occurrence = treatment.occurrence
        if aligned:
            mid_plane = joints._add_path_plane(occurrence.component, occurrence, treatment.curve,
                                              treatment.endpoint_index, "Plan d’about des poutres alignées")
            created.append(mid_plane)
        else:
            mid_plane = joints._add_miter_cut_plane(evaluation, occurrence, created)
        plane = joints._add_offset_to_point(occurrence.component, occurrence, mid_plane, target.point,
                                           "Plan d’appui du faîtage")
        created.append(plane)
        joints._validate_plane_match(plane, occurrence, target.point, target.interior_normal)
        joints._replace_member_end(treatment, joints._treatment_end_face(treatment), plane,
                                   target.point, evaluation.cut_normal, "Coupe d’about du faîtage", created)


def evaluate(design, kind, occurrences, parameters_mm=None, alternate=False, *, check_material=True,
             preview_support=False):
    """Prépare la géométrie à partir des barres sélectionnées. Aucun effet CAO."""
    template = assembly_catalog.template_for(kind)
    if len(occurrences) != len(template.roles) or len(set(o.entityToken for o in occurrences)) != len(occurrences):
        raise ValueError("Sélectionner les profils attendus, chacun une seule fois.")
    if kind.startswith("gusset_end_"):
        support = _member(design, occurrences[0], template.roles[0])
        members = (support, *(_brace_member(design, occurrence, role, support)
                              for occurrence, role in zip(occurrences[1:], template.roles[1:])))
    elif kind == "gusset_cross" and not check_material:
        members = []
        for occurrence, role in zip(occurrences, template.roles):
            bodies = list(occurrence.component.bRepBodies)
            branch = bodies[0] if len(bodies) == 2 and all(map(crossing_braces.is_branch, bodies)) else None
            members.append(_member(design, occurrence, role, branch))
        members = tuple(members)
    else:
        members = tuple(_member(design, o, role, allow_nested=template.family == "Poutre-poteau")
                        for o, role in zip(occurrences, template.roles))
    dims = shapes.dimensions(template, parameters_mm or {})
    drilling, trim, fasteners, ridge_trim, crossing = (), None, (), (), ()
    brace_ends, brace_gaps = (), ()
    support_errors = ()
    if len(members) == 1:
        start, end = joints._line_endpoints(members[0].curve)
        end_index = int(end[2] < start[2])
        if alternate:
            end_index = 1 - end_index
        plates = _base(members[0], dims, end_index, kind, flush_to_skeleton=True)
    elif kind == "shear_plate":
        plates, drilling, hardware = _shear_plate(*members, dims, alternate, check_material=check_material)
        fasteners = (hardware,) if hardware else ()
    elif kind == "splice_web":
        plates, drilling, fasteners = _splice_web(*members, dims, alternate, check_material=check_material)
    elif kind == "gusset_4":
        plates, drilling, fasteners = _central_gusset(members, dims, alternate, check_material=check_material)
    elif kind == "gusset_cross":
        plates, drilling, fasteners, crossing = _crossing_gusset(members, dims, alternate, check_material=check_material)
    elif kind.startswith("gusset_end_"):
        plates, drilling, fasteners, brace_ends, brace_gaps = _end_gusset(members[0], members[1:], dims, alternate, check_material=check_material)
    elif kind.startswith("ridge_"):
        plates, fasteners, ridge_trim = _ridge(design, members, dims, kind == "ridge_double")
    else:
        plates, drilling, trim, hardware, support_errors = _end_plate(
            design, *members, dims, kind == "beam_column_haunch", raked=kind == "beam_column_rake",
            preview_support=preview_support,
        )
        fasteners = (hardware,) if hardware else ()
    settings = {field.key: dims[field.key]*(10 if field.unit == "mm" else 1)
                for _, fields in template.groups for field in fields}
    plates = tuple(shapes.finish_rectangle(plate, dims.get("chamfer", 0.), dims.get("corner_radius", 0.))
                   if plate.finishable else plate for plate in plates)
    return AssemblyPlan(template, members, settings,
                        plates, drilling, trim, fasteners, ridge_trim, alternate, crossing, brace_ends, brace_gaps,
                        base_flush=kind.startswith("base_"), support_errors=support_errors)


def _create_plate(parent, plate, material):
    matrix = core.Matrix3D.create()
    matrix.setWithCoordinateSystem(core.Point3D.create(*plate.origin),
                                   core.Vector3D.create(*plate.u), core.Vector3D.create(*plate.v),
                                   core.Vector3D.create(*plate.normal))
    occurrence = parent.occurrences.addNewComponent(matrix)
    if not occurrence:
        raise RuntimeError("Création du composant de tôle refusée.")
    component = occurrence.component
    component.name = plate.name
    sketch = component.sketches.add(component.xYConstructionPlane)
    sketch.name = "Contour et perçages"
    points = [core.Point3D.create(x, y, 0) for x, y in plate.outline]
    lines = sketch.sketchCurves.sketchLines
    arcs = dict(plate.arcs)
    for index, (start, end) in enumerate(zip(points, points[1:]+points[:1])):
        if index in arcs:
            midpoint = core.Point3D.create(*arcs[index], 0)
            sketch.sketchCurves.sketchArcs.addByThreePoints(start, midpoint, end).isFixed = True
        else:
            lines.addByTwoPoints(start, end).isFixed = True
    for x, y, diameter in plate.holes:
        sketch.sketchCurves.sketchCircles.addByCenterRadius(core.Point3D.create(x, y, 0), diameter/2).isFixed = True
    profile = max(sketch.profiles, key=lambda region: region.profileLoops.count)
    if profile.profileLoops.count != 1+len(plate.holes):
        raise RuntimeError("Le contour de la tôle et ses perçages ne forment pas un profil unique.")
    feature = component.features.extrudeFeatures.addSimple(
        profile, core.ValueInput.createByReal(plate.thickness_cm), fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    if not feature or feature.bodies.count != 1:
        raise RuntimeError("Extrusion de la tôle incomplète.")
    feature.name = "Épaisseur de la tôle"
    body = feature.bodies.item(0)
    if isinstance(plate, upn_splice.WedgePlate):
        body = upn_splice.trim_wedge(component, body, plate)
    body.name = plate.name
    if material:
        body.material = material
    sketch.isVisible = False
    if geo.length(geo.subtract(occurrence.transform2.translation.asArray(), plate.origin)) > TOL:
        raise RuntimeError("Fusion n’a pas conservé la position de la tôle.")
    return occurrence


def _check_bolted_assembly(design, plan, group):
    hardware = fastener_creator.assembly_hardware(group)
    model = [*(child for child in group.childOccurrences if child not in hardware),
             *_associated_bolts(group)]
    # The secondary can still overlap its future end plate until it is trimmed.
    members = plan.members[:1] if plan.trim and plan.trim.treatment.requires_split else plan.members
    for member in members:
        if member.occurrence not in model:
            model.append(member.occurrence)
    fastener_creator.verify_clearance(design, model)


def _base_end_index(member, normal):
    start, end = joints._line_endpoints(member.curve)
    return int(geo.dot(geo.subtract(end, start), normal) > 0)


def _link_group_to_end(root, group, member, end_index, created, label):
    # Let Fusion solve the group pose first, then build the plates in its local frame.
    frame = group.component.sketches.add(group.component.xYConstructionPlane)
    frame.name = "Repère du raccord"
    local = fusion.JointGeometry.createByPoint(frame.originPoint.createForAssemblyContext(group))
    key = (fusion.JointKeyPointTypes.StartKeyPoint, fusion.JointKeyPointTypes.EndKeyPoint)[end_index]
    source = fusion.JointGeometry.createByCurve(member.curve, key)
    joint_input = root.joints.createInput(local, source)
    joint_input.setAsRigidJointMotion()
    joint = root.joints.add(joint_input)
    if not joint:
        raise RuntimeError("Fusion a refusé la liaison avec l’extrémité du profil.")
    created.append(joint)
    joint.name = "Liaison au squelette – " + label
    frame.isVisible = False


def _local_plate(plate, world_to_group):
    origin = core.Point3D.create(*plate.origin)
    u, v = (core.Vector3D.create(*axis) for axis in (plate.u, plate.v))
    for value in (origin, u, v):
        value.transformBy(world_to_group)
    return replace(plate, origin=origin.asArray(), u=u.asArray(), v=v.asArray())


def _plates_match(group, plates):
    hardware = fastener_creator.assembly_hardware(group)
    children = [child for child in group.childOccurrences if child not in hardware]
    if len(children) != len(plates):
        return False
    for child, plate in zip(children, plates):
        actual = child.transform2.getAsCoordinateSystem()
        expected = (plate.origin, plate.u, plate.v, plate.normal)
        if any(geo.length(geo.subtract(got.asArray(), want)) > TOL
               for got, want in zip(actual, expected)):
            return False
    return True


def _associated_bolts(group):
    def bolts_in(occurrence):
        if occurrence.component.attributes.itemByName(fastener_creator.ATTRIBUTE_GROUP, "configuration"):
            yield occurrence
        else:
            for child in occurrence.childOccurrences:
                yield from bolts_in(child)

    return [bolt for folder in fastener_creator.assembly_hardware(group) for bolt in bolts_in(folder)]


def _associated_cut_matches(feature, drill):
    if feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
        return False
    contextual = feature.createForAssemblyContext(drill.member.occurrence)
    if contextual.sideFaces.count != len(drill.centres):
        return False
    centres = list(drill.centres)
    for face in contextual.sideFaces:
        cylinder = core.Cylinder.cast(face.geometry)
        if (not cylinder or abs(2*cylinder.radius-drill.diameter) > TOL
                or abs(geo.dot(cylinder.axis.asArray(), drill.axis)) < 1.-TOL
                or sum(bool(core.Circle3D.cast(edge.geometry)) for edge in face.edges) != 2):
            return False
        centre = min(centres, key=lambda p: geo.length(
            geo.cross(geo.subtract(cylinder.origin.asArray(), p), drill.axis)))
        if geo.length(geo.cross(geo.subtract(cylinder.origin.asArray(), centre), drill.axis)) > TOL:
            return False
        centres.remove(centre)
    return True


def _associated_bolts_match(group, fasteners):
    bolts = _associated_bolts(group)
    poses = [pose for batch in fasteners for pose in batch[0]]
    if len(bolts) != len(poses):
        return False
    for bolt in bolts:
        origin, _, _, axis = bolt.transform2.getAsCoordinateSystem()
        match = next((pose for pose in poses
                      if geo.length(geo.subtract(origin.asArray(), pose.origin)) < TOL
                      and geo.dot(axis.asArray(), pose.z_axis) > 1.-TOL), None)
        if match is None:
            return False
        poses.remove(match)
    return True


def _drill_sources(group, drill):
    circles = []
    for occurrence in group.childOccurrences:
        sketch = occurrence.component.sketches.item(0).createForAssemblyContext(occurrence)
        for circle in sketch.sketchCurves.sketchCircles:
            geometry = circle.worldGeometry
            if abs(geo.dot(geometry.normal.asArray(), drill.axis)) > 1.-TOL:
                circles.append((circle, geometry.center.asArray()))
    matches = []
    for point in drill.centres:
        nearby = [item for item in circles
                  if geo.length(geo.cross(geo.subtract(item[1], point), drill.axis)) < TOL]
        if not nearby:
            raise RuntimeError("La tôle de référence d’un perçage est introuvable.")
        matches.append(min(nearby, key=lambda item: geo.length(geo.subtract(item[1], point)))[0])
    return matches


def _reference_state(member):
    def rounded(vector):
        return [round(number, 6) for number in vector]

    return dict(profile=member.source.name, bounds=rounded(member.bounds), anchor=rounded(member.anchor),
                endpoints=[rounded(point) for point in joints._line_endpoints(member.curve)],
                rotation_axes=[rounded(member.section_x), rounded(member.section_y)],
                transform=rounded(member.occurrence.transform2.asArray()))


def _base_still_matches(group, record, template, member, previous, current):
    # A rigid link can follow a new pose. Section and anchor changes require a new check.
    if any(previous[key] != current[key] for key in ("profile", "bounds", "anchor")):
        return False
    dimensions = shapes.dimensions(template, assembly_catalog.recorded_parameters(template, record["parameters_mm"]))
    flush = bool(record.get("base_flush"))
    plates = _base(member, dimensions, record["base_end_index"], template.key,
                   include_anchor_hardware=bool(record.get("base_anchor_hardware")), flush_to_skeleton=flush)
    if not _plates_match(group, plates):
        return False
    if flush:
        from . import base_seat_trim

        try:
            base_seat_trim.verify_plate_seat(member, plates[0])
        except (ValueError, RuntimeError):
            return False
    return True


def _linked_raccord_matches(design, group, record, template, members, link):
    dimensions = shapes.dimensions(template, assembly_catalog.recorded_parameters(template, record["parameters_mm"]))
    if template.key == "shear_plate":
        plates, drilling, batch = _shear_plate(*members, dimensions, link["alternate"], check_material=False)
        batches = (batch,) if batch else ()
    elif template.key == "splice_web":
        plates, drilling, batches = _splice_web(*members, dimensions, link["alternate"], check_material=False)
    else:
        plates, drilling, _, batch, _ = _end_plate(design, *members, dimensions,
                                                   template.key == "beam_column_haunch",
                                                   raked=template.key == "beam_column_rake")
        batches = (batch,) if batch else ()
    if not _plates_match(group, plates) or not _associated_bolts_match(group, batches):
        return False
    tokens = link.get("cuts", [link["cut"]] if link.get("cut") else [])
    if len(tokens) != len(drilling):
        return False
    for token, drill in zip(tokens, drilling):
        features = [feature for entity in design.findEntityByToken(token)
                    if (feature := fusion.ExtrudeFeature.cast(entity)) and feature.isValid]
        if len(features) != 1 or not _associated_cut_matches(features[0], drill):
            return False
    return True


def inspect_references(design, group):
    attribute = group.component.attributes.itemByName(ATTRIBUTE_GROUP, "definition")
    if not attribute:
        raise ValueError("Sélectionner un groupe d’assemblage à platines JHR.")
    record = json.loads(attribute.value)
    stored = record.get("reference_state")
    if not stored:
        return {"type": record["kind"], "status": "historique_sans_relevé"}
    template = assembly_catalog.template_for(record["kind"])
    changes = []
    members = []
    link = record.get("shear_link") or record.get("end_plate_link") or record.get("splice_link")
    for i, (token, previous, role) in enumerate(zip(record["members"], stored, template.roles)):
        items = [occurrence for entity in design.findEntityByToken(token)
                 if (occurrence := fusion.Occurrence.cast(entity)) and occurrence.isValid]
        if len(items) != 1:
            changes.append({"role": role, "cause": "profil_source_introuvable"})
            continue
        try:
            occurrence = items[0]
            if template.key == "gusset_cross":
                branches = list(occurrence.component.bRepBodies)
                if len(branches) != 2 or not all(crossing_braces.is_branch(body) for body in branches):
                    raise ValueError("Les deux branches du croisement ne sont plus présentes.")
                member = _member(design, occurrence, role, branches[0])
            elif template.key.startswith("gusset_end_") and i:
                if not members:
                    raise ValueError("Le profil porteur est introuvable.")
                member = _brace_member(design, occurrence, role, members[0])
            else:
                member = _member(design, occurrence, role, allow_nested=template.family == "Poutre-poteau")
            members.append(member)
            current = _reference_state(member)
            if link:
                if any(previous[key] != current[key] for key in ("profile", "bounds", "anchor")):
                    changes.append({"role": role, "cause": "section_source_modifiée"})
                continue
            if current == previous:
                continue
            if "base_end_index" in record and _base_still_matches(group, record, template, member, previous, current):
                continue
        except (ValueError, FileNotFoundError) as error:
            changes.append({"role": role, "cause": str(error)})
            continue
        changes.append({"role": role, "cause": "géométrie_source_modifiée"})
    if link and not changes:
        try:
            if not _linked_raccord_matches(design, group, record, template, members, link):
                changes.append({"role": template.label, "cause": "la géométrie ne correspond plus aux profils"})
        except (ValueError, RuntimeError) as error:
            changes.append({"role": template.label, "cause": str(error)})
    return {"type": record["kind"], "status": "à_revoir" if changes else "à_jour", "changes": changes}


def create(design, plan, *, parent=assembly_placement.DEFAULT_PARENT):
    """Applique la géométrie préparée à la conception active et indique l’étape en erreur."""
    from . import timeline_groups

    if plan.support_errors:
        raise support_error(plan.support_errors)

    root = design.rootComponent
    if parent is assembly_placement.DEFAULT_PARENT:
        parent = assembly_placement.parent_for(design, (member.occurrence for member in plan.members))
    stage = "contrôle préalable"
    tokens = [member.occurrence.entityToken for member in plan.members]
    base_end_index = None
    if plan.template.key.startswith("base_"):
        outward = geo.scale(plan.plates[0].normal, -1) if plan.base_flush else plan.plates[0].normal
        base_end_index = _base_end_index(plan.members[0], outward)
    linked_splice = (plan.template.key == "splice_web"
                     and not any(isinstance(plate, upn_splice.WedgePlate) for plate in plan.plates))
    linked_raccord = linked_splice or plan.template.key in ("shear_plate", "beam_column", "beam_column_haunch")
    for attribute in design.findAttributes(ATTRIBUTE_GROUP, "definition"):
        payload = json.loads(attribute.value)
        kind = payload["kind"]
        if (kind == plan.template.key or (kind.startswith("base_") and plan.template.key.startswith("base_"))
                or (kind.startswith("beam_column") and plan.template.key.startswith("beam_column"))):
            if all(any(member.occurrence == resolved for resolved in design.findEntityByToken(token))
                   for member, token in zip(plan.members, payload["members"])):
                # A post can have a plate at both ends.
                offset = geo.subtract(payload["origin"], plan.plates[0].origin)
                prior_end = payload.get("base_end_index")
                same_end = (base_end_index == prior_end if prior_end is not None
                            else abs(geo.dot(offset, plan.plates[0].normal)) < TOL)
                if len(tokens) > 1 or same_end:
                    raise ValueError("Un assemblage de ce type existe déjà à cet emplacement.")
    timeline = design.timeline
    start = timeline_groups.creation_start(timeline)
    group, created, joint_markers, component = None, [], [], None
    trim = plan.trim
    try:
        stage = "création du groupe"
        group = root.occurrences.addNewComponent(core.Matrix3D.create())
        component = group.component
        group.component.name = "JHR - " + plan.template.label
        plates = plan.plates
        if base_end_index is not None or linked_raccord:
            stage = "liaison au squelette"
            member, end_index = plan.members[0], base_end_index
            if linked_splice:
                _, (end_index, _) = _nearest_ends(*plan.members)
            elif linked_raccord:
                main, member = plan.members
                paths = plan.trim.geometry if plan.trim else _perpendicular(main, member)
                end_index = paths.secondary_joint_endpoint_index
            _link_group_to_end(root, group, member, end_index, created, plan.template.label)
            world_to_group = group.transform2.copy()
            if not world_to_group.invert():
                raise RuntimeError("Le repère de l’assemblage ne peut pas être inversé.")
            plates = tuple(_local_plate(plate, world_to_group) for plate in plates)
        for plate in plates:
            stage = plate.name
            _create_plate(group.component, plate, plan.members[-1].body.material if plate.inherit_material else None)
        if (base_end_index is not None or linked_raccord) and not _plates_match(group, plan.plates):
            raise RuntimeError("La liaison au profil a déplacé une tôle hors de sa position calculée.")
        if plan.base_flush:
            from . import base_seat_trim

            stage = "raccourcissement du poteau à la face de la platine"
            base_seat_trim.trim_to_plate(plan.members[0], group.childOccurrences.item(0), plan.plates[0], created)
        if trim and trim.primary_extensions:
            stage = "prolongement du poteau"
            for extension in trim.primary_extensions:
                joints._extend_primary_end(extension, created)
            trim = replace(trim, primary_extensions=())
        changed_bodies = {}
        for adjustment in plan.brace_ends:
            stage = "ajustage de l’about de " + adjustment.member.occurrence.name
            changed_bodies[adjustment.member.occurrence.entityToken] = _adjust_brace_end(adjustment, created)
        cut_tokens = []
        for drill in plan.drilling:
            stage = "perçage de " + drill.member.occurrence.name
            source_circles = _drill_sources(group, drill) if linked_raccord else ()
            body = changed_bodies.get(drill.member.occurrence.entityToken, drill.member.body)
            if plan.brace_ends:
                proxy = joints._body_proxy(body, drill.member.occurrence)
                inward = geo.scale(drill.axis, -(drill.span-.2)/4)
                if any(proxy.pointContainment(core.Point3D.create(*geo.add(point, inward)))
                       != fusion.PointContainment.PointInsidePointContainment for point in drill.centres):
                    raise ValueError("Un perçage sort de la cornière après l’ajustage de l’about.")
            feature, sketch = angle_cleat_creator._create_member_cut_group(
                drill.member.occurrence.component, drill.member.occurrence, body,
                drill.centres, drill.axis, drill.diameter, drill.span, "Perçages JHR", "Centres JHR",
                source_circles=source_circles,
            )
            created.extend((sketch, feature))
            if linked_raccord:
                if not _associated_cut_matches(feature, drill):
                    raise RuntimeError("Les trous projetés ne traversent pas le support aux axes attendus.")
                cut_tokens.append(feature.entityToken)
        stage = "traçabilité"
        definition = dict(
            kind=plan.template.key, members=tokens, parameters_mm=plan.settings_mm, alternate=plan.alternate,
            origin=plan.plates[0].origin, reference_state=[_reference_state(m) for m in plan.members],
        )
        if base_end_index is not None:
            definition["base_end_index"] = base_end_index
            definition["base_anchor_hardware"] = True
            definition["base_flush"] = plan.base_flush
        if linked_raccord:
            key = {"splice_web": "splice_link", "shear_plate": "shear_link"}.get(plan.template.key, "end_plate_link")
            definition[key] = dict(alternate=plan.alternate, cuts=cut_tokens)
        marker = group.component.attributes.add(ATTRIBUTE_GROUP, "definition", json.dumps(definition))
        if plan.ridge_trim:
            stage = "coupes de faîtage"
            _apply_ridge_trim(plan.ridge_trim, created)
        if plan.crossing:
            stage = "recoupe des cornières au croisement"
            for member, cut in zip(plan.members, plan.crossing):
                crossing_braces.create(member, cut, created)
        if plan.fasteners:
            stage = "pose des boulons"
            batches = {}
            for placements, diameter, length in plan.fasteners:
                batches.setdefault((diameter, length), []).extend(placements)
            for (diameter, length), placements in batches.items():
                result = simple_fastener_creator.create_modeled_fasteners(
                    design, placements, diameter, length, created_entities=created, assembly=group,
                )
                if result["occupied"]:
                    raise ValueError("Une position de boulon est déjà occupée.")
            stage = "contrôle des boulons"
            if not _associated_bolts_match(group, plan.fasteners):
                actual = len(_associated_bolts(group))
                planned = sum(len(placements) for placements, _, _ in plan.fasteners)
                raise RuntimeError(f"Implantation des boulons différente du plan ({actual} insérés, {planned} attendus).")
            stage = "contrôle des interférences"
            _check_bolted_assembly(design, plan, group)
        if trim and trim.treatment.requires_split:
            stage = "coupe d’about de la poutre"
            support = trim.secondary_occurrence
            existing = {value.name for value in support.component.attributes.itemsByGroup(joints.JOINT_ATTRIBUTE_GROUP)}
            plate = group.childOccurrences.item(0)
            extrusion = plate.component.features.extrudeFeatures.itemByName("Épaisseur de la tôle")
            if not extrusion or extrusion.endFaces.count != 1:
                raise RuntimeError("La face intérieure de la platine d’about est introuvable.")
            seat = extrusion.endFaces.item(0).createForAssemblyContext(plate)
            with timeline_groups.defer_grouping():
                created.extend(joints.create_straight_joint(trim, seat_face=seat))
            joint_markers = [value for value in support.component.attributes.itemsByGroup(joints.JOINT_ATTRIBUTE_GROUP)
                             if value.name not in existing]
            definition["joint_records"] = [{"member": support.entityToken, "name": value.name}
                                           for value in joint_markers]
            marker.value = json.dumps(definition)
        stage = "rangement dans le sous-assemblage"
        group = assembly_placement.move_group(design, group, parent)
    except Exception as error:
        for value in joint_markers:
            if value.isValid:
                value.deleteMe()
        if group is not None and not group.isValid and component and component.isValid:
            group = next(iter(root.allOccurrencesByComponent(component)), None)
        angle_cleat_creator._delete_valid(([group] if group is not None else []) + created)
        raise RuntimeError(f"{plan.template.label} — {stage} : {error}") from error
    timeline_groups.group_creation(timeline, start, group.component.name)
    return group
