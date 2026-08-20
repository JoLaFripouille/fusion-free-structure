from __future__ import annotations

import adsk.core
import adsk.fusion

from . import addin_info, cope_geometry, joint_builder, joint_geometry, joint_records


COPE_TYPE = "double_ih_cope"
LEGACY_COPE_TYPES = frozenset(("double_ipe_cope",))
KNOWN_COPE_TYPES = LEGACY_COPE_TYPES | frozenset((COPE_TYPE,))
ENDPOINT_PLANE_NAME = "PLAN_GRUGEAGE_EXTREMITE"
PRIMARY_STATION_PLANE_NAME = "PLAN_STATION_PRINCIPALE_GRUGEAGE"
WEB_CUT_AXIS_NAME = "AXE_ORIENTATION_COUPE_AME"
WEB_ORIENTATION_PLANE_NAME = "PLAN_ORIENTATION_AME_PRINCIPALE"
WEB_CUT_PLANE_NAME = "PLAN_COUPE_AME_PRINCIPALE"
FLANGE_START_PLANE_NAME = "PLAN_DEBUT_GRUGEAGE"
COPE_REFERENCE_PLANE_NAME = "PLAN_REFERENCE_ESQUISSE_GRUGEAGE"
WEB_SPLIT_FEATURE_NAME = "COUPE_DROITE_AME_PRINCIPALE"
WEB_REMOVE_FEATURE_NAME = "RETRAIT_APRES_AME_PRINCIPALE"
COPE_SKETCH_NAME = "ESQUISSE_OUTILS_GRUGEAGE"
COPE_CUT_FEATURE_NAME = "GRUGEAGE_SEMELLES_IH"
MINIMUM_REMOVED_VOLUME_CM3 = 1e-8


def ensure_endpoint_available(evaluation):
    attributes = evaluation.secondary_occurrence.component.attributes.itemsByGroup(
        joint_records.ATTRIBUTE_GROUP
    )
    for record in joint_records.records_from_attributes(attributes):
        if record.payload.get("joint_type") not in KNOWN_COPE_TYPES:
            continue
        try:
            endpoint_index = int(record.payload.get("endpoint_index", -1))
        except (TypeError, ValueError):
            continue
        if endpoint_index == evaluation.geometry.secondary_joint_endpoint_index:
            raise ValueError(
                "Cette extrémité possède déjà un grugeage I/H enregistré."
            )


def _add_cut_planes(evaluation, created_entities):
    component = evaluation.secondary_occurrence.component
    occurrence = evaluation.secondary_occurrence
    primary_station_plane = joint_builder._add_path_plane(
        component,
        occurrence,
        evaluation.primary_curve,
        evaluation.geometry.main_parameter,
        PRIMARY_STATION_PLANE_NAME,
    )
    created_entities.append(primary_station_plane)
    endpoint_plane = joint_builder._add_path_plane(
        component,
        occurrence,
        evaluation.secondary_curve,
        evaluation.geometry.secondary_joint_endpoint_index,
        ENDPOINT_PLANE_NAME,
    )
    created_entities.append(endpoint_plane)
    orientation_axis = joint_builder._add_intersection_axis(
        component,
        occurrence,
        primary_station_plane,
        endpoint_plane,
        WEB_CUT_AXIS_NAME,
    )
    created_entities.append(orientation_axis)
    web_orientation_plane = joint_builder._add_oriented_plane(
        component,
        occurrence,
        orientation_axis,
        primary_station_plane,
        evaluation.web_cut_normal,
        WEB_ORIENTATION_PLANE_NAME,
        created_entities,
    )
    flange_start_plane = joint_builder._add_offset_to_point(
        component,
        occurrence,
        web_orientation_plane,
        evaluation.flange_start_point,
        FLANGE_START_PLANE_NAME,
    )
    created_entities.append(flange_start_plane)
    joint_builder._validate_plane_match(
        flange_start_plane,
        occurrence,
        evaluation.flange_start_point,
        evaluation.web_cut_normal,
    )
    web_cut_plane = joint_builder._add_offset_to_point(
        component,
        occurrence,
        web_orientation_plane,
        evaluation.web_cut_point,
        WEB_CUT_PLANE_NAME,
    )
    created_entities.append(web_cut_plane)
    joint_builder._validate_plane_match(
        web_cut_plane,
        occurrence,
        evaluation.web_cut_point,
        evaluation.web_cut_normal,
    )
    cope_reference_plane = joint_builder._add_offset_to_point(
        component,
        occurrence,
        endpoint_plane,
        evaluation.cope_start_point,
        COPE_REFERENCE_PLANE_NAME,
    )
    created_entities.append(cope_reference_plane)
    joint_builder._validate_plane_match(
        cope_reference_plane,
        occurrence,
        evaluation.cope_start_point,
        evaluation.axial_axis,
    )
    return web_cut_plane, flange_start_plane, cope_reference_plane


def _point3d(point):
    return adsk.core.Point3D.create(*point)


def _rectangle_world_points(evaluation, volume):
    return tuple(
        cope_geometry.world_point(
            evaluation.cope_start_point,
            evaluation.profile_x_axis,
            evaluation.profile_y_axis,
            evaluation.axial_axis,
            x,
            y,
            0.0,
        )
        for x, y in (
            (volume.x_min_cm, volume.y_min_cm),
            (volume.x_max_cm, volume.y_min_cm),
            (volume.x_max_cm, volume.y_max_cm),
            (volume.x_min_cm, volume.y_max_cm),
        )
    )


def _add_closed_rectangle(sketch, world_points):
    points = tuple(
        sketch.modelToSketchSpace(_point3d(point)) for point in world_points
    )
    lines = sketch.sketchCurves.sketchLines
    first = lines.addByTwoPoints(points[0], points[1])
    if not first:
        raise RuntimeError("Fusion n'a pas pu dessiner un outil de grugeage fermé.")
    second = lines.addByTwoPoints(first.endSketchPoint, points[2])
    if not second:
        raise RuntimeError("Fusion n'a pas pu dessiner un outil de grugeage fermé.")
    third = lines.addByTwoPoints(second.endSketchPoint, points[3])
    if not third:
        raise RuntimeError("Fusion n'a pas pu dessiner un outil de grugeage fermé.")
    fourth = lines.addByTwoPoints(third.endSketchPoint, first.startSketchPoint)
    if not fourth:
        raise RuntimeError("Fusion n'a pas pu dessiner un outil de grugeage fermé.")


def _create_cope_cut(
    evaluation,
    cope_reference_plane,
    flange_start_plane,
    web_cut_plane,
    created_entities,
):
    component = evaluation.secondary_occurrence.component
    occurrence = evaluation.secondary_occurrence
    sketch = component.sketches.add(cope_reference_plane, occurrence)
    if not sketch:
        raise RuntimeError("Fusion n'a pas pu créer l'esquisse du grugeage.")
    sketch.name = COPE_SKETCH_NAME
    sketch.isLightBulbOn = False
    created_entities.append(sketch)
    sketch.isComputeDeferred = True
    try:
        for volume in evaluation.volumes:
            _add_closed_rectangle(
                sketch,
                _rectangle_world_points(evaluation, volume),
            )
    finally:
        sketch.isComputeDeferred = False
    if sketch.profiles.count != 2:
        raise RuntimeError(
            "L'esquisse du grugeage doit produire exactement deux régions fermées."
        )

    profiles = adsk.core.ObjectCollection.create()
    for index in range(sketch.profiles.count):
        profiles.add(sketch.profiles.item(index))
    body = joint_builder._single_body(occurrence, "secondaire à gruger")
    volume_before_cm3 = float(body.volume)
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        profiles,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    if not extrude_input:
        raise RuntimeError("Fusion n'a pas pu préparer la coupe des semelles.")
    extrude_input.creationOccurrence = occurrence
    extrude_input.participantBodies = [body]
    start_extent = adsk.fusion.FromEntityStartDefinition.create(
        flange_start_plane,
        adsk.core.ValueInput.createByReal(0.0),
    )
    if not start_extent:
        raise RuntimeError(
            "Fusion n'a pas pu limiter le début du grugeage à la face extérieure."
        )
    extent = adsk.fusion.ToEntityExtentDefinition.create(web_cut_plane, False)
    if not extent:
        raise RuntimeError("Fusion n'a pas pu limiter le grugeage au plan de l'âme.")
    extent.directionHint = adsk.core.Vector3D.create(*evaluation.axial_axis)
    _, plane_normal = joint_builder._world_plane_system(
        cope_reference_plane,
        occurrence,
    )
    direction = (
        adsk.fusion.ExtentDirections.PositiveExtentDirection
        if joint_geometry.dot(plane_normal, evaluation.axial_axis) >= 0.0
        else adsk.fusion.ExtentDirections.NegativeExtentDirection
    )
    if not extrude_input.setOneSideExtent(extent, direction):
        raise RuntimeError("Fusion n'a pas pu orienter la coupe des semelles.")
    extrude_input.startExtent = start_extent
    feature = extrudes.add(extrude_input)
    if not feature:
        raise RuntimeError("Fusion n'a pas pu créer le grugeage des semelles.")
    feature.name = COPE_CUT_FEATURE_NAME
    created_entities.append(feature)
    resulting_body = joint_builder._single_body(
        occurrence,
        "secondaire après grugeage",
    )
    removed_volume_cm3 = volume_before_cm3 - float(resulting_body.volume)
    if removed_volume_cm3 <= MINIMUM_REMOVED_VOLUME_CM3:
        raise RuntimeError(
            "La coupe n'a retiré aucune matière mesurable des semelles."
        )
    return feature


def _record_payload(evaluation):
    return {
        "joint_type": COPE_TYPE,
        "endpoint_index": evaluation.geometry.secondary_joint_endpoint_index,
        "reference_component": evaluation.primary_occurrence.component.name,
        "reference_occurrence_token": evaluation.primary_occurrence.entityToken,
        "reference_source_curve_token": evaluation.primary_metadata.source_curve_token,
        "adjusted_source_curve_token": evaluation.secondary_metadata.source_curve_token,
        "angle_deg": evaluation.geometry.angle_degrees,
        "vertical_clearance_mm": evaluation.vertical_clearance_cm * 10.0,
        "longitudinal_clearance_mm": evaluation.longitudinal_clearance_cm * 10.0,
        "web_clearance_mm": evaluation.web_clearance_cm * 10.0,
        "cope_depth_mm": evaluation.depth_cm * 10.0,
        "primary_extensions_mm": [
            extension.extension_cm * 10.0
            for extension in evaluation.primary_extensions
        ],
        "extension_version": addin_info.VERSION,
    }


def create_double_ih_cope(evaluation):
    """Prolonge, coupe sur l'âme puis gruge les deux semelles de la secondaire."""
    ensure_endpoint_available(evaluation)
    created_entities = []
    created_attributes = []
    try:
        web_cut_plane, flange_start_plane, cope_reference_plane = _add_cut_planes(
            evaluation,
            created_entities,
        )
        for extension in evaluation.primary_extensions:
            joint_builder._extend_primary_end(extension, created_entities)
        joint_builder._extend_body(
            evaluation.treatment,
            evaluation.web_cut_point,
            evaluation.web_cut_normal,
            created_entities,
        )
        joint_builder._split_and_keep_interior(
            evaluation.treatment,
            web_cut_plane,
            evaluation.web_cut_point,
            evaluation.web_cut_normal,
            WEB_SPLIT_FEATURE_NAME,
            WEB_REMOVE_FEATURE_NAME,
            created_entities,
        )
        _create_cope_cut(
            evaluation,
            cope_reference_plane,
            flange_start_plane,
            web_cut_plane,
            created_entities,
        )
        created_attributes.append(
            joint_builder._add_record(
                evaluation.secondary_occurrence,
                _record_payload(evaluation),
            )
        )
        return tuple(created_entities)
    except Exception:
        for attribute in reversed(created_attributes):
            if attribute and attribute.isValid:
                attribute.deleteMe()
        for entity in reversed(created_entities):
            if entity and entity.isValid:
                entity.deleteMe()
        raise
