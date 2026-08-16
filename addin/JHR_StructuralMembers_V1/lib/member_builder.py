from __future__ import annotations

import math

import adsk.core
import adsk.fusion

from . import addin_info, profile_catalog


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


def _import_profile_sketch(component, section_plane, profile):
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
    options.position = adsk.core.Point2D.create(*profile.import_offset_cm)

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
    sketch.name = "ESQUISSE_{}_DXF_ANCRAGE_C".format(profile.component_token)
    return sketch, _validate_profile_sketch(sketch, profile)


def _validate_profile_sketch(sketch, profile):
    """Refuse un DXF mal mis à l'échelle, décentré ou non exploitable."""
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
        math.isclose(min_x, -expected_width / 2.0, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(max_x, expected_width / 2.0, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(min_y, -expected_height / 2.0, abs_tol=DIMENSION_TOLERANCE_CM)
        and math.isclose(max_y, expected_height / 2.0, abs_tol=DIMENSION_TOLERANCE_CM)
    ):
        raise RuntimeError(
            "Le DXF {} n'est pas centré sur l'ancrage C."
            .format(profile.designation)
        )
    if sketch.profiles.count < 1:
        raise RuntimeError(
            "Le DXF {} ne produit aucun profil fermé."
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


def create_member(root_component, source_curve, profile):
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
        component.attributes.add(ATTRIBUTE_GROUP, "anchor", "C")
        component.attributes.add(ATTRIBUTE_GROUP, "rotation_deg", "0")
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
