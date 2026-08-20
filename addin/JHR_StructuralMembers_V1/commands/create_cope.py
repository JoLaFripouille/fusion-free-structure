from __future__ import annotations

import html
import traceback

import adsk.core
import adsk.fusion

from ..lib import addin_info, cope_builder, cope_creator, ui_layout
from ..lib.cope_preview import CopePreviewManager


COMMAND_ID = "EI_JHR_PreviewDoubleIpeCopeV1"
COMMAND_NAME = "Grugeage profils ouverts V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = (
    "Gruge les profils I/H, cornières et tés contre la branche verticale de la principale."
)
PRIMARY_SELECTION_ID = "copePrimaryMember"
SECONDARY_SELECTION_ID = "copeSecondaryMember"
VERTICAL_CLEARANCE_ID = "copeVerticalClearance"
LONGITUDINAL_CLEARANCE_ID = "copeLongitudinalClearance"
WEB_CLEARANCE_ID = "copeWebClearance"
REPORT_ID = "copeReport"
PANEL_IDS = (ui_layout.MODIFY_PANEL_ID,)


_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [GRUGEAGE] {}".format(addin_info.LOG_PREFIX, message))


def _escaped(value):
    return html.escape(str(value), quote=True)


def _selected_occurrence(inputs, input_id, role):
    selection = inputs.itemById(input_id)
    if not selection or selection.selectionCount != 1:
        raise ValueError("Sélectionner une seule barre {}.".format(role))
    occurrence = adsk.fusion.Occurrence.cast(selection.selection(0).entity)
    if not occurrence or not occurrence.isValid:
        raise ValueError("La barre {} sélectionnée n'est pas valide.".format(role))
    return occurrence


def _distance_value(inputs, input_id, label):
    distance = inputs.itemById(input_id)
    if not distance or not distance.isValidExpression:
        raise ValueError("{} n'est pas une distance valide.".format(label))
    if distance.value < 0.0:
        raise ValueError("{} ne peut pas être négatif.".format(label))
    return distance.value


def _evaluate(inputs):
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise ValueError("Ouvrir une conception Fusion.")
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise ValueError("Le grugeage nécessite l'historique paramétrique activé.")
    evaluation = cope_builder.evaluate_profile_cope(
        design,
        _selected_occurrence(inputs, PRIMARY_SELECTION_ID, "principale"),
        _selected_occurrence(inputs, SECONDARY_SELECTION_ID, "secondaire"),
        _distance_value(inputs, VERTICAL_CLEARANCE_ID, "Le jeu vertical"),
        _distance_value(inputs, LONGITUDINAL_CLEARANCE_ID, "Le jeu longitudinal"),
        _distance_value(inputs, WEB_CLEARANCE_ID, "Le jeu contre l'appui"),
    )
    cope_creator.ensure_endpoint_available(evaluation)
    return design, evaluation


def _success_report(evaluation):
    if evaluation.secondary_metadata.profile_family in cope_builder.I_H_FAMILIES:
        removed_rows = (
            (
                "Hauteur inférieure retirée",
                "{:.3f} mm".format(
                    evaluation.profile_geometry.bottom_cope_height_mm
                    + evaluation.vertical_clearance_cm * 10.0
                ),
            ),
            (
                "Hauteur supérieure retirée",
                "{:.3f} mm".format(
                    evaluation.profile_geometry.top_cope_height_mm
                    + evaluation.vertical_clearance_cm * 10.0
                ),
            ),
        )
    else:
        removed_rows = (
            (
                "Hauteur de branche retirée",
                "{:.3f} mm".format(
                    evaluation.profile_geometry.cope_height_mm
                    + evaluation.vertical_clearance_cm * 10.0
                ),
            ),
        )
    extension_text = "Aucun — couverture suffisante"
    if evaluation.primary_extensions:
        extension_text = ", ".join(
            "{:.3f} mm".format(extension.extension_cm * 10.0)
            for extension in evaluation.primary_extensions
        )
    rows = (
        ("Barre principale", evaluation.primary_occurrence.component.name),
        ("Profil principal", evaluation.primary_metadata.profile),
        ("Barre secondaire", evaluation.secondary_occurrence.component.name),
        ("Profil secondaire", evaluation.secondary_metadata.profile),
        ("Angle entre axes", "{:.2f}°".format(evaluation.geometry.angle_degrees)),
        (
            "Profondeur maximale du grugeage",
            "{:.3f} mm".format(evaluation.depth_cm * 10.0),
        ),
        ("Coupe droite", "Face de la branche verticale principale"),
        ("Jeu contre l'appui", "{:.3f} mm".format(evaluation.web_clearance_cm * 10.0)),
        ("Prolongement de la principale", extension_text),
    ) + removed_rows + (
        ("Jeu vertical", "{:.3f} mm".format(evaluation.vertical_clearance_cm * 10.0)),
        (
            "Jeu longitudinal",
            "{:.3f} mm".format(evaluation.longitudinal_clearance_cm * 10.0),
        ),
    )
    content = [
        "<b>Les opérations seront créées après validation avec OK.</b><br>",
        "Rouge : matière retirée. Orange : coupe contre la branche verticale principale. ",
        "Vert : prolongement nécessaire de la principale.<br><br>",
    ]
    for label, value in rows:
        content.append("<b>{}</b> : {}<br>".format(_escaped(label), _escaped(value)))
    return "".join(content)


def _refresh(inputs, report_input, preview_manager):
    try:
        design, evaluation = _evaluate(inputs)
        report_input.formattedText = _success_report(evaluation)
        preview_manager.update(design.rootComponent, evaluation)
        return evaluation
    except Exception as error:
        preview_manager.clear()
        report_input.formattedText = (
            "<b>Aperçu non disponible</b><br>{}".format(_escaped(error))
        )
        return None


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs
            preview_manager = CopePreviewManager()

            primary = inputs.addSelectionInput(
                PRIMARY_SELECTION_ID,
                "Barre principale",
                "Sélectionner une I/H, cornière ou té qui sera prolongé si nécessaire.",
            )
            primary.addSelectionFilter("Occurrences")
            primary.setSelectionLimits(0, 1)

            secondary = inputs.addSelectionInput(
                SECONDARY_SELECTION_ID,
                "Barre secondaire",
                "Sélectionner le profil I/H, la cornière ou le té à gruger.",
            )
            secondary.addSelectionFilter("Occurrences")
            secondary.setSelectionLimits(0, 1)

            vertical = inputs.addValueInput(
                VERTICAL_CLEARANCE_ID,
                "Jeu vertical",
                "mm",
                adsk.core.ValueInput.createByString("1 mm"),
            )
            vertical.minimumValue = 0.0
            vertical.isMinimumInclusive = True

            longitudinal = inputs.addValueInput(
                LONGITUDINAL_CLEARANCE_ID,
                "Jeu longitudinal",
                "mm",
                adsk.core.ValueInput.createByString("1 mm"),
            )
            longitudinal.minimumValue = 0.0
            longitudinal.isMinimumInclusive = True

            web_clearance = inputs.addValueInput(
                WEB_CLEARANCE_ID,
                "Jeu contre l'appui",
                "mm",
                adsk.core.ValueInput.createByString("1 mm"),
            )
            web_clearance.minimumValue = 0.0
            web_clearance.isMinimumInclusive = True

            report = inputs.addTextBoxCommandInput(
                REPORT_ID,
                "Contrôle",
                "Sélectionner la principale puis le profil secondaire.",
                12,
                True,
            )

            input_changed = InputChangedHandler(report, preview_manager)
            command.inputChanged.add(input_changed)
            _handlers.append(input_changed)

            validate = ValidateInputsHandler(report, preview_manager)
            command.validateInputs.add(validate)
            _handlers.append(validate)

            execute_preview = ExecutePreviewHandler(report, preview_manager)
            command.executePreview.add(execute_preview)
            _handlers.append(execute_preview)

            execute = ExecuteHandler(preview_manager)
            command.execute.add(execute)
            _handlers.append(execute)

            destroy = DestroyHandler(preview_manager)
            command.destroy.add(destroy)
            _handlers.append(destroy)
            _log("Commande ouverte")
        except Exception:
            _, ui = _app_and_ui()
            ui.messageBox(
                "Échec de l'ouverture du grugeage:\n{}".format(
                    traceback.format_exc()
                )
            )


class InputChangedHandler(adsk.core.InputChangedEventHandler):
    def __init__(self, report_input, preview_manager):
        super().__init__()
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.InputChangedEventArgs.cast(args)
        changed = event_args.input
        if changed and changed.id in (
            PRIMARY_SELECTION_ID,
            SECONDARY_SELECTION_ID,
            VERTICAL_CLEARANCE_ID,
            LONGITUDINAL_CLEARANCE_ID,
            WEB_CLEARANCE_ID,
        ):
            _refresh(event_args.inputs, self._report_input, self._preview_manager)


class ExecutePreviewHandler(adsk.core.CommandEventHandler):
    def __init__(self, report_input, preview_manager):
        super().__init__()
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        event_args.isValidResult = False
        _refresh(
            event_args.command.commandInputs,
            self._report_input,
            self._preview_manager,
        )


class ValidateInputsHandler(adsk.core.ValidateInputsEventHandler):
    def __init__(self, report_input, preview_manager):
        super().__init__()
        self._report_input = report_input
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.ValidateInputsEventArgs.cast(args)
        event_args.areInputsValid = (
            _refresh(event_args.inputs, self._report_input, self._preview_manager)
            is not None
        )


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            self._preview_manager.clear()
            _, evaluation = _evaluate(event_args.command.commandInputs)
            cope_creator.create_profile_cope(evaluation)
            _log(
                "Grugeage créé : principale={}, secondaire={}, "
                "prolongement_principale={} mm, profondeur={} mm"
                .format(
                    evaluation.primary_occurrence.component.name,
                    evaluation.secondary_occurrence.component.name,
                    sum(
                        extension.extension_cm * 10.0
                        for extension in evaluation.primary_extensions
                    ),
                    evaluation.depth_cm * 10.0,
                )
            )
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("Le grugeage a été annulé :\n{}".format(error))


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        self._preview_manager.clear()


def start():
    global _panel_id
    _, ui = _app_and_ui()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if not definition:
        definition = ui.commandDefinitions.addButtonDefinition(
            COMMAND_ID,
            COMMAND_NAME,
            COMMAND_DESCRIPTION,
            "",
        )
    created_handler = CommandCreatedHandler()
    definition.commandCreated.add(created_handler)
    _handlers.append(created_handler)

    for panel_id in PANEL_IDS:
        panel = ui_layout.panel(ui, panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if not control:
                control = panel.controls.addCommand(definition)
            control.isPromoted = True
            _panel_id = panel_id
            break
    if not _panel_id:
        raise RuntimeError("Aucun panneau Fusion compatible n'a été trouvé.")
    _log("Commande chargée dans le panneau {}".format(_panel_id))


def stop():
    global _panel_id
    _, ui = _app_and_ui()
    for panel_id in PANEL_IDS:
        panel = ui_layout.panel(ui, panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if control:
                control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
    _panel_id = None
