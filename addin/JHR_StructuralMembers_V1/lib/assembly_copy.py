"""Copies d’assemblages et partage facultatif de leurs réglages."""

from dataclasses import dataclass
import json

import adsk.fusion as fusion

from . import angle_cleat_copy, assembly_catalog, assembly_edit, assembly_operations as assemblies, brace_bay
from . import joint_geometry as geo


SOURCE_ATTRIBUTE = "base_copy_source"
BAY_TEMPLATE = assembly_catalog.Template("brace_bay", "Contreventements", "Auto-contreventement",
                                        ("Première face d’appui", "Deuxième face d’appui"), ())


@dataclass(frozen=True)
class CopyPlan:
    source: assembly_edit.EditTarget
    targets: tuple
    assembly: assemblies.AssemblyPlan
    master: assembly_edit.EditTarget | None = None

    @property
    def target(self):
        return self.targets[0]


@dataclass
class LinkedEdit:
    journals: list

    def rollback(self):
        errors = []
        for journal in reversed(self.journals):
            try:
                journal.rollback()
            except Exception as error:
                errors.append(str(error))
        self.journals.clear()
        if errors:
            raise RuntimeError("Restauration des pieds liés incomplète : " + " · ".join(errors))


def _occurrences_from_token(design, token):
    return [occurrence for entity in (design.findEntityByToken(token) or ())
            if (occurrence := fusion.Occurrence.cast(entity)) and occurrence.isValid]


def _master_group(design, group):
    """Suit le jeton de la source même si le groupe est renommé."""
    visited = []
    while True:
        if group in visited:
            raise ValueError("La liaison des assemblages forme une boucle.")
        visited.append(group)
        marker = group.component.attributes.itemByName(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE)
        if not marker:
            return group
        matches = _occurrences_from_token(design, marker.value)
        if not matches:
            # Une copie garde ses réglages lorsque sa source est supprimée.
            return group
        if len(matches) != 1:
            raise ValueError("L’assemblage source de cette copie est ambigu.")
        group = matches[0]


def _check_free_end(design, plan):
    member = plan.members[0]
    plate = plan.plates[0]
    outward = geo.scale(plate.normal, -1) if plan.base_flush else plate.normal
    end = assemblies._base_end_index(member, outward)
    for marker in design.findAttributes(assemblies.ATTRIBUTE_GROUP, "definition"):
        record = json.loads(marker.value)
        if not record["kind"].startswith("base_"):
            continue
        if member.occurrence not in _occurrences_from_token(design, record["members"][0]):
            continue
        old_end = record.get("base_end_index")
        if old_end == end or (old_end is None and
                              abs(geo.dot(geo.subtract(record["origin"], plate.origin), outward)) < assemblies.TOL):
            raise ValueError("Le poteau cible possède déjà une platine à cette extrémité.")


def can_link(source):
    return source.writable


def read_source(design, source_entity):
    if brace_bay.find_group(source_entity):
        return _read_bay(design, source_entity)
    if angle_cleat_copy.find_group(source_entity):
        return angle_cleat_copy.read(design, source_entity)
    return assembly_edit.read(design, source_entity)


def prepare(design, source_entity, target_entity, linked=False):
    """Prépare le même montage sur des profils ordonnés selon les rôles du catalogue."""
    source = read_source(design, source_entity)
    is_base = source.template.family == "Pieds de poteau"
    if linked and not can_link(source):
        raise ValueError(source.reason or "Les réglages de cet assemblage ne peuvent pas être liés.")
    entities = tuple(target_entity) if isinstance(target_entity, (tuple, list)) else (target_entity,)
    if len(entities) != len(source.template.roles):
        raise ValueError("Sélectionner les profils cibles dans l’ordre indiqué.")
    targets = []
    for entity, role in zip(entities, source.template.roles):
        if source.template.key == "brace_bay":
            target = fusion.BRepFace.cast(entity)
            if not target or not target.isValid or not target.assemblyContext:
                raise ValueError(f"{role} cible : sélectionner une face d’un profil JHR.")
        else:
            target = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
            if not target or not target.isValid or target not in design.rootComponent.occurrences:
                raise ValueError(f"{role} cible : sélectionner un profil JHR à la racine de la conception.")
        if target in targets:
            raise ValueError("Sélectionner un profil différent pour chaque rôle.")
        targets.append(target)
    if all(target in source.occurrences for target in targets):
        notice = ("Sélectionner un autre poteau pour la copie." if is_base
                  else "Sélectionner au moins un profil différent de l’assemblage source.")
        raise ValueError(notice)
    master = None
    settings = source.parameters_mm
    alternate = source.alternate
    if linked:
        master = read_source(design, _master_group(design, source.group))
        if all(target in master.occurrences for target in targets):
            raise ValueError("Sélectionner au moins un profil différent de l’assemblage maître.")
        if master.template.key != source.template.key or not can_link(master):
            raise ValueError("Les réglages de cet assemblage source ne peuvent pas être liés à une copie.")
        settings = master.parameters_mm
        alternate = master.alternate
    targets = tuple(targets)
    assembly = _plan_on_targets(design, source, targets, settings, alternate)
    if is_base:
        _check_free_end(design, assembly)
    return CopyPlan(source, targets, assembly, master)


def _plan_on_targets(design, source, targets, settings, alternate):
    if source.template.key == "brace_bay":
        brace_bay.check_free_faces(design, targets)
        return _bay_plan(design, targets, settings)
    if angle_cleat_copy.find_group(source.group):
        return angle_cleat_copy.evaluate(design, source, targets, settings)
    if _is_purlin_connection(source):
        batch = _purlin_batch(design, source, targets, settings, alternate)
        return batch.plans[0]
    return assemblies.evaluate(design, source.template.key, targets, settings, alternate)


def _is_purlin_connection(source):
    if source.template.key != "shear_plate":
        return False
    record = json.loads(source.original)
    return bool(record.get("purlin_connection") or record.get("joint_records"))


def _purlin_batch(design, source, targets, settings, alternate):
    from . import purlin_connections

    beam, purlin = targets
    clearances = json.loads(source.original).get("cope_clearances_cm")
    batch = purlin_connections.evaluate_batch(design, (beam,), (purlin,), settings, allow_bars=True,
                                              alternate=alternate, cope_clearances_cm=clearances)
    if len(batch.plans) != 1:
        raise ValueError("Impossible de créer un nouveau raccord sur ce couple poutre-panne.")
    return batch


def create(design, plan):
    """Crée le montage cible dans la transaction Fusion courante."""
    plan = prepare(design, plan.source.group, plan.targets, linked=plan.master is not None)
    if plan.source.template.key == "brace_bay":
        group = brace_bay.create(design, plan.assembly)
    elif angle_cleat_copy.find_group(plan.source.group):
        group = angle_cleat_copy.create_copy(design, plan.assembly)
    elif _is_purlin_connection(plan.source):
        from . import purlin_connections

        batch = _purlin_batch(design, plan.source, plan.targets, plan.assembly.settings_mm, plan.assembly.alternate)
        group, = purlin_connections.create_batch(design, batch)
    else:
        group = assemblies.create(design, plan.assembly)
    if plan.master is not None:
        try:
            attribute = group.component.attributes.add(
                assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE, plan.master.group.entityToken,
            )
            if not attribute:
                raise RuntimeError("La liaison des réglages de la copie n’a pas pu être enregistrée.")
        except Exception:
            from ..commands.remove_assembly import remove

            if plan.source.template.key == "brace_bay":
                brace_bay.remove(design, group)
            else:
                remove(design, group)
            raise
    return group


def _linked_groups(design, master):
    for marker in design.findAttributes(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE):
        # Les nouveaux liens pointent directement vers le maître. Comparer les
        # occurrences résolues puisque le texte du jeton peut changer.
        if master not in _occurrences_from_token(design, marker.value):
            continue
        copies = [item for item in design.rootComponent.occurrences if item.component == marker.parent]
        if len(copies) != 1 or copies[0] == master:
            raise ValueError("Une copie liée n’est plus identifiable dans la conception.")
        yield copies[0]


def rebuild_linked(design, target, plan):
    return _rebuild_settings(design, target, plan, (plan.settings_mm, plan.alternate),
                             assembly_edit.read, assembly_edit.evaluate, assembly_edit._rebuild)


def _write_link(group, token):
    if not group.component.attributes.add(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE, token):
        raise RuntimeError(f"{group.name} : impossible de rétablir le lien vers l’assemblage source.")


def target_name(entity):
    return entity.name if hasattr(entity, "name") else entity.assemblyContext.name


def _rebuild_settings(design, target, plan, recipe, read, evaluate, rebuild):
    if recipe == (target.parameters_mm, target.alternate):
        return target.group
    master_group = _master_group(design, target.group)
    master = target if master_group == target.group else read(design, master_group)
    copies = list(_linked_groups(design, master_group))
    changes = [(master, plan if master.group == target.group else
                evaluate(design, master, *recipe))]
    for group in copies:
        copy = read(design, group)
        if not copy.writable or copy.template.key != master.template.key:
            raise ValueError(f"{group.name} : {copy.reason or 'le type de montage est différent de la source.'}")
        try:
            changes.append((copy, plan if group == target.group else
                            evaluate(design, copy, *recipe)))
        except (ValueError, RuntimeError, FileNotFoundError) as error:
            raise ValueError(f"{group.name} : {error}") from error

    result = None
    for original, updated in changes:
        is_requested = original.group == target.group
        group = rebuild(design, original, updated)
        if original is master:
            token = group.entityToken
        else:
            _write_link(group, token)
        if is_requested:
            result = group
    return result


def _read_bay(design, entity):
    group, faces, record = brace_bay.read(design, entity)
    reason = ""
    try:
        brace_bay.target_group(design, group)
    except (ValueError, RuntimeError) as error:
        reason = str(error)
    settings = {**record["settings"], "profiles": tuple(record["profiles"])}
    return assembly_edit.EditTarget(group, BAY_TEMPLATE, faces, settings, False, not reason, reason, "")


def _bay_plan(design, faces, recipe):
    return brace_bay.evaluate(design, faces, recipe["profiles"],
                              {key: value for key, value in recipe.items() if key != "profiles"})


def reconfigure_bay(design, group, plan):
    target = _read_bay(design, group)
    if not target.writable:
        raise ValueError(target.reason)
    settings = {**plan.settings, "profiles": tuple(plan.profiles)}
    marker = group.component.attributes.itemByName(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE)
    copies = tuple(_linked_groups(design, group))
    if not marker and not copies:
        return brace_bay.reconfigure(design, group, plan)
    if settings == target.parameters_mm:
        token = marker.value if marker else None
        updated = brace_bay.reconfigure(design, group, plan, allow_earlier=True)
        if token:
            _write_link(updated, token)
        for copy in copies:
            _write_link(copy, updated.entityToken)
        return updated

    def evaluate(design, target, values, _alternate):
        proposal = _bay_plan(design, target.occurrences, values)
        brace_bay.prepare_edit(design, target.group, proposal, allow_earlier=True)
        return proposal

    def rebuild(design, target, proposal):
        return brace_bay.reconfigure(design, target.group, proposal, allow_earlier=True)

    brace_bay.prepare_edit(design, group, plan, allow_earlier=True)
    return _rebuild_settings(design, target, plan, (settings, False), _read_bay, evaluate, rebuild)


def apply_master_settings(design, revision, plan):
    """Applique les réglages à tous les pieds liés, avec annulation groupée."""
    if plan.settings_mm == revision.plan.settings_mm and plan.alternate == revision.plan.alternate:
        return LinkedEdit([assembly_edit._apply(design, revision, plan)])
    current = revision.target.group
    master = _master_group(design, current)
    if master != current:
        revision = assembly_edit.prepare_refresh(design, master)
        plan = assembly_edit.evaluate(design, revision.target, plan.settings_mm)
    assembly_edit._check_piece_layout(revision.plan.plates, plan.plates)
    changes = [(revision, plan)]
    for group in _linked_groups(design, master):
        try:
            copy = assembly_edit.prepare_refresh(design, group)
            if copy.target.template.key != revision.target.template.key:
                raise ValueError("Le type du pied lié ne correspond plus au pied source.")
            update = assembly_edit.evaluate(design, copy.target, plan.settings_mm)
            assembly_edit._check_piece_layout(copy.plan.plates, update.plates)
        except (ValueError, RuntimeError, FileNotFoundError) as error:
            raise ValueError(f"{group.component.name} : {error}") from error
        changes.append((copy, update))

    journal = LinkedEdit([])
    try:
        for change, prepared in changes:
            journal.journals.append(assembly_edit._apply(design, change, prepared))
        attributes = master.component.attributes
        orphan = attributes.itemByName(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE)
        if (orphan and not _occurrences_from_token(design, orphan.value)
                and revision.plan.settings_mm != plan.settings_mm):
            token = orphan.value
            if not orphan.deleteMe():
                raise RuntimeError("Impossible de détacher le pied de sa source supprimée.")
            journal.journals[0].undo.append(
                lambda: _restore_source_link(attributes, token),
            )
    except Exception:
        journal.rollback()
        raise
    return journal


def _restore_source_link(attributes, token):
    if not attributes.add(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE, token):
        raise RuntimeError("Impossible de restaurer la liaison au pied source.")
