"""Crée en série les plats d’âme des pannes choisies dans Fusion."""
from html import escape
import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, assembly_catalog, joint_geometry
from ..lib import purlin_connections, ui_layout

COMMAND_ID = "EI_JHR_ConnectPurlins"
COMMAND_NAME = "Raccorder les pannes"
_handlers = []


class Form:
    def __init__(self, command):
        self.app = core.Application.get()
        self.document = self.app.activeDocument
        self.design = fusion.Design.cast(self.app.activeProduct)
        if not self.design:
            raise ValueError("Ouvrir une conception Fusion.")
        self.graphics = None
        self.batch = None
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.setDialogInitialSize(465, 380)
        command.okButtonText = "Créer les raccords"
        inputs = command.commandInputs
        selection = inputs.addTabCommandInput("purlinProfiles", "Profils").children
        self.beams = selection.addSelectionInput("purlinBeams", "Poutres porteuses", "Choisir les poutres porteuses JHR")
        self.purlins = selection.addSelectionInput("purlins", "Pannes", "Choisir les pannes JHR à raccorder")
        for control in (self.beams, self.purlins):
            control.addSelectionFilter("Occurrences")
            control.setSelectionLimits(1)
        self.allow_bars = selection.addBoolValueInput(
            "allowBars", "Inclure les profils classés Barre", True, "", False,
        )
        settings = inputs.addTabCommandInput("purlinSettings", "Plat d’âme").children
        self.values = []
        template = assembly_catalog.template_for(purlin_connections.KIND)
        for label, fields in template.groups:
            group = settings.addGroupCommandInput("purlinGroup_" + fields[0].key, label)
            group.isExpanded = label == "Plat d’âme" or label == "Perçages"
            for field in fields:
                if field.unit:
                    value = group.children.addValueInput(
                        field.key, field.label, field.unit, core.ValueInput.createByReal(field.default * .1),
                    )
                else:
                    value = group.children.addIntegerSpinnerCommandInput(
                        field.key, field.label, field.min_count, field.max_count, 1, int(field.default),
                    )
                self.values.append((field, value))
        self.report = inputs.addTextBoxCommandInput("purlinStatus", "", "Choisir les poutres et les pannes.", 4, True)
        self.report.isFullWidth = True

    def evaluate(self):
        if self.app.activeDocument != self.document:
            raise ValueError("La conception active a changé.")
        params = {}
        for field, value in self.values:
            if not getattr(value, "isValidExpression", True):
                raise ValueError(f"Vérifier le champ « {value.name} ».")
            params[field.key] = value.value * (10 if field.unit else 1)
        beams, purlins = [
            tuple(fusion.Occurrence.cast(control.selection(i).entity) for i in range(control.selectionCount))
            for control in (self.beams, self.purlins)
        ]
        return purlin_connections.evaluate_batch(
            self.design, beams, purlins, params, allow_bars=self.allow_bars.value,
        )

    def report_batch(self, batch):
        counts = [f"<b>{len(batch.plans)} raccord(s) à créer</b>"]
        if batch.cope_count:
            counts.append(f"{batch.cope_count} about(s) à gruger")
        if batch.existing_count:
            counts.append(f"{batch.existing_count} déjà en place")
        if batch.unmatched:
            names = ", ".join(escape(purlin.name) for purlin in batch.unmatched[:2])
            remaining = len(batch.unmatched) - 2
            if remaining > 0:
                names += f" et {remaining} autre(s)"
            counts.append(f"Sans appui aux abouts — {names}")
        self.report.formattedText = "<br>".join(counts)

    def clear_preview(self):
        if self.graphics and self.graphics.isValid:
            self.graphics.deleteMe()
        self.graphics = None

    def preview(self):
        self.clear_preview()
        if not self.batch or not self.batch.plans:
            return
        self.graphics = self.design.rootComponent.customGraphicsGroups.add()
        self.graphics.id = "EI_JHR_PURLIN_PREVIEW"
        colour = fusion.CustomGraphicsSolidColorEffect.create(core.Color.create(230, 171, 20, 255))
        for plan in self.batch.plans:
            for plate in plan.plates:
                outline = plate.display_outline()
                offset = joint_geometry.scale(plate.normal, plate.thickness_cm)
                points = [joint_geometry.add(plate.point(x, y), offset) for x, y in outline]
                coordinates = fusion.CustomGraphicsCoordinates.create(
                    [value for point in points + points[:1] for value in point],
                )
                wire = self.graphics.addLines(coordinates, list(range(len(points) + 1)), True)
                wire.color = colour
                wire.weight = 2.0
                wire.isSelectable = False
        self.app.activeViewport.refresh()

    def create(self):
        self.clear_preview()
        purlin_connections.create_batch(self.design, self.evaluate())


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        self.form.batch = None
        try:
            self.form.batch = self.form.evaluate()
            self.form.report_batch(self.form.batch)
            args.areInputsValid = bool(self.form.batch.plans)
            if not args.areInputsValid:
                self.form.clear_preview()
        except Exception as error:
            self.form.clear_preview()
            self.form.report.formattedText = escape(str(error))
            args.areInputsValid = False


class Action(core.CommandEventHandler):
    def __init__(self, form, action):
        super().__init__()
        self.form, self.action = form, action

    def notify(self, args):
        try:
            self.action()
        except Exception as error:
            app = self.form.app
            app.log("[JHR] Raccordement des pannes\n" + traceback.format_exc(),
                    core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)
            if self.action == self.form.create:
                args.executeFailed = True
                args.executeFailedMessage = str(error)
                app.userInterface.messageBox(str(error), COMMAND_NAME)
            else:
                self.form.clear_preview()


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        command = args.command
        try:
            form = Form(command)
            handlers = [(command.validateInputs, Validate(form)),
                        (command.executePreview, Action(form, form.preview)),
                        (command.execute, Action(form, form.create))]

            def release():
                form.clear_preview()
                _handlers.remove(handlers)

            handlers.append((command.destroy, Action(form, release)))
            for event, handler in handlers:
                event.add(handler)
            _handlers.append(handlers)
        except Exception as error:
            command.isOKButtonVisible = False
            core.Application.get().userInterface.messageBox(str(error), COMMAND_NAME)


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, COMMAND_NAME, "Créer les mêmes plats d’âme aux abouts des pannes sélectionnées.",
        addin_info.ribbon_icon("raccord_pannes"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    control = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID).controls.addCommand(definition)
    control.isPromoted = True


def stop():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    _handlers.clear()
