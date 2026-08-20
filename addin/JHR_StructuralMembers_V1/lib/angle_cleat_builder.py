from __future__ import annotations

from dataclasses import dataclass

from . import (
    anchors,
    angle_cleat_geometry,
    cope_builder,
    cope_geometry,
    joint_builder,
    joint_geometry,
    profile_catalog,
)


ANGLE_FAMILY_ID = "Corniere_Egale"
VERTICAL_ALIGNMENT_TOLERANCE = 0.995


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
    cleat_height_cm: float
    vertical_offset_cm: float
    angle_contours_cm: tuple
    placements: tuple


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


def evaluate_double_angle_preview(
    design,
    primary_occurrence,
    secondary_occurrence,
    angle_profile,
    cleat_height_cm,
    vertical_offset_cm,
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
    placements = angle_cleat_geometry.build_double_angle_frames(
        primary_web_face_point=primary_web_face_point,
        secondary_profile_x_axis=secondary_x,
        vertical_axis=secondary_y,
        toward_secondary_axis=geometry.plane_normal,
        secondary_web_face_offsets_cm=secondary_web_face_offsets_cm,
        cleat_height_cm=cleat_height_cm,
        vertical_offset_cm=vertical_offset_cm,
        angle_degrees=geometry.angle_degrees,
    )
    contours = angle_cleat_geometry.profile_contours_from_outer_corner_cm(
        angle_profile.dxf_path
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
        cleat_height_cm=float(cleat_height_cm),
        vertical_offset_cm=float(vertical_offset_cm),
        angle_contours_cm=contours,
        placements=placements,
    )
