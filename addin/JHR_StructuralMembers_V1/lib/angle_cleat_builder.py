from __future__ import annotations

import math
from dataclasses import dataclass

from . import (
    anchors,
    angle_cleat_geometry,
    bolt_geometry,
    bolt_specs,
    cope_builder,
    cope_geometry,
    joint_builder,
    joint_geometry,
    profile_catalog,
)


ANGLE_FAMILY_ID = "Corniere_Egale"
VERTICAL_ALIGNMENT_TOLERANCE = 0.995
_WEB_MARGIN_CM = .3
_SLICE_EPSILON_CM = 1e-5


@dataclass(frozen=True)
class DoubleAnglePreviewEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: object
    secondary_metadata: object
    primary_curve: object
    secondary_curve: object
    geometry: object
    angle_profile: object
    angle_profile_geometry: object
    primary_profile_geometry: object
    secondary_profile_geometry: object
    primary_web_face_point: tuple
    secondary_web_face_offsets_cm: tuple
    primary_profile_x_axis: tuple
    primary_profile_y_axis: tuple
    secondary_profile_x_axis: tuple
    secondary_profile_y_axis: tuple
    cleat_height_cm: float
    vertical_offset_cm: float
    hole_pattern: object
    bolt_spec: object
    bolt_placements: tuple
    primary_hole_centers_world: tuple
    secondary_hole_centers_world: tuple
    angle_contours_cm: tuple
    placements: tuple


@dataclass(frozen=True)
class OpposedAnglePreviewEvaluation:
    first: DoubleAnglePreviewEvaluation
    opposite: DoubleAnglePreviewEvaluation
    bolt_placements: tuple


@dataclass(frozen=True)
class _MemberSection:
    occurrence: object
    curve: object
    shape: object
    anchor: tuple
    x: tuple
    y: tuple

    @property
    def web_thickness_mm(self):
        return self.shape.web_max_x_mm - self.shape.web_min_x_mm


def equal_angle_profiles(profiles):
    return tuple(
        profile
        for profile in profiles
        if profile.category_id == profile_catalog.GEOGRAPHIC_CATEGORY_ID
        and profile.region_id == profile_catalog.DEFAULT_REGION_ID
        and profile.family_id == ANGLE_FAMILY_ID
    )


def default_equal_angle_profile(profiles):
    available = equal_angle_profiles(profiles)
    if not available:
        raise FileNotFoundError(
            "La bibliothèque Europe ne contient aucune cornière égale."
        )
    for profile in available:
        if profile.dxf_path.name == "Corniere_Egale_50x50_ep5.dxf":
            return profile
    return available[0]


def suggest_double_angle(design, primary, secondary, profiles, row_count=0):
    """Propose une implantation géométrique avec appui complet des rondelles."""
    dimensions = _suggest_angle_dimensions(design, primary, (secondary,), profiles, row_count)
    return evaluate_double_angle_preview(design, primary, secondary, *dimensions)


def suggest_opposed_double_angle(design, primary, secondary, opposite, profiles, row_count=0):
    """Choisit une hauteur et un motif communs aux trois âmes."""
    dimensions = _suggest_angle_dimensions(design, primary, (secondary, opposite), profiles, row_count)
    return evaluate_opposed_double_angle_preview(design, primary, secondary, opposite, *dimensions)


def _gauge_bounds(profile, section, spec):
    radius = spec.washer_outer_diameter_mm * .05
    edge = radius + .1
    heel = (section.flange_thickness_mm + section.negative_root_radius_mm
            + section.positive_root_radius_mm) * .1
    # Laisser passer la boulonnerie de la branche perpendiculaire.
    return_stack = (spec.nut_height_mm + spec.washer_thickness_mm
                    + spec.thread_projection_mm + section.flange_thickness_mm) * .1
    lower = max(heel + edge, return_stack + radius)
    tip = min(profile.width_mm, profile.height_mm) * .1 - edge
    return lower, tip


def _member_section(design, occurrence, role):
    metadata = joint_builder._member_metadata(occurrence, role)
    if metadata.profile_family not in cope_builder.I_H_FAMILIES:
        raise ValueError(f"La barre {role} doit être un profil IPE, HEA ou HEB.")
    curve = joint_builder._linked_curve(design, metadata, role, allow_arc=False)
    shape = cope_geometry.analyze_i_profile_dxf(
        profile_catalog.resolve_profile_source(metadata.profile_source),
    )
    anchor = anchors.point_for_bounds(shape.bounds_mm, metadata.anchor)
    return _MemberSection(occurrence, curve, shape, anchor, *cope_builder._profile_axes(curve, metadata))


def _web_edges(member, origin, axial, up):
    import adsk.core

    native = joint_builder._single_body(member.occurrence, "à mesurer")
    body = joint_builder._body_proxy(native, member.occurrence)
    base = joint_builder._line_endpoints(member.curve)[0]
    surfaces = [[], []]
    expected = tuple((x - member.anchor[0]) * cope_geometry.MM_TO_CM
                     for x in (member.shape.web_min_x_mm, member.shape.web_max_x_mm))
    for face in body.faces:
        plane = adsk.core.Plane.cast(face.geometry)
        if not plane or abs(joint_geometry.dot(plane.normal.asArray(), member.x)) < .999:
            continue
        station = joint_geometry.dot(joint_geometry.subtract(plane.origin.asArray(), base), member.x)
        for index, target in enumerate(expected):
            if abs(station - target) > .005:
                continue
            edges = []
            for edge in face.edges:
                points = [joint_geometry.subtract(point, origin) for point in joint_builder._edge_points(edge)]
                points = [(joint_geometry.dot(point, axial), joint_geometry.dot(point, up)) for point in points]
                edges.extend(zip(points, points[1:]))
            if edges:
                surfaces[index].append(edges)
    if not all(surfaces):
        raise ValueError("Impossible de mesurer les deux faces planes de l’âme.")
    return surfaces


def _section_band(member, origin, up):
    base = joint_geometry.subtract(joint_builder._line_endpoints(member.curve)[0], origin)
    heights = [joint_geometry.dot(joint_geometry.add(base, joint_geometry.scale(
        member.y, (value - member.anchor[1]) * cope_geometry.MM_TO_CM)), up)
        for value in (member.shape.web_min_y_mm, member.shape.web_max_y_mm)]
    return tuple(sorted(heights))


def _intersect_bands(first, second):
    return [(max(a, c), min(b, d)) for a, b in first for c, d in second
            if min(b, d) - max(a, c) > _SLICE_EPSILON_CM]


def _face_intervals(edges, position):
    crossings = []
    for (x0, y0), (x1, y1) in edges:
        if min(x0, x1) <= position < max(x0, x1):
            crossings.append(y0 + (position - x0) * (y1 - y0) / (x1 - x0))
    crossings.sort()
    return zip(crossings[::2], crossings[1::2])


def _surface_band(surfaces, low, high, bands):
    """Intersection des sections du contour rogné sous la portée de la rondelle."""
    for plane_faces in surfaces:
        stops = sorted({low, high, *(x for edges in plane_faces for edge in edges for x, _ in edge
                                      if low < x < high)})
        for a, b in zip(stops, stops[1:]):
            if b - a <= _SLICE_EPSILON_CM:
                continue
            shift = min(_SLICE_EPSILON_CM, (b - a) / 4.)
            for station in (a + shift, b - shift):
                sections = [item for edges in plane_faces for item in _face_intervals(edges, station)]
                bands = _intersect_bands(bands, sections)
                if not bands:
                    return []
    return bands


def _row_dimensions(height, frozen_rows, radius, hole_mm):
    edge = radius + .1
    minimum_pitch = max(2 * edge, hole_mm * .25)
    if height < 2 * edge:
        return None
    usable = height - 2 * edge
    rows = frozen_rows or min(6, 1 + math.floor((usable + _SLICE_EPSILON_CM) / minimum_pitch))
    pitch = usable / (rows - 1) if rows > 1 else minimum_pitch
    if rows > 1 and pitch < minimum_pitch - _SLICE_EPSILON_CM:
        return None
    return rows, pitch


def _suggest_angle_dimensions(design, primary, secondaries, profiles, row_count):
    if row_count is not None and (type(row_count) != int or not 0 <= row_count <= 6):
        raise ValueError("Choisir de 1 à 6 rangées, ou 0 pour le calcul automatique.")
    main = _member_section(design, primary, "principale")
    sides = tuple(_member_section(design, occurrence, "secondaire") for occurrence in secondaries)
    intersections = tuple(joint_builder._analyze_adjusted_curve(main.curve, side.curve) for side in sides)
    if len(intersections) == 2:
        bolt_geometry.validate_opposed_axes(intersections[0].plane_normal, intersections[1].plane_normal)
    origin, up = intersections[0].secondary_joint_endpoint, sides[0].y
    if any(abs(joint_geometry.dot(member.y, up)) < VERTICAL_ALIGNMENT_TOLERANCE
           for member in (main, *sides)):
        raise ValueError("Les hauteurs des profils ne sont pas orientées dans le même plan.")
    station_axis = intersections[0].main_direction
    main_faces = _web_edges(main, origin, station_axis, up)

    bands = [_section_band(main, origin, up)]
    first_low, first_high = _section_band(sides[0], origin, up)
    supports = []
    for side, intersection in zip(sides, intersections):
        direction = intersection.plane_normal
        faces = _web_edges(side, origin, direction, up)
        bands = _intersect_bands(bands, [_section_band(side, origin, up)])
        contact = cope_geometry.web_face_cut_point(main.shape, main.anchor,
                                                  intersection.secondary_joint_endpoint, main.x, direction, 0.)
        supports.append((faces, joint_geometry.dot(joint_geometry.subtract(contact, origin), direction),
                         intersection.secondary_joint_endpoint, side))
    if not bands:
        raise ValueError("Les âmes n’ont pas de hauteur libre commune.")

    # La coupe au nez peut laisser un jeu longitudinal. Mesurer dans la matière,
    # en deçà de la rangée de boulons, pour relever les grugeages effectifs.
    for faces, start, _, _ in supports:
        material_start = max(min(x for edges in plane for edge in edges for x, _ in edge) for plane in faces)
        probe = max(start, material_start) + .1
        bands = _surface_band(faces, probe, probe + .1, bands)
    if not bands:
        raise ValueError("Les grugeages ne laissent pas de hauteur d’âme commune.")

    height = max(b - a for a, b in bands) - 2 * _WEB_MARGIN_CM
    min_leg = min(120., height * 3.2)
    thin_web = min(member.web_thickness_mm for member in (main, *sides))
    angles = [(profile, cope_geometry.analyze_single_flange_profile_dxf(profile.dxf_path))
              for profile in equal_angle_profiles(profiles)]
    angles.sort(key=lambda item: (
        min(item[0].width_mm, item[0].height_mm) < min_leg,
        abs(min(item[0].width_mm, item[0].height_mm) - min_leg),
        abs(item[1].flange_thickness_mm - thin_web),
    ))
    diameters = sorted(bolt_specs.BOLT_SPECS,
                       key=lambda spec: abs(spec.nominal_diameter_mm - height * 10 / 12))
    for spec in diameters:
        radius = spec.washer_outer_diameter_mm * .05
        if not _row_dimensions(height, row_count, radius, spec.recommended_hole_mm):
            continue
        for profile, shape in angles:
            lower, tip = _gauge_bounds(profile, shape, spec)
            if lower > tip:
                continue
            gauge = (lower + tip) / 2.
            available = bands
            for faces, start, end, side in supports:
                available = _surface_band(faces, start + gauge - radius, start + gauge + radius, available)
                correction = (sides[0].web_thickness_mm - side.web_thickness_mm) * .05
                if not lower <= gauge + correction <= tip:
                    available = []
                    break
                for value, sign in ((side.shape.web_min_x_mm, -1), (side.shape.web_max_x_mm, 1)):
                    offset = (value - side.anchor[0]) * .1 + sign * (gauge + correction)
                    point = joint_geometry.add(joint_geometry.subtract(end, origin),
                                               joint_geometry.scale(side.x, offset))
                    station = joint_geometry.dot(point, station_axis)
                    available = _surface_band(main_faces, station - radius, station + radius, available)
            if available:
                low, high = max(available, key=lambda band: band[1] - band[0])
                actual_height = high - low - 2 * _WEB_MARGIN_CM
                if pattern := _row_dimensions(actual_height, row_count, radius, spec.recommended_hole_mm):
                    center = (low + high) / 2.
                    offset = center - (first_low + first_high) / 2.
                    rows, pitch = pattern
                    return profile, actual_height, offset, spec.recommended_hole_mm * .1, rows, pitch, gauge, gauge, spec
    raise ValueError("Aucune cornière ne garde les rangées et les rondelles dans l’âme mesurée.")


def evaluate_double_angle_preview(
    design,
    primary_occurrence,
    secondary_occurrence,
    angle_profile,
    cleat_height_cm,
    vertical_offset_cm,
    hole_diameter_cm,
    hole_row_count,
    hole_pitch_cm,
    primary_hole_gauge_cm,
    secondary_hole_gauge_cm,
    bolt_spec,
):
    if primary_occurrence == secondary_occurrence:
        raise ValueError("Les deux barres sélectionnées doivent être différentes.")
    if angle_profile.family_id != ANGLE_FAMILY_ID:
        raise ValueError(
            "Cette première phase accepte uniquement une cornière égale européenne."
        )

    primary_metadata = joint_builder._member_metadata(
        primary_occurrence,
        "principale",
    )
    secondary_metadata = joint_builder._member_metadata(
        secondary_occurrence,
        "secondaire",
    )
    if primary_metadata.profile_family not in cope_builder.I_H_FAMILIES:
        raise ValueError(
            "La barre principale doit être un profil IPE, HEA ou HEB."
        )
    if secondary_metadata.profile_family not in cope_builder.I_H_FAMILIES:
        raise ValueError(
            "La barre secondaire doit être un profil IPE, HEA ou HEB."
        )

    primary_curve = joint_builder._linked_curve(
        design,
        primary_metadata,
        "principale",
        allow_arc=False,
    )
    secondary_curve = joint_builder._linked_curve(
        design,
        secondary_metadata,
        "secondaire",
        allow_arc=False,
    )
    geometry = joint_builder._analyze_adjusted_curve(primary_curve, secondary_curve)

    primary_source = profile_catalog.resolve_profile_source(
        primary_metadata.profile_source
    )
    secondary_source = profile_catalog.resolve_profile_source(
        secondary_metadata.profile_source
    )
    if not primary_source.is_file():
        raise FileNotFoundError("Le DXF source de la barre principale est introuvable.")
    if not secondary_source.is_file():
        raise FileNotFoundError("Le DXF source de la barre secondaire est introuvable.")
    if not angle_profile.dxf_path.is_file():
        raise FileNotFoundError("Le DXF source de la cornière est introuvable.")

    primary_geometry = cope_geometry.analyze_i_profile_dxf(primary_source)
    secondary_geometry = cope_geometry.analyze_i_profile_dxf(secondary_source)
    angle_geometry = cope_geometry.analyze_single_flange_profile_dxf(
        angle_profile.dxf_path
    )
    primary_anchor_mm = anchors.point_for_bounds(
        primary_geometry.bounds_mm,
        primary_metadata.anchor,
    )
    secondary_anchor_mm = anchors.point_for_bounds(
        secondary_geometry.bounds_mm,
        secondary_metadata.anchor,
    )
    primary_x, primary_y = cope_builder._profile_axes(
        primary_curve,
        primary_metadata,
    )
    secondary_x, secondary_y = cope_builder._profile_axes(
        secondary_curve,
        secondary_metadata,
    )
    if abs(joint_geometry.dot(primary_y, secondary_y)) < (
        VERTICAL_ALIGNMENT_TOLERANCE
    ):
        raise ValueError(
            "Les hauteurs des deux profils ne sont pas orientées dans le même plan."
        )

    primary_web_face_point = cope_geometry.web_face_cut_point(
        primary_geometry,
        primary_anchor_mm,
        geometry.secondary_joint_endpoint,
        primary_x,
        geometry.plane_normal,
        0.0,
    )
    secondary_web_face_offsets_cm = (
        (
            secondary_geometry.web_min_x_mm - secondary_anchor_mm[0]
        ) * cope_geometry.MM_TO_CM,
        (
            secondary_geometry.web_max_x_mm - secondary_anchor_mm[0]
        ) * cope_geometry.MM_TO_CM,
    )
    secondary_web_min_y = (
        secondary_geometry.web_min_y_mm - secondary_anchor_mm[1]
    ) * cope_geometry.MM_TO_CM
    secondary_web_max_y = (
        secondary_geometry.web_max_y_mm - secondary_anchor_mm[1]
    ) * cope_geometry.MM_TO_CM
    secondary_web_center_offset = (
        angle_cleat_geometry.web_center_offset_from_anchor_cm(
            secondary_web_min_y,
            secondary_web_max_y,
        )
    )
    effective_vertical_offset = (
        secondary_web_center_offset + float(vertical_offset_cm)
    )
    placements = angle_cleat_geometry.build_double_angle_frames(
        primary_web_face_point=primary_web_face_point,
        secondary_profile_x_axis=secondary_x,
        vertical_axis=secondary_y,
        toward_secondary_axis=geometry.plane_normal,
        secondary_web_face_offsets_cm=secondary_web_face_offsets_cm,
        cleat_height_cm=cleat_height_cm,
        vertical_offset_cm=effective_vertical_offset,
        angle_degrees=geometry.angle_degrees,
    )
    hole_pattern = angle_cleat_geometry.build_hole_pattern(
        cleat_height_cm=cleat_height_cm,
        angle_width_cm=angle_profile.width_mm * cope_geometry.MM_TO_CM,
        angle_height_cm=angle_profile.height_mm * cope_geometry.MM_TO_CM,
        diameter_cm=hole_diameter_cm,
        row_count=hole_row_count,
        pitch_cm=hole_pitch_cm,
        primary_gauge_cm=primary_hole_gauge_cm,
        secondary_gauge_cm=secondary_hole_gauge_cm,
    )
    bolt_specs.validate_hole_diameter(bolt_spec, hole_pattern.diameter_cm)
    row_offsets = angle_cleat_geometry.hole_row_offsets_from_web_center(
        pattern=hole_pattern,
        cleat_height_cm=cleat_height_cm,
        vertical_offset_cm=vertical_offset_cm,
        web_min_y_cm=secondary_web_min_y,
        web_max_y_cm=secondary_web_max_y,
    )
    angle_cleat_geometry.validate_hole_rows_in_web(
        row_offsets,
        hole_pattern.diameter_cm / 2.0,
        secondary_web_min_y,
        secondary_web_max_y,
        "secondaire",
    )
    vertical_alignment = joint_geometry.dot(secondary_y, primary_y)
    primary_row_offsets = tuple(
        value * vertical_alignment for value in row_offsets
    )
    primary_web_min_y = (
        primary_geometry.web_min_y_mm - primary_anchor_mm[1]
    ) * cope_geometry.MM_TO_CM
    primary_web_max_y = (
        primary_geometry.web_max_y_mm - primary_anchor_mm[1]
    ) * cope_geometry.MM_TO_CM
    angle_cleat_geometry.validate_hole_rows_in_web(
        primary_row_offsets,
        hole_pattern.diameter_cm / 2.0,
        primary_web_min_y,
        primary_web_max_y,
        "principale",
    )
    placement_holes = tuple(
        angle_cleat_geometry.hole_centers_for_placement(placement, hole_pattern)
        for placement in placements
    )
    primary_hole_centers = tuple(
        center
        for primary_centers, _ in placement_holes
        for center in primary_centers
    )
    secondary_hole_centers = placement_holes[0][1]
    contours = angle_cleat_geometry.profile_contours_from_outer_corner_cm(
        angle_profile.dxf_path
    )
    bolt_placements = bolt_geometry.build_angle_cleat_bolt_placements(
        placements=placements,
        hole_pattern=hole_pattern,
        primary_axis=geometry.plane_normal,
        secondary_axis=secondary_x,
        primary_web_thickness_cm=(
            primary_geometry.web_max_x_mm - primary_geometry.web_min_x_mm
        ) * cope_geometry.MM_TO_CM,
        secondary_web_thickness_cm=(
            secondary_geometry.web_max_x_mm - secondary_geometry.web_min_x_mm
        ) * cope_geometry.MM_TO_CM,
        angle_thickness_cm=(
            angle_geometry.flange_thickness_mm * cope_geometry.MM_TO_CM
        ),
        spec=bolt_spec,
    )
    return DoubleAnglePreviewEvaluation(
        primary_occurrence=primary_occurrence,
        secondary_occurrence=secondary_occurrence,
        primary_metadata=primary_metadata,
        secondary_metadata=secondary_metadata,
        primary_curve=primary_curve,
        secondary_curve=secondary_curve,
        geometry=geometry,
        angle_profile=angle_profile,
        angle_profile_geometry=angle_geometry,
        primary_profile_geometry=primary_geometry,
        secondary_profile_geometry=secondary_geometry,
        primary_web_face_point=primary_web_face_point,
        secondary_web_face_offsets_cm=secondary_web_face_offsets_cm,
        primary_profile_x_axis=primary_x,
        primary_profile_y_axis=primary_y,
        secondary_profile_x_axis=secondary_x,
        secondary_profile_y_axis=secondary_y,
        cleat_height_cm=float(cleat_height_cm),
        vertical_offset_cm=float(vertical_offset_cm),
        hole_pattern=hole_pattern,
        bolt_spec=bolt_spec,
        bolt_placements=bolt_placements,
        primary_hole_centers_world=primary_hole_centers,
        secondary_hole_centers_world=secondary_hole_centers,
        angle_contours_cm=contours,
        placements=placements,
    )


def evaluate_opposed_double_angle_preview(
    design,
    primary_occurrence,
    secondary_occurrence,
    opposite_occurrence,
    angle_profile,
    cleat_height_cm,
    vertical_offset_cm,
    hole_diameter_cm,
    hole_row_count,
    hole_pitch_cm,
    primary_hole_gauge_cm,
    secondary_hole_gauge_cm,
    bolt_spec,
):
    if (primary_occurrence == secondary_occurrence or primary_occurrence == opposite_occurrence
            or secondary_occurrence == opposite_occurrence):
        raise ValueError("Sélectionner trois barres différentes.")
    first = evaluate_double_angle_preview(
        design, primary_occurrence, secondary_occurrence, angle_profile, cleat_height_cm,
        vertical_offset_cm, hole_diameter_cm, hole_row_count, hole_pitch_cm, primary_hole_gauge_cm,
        secondary_hole_gauge_cm, bolt_spec,
    )
    other_metadata = joint_builder._member_metadata(opposite_occurrence, "secondaire opposée")
    if other_metadata.profile_family not in cope_builder.I_H_FAMILIES:
        raise ValueError("La barre secondaire opposée doit être un profil IPE, HEA ou HEB.")
    other_curve = joint_builder._linked_curve(design, other_metadata, "secondaire opposée", allow_arc=False)
    other_geometry = joint_builder._analyze_adjusted_curve(first.primary_curve, other_curve)
    bolt_geometry.validate_opposed_axes(first.geometry.plane_normal, other_geometry.plane_normal)
    _, other_vertical = cope_builder._profile_axes(other_curve, other_metadata)

    other_section = cope_geometry.analyze_i_profile_dxf(
        profile_catalog.resolve_profile_source(other_metadata.profile_source)
    )
    other_anchor_y = anchors.point_for_bounds(other_section.bounds_mm, other_metadata.anchor)[1]
    other_center = ((other_section.web_min_y_mm + other_section.web_max_y_mm) / 2.
                    - other_anchor_y) * cope_geometry.MM_TO_CM
    first_bottom, first_top = (frame[0] for frame in first.placements[0].frames)
    first_center = joint_geometry.scale(joint_geometry.add(first_bottom, first_top), .5)
    other_offset = joint_geometry.dot(
        joint_geometry.subtract(first_center, other_geometry.secondary_joint_endpoint), other_vertical,
    ) - other_center
    first_section = first.secondary_profile_geometry
    thickness_change_mm = ((first_section.web_max_x_mm - first_section.web_min_x_mm)
                           - (other_section.web_max_x_mm - other_section.web_min_x_mm))
    # Les ailes de la cornière partent des faces de l'âme secondaire.
    other_gauge = float(primary_hole_gauge_cm) + thickness_change_mm * cope_geometry.MM_TO_CM / 2.0
    if abs(thickness_change_mm) > bolt_geometry.SPACING_TOLERANCE_CM / cope_geometry.MM_TO_CM:
        lower, tip = _gauge_bounds(angle_profile, first.angle_profile_geometry, bolt_spec)
        if not lower <= other_gauge <= tip:
            raise ValueError("Les épaisseurs d’âme demandent un autre déport ou une cornière plus large.")
    opposite = evaluate_double_angle_preview(
        design, primary_occurrence, opposite_occurrence, angle_profile, cleat_height_cm,
        other_offset, hole_diameter_cm, hole_row_count, hole_pitch_cm, other_gauge,
        secondary_hole_gauge_cm, bolt_spec,
    )
    web = first.primary_profile_geometry
    web_thickness = (web.web_max_x_mm - web.web_min_x_mm) * cope_geometry.MM_TO_CM
    angle_thickness = first.angle_profile_geometry.flange_thickness_mm * cope_geometry.MM_TO_CM
    bolts = bolt_geometry.build_opposed_angle_cleat_bolt_placements(
        first.bolt_placements, opposite.bolt_placements, web_thickness, angle_thickness, bolt_spec,
    )
    return OpposedAnglePreviewEvaluation(first, opposite, bolts)
