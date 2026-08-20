from __future__ import annotations

import math
from dataclasses import dataclass

from . import angle_cleat_geometry, joint_geometry


MM_TO_CM = 0.1
LENGTH_STEP_MM = 5.0
SPACING_TOLERANCE_CM = 1e-4


@dataclass(frozen=True)
class BoltPlacement:
    connection: str
    side: str
    row_index: int
    origin: tuple
    x_axis: tuple
    y_axis: tuple
    z_axis: tuple
    grip_length_cm: float
    bolt_length_cm: float

    @property
    def name_suffix(self):
        return "{}_{}_R{:02d}".format(
            self.connection.upper(),
            self.side.upper(),
            self.row_index,
        )


def perpendicular_axes(axis):
    z_axis = joint_geometry.normalize(axis)
    reference = (
        (0.0, 0.0, 1.0)
        if abs(joint_geometry.dot(z_axis, (0.0, 0.0, 1.0))) < 0.9
        else (1.0, 0.0, 0.0)
    )
    x_axis = joint_geometry.normalize(joint_geometry.cross(reference, z_axis))
    y_axis = joint_geometry.normalize(joint_geometry.cross(z_axis, x_axis))
    return x_axis, y_axis, z_axis


def rounded_bolt_length_cm(spec, grip_length_cm):
    required_mm = (
        float(grip_length_cm) / MM_TO_CM
        + 2.0 * spec.washer_thickness_mm
        + spec.nut_height_mm
        + spec.thread_projection_mm
    )
    return math.ceil(required_mm / LENGTH_STEP_MM) * LENGTH_STEP_MM * MM_TO_CM


def _placement(connection, side, row_index, workpiece_start, axis, grip_cm, spec):
    x_axis, y_axis, z_axis = perpendicular_axes(axis)
    washer_cm = spec.washer_thickness_mm * MM_TO_CM
    origin = joint_geometry.subtract(
        tuple(float(value) for value in workpiece_start),
        joint_geometry.scale(z_axis, washer_cm),
    )
    return BoltPlacement(
        connection=connection,
        side=side,
        row_index=int(row_index),
        origin=origin,
        x_axis=x_axis,
        y_axis=y_axis,
        z_axis=z_axis,
        grip_length_cm=float(grip_cm),
        bolt_length_cm=rounded_bolt_length_cm(spec, grip_cm),
    )


def build_angle_cleat_bolt_placements(
    placements,
    hole_pattern,
    primary_axis,
    secondary_axis,
    primary_web_thickness_cm,
    secondary_web_thickness_cm,
    angle_thickness_cm,
    spec,
):
    """Place quatre boulons de principale et un traversant par rangée secondaire."""
    angle_thickness = float(angle_thickness_cm)
    primary_web_thickness = float(primary_web_thickness_cm)
    secondary_web_thickness = float(secondary_web_thickness_cm)
    if min(angle_thickness, primary_web_thickness, secondary_web_thickness) <= 0.0:
        raise ValueError("Une épaisseur de l'assemblage boulonné est nulle.")
    if len(placements) != 2:
        raise ValueError("L'assemblage boulonné exige exactement deux cornières.")

    primary_direction = joint_geometry.normalize(primary_axis)
    secondary_direction = joint_geometry.normalize(secondary_axis)
    holes_by_placement = tuple(
        angle_cleat_geometry.hole_centers_for_placement(placement, hole_pattern)
        for placement in placements
    )
    result = []
    primary_grip = primary_web_thickness + angle_thickness
    for placement, (primary_centers, _) in zip(placements, holes_by_placement):
        for row_index, center in enumerate(primary_centers, start=1):
            workpiece_start = joint_geometry.subtract(
                center,
                joint_geometry.scale(primary_direction, primary_web_thickness),
            )
            result.append(
                _placement(
                    "principale",
                    placement.side,
                    row_index,
                    workpiece_start,
                    primary_direction,
                    primary_grip,
                    spec,
                )
            )

    left_centers = holes_by_placement[0][1]
    right_centers = holes_by_placement[1][1]
    if len(left_centers) != len(right_centers):
        raise ValueError("Les rangées secondaires des deux cornières ne correspondent pas.")
    secondary_grip = 2.0 * angle_thickness + secondary_web_thickness
    for row_index, (first, second) in enumerate(
        zip(left_centers, right_centers),
        start=1,
    ):
        if joint_geometry.dot(
            joint_geometry.subtract(second, first), secondary_direction
        ) < 0.0:
            first, second = second, first
        center_spacing = joint_geometry.dot(
            joint_geometry.subtract(second, first), secondary_direction
        )
        if abs(center_spacing - secondary_web_thickness) > SPACING_TOLERANCE_CM:
            raise ValueError(
                "Les deux perçages secondaires ne suivent pas l'épaisseur de l'âme."
            )
        workpiece_start = joint_geometry.subtract(
            first,
            joint_geometry.scale(secondary_direction, angle_thickness),
        )
        result.append(
            _placement(
                "secondaire",
                "traversant",
                row_index,
                workpiece_start,
                secondary_direction,
                secondary_grip,
                spec,
            )
        )
    return tuple(result)
