from __future__ import annotations

from dataclasses import dataclass

from . import dxf_geometry, joint_geometry


MM_TO_CM = 0.1
RIGHT_ANGLE_TOLERANCE_DEGREES = 0.5
AXIS_ALIGNMENT_TOLERANCE = 0.995


@dataclass(frozen=True)
class CleatPlacement:
    side: str
    web_face_offset_cm: float
    frames: tuple


@dataclass(frozen=True)
class RigidCleatFrame:
    origin: tuple
    x_axis: tuple
    y_axis: tuple
    z_axis: tuple


@dataclass(frozen=True)
class CleatHolePattern:
    diameter_cm: float
    row_count: int
    pitch_cm: float
    primary_gauge_cm: float
    secondary_gauge_cm: float
    row_positions_cm: tuple


def profile_contours_from_outer_corner_cm(dxf_path, max_angle_deg=5.0):
    """Rebase le contour d'aperçu en (0, 0), sans modifier le DXF source."""
    contours_mm = dxf_geometry.tessellate_profile_contours_mm(
        dxf_path,
        max_angle_deg,
    )
    if len(contours_mm) != 1:
        raise ValueError(
            "La cornière d'assemblage doit contenir un unique contour fermé."
        )
    min_x_mm, min_y_mm, max_x_mm, max_y_mm = dxf_geometry.profile_bounds_mm(
        dxf_path
    )
    if (
        max_x_mm - min_x_mm <= joint_geometry.GEOMETRY_TOLERANCE_CM
        or max_y_mm - min_y_mm <= joint_geometry.GEOMETRY_TOLERANCE_CM
    ):
        raise ValueError("La section de cornière possède une dimension nulle.")
    return tuple(
        tuple(
            (
                (float(x_mm) - min_x_mm) * MM_TO_CM,
                (float(y_mm) - min_y_mm) * MM_TO_CM,
            )
            for x_mm, y_mm in contour
        )
        for contour in contours_mm
    )


def validate_double_angle_axes(
    angle_degrees,
    secondary_profile_x_axis,
    vertical_axis,
    toward_secondary_axis,
):
    if abs(float(angle_degrees) - 90.0) > RIGHT_ANGLE_TOLERANCE_DEGREES:
        raise ValueError(
            "Cette première phase d'assemblage accepte uniquement deux axes à 90°."
        )
    side_axis = joint_geometry.normalize(secondary_profile_x_axis)
    vertical = joint_geometry.normalize(vertical_axis)
    toward_secondary = joint_geometry.normalize(toward_secondary_axis)
    if abs(joint_geometry.dot(side_axis, toward_secondary)) > (
        1.0 - AXIS_ALIGNMENT_TOLERANCE
    ):
        raise ValueError(
            "L'âme secondaire n'est pas perpendiculaire à l'âme principale."
        )
    if (
        abs(joint_geometry.dot(vertical, side_axis))
        > 1.0 - AXIS_ALIGNMENT_TOLERANCE
        or abs(joint_geometry.dot(vertical, toward_secondary))
        > 1.0 - AXIS_ALIGNMENT_TOLERANCE
    ):
        raise ValueError(
            "Les hauteurs des deux profils ne partagent pas un axe vertical exploitable."
        )
    return side_axis, vertical, toward_secondary


def build_double_angle_frames(
    primary_web_face_point,
    secondary_profile_x_axis,
    vertical_axis,
    toward_secondary_axis,
    secondary_web_face_offsets_cm,
    cleat_height_cm,
    vertical_offset_cm,
    angle_degrees=90.0,
):
    """Construit deux repères symétriques, un par face de l'âme secondaire."""
    height_cm = float(cleat_height_cm)
    if height_cm <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("La hauteur des cornières doit être strictement positive.")
    offsets = tuple(float(value) for value in secondary_web_face_offsets_cm)
    if len(offsets) != 2 or offsets[0] >= offsets[1]:
        raise ValueError("Les deux faces de l'âme secondaire sont invalides.")

    side_axis, vertical, toward_secondary = validate_double_angle_axes(
        angle_degrees,
        secondary_profile_x_axis,
        vertical_axis,
        toward_secondary_axis,
    )
    middle = joint_geometry.add(
        tuple(float(value) for value in primary_web_face_point),
        joint_geometry.scale(vertical, float(vertical_offset_cm)),
    )
    bottom_shift = joint_geometry.scale(vertical, -height_cm / 2.0)
    placements = []
    for side, face_offset_cm, outward_sign in (
        ("gauche", offsets[0], -1.0),
        ("droite", offsets[1], 1.0),
    ):
        outer_corner = joint_geometry.add(
            middle,
            joint_geometry.scale(side_axis, face_offset_cm),
        )
        bottom = joint_geometry.add(outer_corner, bottom_shift)
        top = joint_geometry.add(bottom, joint_geometry.scale(vertical, height_cm))
        outward_axis = joint_geometry.scale(side_axis, outward_sign)
        placements.append(
            CleatPlacement(
                side=side,
                web_face_offset_cm=face_offset_cm,
                frames=(
                    (bottom, outward_axis, toward_secondary),
                    (top, outward_axis, toward_secondary),
                ),
            )
        )
    return tuple(placements)


def rigid_frame_for_placement(placement):
    """Retourne un repère direct dont +Z parcourt exactement la cornière."""
    bottom, x_axis, y_axis = placement.frames[0]
    top = placement.frames[-1][0]
    x_axis = joint_geometry.normalize(x_axis)
    y_axis = joint_geometry.normalize(y_axis)
    z_axis = joint_geometry.normalize(joint_geometry.cross(x_axis, y_axis))
    path = joint_geometry.subtract(top, bottom)
    if joint_geometry.dot(z_axis, path) >= 0.0:
        origin = bottom
    else:
        origin = top
    return RigidCleatFrame(
        origin=origin,
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
    )


def world_point_in_rigid_frame(frame, point):
    """Convertit un point monde dans le repère local exact de la cornière."""
    delta = joint_geometry.subtract(
        tuple(float(value) for value in point),
        frame.origin,
    )
    return (
        joint_geometry.dot(delta, frame.x_axis),
        joint_geometry.dot(delta, frame.y_axis),
        joint_geometry.dot(delta, frame.z_axis),
    )


def build_hole_pattern(
    cleat_height_cm,
    angle_width_cm,
    angle_height_cm,
    diameter_cm,
    row_count,
    pitch_cm,
    primary_gauge_cm,
    secondary_gauge_cm,
):
    """Valide un motif centré; les valeurs restent des choix de dessin."""
    height = float(cleat_height_cm)
    diameter = float(diameter_cm)
    count = int(row_count)
    pitch = float(pitch_cm)
    primary_gauge = float(primary_gauge_cm)
    secondary_gauge = float(secondary_gauge_cm)
    if height <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("La hauteur des cornières doit être strictement positive.")
    if diameter <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("Le diamètre des perçages doit être strictement positif.")
    if count < 1:
        raise ValueError("Le nombre de rangées de perçages doit être au moins égal à 1.")
    if count > 1 and pitch <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("L'entraxe vertical doit être strictement positif.")

    radius = diameter / 2.0
    for label, gauge, leg in (
        ("principale", primary_gauge, float(angle_width_cm)),
        ("secondaire", secondary_gauge, float(angle_height_cm)),
    ):
        if gauge - radius < -joint_geometry.GEOMETRY_TOLERANCE_CM:
            raise ValueError(
                "La distance de perçage sur la branche {} est trop faible pour ce diamètre."
                .format(label)
            )
        if gauge + radius > leg + joint_geometry.GEOMETRY_TOLERANCE_CM:
            raise ValueError(
                "Le perçage sort de la branche {} de la cornière."
                .format(label)
            )

    span = (count - 1) * pitch
    first = (height - span) / 2.0
    rows = tuple(first + index * pitch for index in range(count))
    if rows[0] - radius < -joint_geometry.GEOMETRY_TOLERANCE_CM or (
        rows[-1] + radius > height + joint_geometry.GEOMETRY_TOLERANCE_CM
    ):
        raise ValueError(
            "Le motif vertical de perçage ne tient pas dans la hauteur des cornières."
        )
    return CleatHolePattern(
        diameter_cm=diameter,
        row_count=count,
        pitch_cm=pitch,
        primary_gauge_cm=primary_gauge,
        secondary_gauge_cm=secondary_gauge,
        row_positions_cm=rows,
    )


def hole_centers_for_placement(placement, pattern):
    """Calcule les centres monde sur les deux branches d'une cornière."""
    bottom, outward_axis, toward_secondary = placement.frames[0]
    vertical = joint_geometry.normalize(
        joint_geometry.subtract(
            placement.frames[-1][0],
            placement.frames[0][0],
        )
    )

    def centers(gauge, gauge_axis):
        return tuple(
            joint_geometry.add(
                joint_geometry.add(
                    bottom,
                    joint_geometry.scale(gauge_axis, gauge),
                ),
                joint_geometry.scale(vertical, row),
            )
            for row in pattern.row_positions_cm
        )

    return (
        centers(pattern.primary_gauge_cm, outward_axis),
        centers(pattern.secondary_gauge_cm, toward_secondary),
    )


def validate_hole_rows_in_web(
    row_offsets_from_anchor_cm,
    hole_radius_cm,
    web_min_y_cm,
    web_max_y_cm,
    label,
):
    """Refuse un trou qui mord une semelle ou son congé dans le profil donné."""
    for offset in row_offsets_from_anchor_cm:
        if (
            offset - hole_radius_cm
            < float(web_min_y_cm) - joint_geometry.GEOMETRY_TOLERANCE_CM
            or offset + hole_radius_cm
            > float(web_max_y_cm) + joint_geometry.GEOMETRY_TOLERANCE_CM
        ):
            raise ValueError(
                "Le motif de perçage sort de la hauteur libre de l'âme {}."
                .format(label)
            )
