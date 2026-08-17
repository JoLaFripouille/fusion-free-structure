from __future__ import annotations

import html
import traceback

import adsk.core
import adsk.fusion

from ..lib import addin_info, joint_builder, ui_layout
from ..lib.joint_preview import JointPreviewManager


COMMAND_ID = "EI_JHR_CreateStraightJointV1"
COMMAND_NAME = "Jonction droite V{}".format(addin_info.VERSION)
COMMAND_DESCRIPTION = (
    "Coupe une barre secondaire droite ou cintrée à l'enveloppe d'une barre principale droite."
)
PRIMARY_SELECTION_ID = "primaryMember"
SECONDARY_SELECTION_ID = "secondaryMember"
GAP_INPUT_ID = "jointGap"
REPORT_ID = "jointReport"
PANEL_IDS = (ui_layout.MODIFY_PANEL_ID,)


_handlers = []
_panel_id = None


def _app_and_ui():
    app = adsk.core.Application.get()
    return app, app.userInterface


def _log(message):
    app, _ = _app_and_ui()
    app.log("{} [JONCTION] {}".format(addin_info.LOG_PREFIX, message))


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


def _evaluate(inputs):
    app, _ = _app_and_ui()
    design = adsk.fusion.Design.cast(app.activeProduct)
    if not design:
        raise ValueError("Ouvrir une conception Fusion.")
    if design.designType != adsk.fusion.DesignTypes.ParametricDesignType:
        raise ValueError("La jonction nécessite l'historique de conception paramétrique activé.")
    primary = _selected_occurrence(inputs, PRIMARY_SELECTION_ID, "principale")
    secondary = _selected_occurrence(inputs, SECONDARY_SELECTION_ID, "secondaire")
    gap_input = inputs.itemById(GAP_INPUT_ID)
    if not gap_input or not gap_input.isValidExpression:
        raise ValueError("Le jeu de jonction n'est pas une distance valide.")
    return design, joint_builder.evaluate_straight_joint(
        design,
        primary,
        secondary,
        gap_input.value,
    )


def _success_report(evaluation):
    rows = (
        ("Barre principale", evaluation.primary_occurrence.component.name),
        ("Profil principal", evaluation.primary_metadata.profile),
        ("Barre secondaire", evaluation.secondary_occurrence.component.name),
        ("Profil secondaire", evaluation.secondary_metadata.profile),
        (
            "Chemin secondaire",
            "Arc cintré" if evaluation.secondary_metadata.source_curve_type == "arc" else "Ligne droite",
        ),
        ("Angle entre axes", "{:.1f}°".format(evaluation.geometry.angle_degrees)),
        ("Jeu", "{:.3f} mm".format(evaluation.gap_cm * 10.0)),
        ("Longueur retirée estimée", "{:.3f} mm".format(evaluation.removed_length_cm * 10.0)),
    )
    content = [
        "<b>Prêt — le plan orange montre la coupe.</b><br>",
        "La barre principale restera intacte.<br><br>",
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
            "<b>Jonction non disponible</b><br>{}".format(_escaped(error))
        )
        return None


class CommandCreatedHandler(adsk.core.CommandCreatedEventHandler):
    def notify(self, args):
        try:
            event_args = adsk.core.CommandCreatedEventArgs.cast(args)
            command = event_args.command
            command.isRepeatable = False
            inputs = command.commandInputs
            preview_manager = JointPreviewManager()

            primary = inputs.addSelectionInput(
                PRIMARY_SELECTION_ID,
                "Barre principale",
                "Sélectionner la barre qui doit rester intacte.",
            )
            primary.addSelectionFilter("Occurrences")
            primary.setSelectionLimits(0, 1)

            secondary = inputs.addSelectionInput(
                SECONDARY_SELECTION_ID,
                "Barre secondaire",
                "Sélectionner la barre droite ou cintrée dont l'extrémité sera coupée.",
            )
            secondary.addSelectionFilter("Occurrences")
            secondary.setSelectionLimits(0, 1)

            gap = inputs.addValueInput(
                GAP_INPUT_ID,
                "Jeu",
                "mm",
                adsk.core.ValueInput.createByString("0 mm"),
            )
            gap.minimumValue = 0.0
            gap.isMinimumInclusive = True

            report = inputs.addTextBoxCommandInput(
                REPORT_ID,
                "Contrôle",
                "Sélectionner d'abord la barre principale, puis la barre secondaire.",
                10,
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
                "Échec de l'ouverture de la jonction:\n{}".format(traceback.format_exc())
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
            GAP_INPUT_ID,
        ):
            _refresh(event_args.inputs, self._report_input, self._preview_manager)


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


class ExecuteHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        event_args = adsk.core.CommandEventArgs.cast(args)
        try:
            self._preview_manager.clear()
            _, evaluation = _evaluate(event_args.command.commandInputs)
            joint_builder.create_straight_joint(evaluation)
            _log(
                "Jonction droite créée : principale={}, secondaire={}, jeu={} mm"
                .format(
                    evaluation.primary_occurrence.component.name,
                    evaluation.secondary_occurrence.component.name,
                    evaluation.gap_cm * 10.0,
                )
            )
        except Exception as error:
            event_args.executeFailed = True
            _log("ÉCHEC: {}\n{}".format(error, traceback.format_exc()))
            _, ui = _app_and_ui()
            ui.messageBox("La jonction a été annulée :\n{}".format(error))


class DestroyHandler(adsk.core.CommandEventHandler):
    def __init__(self, preview_manager):
        super().__init__()
        self._preview_manager = preview_manager

    def notify(self, args):
        self._preview_manager.clear()


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
        panel = ui_layout.panel(ui, panel_id)
        if panel:
            control = panel.controls.itemById(COMMAND_ID)
            if not control:
                control = panel.controls.addCommand(command_definition)
            control.isPromoted = True
            _panel_id = panel_id
            break
    if not _panel_id:
        raise RuntimeError("Aucun panneau Fusion compatible n'a été trouvé pour la jonction.")
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
    command_definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if command_definition:
        command_definition.deleteMe()
    _handlers.clear()
    _panel_id = None
