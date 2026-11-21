"""Entrées JHR réutilisables depuis le mode script du MCP Autodesk Fusion."""

import adsk.core
import adsk.fusion

from . import (
    angle_cleat_builder, angle_cleat_creator, assembly_catalog, assembly_operations,
    fastener_creator, fastener_geometry, joint_builder, member_builder,
    member_links, physical_materials, profile_catalog, rivet_nut, simple_fastener_creator, tapped_fastener,
)


def active_design(creation_id, file_id=None):
    app = adsk.core.Application.get()
    document = app.activeDocument
    if not document or not creation_id or document.creationId != creation_id:
        raise ValueError("La conception active ne correspond pas au document demandé.")
    if document.isSaved and (not file_id or document.dataFile.id != file_id):
        raise ValueError("L'identifiant du fichier Fusion est absent ou différent.")
    if app.userInterface.activeCommand != "SelectCommand":
        raise ValueError("Terminer la commande Fusion en cours avant de lancer l'opération.")
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design or design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise ValueError("Ouvrir une conception Fusion avec historique paramétrique.")
    if design.timeline.markerPosition != design.timeline.count:
        raise ValueError("Placer le marqueur d'historique à la fin du modèle.")
    return design


def _entity(design, token, cast):
    matches = [entity for item in design.findEntityByToken(token)
               if (entity := cast(item)) and entity.isValid]
    if len(matches) != 1:
        raise ValueError("La référence Fusion ne désigne plus une entité unique.")
    return matches[0]


def _path(entity):
    return adsk.fusion.SketchLine.cast(entity) or adsk.fusion.SketchArc.cast(entity)


def _profile(identifier, profiles):
    matches = [p for p in profiles
               if identifier.casefold() in (p.relative_path.casefold(), p.component_token.casefold())]
    if len(matches) != 1:
        raise ValueError("Profil introuvable ou ambigu. Fournir son chemin dans le catalogue JHR.")
    return matches[0]


def create_members(creation_id, curve_tokens, profile, anchor="C", rotation_degrees=0.0,
                   flip_x=False, flip_y=False, material_name=None, file_id=None, role="BARRE"):
    import math

    design = active_design(creation_id, file_id)
    root = design.rootComponent
    curves = []
    for token in curve_tokens:
        curve = _entity(design, token, _path)
        if curve.parentSketch.parentComponent != root:
            raise ValueError("Le chemin doit appartenir au composant racine.")
        if curve not in curves:
            curves.append(curve)
    if not curves:
        raise ValueError("Fournir au moins une ligne ou un arc.")
    usages = member_links.curve_usages(design, root, curves)
    todo = [usage.curve for usage in usages if not usage.occurrences]
    if not todo:
        return {"created": [], "existing": len(curves)}
    section = _profile(profile, profile_catalog.discover_profiles())
    libraries = adsk.core.Application.get().materialLibraries
    choices = physical_materials.discover_steel_materials(libraries, design.materials)
    if material_name:
        choices = [choice for choice in choices if choice.material_name == material_name]
        if len(choices) != 1:
            raise ValueError("Choisir un matériau acier Fusion identifié sans ambiguïté.")
        choice = choices[0]
    else:
        choice = physical_materials.default_choice(choices)
    material = physical_materials.resolve_material(libraries, choice, design.materials)
    created = [member_builder.create_member(
        root, curve, section, anchor, math.radians(rotation_degrees),
        flip_x, flip_y, material, choice, name_prefix=role,
    ) for curve in todo]
    return {"created": [{"name": o.name, "token": o.entityToken} for o in created],
            "existing": len(curves) - len(created)}


def create_joint(creation_id, primary_token, secondary_token, kind, gap_mm=0.0, file_id=None):
    design = active_design(creation_id, file_id)
    primary, secondary = [_entity(design, token, adsk.fusion.Occurrence.cast)
                          for token in (primary_token, secondary_token)]
    if kind == "miter":
        evaluation = joint_builder.evaluate_miter_joint(design, primary, secondary)
        features = joint_builder.create_miter_joint(evaluation)
    elif kind == "straight":
        evaluation = joint_builder.evaluate_straight_joint(design, primary, secondary, gap_mm * .1)
        features = joint_builder.create_straight_joint(evaluation)
    else:
        raise ValueError("Choisir un onglet (miter) ou une coupe droite (straight).")
    return {"kind": kind, "features": [item.name for item in features]}


def assembly_templates():
    """Réglages disponibles et ordre de sélection, sans modifier le dessin."""
    return [{"type": t.key, "family": t.family, "name": t.label, "roles": list(t.roles),
             "groups": {label: {f.key: {"label": f.label, "default": f.default, "unit": f.unit,
                                       **({"choices": list(f.choices)} if f.choices else {})}
                                for f in fields} for label, fields in t.groups}}
            for t in assembly_catalog.TEMPLATES]


def create_assembly(creation_id, kind, member_tokens, parameters_mm=None,
                    alternate=False, preview=False, file_id=None):
    design = active_design(creation_id, file_id)
    occurrences = [_entity(design, token, adsk.fusion.Occurrence.cast) for token in member_tokens]
    plan = assembly_operations.evaluate(design, kind, occurrences, parameters_mm, alternate)
    report = {"type": kind, "plates": [{"name": p.name, "thickness_mm": 10*p.thickness_cm,
                                       "holes": len(p.holes)} for p in plan.plates],
              "holes_on_members": sum(len(drill.centres) for drill in plan.drilling),
              "bolts": sum(len(poses) for poses, _, _ in plan.fasteners)}
    if plan.brace_gaps_cm:
        report["brace_gaps_mm"] = [10*gap for gap in plan.brace_gaps_cm]
    if not preview:
        group = assembly_operations.create(design, plan)
        report.update(name=group.name, token=group.entityToken)
    return report


def inspect_assembly(creation_id, assembly_token, file_id=None):
    design = active_design(creation_id, file_id)
    group = _entity(design, assembly_token, adsk.fusion.Occurrence.cast)
    return assembly_operations.inspect_references(design, group)


def create_double_angle(creation_id, primary_token, secondary_token, rows=0,
                        bolts=True, preview=False, file_id=None, *, opposite_token=None):
    design = active_design(creation_id, file_id)
    members = [_entity(design, token, adsk.fusion.Occurrence.cast)
               for token in (primary_token, secondary_token)]
    profiles = profile_catalog.discover_profiles()
    if opposite_token is not None:
        opposite = _entity(design, opposite_token, adsk.fusion.Occurrence.cast)
        plan = angle_cleat_builder.suggest_opposed_double_angle(design, *members, opposite, profiles, rows)
        first = plan.first
    else:
        plan = first = angle_cleat_builder.suggest_double_angle(design, *members, profiles, rows)
    report = {"profile": first.angle_profile.designation, "rows": first.hole_pattern.row_count,
              "cleat_height_mm": first.cleat_height_cm*10,
              "hole_mm": 10*first.hole_pattern.diameter_cm,
              "bolt": first.bolt_spec.designation, "bolt_positions": len(plan.bolt_placements)}
    if not preview:
        if opposite_token is not None:
            result = angle_cleat_creator.create_opposed_double_angle_assembly(
                design.rootComponent, plan, model_bolts=bolts,
            )
            parts = result.angle_occurrences
        else:
            result = angle_cleat_creator.create_double_angle_assembly(design.rootComponent, plan, model_bolts=bolts)
            parts = (result.left_occurrence, result.right_occurrence)
        report.update(bolts_created=result.bolts_created,
                      parts=[part.entityToken for part in parts])
    return report


def place_bolts(creation_id, hole_tokens, head_support_token, nut_support_token,
                diameter_mm, length_mm=None, projection_mm=5.0, head="H",
                reverse=False, file_id=None):
    design = active_design(creation_id, file_id)
    cast_face = adsk.fusion.BRepFace.cast
    head_support = fastener_creator.read_support(_entity(design, head_support_token, cast_face))
    nut_support = fastener_creator.read_support(_entity(design, nut_support_token, cast_face))
    if head == "TF":
        holes = [fastener_creator.read_countersink(_entity(design, token, cast_face))
                 for token in hole_tokens]
    else:
        def hole_entity(entity):
            return cast_face(entity) or adsk.fusion.BRepEdge.cast(entity)

        holes = [fastener_creator.read_hole(_entity(design, token, hole_entity))
                 for token in hole_tokens]
    occupied = fastener_creator.existing_positions(design.rootComponent)
    _, placements, ignored, length = fastener_geometry.plan_modeled_fasteners(
        holes, head_support, nut_support, diameter_mm, length_mm, projection_mm,
        occupied, reverse, head=head,
    )
    result = simple_fastener_creator.create_modeled_fasteners(
        design, placements, diameter_mm, length, projection_mm, head=head
    )
    result["occupied"] += ignored
    return dict(result, head=head, length_mm=length)


def place_tapped_screw(creation_id, hole_token, head_support_token, diameter_mm,
                       engagement_mm, modeled=False, preview=False, file_id=None):
    design = active_design(creation_id, file_id)
    cast = adsk.fusion.BRepFace.cast
    face, support = (_entity(design, token, cast) for token in (hole_token, head_support_token))
    return tapped_fastener.place(design, face, support, diameter_mm, engagement_mm, modeled, preview)


def create_guardrail(creation_id, path_tokens, support_face_tokens, settings=None,
                     preview=False, file_id=None):
    """Pose à la française ou à l'anglaise sur un parcours droit par segments."""
    from . import guardrail_operations

    design = active_design(creation_id, file_id)

    def cast_path(entity):
        return adsk.fusion.SketchLine.cast(entity) or adsk.fusion.BRepEdge.cast(entity)

    paths = [_entity(design, token, cast_path) for token in path_tokens]
    faces = [_entity(design, token, adsk.fusion.BRepFace.cast) for token in support_face_tokens]
    if preview:
        return guardrail_operations.evaluate(paths, faces, settings)
    group, plan = guardrail_operations.create(design, paths, faces, settings)
    return {
        "assembly": group.entityToken, "name": group.component.name,
        "posts": len(plan["posts"]), "rails": sum(len(row) for row in plan["rails"]),
        "plates": len(plan["plates"]), "holes": sum(len(plate["holes"]) for plate in plan["plates"]),
        "support_holes": len(plan["support_holes"]), "anchors": len(plan["anchors"]),
        "pitch_mm": plan["pitch_mm"],
        "bars": len(plan.get("bars", ())), "max_clear_mm": plan.get("max_clear_mm"),
        "bottom_clear_mm": plan.get("bottom_clear_mm"),
    }


def segment_guardrail(creation_id, post_token, mode="halves", gap_mm=0., added_thickness_mm=5.,
                      preview=False, file_id=None, *, bolt_count=5):
    from . import guardrail_operations

    design = active_design(creation_id, file_id)
    post = _entity(design, post_token, adsk.fusion.Occurrence.cast)
    return guardrail_operations.segment_guardrail(design, post, mode, gap_mm, added_thickness_mm,
                                                  preview=preview, bolt_count=bolt_count)


def replace_member_section(creation_id, member_token, profile, file_id=None):
    from . import member_section

    design = active_design(creation_id, file_id)
    occurrence = _entity(design, member_token, adsk.fusion.Occurrence.cast)
    section = _profile(profile, profile_catalog.discover_profiles())
    return member_section.replace_section(design, occurrence, section)


def place_rivet_nut(creation_id, bore_token, entry_token, diameter_mm, head="flat",
                    preview=False, file_id=None, prepare_hole=False, *, screw_head=None,
                    screw_length_mm=None, screw_stack_mm=0., blind_clearance_mm=None):
    design = active_design(creation_id, file_id)
    cast = adsk.fusion.BRepFace.cast
    bore, entry = (_entity(design, token, cast) for token in (bore_token, entry_token))
    return rivet_nut.place(
        design, bore, entry, diameter_mm, head, preview=preview, prepare_hole=prepare_hole,
        screw_head=screw_head, screw_length_mm=screw_length_mm, screw_stack_mm=screw_stack_mm,
        blind_clearance_mm=blind_clearance_mm,
    )
