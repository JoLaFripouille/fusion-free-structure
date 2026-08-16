from __future__ import annotations

import traceback

import adsk.core
import adsk.fusion

from ..lib.member_builder import create_member


COMMAND_ID = "EI_JHR_CreateStructuralMembersV1"
COMMAND_NAME = "Profil acier V1"
COMMAND_DESCRIPTION = "Crée un composant IPE 100 sur chaque ligne droite d'esquisse sélectionnée."
SELECTION_ID = "skeletonLines"
PANEL_IDS = ("SolidCreatePanel", "SolidScriptsAddinsPanel")

_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("[EI_JHR V1] {}".format(message))


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs

            selection = inputs.addSelectionInput(
                SELECTION_ID,
                "Lignes du squelette",
                "Sélectionner une ou plusieurs lignes droites d'esquisse dans le composant racine.",
            )
            selection.addSelectionFilter("SketchLines")
            selection.setSelectionLimits(1, 0)
            inputs.addTextBoxCommandInput(
                "v1Info",
                "V1 technique",
                "Profil fixe : IPE 100<br>Ancrage : C<br>Rotation : 0°<br>Un composant indépendant par ligne.",
                4,
                True,
            )

            execute_handler = ExecuteHandler()
            command.execute.add(execute_handler)
            _handlers.append(execute_handler)

            validate_handler = ValidateInputsHandler()
            command.validateInputs.add(validate_handler)
            _handlers.append(validate_handler)
            _log("Commande ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox("Échec de la création de la commande:\n{}".format(traceback.format_exc()))


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        selection = event_args.inputs.itemById(SELECTION_ID)
        event_args.areInputsValid = bool(selection and selection.selectionCount >= 1)


class ExecuteHandler(adsk.core.CommandEventHandler):
    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        created_occurrences = []
        try:
            app, ui = _app_and_ui()
            design = adsk.fusion.Design.cast(app.activeProduct)
            if not design:
                raise RuntimeError("Ouvrir un document de conception Fusion avant d'utiliser la commande.")
            if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
                raise RuntimeError("La V1 nécessite l'historique de conception paramétrique activé.")

            root_component = design.rootComponent
            selection = event_args.command.commandInputs.itemById(SELECTION_ID)
            lines = []
            for index in range(selection.selectionCount):
                line = adsk.fusion.SketchLine.cast(selection.selection(index).entity)
                if not line:
                    raise RuntimeError("La sélection {} n'est pas une ligne d'esquisse.".format(index + 1))
                native_line = line.nativeObject if line.nativeObject else line
                if native_line.parentSketch.parentComponent != root_component:
                    raise RuntimeError("La V1 accepte uniquement les lignes d'un squelette placé dans le composant racine.")
                if native_line.length <= 1e-6:
                    raise RuntimeError("Une ligne sélectionnée a une longueur nulle ou trop petite.")
                lines.append(native_line)

            _log("Création demandée pour {} ligne(s)".format(len(lines)))
            for line in lines:
                occurrence = create_member(root_component, line)
                created_occurrences.append(occurrence)
                _log("Composant créé: {}".format(occurrence.component.name))

            ui.messageBox("{} barre(s) IPE 100 créée(s).".format(len(created_occurrences)))
        except Exception as error:
            for occurrence in reversed(created_occurrences):
                if occurrence and occurrence.isValid:
                    occurrence.deleteMe()
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("La création a été annulée:\n{}".format(error))


def start():
    global _panel_id
    _, ui = _app_and_ui()
    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if not command_definition:
        command_definition = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_DESCRIPTION,
            "",
        )

    created_handler = CommandCreatedHandler()
    command_definition.commandCreated.add(created_handler)
    _handlers.append(created_handler)

    for panel_id in PANEL_IDS:
        panel = ui.allToolbarPanels.itemById(panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if not control:
                control = panel.controls.addCommand(command_definition)
            control.isPromoted = True
            _panel_id = panel_id
            break
    if not _panel_id:
        raise RuntimeError("Aucun panneau Fusion compatible n'a été trouvé pour ajouter la commande.")
    _log("Extension chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id
    _, ui = _app_and_ui()
    for panel_id in PANEL_IDS:
        panel = ui.allToolbarPanels.itemById(panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()
    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if command_definition:
        command_definition.deleteMe()
    _handlers.clear()
    _panel_id = None
