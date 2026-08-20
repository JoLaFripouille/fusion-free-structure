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
