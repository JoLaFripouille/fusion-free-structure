"""Retire un assemblage JHR via son groupe d’historique Fusion."""

import html
import json

import adsk.core as core
import adsk.fusion as fusion

from .inspect_assembly import _assembly
from ..lib import addin_info, angle_cleat_creator, assembly_operations, brace_bay, joint_records, ui_layout


COMMAND_ID = "EI_JHR_RemoveAssembly"
COMMAND_NAME = "Supprimer un assemblage"
_handlers = []


def _find_assembly(entity):
    try:
        return _assembly(entity)
    except ValueError:
        occurrence = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
        while occurrence:
            marker = occurrence.component.attributes.itemByName(
                angle_cleat_creator.ATTRIBUTE_GROUP, "assembly_index",
            )
            if marker:
                return occurrence
            occurrence = occurrence.assemblyContext
        raise ValueError("Sélectionner l’assemblage JHR ou l’une de ses pièces.") from None


def _belongs_to(occurrence, assembly):
    while occurrence:
        if occurrence == assembly:
            return True
        occurrence = occurrence.assemblyContext
    return False


def _definition(assembly):
    attributes = assembly.component.attributes
    marker = (attributes.itemByName(assembly_operations.ATTRIBUTE_GROUP, "definition")
              or attributes.itemByName(angle_cleat_creator.ATTRIBUTE_GROUP, "definition"))
    return json.loads(marker.value) if marker else {}


def _source_components(design, assembly):
    definition = _definition(assembly)
    if definition:
        return [
            occurrence.component for token in definition["members"]
            for entity in (design.findEntityByToken(token) or ())
            if (occurrence := fusion.Occurrence.cast(entity))
        ]
    names = set()
    for child in assembly.childOccurrences:
        for key in ("primary_component", "secondary_component"):
            value = child.component.attributes.itemByName(angle_cleat_creator.ATTRIBUTE_GROUP, key)
            if value:
                names.add(value.value)
    return [occ.component for occ in design.rootComponent.occurrences if occ.component.name in names]


def _joint_markers(design, assembly):
    markers = []
    for record in _definition(assembly).get("joint_records", ()):
        matches = [
            occurrence for item in (design.findEntityByToken(record["member"]) or ())
            if (occurrence := fusion.Occurrence.cast(item)) and occurrence.isValid
        ]
        if len(matches) != 1:
            raise ValueError("Le profil qui porte la trace de grugeage est introuvable ou ambigu.")
        marker = matches[0].component.attributes.itemByName(joint_records.ATTRIBUTE_GROUP, record["name"])
        if marker:
            markers.append(marker)
    return markers


def target_group(design, entity):
    """Identifie le groupe d’historique et contrôle son périmètre sans le modifier."""
    if not design:
        raise ValueError("Ouvrir une conception Fusion.")
    if brace_bay.find_group(entity):
        return brace_bay.target_group(design, entity)
    assembly = _find_assembly(entity)
    root = design.rootComponent
    if assembly not in root.occurrences or root.allOccurrencesByComponent(assembly.component).count != 1:
        raise ValueError("L’assemblage est imbriqué ou sa définition est utilisée plusieurs fois.")
    history = assembly.timelineObject
    group = history.parentGroup if history else None
    if not group or not group.isValid or group.name != assembly.component.name:
        raise ValueError("Le groupe d’historique de cet assemblage est introuvable ou a été renommé.")
    if any(occ != assembly and occ.timelineObject and occ.timelineObject.parentGroup == group
           for occ in root.occurrences):
        raise ValueError("Le groupe d’historique contient un autre composant racine.")
    assembly_components = [assembly.component]
    assembly_components.extend(occ.component for occ in assembly.component.allOccurrences)
    allowed_owners = [root, *assembly_components, *_source_components(design, assembly)]
    for i in range(group.count):
        item = group.item(i).entity
        occurrence = fusion.Occurrence.cast(item) if item else None
        if occurrence and occurrence.component not in assembly_components and not _belongs_to(occurrence, assembly):
            raise ValueError("Le groupe contient une occurrence extérieure à l’assemblage.")
        owner = getattr(item, "parentComponent", None)
        if owner and owner not in allowed_owners:
            raise ValueError(f"Le groupe contient une opération dans le composant {owner.name}.")
    return assembly, group


def remove(design, entity):
    """Supprime le groupe vérifié dans la transaction de la commande Fusion."""
    if design and brace_bay.find_group(entity):
        return brace_bay.remove(design, entity)
    assembly, group = target_group(design, entity)
    timeline = design.timeline
    if timeline.markerPosition != timeline.count:
        raise ValueError("Placer le marqueur en fin d’historique avant la suppression.")
    markers = _joint_markers(design, assembly)
    other_occurrences = [occ for occ in design.rootComponent.occurrences if occ != assembly]
    was_collapsed = group.isCollapsed
    if not was_collapsed:
        group.isCollapsed = True
    try:
        if group.index < 0:
            raise RuntimeError("Fusion n’a pas identifié la position du groupe dans l’historique.")
        later = [timeline.item(i) for i in range(group.index + 1, timeline.count)]
        positions = set(_definition(assembly).get("position_snapshots", ()))
        owned = {}
        preserved = []
        for item in later:
            snapshot = fusion.Snapshot.cast(item.entity) if positions and item.name in positions else None
            if not snapshot:
                preserved.append(item)
                continue
            if snapshot.name in owned:
                raise ValueError("Deux captures de position portent le même nom.")
            owned[snapshot.name] = snapshot
        if not group.deleteMe(True) or assembly.isValid:
            raise RuntimeError("Fusion n’a pas supprimé complètement le groupe sélectionné.")
        for snapshot in owned.values():
            if snapshot.isValid and not snapshot.deleteMe():
                raise RuntimeError("Fusion n’a pas supprimé la position capturée de cet assemblage.")
        if any(not occurrence.isValid for occurrence in other_occurrences):
            raise RuntimeError("La suppression toucherait un autre composant de la conception.")
        if any(not item.isValid for item in preserved):
            raise RuntimeError("La suppression toucherait aussi une opération ultérieure.")
        for marker in markers:
            if marker.isValid and not marker.deleteMe():
                raise RuntimeError("Fusion n’a pas effacé la trace du grugeage supprimé.")
    finally:
        if not was_collapsed and group.isValid:
            group.isCollapsed = False


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, selection, report):
        super().__init__()
        self.selection, self.report = selection, report

    def notify(self, event):
        args = core.ValidateInputsEventArgs.cast(event)
        args.areInputsValid = False
        if self.selection.selectionCount != 1:
            self.report.formattedText = "Sélectionner le montage ou l’une de ses pièces."
            return
        try:
            design = fusion.Design.cast(core.Application.get().activeProduct)
            assembly, _ = target_group(design, self.selection.selection(0).entity)
            self.report.formattedText = html.escape(assembly.component.name)
            args.areInputsValid = True
        except (ValueError, RuntimeError) as error:
            self.report.formattedText = html.escape(str(error))


class Execute(core.CommandEventHandler):
    def __init__(self, selection, design, document):
        super().__init__()
        self.selection, self.design, self.document = selection, design, document

    def notify(self, event):
        args = core.CommandEventArgs.cast(event)
        try:
            if core.Application.get().activeDocument != self.document:
                raise ValueError("La conception active a changé.")
            remove(self.design, self.selection.selection(0).entity)
        except Exception as error:
            args.executeFailed = True
            args.executeFailedMessage = str(error)
            core.Application.get().userInterface.messageBox(str(error), COMMAND_NAME)


class Destroyed(core.CommandEventHandler):
    def __init__(self, handlers):
        super().__init__()
        self.handlers = handlers

    def notify(self, _event):
        _handlers.remove(self.handlers)


class Created(core.CommandCreatedEventHandler):
    def notify(self, event):
        command = core.CommandCreatedEventArgs.cast(event).command
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.okButtonText = "Supprimer"
        inputs = command.commandInputs
        selection = inputs.addSelectionInput("assembly", "Assemblage", "Choisir le montage ou une pièce.")
        for kind in ("Occurrences", "SolidBodies", "Faces"):
            selection.addSelectionFilter(kind)
        selection.setSelectionLimits(1, 1)
        report = inputs.addTextBoxCommandInput("target", "", "Sélectionner le montage ou l’une de ses pièces.", 3, True)
        report.isFullWidth = True
        app = core.Application.get()
        design = fusion.Design.cast(app.activeProduct)
        handlers = [
            (command.validateInputs, Validate(selection, report)),
            (command.execute, Execute(selection, design, app.activeDocument)),
        ]
        handlers.append((command.destroy, Destroyed(handlers)))
        for command_event, handler in handlers:
            command_event.add(handler)
        _handlers.append(handlers)


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, COMMAND_NAME, "Supprimer le groupe d’historique d’un assemblage JHR.",
        addin_info.ribbon_icon("supprimer_assemblage"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    ui_layout.panel(ui, ui_layout.MODIFY_PANEL_ID).controls.addCommand(definition).isPromoted = True


def stop():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, ui_layout.MODIFY_PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
