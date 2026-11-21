"""Remplacement de section dans le balayage existant, avec contrôle des raccords."""

import json
import math
from pathlib import PurePosixPath
import re

import adsk.fusion as fusion

from . import assembly_catalog, assembly_edit, assembly_geometry, assembly_operations as assemblies
from . import joint_builder as joints, member_builder, member_metadata, rotation


def attachments(design, occurrence):
    """Retourne les définitions d'assemblage qui utilisent exactement cette barre."""
    results = []
    for marker in design.findAttributes(assemblies.ATTRIBUTE_GROUP, "definition"):
        record = json.loads(marker.value)
        for index, token in enumerate(record["members"]):
            if any(entity == occurrence for entity in design.findEntityByToken(token)):
                group = next((candidate for candidate in design.rootComponent.occurrences
                              if candidate.component == marker.parent), None)
                if group:
                    results.append((marker, group, record, index))
    return results


def _link(record):
    return record.get("shear_link") or record.get("end_plate_link") or record.get("splice_link")


def _validate_assembly(design, group, record):
    template = assembly_catalog.template_for(record["kind"])
    members = []
    for token, role in zip(record["members"], template.roles):
        occurrences = [occurrence for entity in design.findEntityByToken(token)
                       if (occurrence := fusion.Occurrence.cast(entity)) and occurrence.isValid]
        if len(occurrences) != 1:
            raise ValueError(f"Profil {role} introuvable dans {group.component.name}.")
        members.append(assemblies._member(design, occurrences[0], role))
    if "base_end_index" in record:
        stored = assembly_catalog.recorded_parameters(template, record["parameters_mm"])
        dims = assembly_geometry.dimensions(template, stored)
        plates = assemblies._base(members[0], dims, record["base_end_index"], template.key,
                                  include_anchor_hardware=bool(record.get("base_anchor_hardware")),
                                  flush_to_skeleton=bool(record.get("base_flush")))
        matches = assemblies._plates_match(group, plates)
    else:
        matches = assemblies._linked_raccord_matches(design, group, record, template, members, _link(record))
    if not matches:
        raise ValueError(f"Le nouveau profil demande de modifier {group.component.name}.")
    return [assemblies._reference_state(member) for member in members]


def replace_section(design, occurrence, profile, *, placement=None):
    """Change la section en conservant les autres réglages des appels existants."""
    if not occurrence or not occurrence.isValid:
        raise ValueError("Sélectionner un profil JHR valide.")
    metadata = joints._member_metadata(occurrence, "à modifier")
    if placement:
        anchor, radians, flip_x, flip_y, material_id = placement
        if (anchor != metadata.anchor or abs(math.degrees(radians)-metadata.rotation_deg) > 1e-6
                or (flip_x, flip_y, material_id) != (metadata.flip_x, metadata.flip_y, metadata.material_id)):
            raise ValueError("Le changement de section liée conserve l’ancrage, l’orientation et le matériau.")
    return edit_member(
        design, occurrence, profile, metadata.anchor, math.radians(metadata.rotation_deg),
        metadata.flip_x, metadata.flip_y,
    )


def edit_member(design, occurrence, profile, anchor, radians, flip_x, flip_y, *,
                physical_material=None, material_choice=None, role=None):
    """Modifie la section du balayage et conserve l’occurrence ainsi que son chemin."""
    if (not occurrence or not occurrence.isValid or occurrence not in design.rootComponent.occurrences
            or design.timeline.markerPosition != design.timeline.count):
        raise ValueError("Sélectionner un profil JHR à la racine avec l’historique en fin de conception.")
    metadata = joints._member_metadata(occurrence, "à modifier")
    section_changed = metadata.profile_source.casefold() != profile.relative_path.casefold()
    geometry_changed = (
        section_changed or metadata.anchor != anchor or abs(math.degrees(radians) - metadata.rotation_deg) > 1e-6
        or (metadata.flip_x, metadata.flip_y) != (flip_x, flip_y)
    )
    component = occurrence.component
    previous_role = member_metadata.role_for(component)
    role = previous_role if role is None else role
    if role not in member_metadata.ROLES:
        raise ValueError("La fonction de profil JHR est inconnue.")
    role_changed = role != previous_role
    body = joints._single_body(occurrence, "à modifier")
    material = body.material
    material_changed = physical_material is not None and physical_material != material
    if not geometry_changed and not material_changed and not role_changed:
        return {"changed": False, "assemblies": 0}
    if design.rootComponent.allOccurrencesByComponent(component).count != 1:
        raise ValueError("Cette définition de profil est utilisée par plusieurs occurrences.")
    if material_changed and (not physical_material.isValid or material_choice is None):
        raise ValueError("Le matériau choisi est indisponible.")
    used = attachments(design, occurrence) if geometry_changed else ()
    revisions = []
    for _, group, record, _ in used:
        if "base_end_index" not in record and not _link(record):
            raise ValueError(f"{group.component.name} nécessite une reprise spécifique avant cette modification.")
        if assemblies.inspect_references(design, group)["status"] != "à_jour":
            raise ValueError(f"Revoir {group.component.name} avant de modifier le profil.")
        revisions.append(assembly_edit.prepare_refresh(design, group) if "base_end_index" in record else None)

    timeline = design.timeline
    collapsed = False
    new_sketch = None
    profile_switched = False
    material_assigned = False
    metadata_backup = {}
    records_backup = []
    foot_journals = []
    name_backup = []
    original_sketches = None
    new_values = {member_metadata.ROLE_ATTRIBUTE: role} if role_changed else {}
    try:
        if geometry_changed:
            sweep = component.features.sweepFeatures.itemByName("BARRE_CENTREE_SUR_CHEMIN")
            plane = component.constructionPlanes.itemByName("PLAN_PROFIL_MILIEU")
            if not sweep or not sweep.isParametric or not plane:
                raise ValueError("Le balayage paramétrique et son plan de section sont introuvables.")
            curve = joints._linked_curve(design, metadata, "à modifier", allow_arc=True)
            healthy = [(feature, feature.name) for feature in component.features
                       if feature.healthState == fusion.FeatureHealthStates.HealthyFeatureHealthState]
            owner = sweep.timelineObject.parentGroup
            collapsed = owner.isCollapsed if owner else False
            original = sweep.profile
            if collapsed:
                owner.isCollapsed = False
            if not sweep.timelineObject.rollTo(True):
                raise RuntimeError("Impossible d’insérer la section avant le balayage.")
            original_sketches = list(component.sketches)
            new_sketch, section = member_builder._import_profile_sketch(
                component, plane, curve, profile, anchor, radians, flip_x, flip_y,
            )
            sweep.profile = section
            profile_switched = True
            new_sketch.isVisible = False
            timeline.moveToEnd()
            if sweep.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
                raise RuntimeError(sweep.errorOrWarningMessage or "La nouvelle section ne se balaie pas.")
            for feature, name in healthy:
                if not feature.isValid or feature.healthState != fusion.FeatureHealthStates.HealthyFeatureHealthState:
                    raise ValueError(f"Le nouveau profil invalide la fonction {name}.")
            body = joints._single_body(occurrence, "modifiée")
            new_values.update(
                profile=profile.designation, profile_category=profile.category_id,
                profile_region=profile.region_id, profile_family=profile.family_id,
                profile_source=profile.relative_path, anchor=anchor, rotation_deg=rotation.format_degrees(radians),
                flip_x=str(flip_x).lower(), flip_y=str(flip_y).lower(),
            )

        if material_changed:
            body.material = physical_material
            material_assigned = True
            assigned = body.material
            properties = assigned.materialProperties if assigned else None
            if not properties or properties.count < 1 or assigned.name != physical_material.name:
                raise RuntimeError("Fusion n’a pas conservé le matériau choisi.")
            new_values.update(
                material_name=assigned.name, material_id=assigned.id,
                material_library_name=material_choice.library_name,
                material_library_id=material_choice.library_id,
                material_source_id=material_choice.material_id,
                material_property_count=str(properties.count),
            )
        elif material and (not body.material or body.material.id != material.id):
            raise RuntimeError("Le remplacement n’a pas conservé le matériau du solide.")
        if not body.isSolid:
            raise RuntimeError("Le profil modifié ne forme pas un solide.")

        attributes = component.attributes
        for key, value in new_values.items():
            current = attributes.itemByName(member_metadata.ATTRIBUTE_GROUP, key)
            if not current or current.value != value:
                metadata_backup[key] = current.value if current else None
                attributes.add(member_metadata.ATTRIBUTE_GROUP, key, value)
        for (marker, group, record, _), revision in zip(used, revisions):
            if revision is not None:
                foot_journals.append(assembly_edit.refresh(design, revision))
            else:
                states = _validate_assembly(design, group, record)
                records_backup.append((marker, marker.value))
                record["reference_state"] = states
                marker.value = json.dumps(record)
        if section_changed or role_changed:
            _rename_catalogue_profile(design, occurrence, body, metadata, profile, role, name_backup)
    except Exception:
        try:
            for journal in reversed(foot_journals):
                journal.rollback()
            for entity, name in reversed(name_backup):
                entity.name = name
            for marker, value in records_backup:
                marker.value = value
            for key, value in metadata_backup.items():
                item = component.attributes.itemByName(member_metadata.ATTRIBUTE_GROUP, key)
                if value is None:
                    if item:
                        item.deleteMe()
                else:
                    component.attributes.add(member_metadata.ATTRIBUTE_GROUP, key, value)
            if material_assigned and material:
                body.material = material
            if original_sketches is not None:
                if not sweep.timelineObject.rollTo(True):
                    raise RuntimeError("Impossible de revenir au balayage d’origine.")
                if profile_switched:
                    sweep.profile = original
                for sketch in reversed(list(component.sketches)):
                    if sketch not in original_sketches and sketch.isValid:
                        sketch.deleteMe()
        finally:
            timeline.moveToEnd()
        raise
    finally:
        if collapsed:
            current_group = occurrence.timelineObject.parentGroup
            if current_group and current_group.isValid:
                current_group.isCollapsed = True
        if geometry_changed:
            timeline.moveToEnd()
    return {"changed": True, "assemblies": len(used)}


def _rename_catalogue_profile(design, occurrence, body, metadata, profile, role, backup):
    """Actualise les noms générés par JHR, avec conservation des noms personnalisés."""
    component = occurrence.component
    previous_token = re.sub(r"[^A-Z0-9]+", "", PurePosixPath(metadata.profile_source).stem.upper())
    match = re.fullmatch(rf"(?:BARRE|POTEAU|POUTRE|PANNE)_{previous_token}_(\d+)", component.name)
    if match:
        new_name = f"{role}_{profile.component_token}_{match.group(1)}"
        if any(other.component.name == new_name and other.component != component
               for other in design.rootComponent.allOccurrences):
            new_name = member_builder._next_component_name(design.rootComponent, profile, role)
        previous_entity = occurrence.entityToken
        backup.append((component, component.name))
        component.name = new_name
        if not any(candidate == occurrence for candidate in design.findEntityByToken(previous_entity)):
            raise RuntimeError("Fusion n’a pas conservé la référence au profil renommé.")
    if previous_token != profile.component_token and body.name == f"CORPS_{previous_token}":
        backup.append((body, body.name))
        body.name = f"CORPS_{profile.component_token}"
