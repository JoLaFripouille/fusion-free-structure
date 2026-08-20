from __future__ import annotations

import math
from dataclasses import dataclass

from . import (
    anchors,
    cope_geometry,
    joint_builder,
    joint_geometry,
    path_frames,
    profile_catalog,
    rotation,
)


I_H_FAMILIES = frozenset(("IPE", "HEA", "HEB"))
L_T_FAMILIES = frozenset(("Corniere_Egale", "Corniere_Inegale", "Te_Egal"))
PRIMARY_FAMILIES = I_H_FAMILIES | L_T_FAMILIES
SECONDARY_FAMILIES = PRIMARY_FAMILIES


@dataclass(frozen=True)
class CopeEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: object
    secondary_metadata: object
    primary_curve: object
    secondary_curve: object
    geometry: object
    primary_profile_geometry: object
    profile_geometry: object
    depth_cm: float
    vertical_clearance_cm: float
    longitudinal_clearance_cm: float
    web_clearance_cm: float
    origin: tuple
    cope_start_point: tuple
    flange_start_point: tuple
    web_cut_point: tuple
    web_cut_normal: tuple
    primary_anchor_mm: tuple
    secondary_anchor_mm: tuple
    primary_profile_source: object
    primary_profile_x_axis: tuple
    primary_profile_y_axis: tuple
    profile_x_axis: tuple
    profile_y_axis: tuple
    axial_axis: tuple
    volumes: tuple
    primary_extensions: tuple
    primary_extension_segments: tuple
    treatment: object


def _vector_tuple(vector):
    return float(vector.x), float(vector.y), float(vector.z)


def _combine_axes(first, second, first_scale, second_scale):
    first = _vector_tuple(first)
    second = _vector_tuple(second)
    return joint_geometry.normalize(
        tuple(
            first[index] * first_scale + second[index] * second_scale
            for index in range(3)
        )
    )


def _profile_axes(curve, metadata):
    _, base_x, base_y = path_frames.frame_at_fraction(curve, 0.5)
    xx, xy, yx, yy = rotation.orientation_matrix_2d(
        math.radians(metadata.rotation_deg),
        metadata.flip_x,
        metadata.flip_y,
    )
    return (
        _combine_axes(base_x, base_y, xx, yx),
        _combine_axes(base_x, base_y, xy, yy),
    )


def _extension_segment(extension, primary_body_points):
    direction = joint_geometry.normalize(extension.approach_direction)
    current_projection = max(
        joint_geometry.dot(point, direction) for point in primary_body_points
    )
    endpoint_projection = joint_geometry.dot(extension.joint_endpoint, direction)
    start_point = joint_geometry.add(
        extension.joint_endpoint,
        joint_geometry.scale(
            direction,
            current_projection - endpoint_projection,
        ),
    )
    return (
        start_point,
        joint_geometry.add(
            start_point,
            joint_geometry.scale(direction, extension.extension_cm),
        ),
    )


def _cope_section_points(
    profile,
    family_id,
    anchor_mm,
    vertical_clearance_cm,
    origin,
    profile_x_axis,
    profile_y_axis,
    axial_axis,
):
    points = []
    rectangle_bounds = (
        cope_geometry.double_cope_rectangle_bounds(
            profile,
            anchor_mm,
            vertical_clearance_cm,
        )
        if family_id in I_H_FAMILIES
        else cope_geometry.single_cope_rectangle_bounds(
            profile,
            anchor_mm,
            vertical_clearance_cm,
        )
    )
    for x_min, x_max, y_min, y_max in rectangle_bounds:
        for x, y in (
            (x_min, y_min),
            (x_max, y_min),
            (x_max, y_max),
            (x_min, y_max),
        ):
            points.append(
                cope_geometry.world_point(
                    origin,
                    profile_x_axis,
                    profile_y_axis,
                    axial_axis,
                    x,
                    y,
                    0.0,
                )
            )
    return tuple(points)


def _analyze_profile_geometry(dxf_path, family_id):
    if family_id in I_H_FAMILIES:
        return cope_geometry.analyze_i_profile_dxf(dxf_path)
    if family_id in L_T_FAMILIES:
        return cope_geometry.analyze_single_flange_profile_dxf(dxf_path)
    raise ValueError("Cette famille de profil ne prend pas encore en charge le grugeage.")


def _cope_volumes(profile, family_id, anchor_mm, depth_cm, clearance_cm):
    if family_id in I_H_FAMILIES:
        return cope_geometry.double_cope_volumes(
            profile,
            anchor_mm,
            depth_cm,
            clearance_cm,
        )
    return cope_geometry.single_cope_volumes(
        profile,
        anchor_mm,
        depth_cm,
        clearance_cm,
    )


def evaluate_profile_cope(
    design,
    primary_occurrence,
    secondary_occurrence,
    vertical_clearance_cm,
    longitudinal_clearance_cm,
    web_clearance_cm,
):
    if primary_occurrence == secondary_occurrence:
        raise ValueError("Les deux barres sélectionnées doivent être différentes.")
    if (
        vertical_clearance_cm < 0.0
        or longitudinal_clearance_cm < 0.0
        or web_clearance_cm < 0.0
    ):
        raise ValueError("Les jeux du grugeage ne peuvent pas être négatifs.")

    primary_metadata = joint_builder._member_metadata(primary_occurrence, "principale")
    secondary_metadata = joint_builder._member_metadata(secondary_occurrence, "secondaire")
    if primary_metadata.profile_family not in PRIMARY_FAMILIES:
        raise ValueError(
            "La famille de la barre principale ne prend pas encore en charge le grugeage."
        )
    if secondary_metadata.profile_family not in SECONDARY_FAMILIES:
        raise ValueError(
            "La famille de la barre secondaire ne prend pas encore en charge le grugeage."
        )
    both_i_h = (
        primary_metadata.profile_family in I_H_FAMILIES
        and secondary_metadata.profile_family in I_H_FAMILIES
    )
    both_l_t = (
        primary_metadata.profile_family in L_T_FAMILIES
        and secondary_metadata.profile_family in L_T_FAMILIES
    )
    if not (both_i_h or both_l_t):
        raise ValueError(
            "Cette première version accepte I/H vers I/H ou cornière/té vers "
            "cornière/té, sans mélange entre ces deux groupes."
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

    primary_body = joint_builder._single_body(primary_occurrence, "principale")
    secondary_body = joint_builder._single_body(secondary_occurrence, "secondaire")
    primary_dxf_path = profile_catalog.resolve_profile_source(
        primary_metadata.profile_source
    )
    secondary_dxf_path = profile_catalog.resolve_profile_source(
        secondary_metadata.profile_source
    )
    if not primary_dxf_path.is_file():
        raise FileNotFoundError("Le DXF source de la barre principale est introuvable.")
    if not secondary_dxf_path.is_file():
        raise FileNotFoundError("Le DXF source de la barre secondaire est introuvable.")
    primary_profile_geometry = _analyze_profile_geometry(
        primary_dxf_path,
        primary_metadata.profile_family,
    )
    profile_geometry = _analyze_profile_geometry(
        secondary_dxf_path,
        secondary_metadata.profile_family,
    )
    primary_anchor_mm = anchors.point_for_bounds(
        primary_profile_geometry.bounds_mm,
        primary_metadata.anchor,
    )
    secondary_anchor_mm = anchors.point_for_bounds(
        profile_geometry.bounds_mm,
        secondary_metadata.anchor,
    )
    primary_profile_x_axis, primary_profile_y_axis = _profile_axes(
        primary_curve,
        primary_metadata,
    )
    profile_x_axis, profile_y_axis = _profile_axes(
        secondary_curve,
        secondary_metadata,
    )
    axial_axis = joint_geometry.normalize(geometry.approach_direction)
    primary_points = joint_builder._body_sample_points(primary_body, primary_occurrence)
    secondary_section_points = _cope_section_points(
        profile_geometry,
        secondary_metadata.profile_family,
        secondary_anchor_mm,
        float(vertical_clearance_cm),
        geometry.secondary_joint_endpoint,
        profile_x_axis,
        profile_y_axis,
        axial_axis,
    )
    automatic_depth_cm = cope_geometry.depth_to_facing_support(
        geometry.secondary_joint_endpoint,
        geometry.approach_direction,
        geometry.plane_normal,
        primary_points,
        secondary_section_points,
    )
    depth_cm = automatic_depth_cm + float(longitudinal_clearance_cm)
    reference_depth_cm = depth_cm + cope_geometry.COPE_REFERENCE_MARGIN_CM
    outer_support_point = cope_geometry.facing_support_plane_point(
        geometry.secondary_joint_endpoint,
        geometry.plane_normal,
        primary_points,
    )
    flange_start_point = joint_geometry.add(
        outer_support_point,
        joint_geometry.scale(
            axial_axis,
            -float(longitudinal_clearance_cm),
        ),
    )
    available_length_cm = joint_geometry.length(
        joint_geometry.subtract(
            geometry.secondary_joint_endpoint,
            geometry.secondary_inner_endpoint,
        )
    )
    if reference_depth_cm >= (
        available_length_cm - joint_geometry.PLANE_RELATION_TOLERANCE_CM
    ):
        raise ValueError(
            "La profondeur du grugeage atteint toute la longueur de la secondaire."
        )
    volumes = _cope_volumes(
        profile_geometry,
        secondary_metadata.profile_family,
        secondary_anchor_mm,
        depth_cm,
        float(vertical_clearance_cm),
    )
    web_cut_point = cope_geometry.web_face_cut_point(
        primary_profile_geometry,
        primary_anchor_mm,
        geometry.secondary_joint_endpoint,
        primary_profile_x_axis,
        geometry.plane_normal,
        float(web_clearance_cm),
    )
    cope_start_point = joint_geometry.add(
        geometry.secondary_joint_endpoint,
        joint_geometry.scale(axial_axis, -reference_depth_cm),
    )
    axial_rate = joint_geometry.dot(axial_axis, geometry.plane_normal)
    if abs(axial_rate) <= joint_geometry.GEOMETRY_TOLERANCE_CM:
        raise ValueError("L'axe secondaire est parallèle au plan d'appui principal.")
    cut_length_cm = -joint_geometry.plane_signed_distance(
        cope_start_point,
        web_cut_point,
        geometry.plane_normal,
    ) / axial_rate
    if cut_length_cm <= joint_geometry.PLANE_RELATION_TOLERANCE_CM:
        raise ValueError(
            "Le début du grugeage dépasse le plan de coupe contre l'appui."
        )
    treatment = joint_builder._evaluate_treatment(
        secondary_occurrence,
        secondary_body,
        secondary_curve,
        geometry.secondary_joint_endpoint_index,
        geometry.secondary_joint_endpoint,
        geometry.secondary_inner_endpoint,
        geometry.approach_direction,
        web_cut_point,
        geometry.plane_normal,
    )
    primary_extensions = joint_builder._evaluate_primary_extensions(
        primary_occurrence,
        primary_body,
        primary_curve,
        secondary_occurrence,
        secondary_body,
        geometry,
        web_cut_point,
        geometry.plane_normal,
    )
    primary_extension_segments = tuple(
        _extension_segment(extension, primary_points)
        for extension in primary_extensions
    )
    return CopeEvaluation(
        primary_occurrence=primary_occurrence,
        secondary_occurrence=secondary_occurrence,
        primary_metadata=primary_metadata,
        secondary_metadata=secondary_metadata,
        primary_curve=primary_curve,
        secondary_curve=secondary_curve,
        geometry=geometry,
        primary_profile_geometry=primary_profile_geometry,
        profile_geometry=profile_geometry,
        depth_cm=depth_cm,
        vertical_clearance_cm=float(vertical_clearance_cm),
        longitudinal_clearance_cm=float(longitudinal_clearance_cm),
        web_clearance_cm=float(web_clearance_cm),
        origin=geometry.secondary_joint_endpoint,
        cope_start_point=cope_start_point,
        flange_start_point=flange_start_point,
        web_cut_point=web_cut_point,
        web_cut_normal=geometry.plane_normal,
        primary_anchor_mm=primary_anchor_mm,
        secondary_anchor_mm=secondary_anchor_mm,
        primary_profile_source=primary_dxf_path,
        primary_profile_x_axis=primary_profile_x_axis,
        primary_profile_y_axis=primary_profile_y_axis,
        profile_x_axis=profile_x_axis,
        profile_y_axis=profile_y_axis,
        axial_axis=axial_axis,
        volumes=volumes,
        primary_extensions=primary_extensions,
        primary_extension_segments=primary_extension_segments,
        treatment=treatment,
    )


def evaluate_double_ih_cope(*args, **kwargs):
    """Compatibilité interne avec le nom utilisé jusqu'à la V1.19.1."""
    return evaluate_profile_cope(*args, **kwargs)
