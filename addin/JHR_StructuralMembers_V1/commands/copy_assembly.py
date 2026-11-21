"""Commande Fusion de copie des assemblages du catalogue JHR."""

from html import escape
import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, assembly_copy, plate_preview, ui_layout


COMMAND_ID = "EI_JHR_CopyAssembly"
COMMAND_NAME = "Copier un assemblage"
PANEL_ID = ui_layout.MODIFY_PANEL_ID
_handlers = []


class Form:
    def __init__(self, command):
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.okButtonText = "Copier"
        command.setDialogInitialSize(440, 330)
        self.app = core.Application.get()
        self.document = self.app.activeDocument
        self.design = fusion.Design.cast(self.app.activeProduct)
        self.graphics = None
        inputs = command.commandInputs
        self.source = self._selection(inputs, "copySource", "Assemblage source",
                                      "Sélectionner un assemblage du catalogue JHR ou l’une de ses pièces.")
        self.target_group = inputs.addGroupCommandInput("copyTargets", "Cibles")
        self.target_group.isExpanded = True
        self.target_group.isVisible = False
        self.selectors = {}
        self.targets = ()
        self.source_assembly = None
        self.source_error = ""
        self.linked = inputs.addBoolValueInput("copyLinked", "Lier les réglages à l’assemblage source", True, "", False)
        self.linked.isVisible = False
        self.report = inputs.addTextBoxCommandInput("copyReport", "", "Sélectionner l’assemblage à copier.", 3, True)
        self.report.isFullWidth = True

    @staticmethod
    def _selection(inputs, key, label, prompt, filters=("Occurrences", "SolidBodies", "Faces")):
        selection = inputs.addSelectionInput(key, label, prompt)
        for kind in filters:
            selection.addSelectionFilter(kind)
        selection.setSelectionLimits(1, 1)
        return selection

    def update_source(self):
        for control in self.targets:
            control.clearSelection()
            control.setSelectionLimits(0, 1)
            control.isVisible = False
        self.targets = ()
        self.source_assembly = None
        self.source_error = ""
        if self.source.selectionCount:
            try:
                self.source_assembly = assembly_copy.read_source(self.design, self.source.selection(0).entity)
            except (ValueError, RuntimeError, FileNotFoundError) as error:
                self.source_error = str(error)
        self.target_group.isVisible = self.source_assembly is not None
        self.linked.isVisible = bool(self.source_assembly and assembly_copy.can_link(self.source_assembly))
        if not self.linked.isVisible:
            self.linked.value = False
        if not self.source_assembly:
            return
        template = self.source_assembly.template
        if template.roles not in self.selectors:
            prefix = f"copyTarget{len(self.selectors)}_"
            roles = ("Poteau cible",) if template.family == "Pieds de poteau" else template.roles
            filters = ("PlanarFaces",) if template.key == "brace_bay" else ("Occurrences", "SolidBodies", "Faces")
            self.selectors[template.roles] = tuple(
                self._selection(self.target_group.children, prefix + str(index), role,
                                f"Sélectionner la cible « {role} ».", filters)
                for index, role in enumerate(roles)
            )
        self.targets = self.selectors[template.roles]
        for control in self.targets:
            control.isVisible = True
            control.setSelectionLimits(1, 1)

    def plan(self):
        if self.app.activeDocument != self.document or self.app.activeProduct != self.design or not self.design:
            raise ValueError("La conception active a changé.")
        if not self.source_assembly:
            raise ValueError(self.source_error or "Sélectionner l’assemblage à copier.")
        if any(selection.selectionCount != 1 for selection in self.targets):
            raise ValueError(f"{self.source_assembly.template.label} · Sélectionner les cibles demandées.")
        return assembly_copy.prepare(
            self.design, self.source.selection(0).entity,
            tuple(selection.selection(0).entity for selection in self.targets),
            self.linked.isVisible and self.linked.value,
        )

    def clear_preview(self):
        if self.graphics and self.graphics.isValid:
            self.graphics.deleteMe()
        self.graphics = None

    def preview(self, plan):
        self.clear_preview()
        self.graphics = self.design.rootComponent.customGraphicsGroups.add()
        self.graphics.id = "EI_JHR_COPY_ASSEMBLY_PREVIEW"
        plate_preview.draw_plates(self.graphics, plan.assembly.plates)
        self.app.activeViewport.refresh()


class Changed(core.InputChangedEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        if args.input.id == self.form.source.id:
            self.form.update_source()


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        args.areInputsValid = False
        try:
            plan = self.form.plan()
            targets = " · ".join(escape(assembly_copy.target_name(target)) for target in plan.targets)
            summary = f"{escape(plan.source.template.label)} sur {targets}"
            link = (f"Réglages liés à {escape(plan.master.group.name)}"
                    if plan.master else "Copie indépendante")
            self.form.report.formattedText = f"{summary}<br>{link}"
            args.areInputsValid = True
        except (ValueError, RuntimeError, FileNotFoundError) as error:
            self.form.clear_preview()
            self.form.report.formattedText = escape(str(error))


class Action(core.CommandEventHandler):
    def __init__(self, form, action):
        super().__init__()
        self.form, self.action = form, action

    def notify(self, args):
        try:
            if self.action == "destroy":
                self.form.clear_preview()
                _handlers.remove(self.form.handlers)
            elif self.action == "preview":
                core.CommandEventArgs.cast(args).isValidResult = False
                self.form.preview(self.form.plan())
            else:
                self.form.clear_preview()
                assembly_copy.create(self.form.design, self.form.plan())
        except Exception as error:
            app = self.form.app
            app.log("[JHR] Copie d’assemblage\n" + traceback.format_exc(),
                    core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)
            if self.action == "execute":
                args.executeFailed = True
                args.executeFailedMessage = str(error)
                app.userInterface.messageBox(str(error), COMMAND_NAME)
            elif self.action == "preview":
                self.form.clear_preview()
                self.form.report.formattedText = escape(str(error))


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        command = core.CommandCreatedEventArgs.cast(args).command
        form = Form(command)
        form.handlers = [
            (command.inputChanged, Changed(form)),
            (command.validateInputs, Validate(form)),
            (command.executePreview, Action(form, "preview")),
            (command.execute, Action(form, "execute")),
            (command.destroy, Action(form, "destroy")),
        ]
        for event, handler in form.handlers:
            event.add(handler)
        _handlers.append(form.handlers)


def start():
    ui = core.Application.get().userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, COMMAND_NAME, "Reprendre un montage du catalogue JHR sur d’autres profils.",
        addin_info.ribbon_icon("copier_assemblage"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    ui_layout.panel(ui, PANEL_ID).controls.addCommand(definition).isPromoted = True


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
