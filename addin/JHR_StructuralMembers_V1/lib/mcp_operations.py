"""Entrées JHR réutilisables depuis le mode script du MCP Autodesk Fusion."""

from dataclasses import asdict, replace
from inspect import signature
from unicodedata import normalize

import adsk.core
import adsk.fusion

from . import (
    addin_info, angle_cleat_builder, angle_cleat_creator, assembly_catalog, assembly_operations,
    custom_profiles, default_settings, fastener_creator, fastener_geometry, joint_builder, member_builder,
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
    matches = [entity for item in (design.findEntityByToken(token) or ())
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


def _search_key(value):
    return "".join(char for char in normalize("NFKD", value.casefold().replace("×", "x"))
                   if char.isalnum())


def _profile_record(profile):
    return {"reference": profile.relative_path, "designation": profile.designation,
            "category": profile.category_label, "region": profile.region_label,
            "family": profile.family_label, "section": profile.section_label,
            "width_mm": round(profile.width_mm, 3), "height_mm": round(profile.height_mm, 3)}


def list_profiles(query="", family=None, *, offset=0, limit=30):
    """Cherche les DXF livrés et personnalisés. Passer leur référence à create_members."""
    if type(offset) is not int or type(limit) is not int or offset < 0 or not 1 <= limit <= 100:
        raise ValueError("Pagination invalide : décalage positif ou nul et limite de 1 à 100.")
    needle = _search_key(query)
    family_key = _search_key(family) if family is not None else None
    matches = [item for item in profile_catalog.discover_profiles()
               if (family_key is None or family_key in (_search_key(item.family_id), _search_key(item.family_label)))
               and (needle in _search_key(item.designation) or needle in _search_key(item.relative_path))]
    return {"total": len(matches), "offset": offset,
            "profiles": [_profile_record(item) for item in matches[offset:offset + limit]]}


def active_context():
    """Identifie le dessin actif et les jetons de la sélection, en lecture seule."""
    app = adsk.core.Application.get()
    document = app.activeDocument
    if not document:
        raise ValueError("Ouvrir le dessin Fusion à travailler.")
    selection = app.userInterface.activeSelections
    return {"version": addin_info.VERSION, "name": document.name, "creation_id": document.creationId,
            "file_id": document.dataFile.id if document.isSaved else None,
            "active_command": app.userInterface.activeCommand,
            "selection_count": selection.count, "selection": [
                {"type": entity.objectType, "name": getattr(entity, "name", None),
                 "token": getattr(entity, "entityToken", None)}
                for entity in (selection.item(i).entity for i in range(min(selection.count, 20)))]}


def import_custom_profile(source_path, family, designation, *, preview=True):
    """Contrôle le DXF fourni et l’ajoute à la bibliothèque locale sur demande."""
    imported = None if preview else custom_profiles.import_profile(source_path, family, designation)
    analysis = imported.analysis if imported else custom_profiles.validate_dxf(source_path)
    result = {"width_mm": analysis.width_mm, "height_mm": analysis.height_mm,
              "contours": analysis.contour_count, "entities": analysis.entity_count}
    if imported:
        result.update(reference=imported.record.relative_path, family=imported.record.family_label,
                      designation=imported.record.section_label)
    return result


def remove_custom_profile(creation_id, reference, file_id=None, *, preview=True, allow_in_use=False):
    """Contrôle les références du dessin et déplace le DXF dans la corbeille locale."""
    from ..commands import manage_custom_profiles

    active_design(creation_id, file_id)
    section = _profile(reference, profile_catalog.discover_profiles())
    if section.category_id != custom_profiles.CATEGORY_ID:
        raise ValueError("Le profil doit appartenir à la bibliothèque personnalisée.")
    active_references = manage_custom_profiles._active_reference_count(section.relative_path)
    if active_references and not (preview or allow_in_use):
        raise ValueError(f"Le dessin actif contient {active_references} occurrence(s) de cette section.")
    if not preview:
        custom_profiles.delete_profile(section.relative_path, active_reference_count=active_references)
    return {"reference": section.relative_path, "active_references": active_references, "removed": not preview}


def get_defaults():
    """Lit les jeux JHR locaux utilisés lors des jonctions et grugeages."""
    return asdict(default_settings.load())


def set_defaults(changes_mm, *, preview=True):
    """Valide et applique seulement les changements de jeux fournis."""
    original = default_settings.load()
    original_values = asdict(original)
    if not isinstance(changes_mm, dict) or changes_mm.keys() - original_values.keys():
        raise ValueError("Fournir les réglages reconnus par get_defaults.")
    requested = {field: default_settings._distance(value, field) for field, value in changes_mm.items()}
    changed = {field: value for field, value in requested.items() if value != original_values[field]}
    updated = replace(original, **changed)
    if changed and not preview:
        default_settings.save(updated)
    return {"values": asdict(updated), "changed": list(changed), "saved": bool(changed) and not preview}


_OPERATIONS = {
    "active_context": "Dessin actif et références de sélection",
    "list_profiles": "Catalogue de profils acier, livré et personnalisé",
    "create_members": "Profils acier depuis les chemins et les contours DXF du catalogue",
    "create_columns": "Poteaux depuis les points du squelette",
    "inspect_member": "Section, réglages et référence au squelette d’un profil",
    "edit_member": "Modification du profil, de sa section ou de son orientation",
    "replace_member_section": "Remplacement de section d’un profil existant",
    "create_joint": "Coupe droite ou onglet entre profils",
    "create_cope": "Grugeage des profils ouverts",
    "assembly_templates": "Catalogue des assemblages et ordre de sélection",
    "create_assembly": "Pieds de poteau, jarrets, éclissages, goussets et plats d’âme",
    "create_double_angle": "Attaches de poutres par cornières",
    "create_brace_bay": "Auto-contreventement de deux poteaux",
    "connect_purlins": "Attaches en série des pannes aux poutres",
    "inspect_assembly": "Inspection et suivi du squelette d’un assemblage",
    "edit_assembly": "Modification paramétrique d’un assemblage existant",
    "copy_assembly": "Copie d’un assemblage sur d’autres profils",
    "remove_assembly": "Suppression des pièces et usinages d’un assemblage JHR",
    "place_bolts": "Pose de boulons du catalogue ou copie d’un ensemble existant",
    "place_tapped_screw": "Pose d’une vis dans un taraudage, avec fraisure si demandée",
    "place_rivet_nut": "Pose d’un RIVKLE seul ou avec vis",
    "attach_rivet_screw": "Ajout d’une vis sur un RIVKLE déjà posé",
    "create_guardrail": "Garde-corps à lisses ou à barreaux, sur appuis acier",
    "segment_guardrail": "Tronçonnage de garde-corps au droit d’un poteau plat",
    "import_custom_profile": "Contrôle et ajout d’un DXF dans le catalogue local",
    "remove_custom_profile": "Retrait récupérable d’un profil personnalisé",
    "get_defaults": "Lecture des réglages JHR locaux",
    "set_defaults": "Mise à jour ciblée des réglages JHR locaux",
}


def list_operations():
    """Présente les opérations JHR et leurs arguments au MCP Autodesk Fusion."""
    return {"version": addin_info.VERSION, "operations": [
        {"name": name, "description": label, "arguments": str(signature(globals()[name]))}
        for name, label in _OPERATIONS.items()]}


def run_operation(name, arguments=None):
    """Exécute une opération JHR répertoriée avec un dictionnaire de paramètres."""
    if not isinstance(name, str) or name not in _OPERATIONS:
        raise ValueError("Opération JHR inconnue. Consulter list_operations.")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        raise ValueError("Fournir un dictionnaire de paramètres nommés.")
    return globals()[name](**arguments)


def _material(design, material_name=None):
    libraries = adsk.core.Application.get().materialLibraries
    choices = physical_materials.discover_steel_materials(libraries, design.materials)
    if material_name:
        choices = [choice for choice in choices if choice.material_name == material_name]
        if len(choices) != 1:
            raise ValueError("Choisir un matériau acier Fusion identifié sans ambiguïté.")
        choice = choices[0]
    else:
        choice = physical_materials.default_choice(choices)
    return physical_materials.resolve_material(libraries, choice, design.materials), choice


def create_members(creation_id, curve_tokens, profile, anchor="C", rotation_degrees=0.0,
                   flip_x=False, flip_y=False, material_name=None, file_id=None, role="BARRE", *, preview=False):
    """Crée des profils JHR depuis les lignes ou arcs et le contour DXF du catalogue."""
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
    if preview:
        section = _profile(profile, profile_catalog.discover_profiles())
        section.anchor_mm(anchor)
        return {"profile": _profile_record(section), "to_create": len(todo), "existing": len(curves) - len(todo)}
    if not todo:
        return {"created": [], "existing": len(curves)}
    section = _profile(profile, profile_catalog.discover_profiles())
    material, choice = _material(design, material_name)
    created = [member_builder.create_member(
        root, curve, section, anchor, math.radians(rotation_degrees),
        flip_x, flip_y, material, choice, name_prefix=role,
    ) for curve in todo]
    return {"created": [{"name": o.name, "token": o.entityToken} for o in created],
            "existing": len(curves) - len(created)}


def create_joint(creation_id, primary_token, secondary_token, kind, gap_mm=0.0, file_id=None, *, preview=False):
    design = active_design(creation_id, file_id)
    primary, secondary = [_entity(design, token, adsk.fusion.Occurrence.cast)
                          for token in (primary_token, secondary_token)]
    if kind == "miter":
        evaluation = joint_builder.evaluate_miter_joint(design, primary, secondary)
        create = joint_builder.create_miter_joint
    elif kind == "straight":
        evaluation = joint_builder.evaluate_straight_joint(design, primary, secondary, gap_mm * .1)
        create = joint_builder.create_straight_joint
    else:
        raise ValueError("Choisir un onglet (miter) ou une coupe droite (straight).")
    if preview:
        return {"kind": kind, "angle_deg": evaluation.geometry.angle_degrees,
                "cut_point_mm": [10 * value for value in evaluation.cut_point],
                "cut_normal": evaluation.cut_normal}
    return {"kind": kind, "features": [item.name for item in create(evaluation)]}


def create_cope(creation_id, primary_token, secondary_token, vertical_clearance_mm=None,
                longitudinal_clearance_mm=None, web_clearance_mm=None, under_web_clearance_mm=None,
                root_relief_clearance_mm=None, preview=False, file_id=None):
    """Gruge deux profils ouverts, avec les valeurs mémorisées selon la famille secondaire."""
    import math
    from . import cope_builder, cope_creator

    design = active_design(creation_id, file_id)
    cast = adsk.fusion.Occurrence.cast
    primary, secondary = (_entity(design, token, cast) for token in (primary_token, secondary_token))
    family = joint_builder._member_metadata(secondary, "secondaire").profile_family
    defaults, _ = default_settings.load_or_factory()
    group = default_settings.profile_group(family)
    is_lt = group == default_settings.L_T_GROUP
    settings = (
        (vertical_clearance_mm, 0. if is_lt else defaults.cope_ih_vertical_mm),
        (longitudinal_clearance_mm, defaults.cope_lt_longitudinal_mm if is_lt else defaults.cope_ih_longitudinal_mm),
        (web_clearance_mm, defaults.cope_lt_support_mm if is_lt else defaults.cope_ih_support_mm),
        (under_web_clearance_mm, defaults.cope_lt_under_web_mm if is_lt else 0.),
        (root_relief_clearance_mm, defaults.cope_lt_root_relief_mm if is_lt else 0.),
    )
    distances = [float(default if value is None else value) for value, default in settings]
    if any(not math.isfinite(distance) or distance < 0. for distance in distances):
        raise ValueError("Les jeux du grugeage doivent être finis et positifs ou nuls.")
    evaluation = cope_builder.evaluate_profile_cope(design, primary, secondary, *(value * .1 for value in distances))
    if preview:
        cope_creator.ensure_endpoint_available(evaluation)
    report = cope_creator._record_payload(evaluation)
    if not preview:
        report["features"] = [item.name for item in cope_creator.create_profile_cope(evaluation)]
    return report


def create_columns(creation_id, point_tokens, height_mm, profile=None, material_name=None,
                   preview=False, file_id=None):
    """Crée des poteaux en Z positif sur les points choisis, avec un axe lié par poteau."""
    from ..commands import create_columns as columns

    def point_entity(entity):
        return (adsk.fusion.SketchPoint.cast(entity) or adsk.fusion.ConstructionPoint.cast(entity)
                or adsk.fusion.BRepVertex.cast(entity))

    design = active_design(creation_id, file_id)
    entities = [_entity(design, token, point_entity) for token in point_tokens]
    if not entities:
        raise ValueError("Sélectionner au moins un point de départ.")
    height_cm = float(height_mm) * .1
    profiles = profile_catalog.discover_profiles()
    section = profile_catalog.default_profile(profiles) if profile is None else _profile(profile, profiles)
    material, choice = _material(design, material_name)
    if preview:
        paths = columns.column_endpoints(entities, height_cm)
        return {"profile": section.designation, "columns": [
            {"base_mm": [value * 10 for value in base.asArray()], "top_mm": [value * 10 for value in top.asArray()]}
            for base, top in paths
        ]}
    occurrences = columns.create_columns(design, entities, height_cm, section, material, choice)
    return {"profile": section.designation,
            "created": [{"name": item.name, "token": item.entityToken} for item in occurrences]}


def inspect_member(creation_id, member_token, file_id=None):
    """Lit le profil JHR, sa référence d’esquisse et le matériau physique du corps."""
    from ..commands import inspect_member as inspection
    from . import member_metadata

    design = active_design(creation_id, file_id)
    occurrence = _entity(design, member_token, adsk.fusion.Occurrence.cast)
    metadata = joint_builder._member_metadata(occurrence, "à inspecter")
    component = occurrence.component
    material, material_status, properties = inspection._physical_material_status(occurrence, metadata)
    dxf = profile_catalog.resolve_profile_source(metadata.profile_source, addin_info.ADDIN_ROOT)
    return {**asdict(metadata), "name": occurrence.name, "token": occurrence.entityToken,
            "role": member_metadata.role_for(component), "source_available": dxf.is_file(),
            "source_curve_found": inspection._linked_curve(design, metadata) is not None,
            "body_material_name": material, "body_material_status": material_status,
            "body_material_property_count": int(properties) if properties.isdecimal() else None}


def edit_member(creation_id, member_token, profile=None, anchor=None, rotation_degrees=None,
                flip_x=None, flip_y=None, material_name=None, role=None, file_id=None):
    """Modifie un profil JHR en conservant les réglages omis et via le même recalcul que le ruban."""
    import math
    from . import anchors, member_section

    design = active_design(creation_id, file_id)
    occurrence = _entity(design, member_token, adsk.fusion.Occurrence.cast)
    metadata = joint_builder._member_metadata(occurrence, "à modifier")
    section = _profile(metadata.profile_source if profile is None else profile, profile_catalog.discover_profiles())
    anchor = metadata.anchor if anchor is None else anchor
    anchors.definition(anchor)
    degrees = metadata.rotation_deg if rotation_degrees is None else float(rotation_degrees)
    if not math.isfinite(degrees):
        raise ValueError("L’angle de rotation doit être fini.")
    if any(value is not None and not isinstance(value, bool) for value in (flip_x, flip_y)):
        raise ValueError("Les options miroir doivent être des booléens.")
    material, choice = (None, None) if material_name is None else _material(design, material_name)
    result = member_section.edit_member(
        design, occurrence, section, anchor, math.radians(degrees),
        metadata.flip_x if flip_x is None else flip_x, metadata.flip_y if flip_y is None else flip_y,
        physical_material=material, material_choice=choice, role=role,
    )
    return {**result, "name": occurrence.name, "token": occurrence.entityToken}


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
    """Contrôle un assemblage à platines ou un X depuis le groupe ou une pièce."""
    from ..commands.inspect_assembly import _assembly
    from . import brace_bay

    design = active_design(creation_id, file_id)
    entity = _entity(design, assembly_token, _assembly_selection)
    if brace_bay.find_group(entity):
        group, faces, record = brace_bay.read(design, entity)
        stored = record.get("face_state")
        changes = [{"role": f"Poteau {index}", "cause": "face_porteuse_modifiée"}
                   for index, (before, after) in enumerate(zip(stored or (), brace_bay._face_state(faces)), 1)
                   if before != after]
        status = "historique_sans_relevé" if stored is None else "à_revoir" if changes else "à_jour"
        return {"name": group.name, "token": group.entityToken, "type": "brace_bay", "status": status,
                "changes": changes, "profiles": record["profiles"], "settings": record["settings"]}
    group = _assembly(entity)
    return {"name": group.name, "token": group.entityToken, **assembly_operations.inspect_references(design, group)}


def _assembly_selection(entity):
    return (adsk.fusion.Occurrence.cast(entity) or adsk.fusion.BRepBody.cast(entity)
            or adsk.fusion.BRepFace.cast(entity))


def _assembly_plan_report(plates, fasteners):
    return {"plates": [{"name": plate.name, "thickness_mm": 10 * plate.thickness_cm,
                        "holes": len(plate.holes)} for plate in plates],
            "bolts": sum(len(poses) for poses, _, _ in fasteners)}


def connect_purlins(creation_id, beam_tokens, purlin_tokens, parameters_mm=None, *,
                    allow_bars=False, preview=False, file_id=None):
    """Valide ou crée les plats d’âme et grugeages des abouts appariés."""
    from . import purlin_connections

    design = active_design(creation_id, file_id)
    beams, purlins = (tuple(_entity(design, token, adsk.fusion.Occurrence.cast) for token in tokens)
                     for tokens in (beam_tokens, purlin_tokens))
    batch = purlin_connections.evaluate_batch(design, beams, purlins, parameters_mm, allow_bars=allow_bars)
    report = {"connections": [{"beam": plan.members[0].occurrence.name,
                               "purlin": plan.members[1].occurrence.name, "cope": cope is not None,
                               **_assembly_plan_report(plan.plates, plan.fasteners)}
                              for plan, cope in zip(batch.plans, batch.cope_plans)],
              "cope_count": batch.cope_count, "existing_count": batch.existing_count,
              "unmatched": [{"name": item.name, "token": item.entityToken} for item in batch.unmatched]}
    if not preview:
        groups = purlin_connections.create_batch(design, batch)
        report["created"] = [{"name": group.name, "token": group.entityToken} for group in groups]
    return report


def _brace_profiles(identifiers):
    profiles = profile_catalog.discover_profiles()
    return tuple(_profile(key, profiles).relative_path for key in identifiers)


def _brace_plan_report(brace_bay, plan):
    return {"type": "brace_bay", "profiles": list(plan.profiles), "settings": plan.settings,
            "branches_mm": [[[10 * value for value in point] for point in segment]
                            for segment in brace_bay.preview_segments(plan)],
            **_assembly_plan_report(plan.plates, plan.fasteners)}


def create_brace_bay(creation_id, face_tokens, profiles, settings=None, *, preview=False, file_id=None):
    """Crée le X entre deux faces. Deux sections de cornières, cotes en mm."""
    from . import brace_bay

    design = active_design(creation_id, file_id)
    faces = tuple(_entity(design, token, adsk.fusion.BRepFace.cast) for token in face_tokens)
    plan = brace_bay.evaluate(design, faces, _brace_profiles(profiles), settings or {})
    report = _brace_plan_report(brace_bay, plan)
    if not preview:
        group = brace_bay.create(design, plan)
        report.update(name=group.name, token=group.entityToken)
    return report


def edit_assembly(creation_id, assembly_token, parameters_mm=None, *, alternate=None, profiles=None,
                  preview=False, file_id=None):
    """Modifie les réglages fournis et conserve les autres valeurs enregistrées."""
    from . import assembly_edit, brace_bay

    design = active_design(creation_id, file_id)
    entity = _entity(design, assembly_token, _assembly_selection)
    changes = parameters_mm or {}
    if brace_bay.find_group(entity):
        if alternate is not None:
            raise ValueError("Pour le X, utiliser flip_first ou flip_second dans parameters_mm.")
        group, faces, record = brace_bay.read(design, entity)
        previous = record["settings"]
        settings = {**previous, **changes}
        for key in ("central", "ends"):
            if key in changes:
                settings[key] = {**previous.get(key, {}), **changes[key]}
        sections = record["profiles"] if profiles is None else _brace_profiles(profiles)
        plan = brace_bay.evaluate(design, faces, sections, settings)
        report = _brace_plan_report(brace_bay, plan)
        if not preview:
            group = brace_bay.reconfigure(design, group, plan)
    else:
        if profiles is not None:
            raise ValueError("La modification de l’assemblage ne remplace pas ses profils sources.")
        target = assembly_edit.read(design, entity)
        plan = assembly_edit.evaluate(design, target, {**target.parameters_mm, **changes}, alternate)
        group = target.group
        report = {"type": target.template.key, "parameters_mm": plan.settings_mm, "alternate": plan.alternate,
                  **_assembly_plan_report(plan.plates, plan.fasteners)}
        if not preview:
            result = assembly_edit.apply(design, target, plan)
            if target.template.family != "Pieds de poteau":
                group = result
    return {"name": group.name, "token": group.entityToken, **report}


def copy_assembly(creation_id, assembly_token, target_tokens, *, linked=False, preview=False, file_id=None):
    """Copie un montage du catalogue vers les profils cibles dans l’ordre de ses rôles."""
    from . import assembly_copy

    design = active_design(creation_id, file_id)
    source = _entity(design, assembly_token, _assembly_selection)
    targets = tuple(_entity(design, token, _assembly_selection) for token in target_tokens)
    plan = assembly_copy.prepare(design, source, targets, linked)
    report = {"type": plan.source.template.key, "linked": plan.master is not None,
              "targets": [{"name": item.name, "token": item.entityToken} for item in plan.targets],
              **_assembly_plan_report(plan.assembly.plates, plan.assembly.fasteners)}
    if not preview:
        group = assembly_copy.create(design, plan)
        report.update(name=group.name, token=group.entityToken)
    return report


def remove_assembly(creation_id, assembly_token, *, preview=True, file_id=None):
    """Contrôle le groupe et ses usinages. Passer preview=False pour le supprimer."""
    from ..commands import remove_assembly as command

    design = active_design(creation_id, file_id)
    entity = _entity(design, assembly_token, _assembly_selection)
    group, history = command.target_group(design, entity)
    report = {"name": group.name, "token": group.entityToken, "history": history.name,
              "operations": history.count, "removed": False}
    if not preview:
        command.remove(design, entity)
        report["removed"] = True
    return report


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
                reverse=False, file_id=None, *, head_washer=None, nut_washer=None,
                link_to_hole=False, prepare_countersink=False, preview=False,
                prototype_token=None, prototype_length_mm=None):
    """Calcule ou pose des boulons modélisés, ou reproduit un ensemble modèle."""
    from . import countersink_preparation, fastener_hole_link, timeline_groups

    design = active_design(creation_id, file_id)
    cast_face = adsk.fusion.BRepFace.cast
    head_face = _entity(design, head_support_token, cast_face) if head_support_token is not None else None
    nut_face = _entity(design, nut_support_token, cast_face) if nut_support_token is not None else None
    if prepare_countersink and head != "TF":
        raise ValueError("La préparation d’une fraisure exige une tête fraisée.")

    def cast_hole(entity):
        return cast_face(entity) or adsk.fusion.BRepEdge.cast(entity)

    holes, preparations, sources = [], [], []
    for token in hole_tokens:
        entity = _entity(design, token, cast_hole)
        if head == "TF":
            face = cast_face(entity)
            if face and adsk.core.Cone.cast(face.geometry):
                holes.append(fastener_creator.read_countersink(face))
            elif prepare_countersink:
                preparation = countersink_preparation.plan(entity, head_face, diameter_mm)
                holes.append(preparation.hole)
                preparations.append(preparation)
                continue
            else:
                raise ValueError("Sélectionner une fraisure ou activer la préparation automatique.")
        else:
            holes.append(fastener_creator.read_hole(entity))
        sources.append(entity)
    if preparations:
        head_face = head_face or preparations[0].head_face
        nut_face = nut_face or preparations[0].backing_face
    if not head_face or not nut_face:
        raise ValueError("Choisir les deux faces d’appui extérieures.")
    head_support = fastener_creator.read_support(head_face)
    nut_support = fastener_creator.read_support(nut_face)

    prototype = None
    if prototype_token is not None:
        if prepare_countersink or link_to_hole or head_washer is not None or nut_washer is not None:
            raise ValueError("La copie d’un ensemble existant utilise sa propre composition et des trous préparés.")

        def cast_prototype(entity):
            return adsk.fusion.Occurrence.cast(entity) or adsk.fusion.BRepBody.cast(entity)

        if length_mm is None or prototype_length_mm is None:
            raise ValueError("Préciser la longueur du modèle et celle de la vis à poser.")
        entity = _entity(design, prototype_token, cast_prototype)
        prototype = fastener_creator.read_prototype(entity, diameter_mm, prototype_length_mm)
        occupied = fastener_creator.existing_positions(design.rootComponent, prototype)
        placements, ignored = fastener_geometry.plan_placements(
            holes, head_support, nut_support, prototype.layout, diameter_mm,
            length_mm, head, occupied, reverse,
        )
        length = length_mm
    else:
        occupied = fastener_creator.existing_positions(design.rootComponent)
        _, placements, ignored, length = fastener_geometry.plan_modeled_fasteners(
            holes, head_support, nut_support, diameter_mm, length_mm, projection_mm,
            occupied, reverse, head=head, head_washer=head_washer, nut_washer=nut_washer,
        )
    needed = {pose.countersink for pose in placements}
    pending = {prep.hole: prep for prep in preparations if prep.hole in needed}
    if preview:
        return dict(head=head, length_mm=length, placements=len(placements),
                    occupied=ignored, countersinks_to_prepare=len(pending))

    def bind(pose, occurrence):
        source = fastener_hole_link.source_for_pose(sources, pose, head)
        return fastener_hole_link.bind(design, occurrence, pose, source)

    def create_modeled():
        return simple_fastener_creator.create_modeled_fasteners(
            design, placements, diameter_mm, length, projection_mm, head=head,
            head_washer=head_washer, nut_washer=nut_washer,
            bind_to_hole=bind if link_to_hole else None,
        )

    if prototype:
        result = fastener_creator.create_fasteners(design, prototype, placements, diameter_mm, length, head)
    elif not pending:
        result = create_modeled()
    else:
        start = timeline_groups.creation_start(design.timeline)
        operations = []
        try:
            with timeline_groups.defer_grouping():
                for preparation in pending.values():
                    face, features = countersink_preparation.apply(design, preparation)
                    operations.extend(features)
                    sources.append(face)
                result = create_modeled()
        except Exception as error:
            for operation in reversed(operations):
                if operation.isValid and not operation.deleteMe():
                    raise RuntimeError(f"La pose a échoué et la fraisure n’a pas été retirée : {error}") from error
            raise
        timeline_groups.group_creation(design.timeline, start, "JHR - Fixations tête fraisée")
    result["occupied"] += ignored
    return dict(result, head=head, length_mm=length)


def place_tapped_screw(creation_id, hole_token, head_support_token, diameter_mm,
                       engagement_mm=None, modeled=False, preview=False, file_id=None, *,
                       head_washer=None, length_mm=None, head="H", prepare_countersink=False,
                       link_to_hole=False):
    design = active_design(creation_id, file_id)
    cast = adsk.fusion.BRepFace.cast
    face, support = (_entity(design, token, cast) for token in (hole_token, head_support_token))
    return tapped_fastener.place(
        design, face, support, diameter_mm, engagement_mm, modeled, preview,
        head_washer=head_washer, length_mm=length_mm, head=head,
        prepare_countersink=prepare_countersink, link_to_hole=link_to_hole,
    )


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
                    screw_length_mm=None, screw_stack_mm=0., blind_clearance_mm=None,
                    screw_washer=True, link_to_hole=False):
    design = active_design(creation_id, file_id)
    cast = adsk.fusion.BRepFace.cast
    bore, entry = (_entity(design, token, cast) for token in (bore_token, entry_token))
    return rivet_nut.place(
        design, bore, entry, diameter_mm, head, preview=preview, prepare_hole=prepare_hole,
        screw_head=screw_head, screw_length_mm=screw_length_mm, screw_stack_mm=screw_stack_mm,
        blind_clearance_mm=blind_clearance_mm, screw_washer=screw_washer, link_to_hole=link_to_hole,
    )


def attach_rivet_screw(creation_id, insert_token, *, support_face_token=None, screw_head="CHC",
                       screw_length_mm=None, screw_stack_mm=0., blind_clearance_mm=None,
                       screw_washer=True, preview=False, file_id=None):
    """Ajoute une vis à un insert RIVKLE existant, avec sa rondelle facultative."""
    design = active_design(creation_id, file_id)

    def cast_insert(entity):
        return adsk.fusion.Occurrence.cast(entity) or adsk.fusion.BRepBody.cast(entity)

    insert = _entity(design, insert_token, cast_insert)
    support = (_entity(design, support_face_token, adsk.fusion.BRepFace.cast)
               if support_face_token is not None else None)
    return rivet_nut.attach_screw(
        design, insert, support_face=support, screw_head=screw_head,
        screw_length_mm=screw_length_mm, screw_stack_mm=screw_stack_mm,
        blind_clearance_mm=blind_clearance_mm, screw_washer=screw_washer, preview=preview,
    )
