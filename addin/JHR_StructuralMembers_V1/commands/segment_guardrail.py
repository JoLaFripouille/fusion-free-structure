"""Commande Fusion pour séparer un garde-corps au droit d’un poteau."""

import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, guardrail_operations, ui_layout


COMMAND_ID = "EI_JHR_SegmentGuardrail"
_handlers = []


class Form:
    def __init__(self, command):
        self.app = core.Application.get()
        self.design = fusion.Design.cast(self.app.activeProduct)
        self.document_id = self.app.activeDocument.creationId
        command.isRepeatable = False
        inputs = command.commandInputs
        self.post = inputs.addSelectionInput(
            "post", "Poteau plat", "Sélectionner un poteau d’un garde-corps Structure JHR.",
        )
        self.post.addSelectionFilter("Occurrences")
        self.post.setSelectionLimits(1, 1)
        self.mode = inputs.addDropDownCommandInput("mode", "Jonction", core.DropDownStyles.TextListDropDownStyle)
        self.mode.listItems.add("Deux demi-poteaux égaux", True)
        self.mode.listItems.add("Poteau conservé et plat adjacent", False)
        self.gap = inputs.addValueInput("gap", "Jeu entre les lisses", "mm", core.ValueInput.createByString("0 mm"))
        self.thickness = inputs.addValueInput(
            "added_thickness", "Épaisseur du plat ajouté", "mm", core.ValueInput.createByString("5 mm"),
        )
        self.thickness.isVisible = False
        self.bolts = inputs.addIntegerSpinnerCommandInput(
            "splice_bolts", "Boulons de liaison M8 · perçages Ø10", 0, 5, 1, 5,
        )

    def values(self):
        doc = self.app.activeDocument
        if not doc or doc.creationId != self.document_id or not self.design:
            raise ValueError("La conception a changé pendant la commande.")
        if self.post.selectionCount != 1:
            raise ValueError("Sélectionner un seul poteau plat.")
        post = fusion.Occurrence.cast(self.post.selection(0).entity)
        if not post or not self.gap.isValidExpression or not self.thickness.isValidExpression:
            raise ValueError("Vérifier le poteau sélectionné et les cotes.")
        mode = "halves" if self.mode.selectedItem.index == 0 else "adjacent"
        return post, mode, self.gap.value*10, self.thickness.value*10


class Changed(core.InputChangedEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        if args.input.id == "mode":
            self.form.thickness.isVisible = self.form.mode.selectedItem.index == 1


class Action(core.CommandEventHandler):
    def __init__(self, form, destroy=False):
        super().__init__()
        self.form = form
        self.destroy = destroy

    def notify(self, args):
        if self.destroy:
            _handlers.remove(self.form.handlers)
            return
        try:
            result = guardrail_operations.segment_guardrail(
                self.form.design, *self.form.values(), bolt_count=self.form.bolts.value,
            )
            self.form.app.log(f"[JHR] Garde-corps tronçonné au {result['post']}, {result['rails']} lisses et plinthes.")
        except Exception as error:
            self.form.app.log("[JHR] Tronçonnage du garde-corps\n" + traceback.format_exc())
            args.executeFailed = True
            args.executeFailedMessage = str(error)


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        command = args.command
        form = Form(command)
        form.handlers = [
            (command.inputChanged, Changed(form)),
            (command.execute, Action(form)),
            (command.destroy, Action(form, destroy=True)),
        ]
        for event, handler in form.handlers:
            event.add(handler)
        _handlers.append(form.handlers)


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, "Tronçonner un garde-corps", "Couper les lisses au droit d'un poteau plat.",
        addin_info.ribbon_icon("tronconner_garde_corps"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    ui_layout.panel(ui, ui_layout.MODIFY_PANEL_ID).controls.addCommand(definition)


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
