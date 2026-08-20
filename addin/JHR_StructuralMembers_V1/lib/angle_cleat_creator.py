from __future__ import annotations

from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import (
    addin_info,
    angle_cleat_geometry,
    joint_builder,
    joint_geometry,
    member_builder,
    profile_catalog,
)


ATTRIBUTE_GROUP = "EI_JHR_AngleCleat"
FACE_ALIGNMENT_TOLERANCE = 0.995
PLACEMENT_TOLERANCE_CM = 1e-4


@dataclass(frozen=True)
class DoubleAngleCreationResult:
    left_occurrence: object
    right_occurrence: object
    primary_hole_feature: object
    secondary_hole_feature: object


def _point_tuple(point):
    return float(point.x), float(point.y), float(point.z)


def _vector_tuple(vector):
    return float(vector.x), float(vector.y), float(vector.z)


def _next_assembly_index(root_component):
    prefix = "ASSEMBLAGE_CORNIERES_"
    used = set()
    for occurrence in root_component.allOccurrences:
        name = occurrence.component.name
        if not name.startswith(prefix):
            continue
        suffix = name[len(prefix):].split("_", 1)[0]
        if suffix.isdigit():
            used.add(int(suffix))
    index = 1
    while index in used:
        index += 1
    return index


def _matrix_for_frame(frame):
    matrix = adsk.core.Matrix3D.create()
    if not matrix.setWithCoordinateSystem(
        adsk.core.Point3D.create(*frame.origin),
        adsk.core.Vector3D.create(*frame.x_axis),
        adsk.core.Vector3D.create(*frame.y_axis),
        adsk.core.Vector3D.create(*frame.z_axis),
    ):
        raise RuntimeError("Fusion n'a pas pu préparer le repère de la cornière.")
    return matrix


def _inverse_occurrence_transform(occurrence):
    transform = occurrence.transform2.copy()
    if not transform.invert():
        raise RuntimeError("Le repère du composant n'est pas inversible.")
    return transform


def _world_to_local_point(occurrence, point):
    local = adsk.core.Point3D.create(*point)
    if not local.transformBy(_inverse_occurrence_transform(occurrence)):
        raise RuntimeError("Fusion n'a pas pu convertir un centre de perçage.")
    return local


def _point_from_rigid_frame(frame, local_point):
    point = tuple(float(value) for value in frame.origin)
    for coordinate, axis in zip(
        tuple(float(value) for value in local_point),
        (frame.x_axis, frame.y_axis, frame.z_axis),
    ):
        point = joint_geometry.add(
            point,
            joint_geometry.scale(axis, coordinate),
        )
    return point


def _expected_occurrence_bounds(frame, profile, height_cm):
    width_cm = profile.width_mm * profile_catalog.MM_TO_CM
    depth_cm = profile.height_mm * profile_catalog.MM_TO_CM
    points = tuple(
        _point_from_rigid_frame(frame, (x, y, z))
        for x in (0.0, width_cm)
        for y in (0.0, depth_cm)
        for z in (0.0, float(height_cm))
    )
    return (
        tuple(min(point[index] for point in points) for index in range(3)),
        tuple(max(point[index] for point in points) for index in range(3)),
    )


def _place_completed_occurrence(occurrence, frame, profile, height_cm):
    """Place une cornière terminée et vérifie son enveloppe dans l'assemblage."""
    transform = _matrix_for_frame(frame)
    if getattr(occurrence, "isValidForEditInitialPosition", False):
        occurrence.initialTransform = transform
    else:
        occurrence.transform2 = transform

    bounds = occurrence.preciseBoundingBox
    if not bounds:
        raise RuntimeError(
            "Fusion n'a pas retourné l'enveloppe de la cornière placée."
        )
    expected_min, expected_max = _expected_occurrence_bounds(
        frame,
        profile,
        height_cm,
    )
    actual_min = _point_tuple(bounds.minPoint)
    actual_max = _point_tuple(bounds.maxPoint)
    if any(
        abs(actual - expected) > PLACEMENT_TOLERANCE_CM
        for actual, expected in zip(
            actual_min + actual_max,
            expected_min + expected_max,
        )
    ):
        raise RuntimeError(
            "Fusion a décalé la cornière après sa création "
            "(enveloppe obtenue {} -> {}, attendue {} -> {})."
            .format(actual_min, actual_max, expected_min, expected_max)
        )


def _rebase_sketch_to_anchor(sketch, profile, anchor_code):
    """Corrige le décalage que Fusion peut ignorer dans un composant orienté."""
    entities = adsk.core.ObjectCollection.create()
    boxes = []
    for collection in (
        sketch.sketchCurves.sketchLines,
        sketch.sketchCurves.sketchArcs,
        sketch.sketchCurves.sketchCircles,
    ):
        for index in range(collection.count):
            entity = collection.item(index)
            entities.add(entity)
            boxes.append(entity.boundingBox)
    if not boxes:
        raise RuntimeError(
            "Le DXF {} ne contient aucune courbe à repositionner."
            .format(profile.designation)
        )

    current_min_x = min(box.minPoint.x for box in boxes)
    current_min_y = min(box.minPoint.y for box in boxes)
    source_min_x, source_min_y, _, _ = profile.bounds_mm
    anchor_x, anchor_y = profile.anchor_mm(anchor_code)
    expected_min_x = (
        source_min_x - anchor_x
    ) * profile_catalog.MM_TO_CM
    expected_min_y = (
        source_min_y - anchor_y
    ) * profile_catalog.MM_TO_CM
    delta_x = expected_min_x - current_min_x
    delta_y = expected_min_y - current_min_y
    if (
        abs(delta_x) <= member_builder.DIMENSION_TOLERANCE_CM
        and abs(delta_y) <= member_builder.DIMENSION_TOLERANCE_CM
    ):
        return

    transform = adsk.core.Matrix3D.create()
    if not transform.setCell(0, 3, delta_x) or not transform.setCell(
        1, 3, delta_y
    ):
        raise RuntimeError(
            "Fusion n'a pas pu préparer le recalage de l'ancrage {}."
            .format(anchor_code)
        )
    if not sketch.move(entities, transform):
        raise RuntimeError(
            "Fusion n'a pas pu ramener la cornière sur l'ancrage {}."
            .format(anchor_code)
        )


def _import_angle_sketch(component, profile):
    app = adsk.core.Application.get()
    options = app.importManager.createDXF2DImportOptions(
        str(profile.dxf_path),
        component.xYConstructionPlane,
    )
    if not options:
        raise RuntimeError(
            "Fusion n'a pas pu préparer l'import de la cornière {}."
            .format(profile.designation)
        )
    options.isViewFit = False
    options.isSingleSketchResult = True
    options.position = adsk.core.Point2D.create(
        *profile.import_offset_cm_for_anchor("BL")
    )
    imported = app.importManager.importToTarget2(options, component)
    sketches = []
    if imported:
        for index in range(imported.count):
            sketch = adsk.fusion.Sketch.cast(imported.item(index))
            if sketch:
                sketches.append(sketch)
    if len(sketches) != 1:
        raise RuntimeError(
            "L'import de la cornière devait produire une seule esquisse ({} détectée(s))."
            .format(len(sketches))
        )
    sketch = sketches[0]
    sketch.name = "ESQUISSE_CORNIERE_DXF_ANCRAGE_BL"
    _rebase_sketch_to_anchor(sketch, profile, "BL")
    member_builder._validate_profile_sketch(sketch, profile, "BL")
    return sketch, member_builder._select_material_profile(sketch, profile)


def _create_angle_body(component, profile, height_cm, material):
    sketch, section = _import_angle_sketch(component, profile)
    extrudes = component.features.extrudeFeatures
    extrude_input = extrudes.createInput(
        section,
        adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
    )
    if not extrude_input:
        raise RuntimeError("Fusion n'a pas pu préparer l'extrusion de la cornière.")
    extent = adsk.fusion.DistanceExtentDefinition.create(
        adsk.core.ValueInput.createByReal(float(height_cm))
    )
    if not extrude_input.setOneSideExtent(
        extent,
        adsk.fusion.ExtentDirections.PositiveExtentDirection,
    ):
        raise RuntimeError("Fusion n'a pas pu orienter l'extrusion de la cornière.")
    feature = extrudes.add(extrude_input)
    if not feature or feature.bodies.count != 1:
        raise RuntimeError("La cornière n'a pas produit un corps unique.")
    feature.name = "CORNIERE_EXTRUDEE"
    body = feature.bodies.item(0)
    body.name = "CORPS_CORNIERE_ASSEMBLAGE"
    body.material = material
    assigned = body.material
    if not assigned or not assigned.isValid:
        raise RuntimeError("Fusion n'a pas conservé le matériau sur la cornière.")
    sketch.isVisible = False
    return body


def _planar_face_for_holes(body, occurrence, axis_world, centers_world):
    proxy = body.createForAssemblyContext(occurrence) or body
    axis = joint_geometry.normalize(axis_world)
    reference = centers_world[0]
    candidates = []
    for index in range(proxy.faces.count):
        face = proxy.faces.item(index)
        if not adsk.core.Plane.cast(face.geometry):
            continue
        point = face.pointOnFace
        if not point:
            continue
        success, normal = face.evaluator.getNormalAtPoint(point)
        if not success:
            continue
        alignment = abs(
            joint_geometry.dot(
                joint_geometry.normalize(_vector_tuple(normal)),
                axis,
            )
        )
        if alignment < FACE_ALIGNMENT_TOLERANCE:
            continue
        station_error = abs(
            joint_geometry.dot(
                joint_geometry.subtract(_point_tuple(point), reference),
                axis,
            )
        )
        candidates.append((station_error, -alignment, face))
    if not candidates:
        raise RuntimeError("La face plane portant les perçages est introuvable.")
    _, _, face = min(candidates, key=lambda item: (item[0], item[1]))
    return face.nativeObject if face.nativeObject else face


def _circular_profiles(sketch, expected_count):
    """Exclut la région de fond d'une face et conserve les disques ajoutés."""
    profiles = adsk.core.ObjectCollection.create()
    for index in range(sketch.profiles.count):
        profile = sketch.profiles.item(index)
        loops = profile.profileLoops
        if loops.count != 1:
            continue
        curves = loops.item(0).profileCurves
        if curves.count != 1:
            continue
        if not adsk.core.Circle3D.cast(curves.item(0).geometry):
            continue
        profiles.add(profile)
    if profiles.count != int(expected_count):
        raise RuntimeError(
            "{} disques circulaires isolés au lieu de {} "
            "({} régions totales dans l'esquisse)"
            .format(profiles.count, expected_count, sketch.profiles.count)
        )
    return profiles


def _add_cut_circles(sketch, centers_local, diameter_cm):
    radius_cm = float(diameter_cm) / 2.0
    for center_local in centers_local:
        model_point = adsk.core.Point3D.create(*center_local)
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            sketch.modelToSketchSpace(model_point),
            radius_cm,
        )
        if not circle:
            raise RuntimeError("un cercle de coupe n'a pas été créé")
    return _circular_profiles(sketch, len(centers_local))


def _extrude_symmetric_cuts(
    component,
    body,
    profiles,
    cut_span_cm,
    feature_name,
):
    extrudes = component.features.extrudeFeatures
    cut_input = extrudes.createInput(
        profiles,
        adsk.fusion.FeatureOperations.CutFeatureOperation,
    )
    if not cut_input:
        raise RuntimeError("entrée de coupe indisponible")
    cut_input.participantBodies = [body]
    if not cut_input.setSymmetricExtent(
        adsk.core.ValueInput.createByReal(float(cut_span_cm)),
        True,
    ):
        raise RuntimeError("profondeur symétrique refusée")
    feature = extrudes.add(cut_input)
    if not feature:
        raise RuntimeError("fonction de coupe non créée")
    feature.name = feature_name
    return feature


def _create_local_cut_group(
    component,
    body,
    centers_local,
    sketch_plane,
    diameter_cm,
    cut_span_cm,
    feature_name,
    sketch_name,
):
    """Coupe des cylindres symétriques dans une cornière encore à l'identité."""
    if not centers_local:
        raise ValueError("Le groupe de coupes ne contient aucun centre.")
    sketch = component.sketches.add(sketch_plane)
    if not sketch:
        raise RuntimeError("Fusion n'a pas pu créer l'esquisse des coupes.")
    sketch.name = sketch_name
    try:
        profiles = _add_cut_circles(sketch, centers_local, diameter_cm)
        feature = _extrude_symmetric_cuts(
            component,
            body,
            profiles,
            cut_span_cm,
            feature_name,
        )
        sketch.isVisible = False
        return feature, sketch
    except Exception as error:
        if sketch and sketch.isValid:
            sketch.deleteMe()
        raise RuntimeError(
            "Fusion n'a pas pu créer le groupe de coupes '{}' ({})"
            .format(feature_name, error)
        ) from error


def _create_member_cut_group(
    component,
    occurrence,
    body,
    centers_world,
    axis_world,
    diameter_cm,
    cut_span_cm,
    feature_name,
    sketch_name,
):
    """Coupe symétriquement une âme depuis sa face réelle d'assemblage."""
    if not centers_world:
        raise ValueError("Le groupe de coupes ne contient aucun centre.")
    face = _planar_face_for_holes(
        body,
        occurrence,
        axis_world,
        centers_world,
    )
    sketch = component.sketches.add(face)
    if not sketch:
        raise RuntimeError("Fusion n'a pas pu créer l'esquisse des coupes.")
    sketch.name = sketch_name
    try:
        centers_local = tuple(
            _point_tuple(_world_to_local_point(occurrence, center))
            for center in centers_world
        )
        profiles = _add_cut_circles(sketch, centers_local, diameter_cm)
        feature = _extrude_symmetric_cuts(
            component,
            body,
            profiles,
            cut_span_cm,
            feature_name,
        )
        sketch.isVisible = False
        return feature, sketch
    except Exception as error:
        if sketch and sketch.isValid:
            sketch.deleteMe()
        raise RuntimeError(
            "Fusion n'a pas pu créer le groupe de coupes '{}' ({})"
            .format(feature_name, error)
        ) from error


def _add_attributes(component, evaluation, side):
    values = {
        "assembly_type": "double_angle_cleat",
        "side": side,
        "profile": evaluation.angle_profile.designation,
        "profile_source": evaluation.angle_profile.relative_path,
        "height_mm": "{:.6f}".format(evaluation.cleat_height_cm * 10.0),
        "vertical_offset_mm": "{:.6f}".format(
            evaluation.vertical_offset_cm * 10.0
        ),
        "hole_diameter_mm": "{:.6f}".format(
            evaluation.hole_pattern.diameter_cm * 10.0
        ),
        "hole_rows": str(evaluation.hole_pattern.row_count),
        "hole_pitch_mm": "{:.6f}".format(
            evaluation.hole_pattern.pitch_cm * 10.0
        ),
        "primary_gauge_mm": "{:.6f}".format(
            evaluation.hole_pattern.primary_gauge_cm * 10.0
        ),
        "secondary_gauge_mm": "{:.6f}".format(
            evaluation.hole_pattern.secondary_gauge_cm * 10.0
        ),
        "primary_component": evaluation.primary_occurrence.component.name,
        "secondary_component": evaluation.secondary_occurrence.component.name,
        "extension_version": addin_info.VERSION,
    }
    for name, value in values.items():
        component.attributes.add(ATTRIBUTE_GROUP, name, value)


def _delete_valid(entities):
    for entity in reversed(entities):
        try:
            if entity and entity.isValid:
                entity.deleteMe()
        except Exception:
            pass


def create_double_angle_assembly(root_component, evaluation):
    """Crée les deux cornières puis les trous alignés dans les quatre pièces."""
    primary_body = joint_builder._single_body(
        evaluation.primary_occurrence,
        "principale",
    )
    secondary_body = joint_builder._single_body(
        evaluation.secondary_occurrence,
        "secondaire",
    )
    material = secondary_body.material
    if not material or not material.isValid:
        raise ValueError(
            "Le matériau physique de la barre secondaire est invalide."
        )

    assembly_index = _next_assembly_index(root_component)
    created_occurrences = []
    created_on_members = []
    angle_occurrences = []
    try:
        for placement in evaluation.placements:
            rigid_frame = angle_cleat_geometry.rigid_frame_for_placement(placement)
            occurrence = root_component.occurrences.addNewComponent(
                adsk.core.Matrix3D.create()
            )
            created_occurrences.append(occurrence)
            component = occurrence.component
            component.name = "ASSEMBLAGE_CORNIERES_{:03d}_{}".format(
                assembly_index,
                placement.side.upper(),
            )
            body = _create_angle_body(
                component,
                evaluation.angle_profile,
                evaluation.cleat_height_cm,
                material,
            )
            primary_centers, secondary_centers = (
                angle_cleat_geometry.hole_centers_for_placement(
                    placement,
                    evaluation.hole_pattern,
                )
            )
            primary_centers_local = tuple(
                angle_cleat_geometry.world_point_in_rigid_frame(
                    rigid_frame,
                    center,
                )
                for center in primary_centers
            )
            secondary_centers_local = tuple(
                angle_cleat_geometry.world_point_in_rigid_frame(
                    rigid_frame,
                    center,
                )
                for center in secondary_centers
            )
            cut_span_cm = 2.0 * max(
                evaluation.angle_profile.width_mm,
                evaluation.angle_profile.height_mm,
            ) * profile_catalog.MM_TO_CM
            _create_local_cut_group(
                component,
                body,
                primary_centers_local,
                component.xZConstructionPlane,
                evaluation.hole_pattern.diameter_cm,
                cut_span_cm,
                "PERCAGES_VERS_AME_PRINCIPALE",
                "CENTRES_PERCAGES_PRINCIPALE",
            )
            _create_local_cut_group(
                component,
                body,
                secondary_centers_local,
                component.yZConstructionPlane,
                evaluation.hole_pattern.diameter_cm,
                cut_span_cm,
                "PERCAGES_VERS_AME_SECONDAIRE",
                "CENTRES_PERCAGES_SECONDAIRE",
            )
            _place_completed_occurrence(
                occurrence,
                rigid_frame,
                evaluation.angle_profile,
                evaluation.cleat_height_cm,
            )
            _add_attributes(component, evaluation, placement.side)
            angle_occurrences.append(occurrence)

        primary_cut_span_cm = 2.0 * max(
            evaluation.primary_profile_geometry.width_mm,
            evaluation.primary_profile_geometry.height_mm,
        ) * profile_catalog.MM_TO_CM
        primary_feature, primary_sketch = _create_member_cut_group(
            evaluation.primary_occurrence.component,
            evaluation.primary_occurrence,
            primary_body,
            evaluation.primary_hole_centers_world,
            evaluation.geometry.plane_normal,
            evaluation.hole_pattern.diameter_cm,
            primary_cut_span_cm,
            "PERCAGES_ASSEMBLAGE_CORNIERES_PRINCIPALE",
            "CENTRES_ASSEMBLAGE_CORNIERES_PRINCIPALE",
        )
        created_on_members.extend((primary_sketch, primary_feature))

        secondary_cut_span_cm = 2.0 * max(
            evaluation.secondary_profile_geometry.width_mm,
            evaluation.secondary_profile_geometry.height_mm,
        ) * profile_catalog.MM_TO_CM
        secondary_feature, secondary_sketch = _create_member_cut_group(
            evaluation.secondary_occurrence.component,
            evaluation.secondary_occurrence,
            secondary_body,
            evaluation.secondary_hole_centers_world,
            evaluation.secondary_profile_x_axis,
            evaluation.hole_pattern.diameter_cm,
            secondary_cut_span_cm,
            "PERCAGES_ASSEMBLAGE_CORNIERES_SECONDAIRE",
            "CENTRES_ASSEMBLAGE_CORNIERES_SECONDAIRE",
        )
        created_on_members.extend((secondary_sketch, secondary_feature))
        return DoubleAngleCreationResult(
            left_occurrence=angle_occurrences[0],
            right_occurrence=angle_occurrences[1],
            primary_hole_feature=primary_feature,
            secondary_hole_feature=secondary_feature,
        )
    except Exception:
        _delete_valid(created_on_members)
        _delete_valid(created_occurrences)
        raise
