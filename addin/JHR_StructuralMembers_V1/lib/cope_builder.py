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


PRIMARY_FAMILIES = frozenset(("IPE", "HEA", "HEB"))
SECONDARY_FAMILY = "IPE"
RIGHT_ANGLE_TOLERANCE_DEGREES = 0.5


@dataclass(frozen=True)
class CopeEvaluation:
    primary_occurrence: object
    secondary_occurrence: object
    primary_metadata: object
    secondary_metadata: object
    geometry: object
    primary_profile_geometry: cope_geometry.IProfileGeometry
    profile_geometry: cope_geometry.IProfileGeometry
    depth_cm: float
    vertical_clearance_cm: float
    longitudinal_clearance_cm: float
    web_clearance_cm: float
    origin: tuple
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


def evaluate_double_ipe_cope(
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
            "Ce prototype accepte une principale IPE, HEA ou HEB uniquement."
        )
    if secondary_metadata.profile_family != SECONDARY_FAMILY:
        raise ValueError("Ce prototype accepte une barre secondaire IPE uniquement.")

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
    if abs(geometry.angle_degrees - 90.0) > RIGHT_ANGLE_TOLERANCE_DEGREES:
        raise ValueError(
            "Le premier prototype exige des axes à 90° (angle mesuré : {:.2f}°)."
            .format(geometry.angle_degrees)
        )

    primary_body = joint_builder._single_body(primary_occurrence, "principale")
    secondary_body = joint_builder._single_body(secondary_occurrence, "secondaire")
    primary_points = joint_builder._body_sample_points(primary_body, primary_occurrence)
    axial_axis = joint_geometry.normalize(geometry.approach_direction)
    automatic_depth_cm = cope_geometry.depth_to_facing_support(
        geometry.secondary_joint_endpoint,
        geometry.approach_direction,
        geometry.plane_normal,
        primary_points,
    )
    depth_cm = automatic_depth_cm + float(longitudinal_clearance_cm)

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
    primary_profile_geometry = cope_geometry.analyze_i_profile_dxf(primary_dxf_path)
    profile_geometry = cope_geometry.analyze_i_profile_dxf(secondary_dxf_path)
    primary_anchor_mm = anchors.point_for_bounds(
        primary_profile_geometry.bounds_mm,
        primary_metadata.anchor,
    )
    secondary_anchor_mm = anchors.point_for_bounds(
        profile_geometry.bounds_mm,
        secondary_metadata.anchor,
    )
    volumes = cope_geometry.double_cope_volumes(
        profile_geometry,
        secondary_anchor_mm,
        depth_cm,
        float(vertical_clearance_cm),
    )
    primary_profile_x_axis, primary_profile_y_axis = _profile_axes(
        primary_curve,
        primary_metadata,
    )
    profile_x_axis, profile_y_axis = _profile_axes(
        secondary_curve,
        secondary_metadata,
    )
    web_cut_point = cope_geometry.web_face_cut_point(
        primary_profile_geometry,
        primary_anchor_mm,
        geometry.secondary_joint_endpoint,
        primary_profile_x_axis,
        geometry.plane_normal,
        float(web_clearance_cm),
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
        geometry=geometry,
        primary_profile_geometry=primary_profile_geometry,
        profile_geometry=profile_geometry,
        depth_cm=depth_cm,
        vertical_clearance_cm=float(vertical_clearance_cm),
        longitudinal_clearance_cm=float(longitudinal_clearance_cm),
        web_clearance_cm=float(web_clearance_cm),
        origin=geometry.secondary_joint_endpoint,
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
    )
