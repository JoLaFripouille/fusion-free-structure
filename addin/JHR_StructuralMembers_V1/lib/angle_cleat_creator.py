from __future__ import annotations

from dataclasses import dataclass

import adsk.core
import adsk.fusion

from . import (
    addin_info,
    angle_cleat_geometry,
    fastener_creator,
    fastener_geometry,
    joint_builder,
    joint_geometry,
    member_builder,
    profile_catalog,
    simple_fastener_creator,
    timeline_groups,
)


ATTRIBUTE_GROUP = "EI_JHR_AngleCleat"
FACE_ALIGNMENT_TOLERANCE = 0.995
PLACEMENT_TOLERANCE_CM = 1e-4
CIRCLE_MATCH_TOLERANCE_CM = 1e-3


@dataclass(frozen=True)
class DoubleAngleCreationResult:
    left_occurrence: object
    right_occurrence: object
    primary_hole_feature: object
    secondary_hole_feature: object
    native_fastener_edges: tuple
    bolts_created: int = 0


@dataclass(frozen=True)
class OpposedAngleCreationResult:
    angle_occurrences: tuple
    primary_hole_feature: object
    secondary_hole_features: tuple
    bolts_created: int


def _point_tuple(point):
    return float(point.x), float(point.y), float(point.z)


def _vector_tuple(vector):
    return float(vector.x), float(vector.y), float(vector.z)


def _native_fastener_edges(
    body,
    occurrence,
    centers_world,
    axis_world,
    radius_cm,
    prefer_negative_station,
    label,
):
    """Retrouve une arête circulaire exposée par trou pour l'outil natif Fusion."""
    proxy = body.createForAssemblyContext(occurrence) or body
    axis = joint_geometry.normalize(axis_world)
    circular_edges = []
    for index in range(proxy.edges.count):
        edge = proxy.edges.item(index)
        circle = adsk.core.Circle3D.cast(edge.geometry)
        if not circle or abs(float(circle.radius) - float(radius_cm)) > (
            CIRCLE_MATCH_TOLERANCE_CM
        ):
            continue
        circular_edges.append((edge, _point_tuple(circle.center)))

    selected = []
    for row_index, center in enumerate(centers_world, start=1):
        candidates = []
        for edge, edge_center in circular_edges:
            delta = joint_geometry.subtract(edge_center, center)
            axial_distance = joint_geometry.dot(delta, axis)
            perpendicular = joint_geometry.subtract(
                delta,
                joint_geometry.scale(axis, axial_distance),
            )
            if joint_geometry.length(perpendicular) > CIRCLE_MATCH_TOLERANCE_CM:
                continue
            station = joint_geometry.dot(edge_center, axis)
            candidates.append((station, edge))
        if not candidates:
            raise RuntimeError(
                "L'arête circulaire native {} rangée {} est introuvable."
                .format(label, row_index)
            )
        candidates.sort(key=lambda item: item[0])
        selected.append(candidates[0 if prefer_negative_station else -1][1])
    return tuple(selected)


def _next_assembly_index(root_component):
    prefix = "ASSEMBLAGE_CORNIERES_"
    used = set()
    for occurrence in root_component.occurrences:
        group_index = occurrence.component.attributes.itemByName(ATTRIBUTE_GROUP, "assembly_index")
        if group_index and group_index.value.isdigit():
            used.add(int(group_index.value))
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


def _validate_occurrence_position(occurrence, frame, profile, height_cm):
    """Vérifie l'enveloppe de la cornière dans l'assemblage."""
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


def _circular_profiles(sketch, circles):
    """Sélectionne uniquement les disques créés par cette opération."""
    sources = tuple(circle.nativeObject or circle for circle in circles)
    profiles = adsk.core.ObjectCollection.create()
    for index in range(sketch.profiles.count):
        profile = sketch.profiles.item(index)
        loops = profile.profileLoops
        if loops.count != 1:
            continue
        curves = loops.item(0).profileCurves
        if curves.count != 1:
            continue
        if curves.item(0).sketchEntity not in sources:
            continue
        profiles.add(profile)
    if profiles.count != len(sources):
        raise RuntimeError(
            "{} disques circulaires isolés au lieu de {} "
            "({} régions totales dans l'esquisse)"
            .format(profiles.count, len(sources), sketch.profiles.count)
        )
    return profiles


def _add_cut_circles(sketch, centers_local, diameter_cm):
    radius_cm = float(diameter_cm) / 2.0
    circles = []
    for center_local in centers_local:
        model_point = adsk.core.Point3D.create(*center_local)
        circle = sketch.sketchCurves.sketchCircles.addByCenterRadius(
            sketch.modelToSketchSpace(model_point),
            radius_cm,
        )
        if not circle:
            raise RuntimeError("un cercle de coupe n'a pas été créé")
        circles.append(circle)
    return _circular_profiles(sketch, circles)


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
    *,
    source_circles=(),
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
        if source_circles:
            projected = sketch.createForAssemblyContext(occurrence).project2(source_circles, True) or ()
            if (len(projected) != len(centers_world)
                    or not all(adsk.fusion.SketchCircle.cast(entity) and entity.isReference for entity in projected)):
                raise RuntimeError("Les perçages du plat n’ont pas tous été projetés sur l’âme.")
            profiles = _circular_profiles(sketch, projected)
        else:
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


def _create_cleats(root, plan, material, face, created):
    parts = []
    for placement in plan.placements:
        frame = angle_cleat_geometry.rigid_frame_for_placement(placement)
        occurrence = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        created.append(occurrence)
        component = occurrence.component
        component.name = f"{plan.angle_profile.designation} · {face} {placement.side}"
        body = _create_angle_body(component, plan.angle_profile, plan.cleat_height_cm, material)
        span = 2.0 * max(plan.angle_profile.width_mm, plan.angle_profile.height_mm) * profile_catalog.MM_TO_CM
        primary, secondary = angle_cleat_geometry.hole_centers_for_placement(placement, plan.hole_pattern)
        for member, plane, centers in (
            ("PRINCIPALE", component.xZConstructionPlane, primary),
            ("SECONDAIRE", component.yZConstructionPlane, secondary),
        ):
            local = tuple(angle_cleat_geometry.world_point_in_rigid_frame(frame, center) for center in centers)
            _create_local_cut_group(component, body, local, plane, plan.hole_pattern.diameter_cm, span,
                                    f"PERCAGES_VERS_AME_{member}", f"CENTRES_PERCAGES_{member}")
        _add_attributes(component, plan, placement.side)
        parts.append((occurrence, body, frame, plan))
    return parts


def _cut_web(occurrence, body, section, centers, axis, diameter, member, created):
    span = 2.0 * max(section.width_mm, section.height_mm) * profile_catalog.MM_TO_CM
    feature, sketch = _create_member_cut_group(
        occurrence.component, occurrence, body, centers, axis, diameter, span,
        f"PERCAGES_ASSEMBLAGE_CORNIERES_{member}", f"CENTRES_ASSEMBLAGE_CORNIERES_{member}",
    )
    created.extend((sketch, feature))
    return feature


def _make_bolts(design, group, placements, spec, assembly_parts):
    washer = spec.washer_thickness_mm * .1
    by_length = {}
    for bolt in placements:
        origin = joint_geometry.add(bolt.origin, joint_geometry.scale(bolt.z_axis, washer))
        by_length.setdefault(round(bolt.bolt_length_cm*10, 6), []).append(
            fastener_geometry.Placement(origin, bolt.x_axis, bolt.y_axis, bolt.z_axis, bolt.grip_length_cm),
        )
    count = 0
    for length, poses in by_length.items():
        result = simple_fastener_creator.create_modeled_fasteners(
            design, poses, spec.nominal_diameter_mm, length, spec.thread_projection_mm, assembly=group,
        )
        count += result["created"]
    if count != len(placements):
        raise ValueError("Une position de boulon est déjà occupée dans ce raccord.")
    if count:
        modeled = [bolt for hardware in fastener_creator.assembly_hardware(group)
                   for batch in hardware.childOccurrences for bolt in batch.childOccurrences]
        fastener_creator.verify_clearance(design, (*assembly_parts, *modeled))
    return count


def _create_angle_assembly(root, plans, bolts, model_bolts):
    snapshots = root.parentDesign.snapshots
    if snapshots.hasPendingSnapshot:
        raise ValueError("Valider d’abord les positions en attente dans Fusion.")
    first = plans[0]
    primary = joint_builder._single_body(first.primary_occurrence, "principale")
    secondaries = [joint_builder._single_body(plan.secondary_occurrence, "secondaire") for plan in plans]
    materials = [body.material for body in secondaries]
    if any(not material or not material.isValid for material in materials):
        raise ValueError("Le matériau physique d’une barre secondaire est invalide.")

    index = _next_assembly_index(root)
    opposed = len(plans) > 1
    timeline = root.parentDesign.timeline
    start = timeline_groups.creation_start(timeline)
    member_features, drafts = [], []
    group = root.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    if not group:
        raise RuntimeError("Fusion n’a pas créé le composant d’assemblage.")
    try:
        label = "Cornières opposées" if opposed else "Assemblage par cornières"
        group.component.name = f"{label} {index:03d}"
        group.component.attributes.add(ATTRIBUTE_GROUP, "assembly_index", str(index))
        parts = []
        for side, (plan, material) in enumerate(zip(plans, materials), start=1):
            face = f"face {side}" if opposed else "côté"
            parts.extend(_create_cleats(root, plan, material, face, drafts))

        for occurrence, _, frame, _ in parts:
            occurrence.transform2 = _matrix_for_frame(frame)
        if snapshots.hasPendingSnapshot:
            snapshot = snapshots.add()
            if not snapshot:
                raise RuntimeError("Fusion n’a pas conservé la position des cornières.")
            member_features.append(snapshot)
        moved_parts = []
        for occurrence, _, frame, plan in parts:
            moved = occurrence.moveToComponent(group)
            if not moved:
                raise RuntimeError("Fusion n’a pas rangé la cornière dans l’assemblage.")
            contextual = moved if moved.assemblyContext else moved.createForAssemblyContext(group)
            _validate_occurrence_position(contextual, frame, plan.angle_profile, plan.cleat_height_cm)
            moved_parts.append((contextual, contextual.component.bRepBodies.item(0), frame, plan))
        parts = moved_parts

        diameter = first.hole_pattern.diameter_cm
        primary_feature = _cut_web(first.primary_occurrence, primary, first.primary_profile_geometry,
                                   first.primary_hole_centers_world, first.geometry.plane_normal,
                                   diameter, "PRINCIPALE", member_features)
        secondary_features = tuple(
            _cut_web(plan.secondary_occurrence, body, plan.secondary_profile_geometry,
                     plan.secondary_hole_centers_world, plan.secondary_profile_x_axis,
                     diameter, "SECONDAIRE", member_features)
            for plan, body in zip(plans, secondaries)
        )
        occurrences = tuple(occurrence for occurrence, _, _, _ in parts)
        assembly_parts = (first.primary_occurrence, *(plan.secondary_occurrence for plan in plans), *occurrences)
        count = 0
        if model_bolts:
            with timeline_groups.defer_grouping():
                count = _make_bolts(root.parentDesign, group, bolts, first.bolt_spec, assembly_parts)
        if opposed:
            if not model_bolts:
                fastener_creator.verify_clearance(root.parentDesign, assembly_parts)
            timeline_groups.group_creation(timeline, start, group.component.name)
            return OpposedAngleCreationResult(occurrences, primary_feature, secondary_features, count)

        left_secondary_centers = angle_cleat_geometry.hole_centers_for_placement(first.placements[0],
                                                                                first.hole_pattern)[1]
        primary_edges = _native_fastener_edges(
            primary, first.primary_occurrence, first.primary_hole_centers_world, first.geometry.plane_normal,
            diameter/2, True, "sur l’âme principale",
        )
        secondary_edges = _native_fastener_edges(
            parts[0][1], occurrences[0], left_secondary_centers, first.secondary_profile_x_axis,
            diameter/2, True, "sur la cornière gauche",
        )
        timeline_groups.group_creation(timeline, start, group.component.name)
        return DoubleAngleCreationResult(*occurrences, primary_feature, secondary_features[0],
                                         primary_edges + secondary_edges, count)
    except Exception:
        _delete_valid(member_features)
        _delete_valid(drafts)
        _delete_valid([group])
        raise


def create_double_angle_assembly(root_component, evaluation, model_bolts=False):
    """Crée les deux cornières et les perçages d’une poutre secondaire."""
    return _create_angle_assembly(root_component, (evaluation,), evaluation.bolt_placements, model_bolts)


def create_opposed_double_angle_assembly(root_component, evaluation, model_bolts=True):
    """Crée les quatre cornières et une seule grille dans l’âme principale."""
    return _create_angle_assembly(root_component, (evaluation.first, evaluation.opposite),
                                  evaluation.bolt_placements, model_bolts)
