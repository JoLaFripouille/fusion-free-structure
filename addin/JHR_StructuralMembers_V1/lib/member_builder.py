from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from . import addin_info, profile_catalog, rotation


ATTRIBUTE_GROUP = "EI_JHR_StructuralMember"
DIMENSION_TOLERANCE_CM = 1e-5


def _next_component_name(root_component, profile):
    prefix = "BARRE_{}_".format(profile.component_token)
    used = set()
    for occurrence in root_component.allOccurrences:
        name = occurrence.component.name
        if name.startswith(prefix):
            suffix = name[len(prefix):]
            if suffix.isdigit():
                used.add(int(suffix))
    index = 1
    while index in used:
        index += 1
    return "{}{:03d}".format(prefix, index)


def _import_profile_sketch(
    component,
    section_plane,
    profile,
    anchor_code,
    rotation_radians,
    flip_x,
    flip_y,
):
    """Importe le DXF source dans une esquisse unique sur le plan fourni."""
    app = adsk.core.Application.get()
    import_manager = app.importManager
    options = import_manager.createDXF2DImportOptions(str(profile.dxf_path), section_plane)
    if not options:
        raise RuntimeError(
            "Fusion n'a pas pu préparer l'import du DXF {}."
            .format(profile.designation)
        )

    options.isViewFit = False
    options.isSingleSketchResult = True
    options.position = adsk.core.Point2D.create(
        *profile.import_offset_cm_for_anchor(anchor_code)
    )

    imported_objects = import_manager.importToTarget2(options, component)
    if not imported_objects:
        raise RuntimeError(
            "Fusion n'a retourné aucun objet après l'import du DXF {}."
            .format(profile.designation)
        )

    sketches = []
    for index in range(imported_objects.count):
        sketch = adsk.fusion.Sketch.cast(imported_objects.item(index))
        if sketch:
            sketches.append(sketch)
    if len(sketches) != 1:
        raise RuntimeError(
            "L'import du DXF devait produire une seule esquisse ({} détectée(s))."
            .format(len(sketches))
        )

    sketch = sketches[0]
    sketch.name = "ESQUISSE_{}_DXF_ANCRAGE_{}".format(
        profile.component_token,
        anchor_code,
    )
    _validate_profile_sketch(sketch, profile, anchor_code)
    _orient_profile_sketch(sketch, rotation_radians, flip_x, flip_y)
    return sketch, _select_material_profile(sketch, profile)


def _validate_profile_sketch(sketch, profile, anchor_code):
    """Refuse un DXF mal mis à l'échelle, mal ancré ou non exploitable."""
    boxes = []
    for collection in (
        sketch.sketchCurves.sketchLines,
        sketch.sketchCurves.sketchArcs,
        sketch.sketchCurves.sketchCircles,
    ):
        for index in range(collection.count):
            boxes.append(collection.item(index).boundingBox)
    if not boxes:
        raise RuntimeError(
            "Le DXF {} ne contient aucune courbe exploitable."
            .format(profile.designation)
        )

    min_x = min(box.minPoint.x for box in boxes)
    max_x = max(box.maxPoint.x for box in boxes)
    min_y = min(box.minPoint.y for box in boxes)
    max_y = max(box.maxPoint.y for box in boxes)
    width = max_x - min_x
    height = max_y - min_y
    expected_width = profile.width_mm * profile_catalog.MM_TO_CM
    expected_height = profile.height_mm * profile_catalog.MM_TO_CM
    source_min_x, source_min_y, source_max_x, source_max_y = profile.bounds_mm
    anchor_x, anchor_y = profile.anchor_mm(anchor_code)
    expected_min_x = (source_min_x - anchor_x) * profile_catalog.MM_TO_CM
    expected_max_x = (source_max_x - anchor_x) * profile_catalog.MM_TO_CM
    expected_min_y = (source_min_y - anchor_y) * profile_catalog.MM_TO_CM
    expected_max_y = (source_max_y - anchor_y) * profile_catalog.MM_TO_CM

    if not math.isclose(width, expected_width, abs_tol=DIMENSION_TOLERANCE_CM):
        raise RuntimeError(
            "Largeur DXF incorrecte : {:.6f} mm au lieu de {:.6f} mm."
            .format(width / profile_catalog.MM_TO_CM, profile.width_mm)
        )
    if not math.isclose(height, expected_height, abs_tol=DIMENSION_TOLERANCE_CM):
        raise RuntimeError(
            "Hauteur DXF incorrecte : {:.6f} mm au lieu de {:.6f} mm."
            .format(height / profile_catalog.MM_TO_CM, profile.height_mm)
        )
    if not (
        math.isclose(min_x, expected_min_x, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(max_x, expected_max_x, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(min_y, expected_min_y, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(max_y, expected_max_y, abs_tol=DIMENSION_TOLERANCE_CM)
    ):
        raise RuntimeError(
            "Le DXF {} n'est pas positionné sur l'ancrage {}."
            .format(profile.designation, anchor_code)
        )
    if sketch.profiles.count < 1:
        raise RuntimeError(
            "Le DXF {} ne produit aucun profil fermé."
            .format(profile.designation)
        )


def _orient_profile_sketch(sketch, rotation_radians, flip_x, flip_y):
    """Applique miroirs puis rotation autour de l'ancrage placé à l'origine."""
    if not flip_x and not flip_y and rotation.is_effectively_zero(rotation_radians):
        return

    entities = adsk.core.ObjectCollection.create()
    for collection in (
        sketch.sketchCurves.sketchLines,
        sketch.sketchCurves.sketchArcs,
        sketch.sketchCurves.sketchCircles,
    ):
        for index in range(collection.count):
            entities.add(collection.item(index))
    if entities.count < 1:
        raise RuntimeError("L'esquisse DXF ne contient aucune courbe à orienter.")

    xx, xy, yx, yy = rotation.orientation_matrix_2d(
        rotation_radians,
        flip_x,
        flip_y,
    )
    transform = adsk.core.Matrix3D.create()
    cells = (
        (0, 0, xx),
        (0, 1, xy),
        (1, 0, yx),
        (1, 1, yy),
        # Conserve une matrice 3D de déterminant positif. Dans le plan de
        # l'esquisse, le résultat reste exactement le miroir 2D demandé.
        (2, 2, (-1.0 if flip_x else 1.0) * (-1.0 if flip_y else 1.0)),
    )
    if not all(transform.setCell(row, column, value) for row, column, value in cells):
        raise RuntimeError("Fusion n'a pas pu préparer l'orientation du profil.")
    if not sketch.move(entities, transform):
        raise RuntimeError(
            "Fusion n'a pas pu orienter le profil autour du point d'ancrage."
        )


def _select_material_profile(sketch, profile):
    if sketch.profiles.count < 1:
        raise RuntimeError(
            "Le DXF {} ne produit plus de profil fermé après orientation."
            .format(profile.designation)
        )

    # Pour les tubes, Fusion expose généralement le disque intérieur et la
    # couronne comme deux profils. La couronne est la région qui possède le
    # plus de boucles (contour extérieur + contour intérieur).
    best_profile = sketch.profiles.item(0)
    best_loop_count = best_profile.profileLoops.count
    for index in range(1, sketch.profiles.count):
        candidate = sketch.profiles.item(index)
        loop_count = candidate.profileLoops.count
        if loop_count > best_loop_count:
            best_profile = candidate
            best_loop_count = loop_count
    return best_profile


def create_member(
    root_component,
    source_curve,
    profile,
    anchor_code,
    rotation_radians=0.0,
    flip_x=False,
    flip_y=False,
):
    """Crée un composant du profil choisi, lié à une ligne ou un arc."""
    transform = adsk.core.Matrix3D.create()
    occurrence = root_component.occurrences.addNewComponent(transform)
    component = occurrence.component
    component.name = _next_component_name(root_component, profile)

    try:
        plane_input = component.constructionPlanes.createInput(occurrence)
        midpoint = adsk.core.ValueInput.createByReal(0.5)
        if not plane_input.setByDistanceOnPath(source_curve, midpoint):
            raise RuntimeError("Fusion n'a pas pu définir le plan médian perpendiculaire au chemin.")
        section_plane = component.constructionPlanes.add(plane_input)
        section_plane.name = "PLAN_PROFIL_MILIEU"

        section_sketch, section_profile = _import_profile_sketch(
            component,
            section_plane,
            profile,
            anchor_code,
            rotation_radians,
            flip_x,
            flip_y,
        )

        path = adsk.fusion.Path.create(source_curve, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        if not path:
            raise RuntimeError("Fusion n'a pas pu créer le chemin à partir de la courbe sélectionnée.")

        sweeps = component.features.sweepFeatures
        sweep_input = sweeps.createInput(
            section_profile,
            path,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        sweep_input.creationOccurrence = occurrence
        sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        try:
            sweep = sweeps.add(sweep_input)
        except Exception as error:
            raise RuntimeError(
                "Fusion n'a pas pu balayer le profil sur ce chemin. "
                "Pour un arc, vérifier notamment que son rayon n'est pas trop faible."
            ) from error
        sweep.name = "BARRE_CENTREE_SUR_CHEMIN"
        if sweep.bodies.count != 1:
            raise RuntimeError("La création n'a pas produit un corps unique.")
        body = sweep.bodies.item(0)
        body.name = "CORPS_{}".format(profile.component_token)

        source_token = source_curve.entityToken
        source_type = "arc" if adsk.fusion.SketchArc.cast(source_curve) else "line"
        component.attributes.add(ATTRIBUTE_GROUP, "profile", profile.designation)
        component.attributes.add(ATTRIBUTE_GROUP, "profile_family", profile.family_id)
        component.attributes.add(ATTRIBUTE_GROUP, "profile_source", profile.relative_path)
        component.attributes.add(ATTRIBUTE_GROUP, "anchor", anchor_code)
        component.attributes.add(
            ATTRIBUTE_GROUP,
            "rotation_deg",
            rotation.format_degrees(rotation_radians),
        )
        component.attributes.add(ATTRIBUTE_GROUP, "flip_x", str(bool(flip_x)).lower())
        component.attributes.add(ATTRIBUTE_GROUP, "flip_y", str(bool(flip_y)).lower())
        component.attributes.add(ATTRIBUTE_GROUP, "source_curve_token", source_token)
        component.attributes.add(ATTRIBUTE_GROUP, "source_curve_type", source_type)
        if source_type == "line":
            component.attributes.add(ATTRIBUTE_GROUP, "source_line_token", source_token)
        component.attributes.add(ATTRIBUTE_GROUP, "extension_version", addin_info.VERSION)

        section_plane.isLightBulbOn = False
        section_sketch.isVisible = False
        return occurrence
    except Exception:
        if occurrence and occurrence.isValid:
            occurrence.deleteMe()
        raise
