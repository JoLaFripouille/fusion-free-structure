"""Copies des assemblages du catalogue, avec liaison facultative des pieds."""

from dataclasses import dataclass
import json

import adsk.fusion as fusion

from . import assembly_edit, assembly_operations as assemblies, joint_geometry as geo


SOURCE_ATTRIBUTE = "base_copy_source"


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
            raise ValueError("La liaison des pieds de poteau forme une boucle.")
        visited.append(group)
        marker = group.component.attributes.itemByName(assemblies.ATTRIBUTE_GROUP, SOURCE_ATTRIBUTE)
        if not marker:
            return group
        matches = _occurrences_from_token(design, marker.value)
        if not matches:
            # La suppression du maître laisse chaque pied complet et éditable.
            return group
        if len(matches) != 1:
            raise ValueError("Le pied source de cette copie est ambigu.")
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
    """Les pieds sont les seuls montages dont la copie suit les réglages du maître."""
    return source.template.family == "Pieds de poteau" and source.writable


def read_source(design, source_entity):
    return assembly_edit.read(design, source_entity)


def prepare(design, source_entity, target_entity, linked=False):
    """Prépare le même montage sur des profils ordonnés selon les rôles du catalogue."""
    source = read_source(design, source_entity)
    is_base = source.template.family == "Pieds de poteau"
    if linked and not is_base:
        raise ValueError("La copie liée est disponible uniquement pour les pieds de poteau.")
    entities = tuple(target_entity) if isinstance(target_entity, (tuple, list)) else (target_entity,)
    if len(entities) != len(source.template.roles):
        raise ValueError("Sélectionner les profils cibles dans l’ordre indiqué.")
    targets = []
    for entity, role in zip(entities, source.template.roles):
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
    if linked:
        master = assembly_edit.read(design, _master_group(design, source.group))
        if targets[0] in master.occurrences:
            raise ValueError("Le pied source et la copie liée doivent être sur des poteaux différents.")
        if master.template.key != source.template.key or not can_link(master):
            raise ValueError("Les réglages de ce pied source ne peuvent pas être liés à une copie.")
        settings = master.parameters_mm
    targets = tuple(targets)
    assembly = assemblies.evaluate(design, source.template.key, targets, settings, source.alternate)
    if is_base:
        _check_free_end(design, assembly)
    return CopyPlan(source, targets, assembly, master)


def create(design, plan):
    """Crée le montage cible dans la transaction Fusion courante."""
    plan = prepare(design, plan.source.group, plan.targets, linked=plan.master is not None)
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
