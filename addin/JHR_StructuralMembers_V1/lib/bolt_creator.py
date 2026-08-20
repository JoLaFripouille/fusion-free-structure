from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from . import addin_info


ATTRIBUTE_GROUP = "EI_JHR_Bolt"
GEOMETRY_TOLERANCE_CM = 1e-7


def _matrix_for_placement(placement):
    matrix = adsk.core.Matrix3D.create()
    if not matrix.setWithCoordinateSystem(
        adsk.core.Point3D.create(*placement.origin),
        adsk.core.Vector3D.create(*placement.x_axis),
        adsk.core.Vector3D.create(*placement.y_axis),
        adsk.core.Vector3D.create(*placement.z_axis),
    ):
        raise RuntimeError("Fusion n'a pas pu préparer le repère du boulon.")
    return matrix


def _offset_plane(component, offset_cm, name):
    if abs(float(offset_cm)) <= GEOMETRY_TOLERANCE_CM:
        return component.xYConstructionPlane
    plane_input = component.constructionPlanes.createInput()
    if not plane_input.setByOffset(
        component.xYConstructionPlane,
        adsk.core.ValueInput.createByReal(float(offset_cm)),
    ):
        raise RuntimeError("Fusion n'a pas pu décaler le plan du boulon.")
    plane = component.constructionPlanes.add(plane_input)
    if not plane:
        raise RuntimeError("Fusion n'a pas pu créer le plan du boulon.")
    plane.name = name
    plane.isLightBulbOn = False
    return plane


def _profile_with_loop_count(sketch, loop_count, label):
    matches = []
    for index in range(sketch.profiles.count):
        profile = sketch.profiles.item(index)
        if profile.profileLoops.count == int(loop_count):
            matches.append(profile)
    if len(matches) != 1:
        raise RuntimeError(
            "Le profil {} du boulon est ambigu ({} région(s) trouvée(s))."
            .format(label, len(matches))
        )
    return matches[0]


def _add_hexagon(sketch, across_flats_cm):
    radius = float(across_flats_cm) / math.sqrt(3.0)
    points = tuple(
        adsk.core.Point3D.create(
            radius * math.cos(math.radians(30.0 + index * 60.0)),
            radius * math.sin(math.radians(30.0 + index * 60.0)),
            0.0,
        )
        for index in range(6)
    )
    lines = sketch.sketchCurves.sketchLines
    first = lines.addByTwoPoints(points[0], points[1])
    if not first:
        raise RuntimeError("Fusion n'a pas pu commencer l'hexagone du boulon.")
    previous = first
    for index in range(1, 5):
        previous = lines.addByTwoPoints(previous.endSketchPoint, points[index + 1])
        if not previous:
            raise RuntimeError("Fusion n'a pas pu dessiner l'hexagone du boulon.")
    if not lines.addByTwoPoints(previous.endSketchPoint, first.startSketchPoint):
        raise RuntimeError("Fusion n'a pas pu fermer l'hexagone du boulon.")


def _extrude_new_body(component, profile, length_cm, positive, name, material):
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profile,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    if not extrude_input:
        raise RuntimeError("Fusion n'a pas pu préparer l'extrusion {}.".format(name))
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(float(length_cm))
    )
    direction = (
        adsk.fusion.ExtentDirections.PositiveExtentDirection
        if positive
        else adsk.fusion.ExtentDirections.NegativeExtentDirection
    )
    if not extrude_input.setOneSideExtent(extent, direction):
        raise RuntimeError("Fusion n'a pas pu orienter l'extrusion {}.".format(name))
    feature = extrudes.add(extrude_input)
    if not feature or feature.bodies.count != 1:
        raise RuntimeError("L'extrusion {} n'a pas produit un corps unique.".format(name))
    feature.name = "EXTRUSION_{}".format(name)
    body = feature.bodies.item(0)
    body.name = name
    body.material = material
    return body


def _create_disk(component, plane, diameter_cm, length_cm, name, material):
    sketch = component.sketches.add(plane)
    sketch.name = "ESQUISSE_{}".format(name)
    circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
        float(diameter_cm) / 2.0,
    )
    if not circle:
        raise RuntimeError("Fusion n'a pas pu dessiner {}.".format(name))
    body = _extrude_new_body(
        component,
        _profile_with_loop_count(sketch, 1, name),
        length_cm,
        True,
        name,
        material,
    )
    sketch.isVisible = False
    return body


def _create_hex_body(
    component,
    plane,
    across_flats_cm,
    height_cm,
    name,
    material,
    positive,
    inner_diameter_cm=None,
):
    sketch = component.sketches.add(plane)
    sketch.name = "ESQUISSE_{}".format(name)
    _add_hexagon(sketch, across_flats_cm)
    loops = 1
    if inner_diameter_cm is not None:
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            adsk.core.Point3D.create(0.0, 0.0, 0.0),
            float(inner_diameter_cm) / 2.0,
        )
        if not circle:
            raise RuntimeError("Fusion n'a pas pu dessiner l'alésage de l'écrou.")
        loops = 2
    body = _extrude_new_body(
        component,
        _profile_with_loop_count(sketch, loops, name),
        height_cm,
        positive,
        name,
        material,
    )
    sketch.isVisible = False
    return body


def _create_washer(
    component,
    plane,
    inner_diameter_cm,
    outer_diameter_cm,
    thickness_cm,
    name,
    material,
):
    sketch = component.sketches.add(plane)
    sketch.name = "ESQUISSE_{}".format(name)
    circles = sketch.sketchCurves.sketchCircles
    if not circles.addByCenterRadius(
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
        float(outer_diameter_cm) / 2.0,
    ) or not circles.addByCenterRadius(
        adsk.core.Point3D.create(0.0, 0.0, 0.0),
        float(inner_diameter_cm) / 2.0,
    ):
        raise RuntimeError("Fusion n'a pas pu dessiner {}.".format(name))
    body = _extrude_new_body(
        component,
        _profile_with_loop_count(sketch, 2, name),
        thickness_cm,
        True,
        name,
        material,
    )
    sketch.isVisible = False
    return body


def _add_attributes(component, placement, spec, hole_diameter_cm):
    values = {
        "fastener_type": "hex_bolt_nut_two_washers",
        "designation": spec.designation,
        "strength_class": spec.strength_class,
        "geometry_only": "true",
        "connection": placement.connection,
        "side": placement.side,
        "row": str(placement.row_index),
        "hole_diameter_mm": "{:.6f}".format(hole_diameter_cm * 10.0),
        "grip_length_mm": "{:.6f}".format(placement.grip_length_cm * 10.0),
        "bolt_length_mm": "{:.6f}".format(placement.bolt_length_cm * 10.0),
        "extension_version": addin_info.VERSION,
    }
    for name, value in values.items():
        component.attributes.add(ATTRIBUTE_GROUP, name, value)


def create_bolt_occurrence(
    root_component,
    placement,
    spec,
    material,
    component_name,
    hole_diameter_cm,
):
    """Crée un boulon géométrique complet à l'identité, puis place l'occurrence."""
    occurrence = root_component.occurrences.addNewComponent(
        adsk.core.Matrix3D.create()
    )
    component = occurrence.component
    component.name = component_name
    mm_to_cm = 0.1
    nominal_cm = spec.nominal_diameter_mm * mm_to_cm
    washer_inner_cm = spec.washer_inner_diameter_mm * mm_to_cm
    washer_outer_cm = spec.washer_outer_diameter_mm * mm_to_cm
    washer_thickness_cm = spec.washer_thickness_mm * mm_to_cm
    head_height_cm = spec.head_height_mm * mm_to_cm
    nut_height_cm = spec.nut_height_mm * mm_to_cm
    nut_start_cm = 2.0 * washer_thickness_cm + placement.grip_length_cm
    try:
        _create_disk(
            component,
            component.xYConstructionPlane,
            nominal_cm,
            placement.bolt_length_cm,
            "TIGE_{}".format(spec.designation),
            material,
        )
        _create_hex_body(
            component,
            component.xYConstructionPlane,
            spec.head_across_flats_mm * mm_to_cm,
            head_height_cm,
            "TETE_HEXAGONALE",
            material,
            False,
        )
        _create_washer(
            component,
            component.xYConstructionPlane,
            washer_inner_cm,
            washer_outer_cm,
            washer_thickness_cm,
            "RONDELLE_SOUS_TETE",
            material,
        )
        nut_washer_plane = _offset_plane(
            component,
            washer_thickness_cm + placement.grip_length_cm,
            "PLAN_RONDELLE_ECROU",
        )
        _create_washer(
            component,
            nut_washer_plane,
            washer_inner_cm,
            washer_outer_cm,
            washer_thickness_cm,
            "RONDELLE_SOUS_ECROU",
            material,
        )
        nut_plane = _offset_plane(component, nut_start_cm, "PLAN_ECROU")
        _create_hex_body(
            component,
            nut_plane,
            spec.nut_across_flats_mm * mm_to_cm,
            nut_height_cm,
            "ECROU_HEXAGONAL",
            material,
            True,
            nominal_cm,
        )
        _add_attributes(component, placement, spec, hole_diameter_cm)
        transform = _matrix_for_placement(placement)
        if getattr(occurrence, "isValidForEditInitialPosition", False):
            occurrence.initialTransform = transform
        else:
            occurrence.transform2 = transform
        return occurrence
    except Exception:
        if occurrence and occurrence.isValid:
            occurrence.deleteMe()
        raise
