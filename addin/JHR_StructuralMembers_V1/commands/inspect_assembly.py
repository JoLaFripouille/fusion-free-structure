"""Consulte l'état d'un assemblage à platines depuis le ruban."""

import html

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, assembly_operations, ui_layout


COMMAND_ID = "EI_JHR_InspectPlateAssembly"
PANEL_ID = ui_layout.MODIFY_PANEL_ID
_handlers = []


def _assembly(entity):
    occurrence = fusion.Occurrence.cast(entity) or getattr(entity, "assemblyContext", None)
    while occurrence:
        if occurrence.component.attributes.itemByName(assembly_operations.ATTRIBUTE_GROUP, "definition"):
            return occurrence
        occurrence = occurrence.assemblyContext
    raise ValueError("Sélectionner un assemblage à platines JHR ou l’une de ses tôles.")


def _report(design, entity):
    assembly = _assembly(entity)
    result = assembly_operations.inspect_references(design, assembly)
    status = {
        "à_jour": "À jour",
        "à_revoir": "À revoir",
        "historique_sans_relevé": "Historique sans relevé",
    }[result["status"]]
    rows = [f"<b>{html.escape(assembly.component.name)}</b><br>{status}"]
    rows.extend(html.escape(f"{change['role']} – {change['cause'].replace('_', ' ')}")
                for change in result.get("changes", ()))
    return "<br>".join(rows)


class Changed(core.InputChangedEventHandler):
    def __init__(self, design):
        super().__init__()
        self.design = design

    def notify(self, args):
        event = core.InputChangedEventArgs.cast(args)
        selection = event.inputs.itemById("assembly")
        report = event.inputs.itemById("report")
        if event.input != selection:
            return
        if selection.selectionCount != 1:
            report.formattedText = "Sélectionner un assemblage à platines JHR."
            return
        try:
            report.formattedText = _report(self.design, selection.selection(0).entity)
        except (ValueError, RuntimeError) as error:
            report.formattedText = html.escape(str(error))


class Destroyed(core.CommandEventHandler):
    def __init__(self, handlers):
        super().__init__()
        self.handlers = handlers

    def notify(self, args):
        _handlers.remove(self.handlers)


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        command = args.command
        command.isRepeatable = False
        inputs = command.commandInputs
        selected = inputs.addSelectionInput("assembly", "Assemblage", "Sélectionner le groupe ou une tôle.")
        for kind in ("Occurrences", "SolidBodies", "Faces"):
            selected.addSelectionFilter(kind)
        selected.setSelectionLimits(0, 1)
        inputs.addTextBoxCommandInput("report", "État", "Sélectionner un assemblage à platines JHR.", 6, True)
        design = fusion.Design.cast(core.Application.get().activeProduct)
        handlers = [Changed(design)]
        handlers.append(Destroyed(handlers))
        command.inputChanged.add(handlers[0])
        command.destroy.add(handlers[1])
        _handlers.append(handlers)


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, "Inspecter un assemblage", "Contrôler les références et le suivi du squelette.",
        addin_info.ribbon_icon("inspecter_assemblage"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    ui_layout.panel(ui, PANEL_ID).controls.addCommand(definition)


def stop():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
