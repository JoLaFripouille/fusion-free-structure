from __future__ import annotations

import adsk.core
import adsk.fusion

from . import ipe100


ATTRIBUTE_GROUP = "EI_JHR_StructuralMember"


def _point2d(x, y):
    return adsk.core.Point3D.create(float(x), float(y), 0.0)


def _draw_ipe100(sketch):
    """Dessine un IPE 100 exact avec l'ancrage C sur l'origine de l'esquisse."""
    segments = ipe100.segments_cm(anchor=(0.0, 50.0))
    lines = sketch.sketchCurves.sketchLines
    arcs = sketch.sketchCurves.sketchArcs
    first_entity = None
    previous_entity = None
    sketch.isComputeDeferred = True
    try:
        for index, segment in enumerate(segments):
            is_last = index == len(segments) - 1
            if previous_entity is None:
                start_input = _point2d(*segment["start"])
            else:
                start_input = previous_entity.endSketchPoint

            if segment["type"] == "LINE":
                end_input = first_entity.startSketchPoint if is_last and first_entity else _point2d(*segment["end"])
                entity = lines.addByTwoPoints(start_input, end_input)
            elif segment["type"] == "ARC":
                entity = arcs.addByCenterStartSweep(
                    _point2d(*segment["center"]),
                    start_input,
                    float(segment["sweep"]),
                )
            else:
                raise ValueError("Primitive IPE non prise en charge: {}".format(segment["type"]))

            if first_entity is None:
                first_entity = entity
            previous_entity = entity
    finally:
        sketch.isComputeDeferred = False

    if sketch.profiles.count != 1:
        raise RuntimeError("Le contour IPE 100 ne produit pas un profil fermé unique ({} détecté).".format(sketch.profiles.count))
    return sketch.profiles.item(0)


def _next_component_name(root_component):
    prefix = "BARRE_IPE100_"
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


def create_member(root_component, source_line):
    """Crée un composant IPE 100 paramétriquement lié à une ligne du squelette."""
    transform = adsk.core.Matrix3D.create()
    occurrence = root_component.occurrences.addNewComponent(transform)
    component = occurrence.component
    component.name = _next_component_name(root_component)

    try:
        plane_input = component.constructionPlanes.createInput(occurrence)
        midpoint = adsk.core.ValueInput.createByReal(0.5)
        if not plane_input.setByDistanceOnPath(source_line, midpoint):
            raise RuntimeError("Fusion n'a pas pu définir le plan médian perpendiculaire à la ligne.")
        section_plane = component.constructionPlanes.add(plane_input)
        section_plane.name = "PLAN_PROFIL_MILIEU"

        section_sketch = component.sketches.add(section_plane)
        section_sketch.name = "ESQUISSE_IPE100_ANCRAGE_C"
        section_profile = _draw_ipe100(section_sketch)

        path = adsk.fusion.Path.create(source_line, adsk.fusion.ChainedCurveOptions.noChainedCurves)
        if not path:
            raise RuntimeError("Fusion n'a pas pu créer le chemin à partir de la ligne sélectionnée.")

        sweeps = component.features.sweepFeatures
        sweep_input = sweeps.createInput(
            section_profile,
            path,
            adsk.fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        sweep_input.creationOccurrence = occurrence
        sweep_input.orientation = adsk.fusion.SweepOrientationTypes.PerpendicularOrientationType
        sweep = sweeps.add(sweep_input)
        sweep.name = "BARRE_SYMETRIQUE_SUR_LIGNE"
        if sweep.bodies.count != 1:
            raise RuntimeError("La création n'a pas produit un corps unique.")
        body = sweep.bodies.item(0)
        body.name = "CORPS_IPE100"

        source_token = source_line.entityToken
        component.attributes.add(ATTRIBUTE_GROUP, "profile", ipe100.PROFILE_NAME)
        component.attributes.add(ATTRIBUTE_GROUP, "anchor", ipe100.ANCHOR_NAME)
        component.attributes.add(ATTRIBUTE_GROUP, "rotation_deg", "0")
        component.attributes.add(ATTRIBUTE_GROUP, "source_line_token", source_token)
        component.attributes.add(ATTRIBUTE_GROUP, "extension_version", "1.0.0")

        section_plane.isLightBulbOn = False
        section_sketch.isVisible = False
        return occurrence
    except Exception:
        if occurrence and occurrence.isValid:
            occurrence.deleteMe()
        raise
