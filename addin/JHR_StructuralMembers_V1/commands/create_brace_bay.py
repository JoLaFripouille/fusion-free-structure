"""Commande Fusion du contreventement en X piloté par deux faces."""

from html import escape
import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import addin_info, assembly_catalog as catalogue, assembly_geometry, brace_bay
from ..lib import brace_bay_preview, preview_visibility, profile_catalog, ui_layout


COMMAND_ID = "EI_JHR_CreateBraceBay"
COMMAND_NAME = "Auto-contreventement"
UPDATE_ID = COMMAND_ID + "_Update"
UPDATE_EVENT = COMMAND_ID + "_SourcesChanged"
ANGLE_FAMILIES = ("Corniere_Egale", "Corniere_Inegale")
GEOMETRY = (
    catalogue.Field("bottom_mm", "Hauteur depuis le bas", 150),
    catalogue.Field("top_mm", "Distance depuis le haut", 150),
    catalogue.Field("setback_mm", "Jeu entre cornière et face soudée", 20),
    catalogue.Field("offset_mm", "Déport latéral du plan du X", 0, signed=True),
)
CENTRAL_GROUPS = catalogue.template_for("gusset_cross").groups
END_GROUPS = (
    catalogue.GUSSET, ("Chant soudé", (catalogue.GUSSET_WELD[1][-1],)), catalogue.GUSSET_HOLES, catalogue.FASTENERS,
)
_handlers = []
_auto_handlers = []
_pending = None


def _number_input(inputs, prefix, field):
    key = prefix + field.key
    if field.unit:
        return inputs.addValueInput(key, field.label, field.unit,
                                    core.ValueInput.createByReal(field.default * .1))
    return inputs.addIntegerSpinnerCommandInput(key, field.label, field.min_count, field.max_count,
                                                 1, int(field.default))


class BraceBayForm:
    def __init__(self, command, app, design, *, embedded=False):
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.setDialogInitialSize(490, 480)
        command.okButtonText = "Appliquer" if embedded else "Créer"
        self.embedded = embedded
        self.app = app
        self.design = design
        self.document = app.activeDocument
        self.graphics = None
        self.visibility = preview_visibility.PreviewVisibility()
        self.controls = {}
        self.feedback = {}
        self.target = None

        inputs = command.commandInputs
        self.tabs = tuple(inputs.addTabCommandInput(key, label) for key, label in (
            ("braceGeometryTab", "Géométrie"), ("braceCentralTab", "Platine centrale"),
            ("braceEndsTab", "Goussets"), ("braceOptionsTab", "Options"),
        ))
        geometry, central, ends, options = (tab.children for tab in self.tabs)
        if not embedded:
            self.edit_mode = geometry.addBoolValueInput("editBraceBay", "Modifier ou recalculer un X existant",
                                                       True, "", False)
            self.existing = geometry.addSelectionInput("existingBraceBay", "Pièce du X", "Sélectionner une pièce du X.")
            for kind in ("Occurrences", "SolidBodies", "PlanarFaces"):
                self.existing.addSelectionFilter(kind)
            self.existing.setSelectionLimits(0, 1)
            self.existing.isVisible = False
            self.faces = tuple(self._face_selector(geometry, index) for index in (1, 2))

        self.profiles = tuple(profile for profile in profile_catalog.discover_profiles()
                              if profile.family_id in ANGLE_FAMILIES)
        if not self.profiles:
            raise FileNotFoundError("La bibliothèque ne contient aucune section de cornière.")
        default = next((profile for profile in self.profiles
                        if profile.component_token == "CORNIEREEGALE60X60EP6"), self.profiles[0])
        style = core.DropDownStyles.TextListDropDownStyle
        self.sections = tuple(
            geometry.addDropDownCommandInput(f"braceSection{index}", f"Cornière {index}", style)
            for index in (1, 2)
        )
        for section in self.sections:
            for profile in self.profiles:
                section.listItems.add(profile.designation, profile == default)
        self.flips = tuple(
            geometry.addBoolValueInput(f"reverseBrace{index}", f"Inverser l’aile de la cornière {index}",
                                       True, "", False)
            for index in (1, 2)
        )
        self.geometry = self._fields(geometry, "", (("Position", GEOMETRY),), id_prefix="braceGeometry_")
        self.central = self._fields(central, "central.", CENTRAL_GROUPS)
        self.ends = self._fields(ends, "ends.", END_GROUPS)
        self.scalloped = options.addBoolValueInput("scalloped", "Évidements arrondis de la platine centrale",
                                                   True, "", False)
        self.option_fields = self._fields(options, "", (("Évidements", (
            catalogue.Field("scallop_depth_mm", "Profondeur de l’évidement", 5),
        )),), id_prefix="braceOptions_")
        self.controls["scallop_depth_mm"].isVisible = False
        self.controls["scallop_depth_mm"].parentCommandInput.isVisible = False
        self.report = inputs.addTextBoxCommandInput("braceBayStatus", "", "Sélectionner les deux faces opposées.", 2, True)
        self.report.isFullWidth = True

    def _face_selector(self, inputs, index):
        selection = inputs.addSelectionInput(
            f"braceFace{index}", f"Face du poteau {index}", "Sélectionner une face plane tournée vers la travée.",
        )
        selection.addSelectionFilter("PlanarFaces")
        selection.setSelectionLimits(1, 1)
        return selection

    def _fields(self, tab, prefix, groups, *, id_prefix=None):
        fields = {}
        id_prefix = id_prefix or prefix.replace(".", "_")
        for index, (label, values) in enumerate(groups):
            identifier = id_prefix + f"group{index}"
            group = tab.addGroupCommandInput(identifier, label)
            group.isExpanded = index == 0
            children = group.children
            message = children.addTextBoxCommandInput(identifier + "Error", "", "", 2, True)
            message.isFullWidth = True
            message.isVisible = False
            for field in values:
                control = _number_input(children, id_prefix, field)
                fields[field.key] = control, field
                self.controls[prefix + field.key] = control
                self.feedback[prefix + field.key] = message
        return fields

    @property
    def has_faces(self):
        return self.existing.selectionCount == 1 if self.edit_mode.value else all(
            selection.selectionCount == 1 for selection in self.faces
        )

    def change_mode(self):
        editing = self.edit_mode.value
        for selection in self.faces:
            selection.clearSelection()
            selection.setSelectionLimits(0 if editing else 1, 1)
            selection.isVisible = not editing
        self.existing.clearSelection()
        self.existing.setSelectionLimits(int(editing), 1)
        self.existing.isVisible = editing
        self.target = None

    def read_existing(self, entity=None):
        if entity is None:
            entity = self.existing.selection(0).entity
        group, faces, record = brace_bay.read(self.design, entity)
        self.target = group, faces
        settings = record["settings"]
        for fields, values in ((self.geometry, settings), (self.central, settings["central"]),
                               (self.ends, settings["ends"])):
            for key, (control, field) in fields.items():
                value = values.get(key, field.default)
                control.value = value * .1 if field.unit else int(value)
        for section, path in zip(self.sections, record["profiles"]):
            index = next((index for index, profile in enumerate(self.profiles) if profile.relative_path == path), None)
            if index is None:
                raise ValueError("Une des sections enregistrées est absente du catalogue.")
            section.listItems.item(index).isSelected = True
        for checkbox, key in zip(self.flips, ("flip_first", "flip_second")):
            checkbox.value = settings[key]
        self.scalloped.value = settings.get("scalloped", False)
        self.controls["scallop_depth_mm"].value = settings.get("scallop_depth_mm", 5) * .1
        self.show_scallop_depth()

    def show_scallop_depth(self):
        control = self.controls["scallop_depth_mm"]
        control.parentCommandInput.isVisible = self.scalloped.value
        control.isVisible = self.scalloped.value

    def set_visible(self, visible):
        for tab in self.tabs:
            tab.isVisible = visible
        if not visible:
            self.clear_preview()
        self.report.isVisible = visible and not self.embedded

    @staticmethod
    def _values(controls, prefix=""):
        result = {}
        for key, (control, field) in controls.items():
            if field.unit and not control.isValidExpression:
                raise assembly_geometry.DimensionError((prefix + key,), "Vérifier l’expression de la cote.")
            result[key] = control.value * 10 if field.unit else control.value
        return result

    def plan(self):
        if self.app.activeDocument != self.document or self.app.activeProduct != self.design:
            raise ValueError("Revenir à la conception où la commande a été ouverte.")
        if not self.embedded and not self.has_faces:
            raise ValueError("Sélectionner les deux faces opposées.")
        if self.embedded or self.edit_mode.value:
            if not self.target:
                self.read_existing()
            faces = self.target[1]
        else:
            faces = tuple(fusion.BRepFace.cast(selection.selection(0).entity) for selection in self.faces)
        if not all(faces):
            raise ValueError("Sélectionner une face plane sur chaque poteau.")
        profiles = tuple(self.profiles[section.selectedItem.index].relative_path for section in self.sections)
        settings = self._values(self.geometry)
        settings.update(flip_first=self.flips[0].value, flip_second=self.flips[1].value,
                        central=self._values(self.central, "central."), ends=self._values(self.ends, "ends."),
                        scalloped=self.scalloped.value)
        if self.scalloped.value:
            settings.update(self._values(self.option_fields))
        return brace_bay.evaluate(self.design, faces, profiles, settings)

    def clear_preview(self):
        self.visibility.restore()
        if self.graphics and self.graphics.isValid:
            self.graphics.deleteMe()
        self.graphics = None

    def preview(self, plan):
        self.clear_preview()
        self.graphics = self.design.rootComponent.customGraphicsGroups.add()
        self.graphics.id = "EI_JHR_BRACE_BAY_PREVIEW"
        brace_bay_preview.draw(self.graphics, plan)
        if self.target:
            self.visibility.hide(self.target[0])
        self.app.activeViewport.refresh()

    def set_status(self, message, error=None):
        for box in self.feedback.values():
            if box.isVisible:
                box.isVisible = False
        rendered = escape(message)
        if error:
            for key in getattr(error, "keys", ()):
                control = self.controls.get(key)
                if control:
                    rendered = f"<b>{escape(control.name)}</b><br>{rendered}"
                    box = self.feedback[key]
                    box.formattedText = f'<font color="#D43B3B">{rendered}</font>'
                    box.isVisible = True
                    break
            rendered = f'<font color="#D43B3B">{rendered}</font>'
        self.report.formattedText = rendered


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        args.areInputsValid = False
        if not self.form.has_faces:
            self.form.clear_preview()
            self.form.set_status("Sélectionner une pièce du X." if self.form.edit_mode.value else
                                 "Sélectionner les deux faces opposées.")
            return
        try:
            self.form.plan()
            self.form.set_status("Cotes du X actualisées d’après les faces porteuses." if self.form.edit_mode.value else
                                 "Deux cornières en X avec platine centrale et quatre goussets.")
            args.areInputsValid = True
        except Exception as error:
            self.form.clear_preview()
            self.form.set_status(str(error), error)


class Action(core.CommandEventHandler):
    def __init__(self, form, action):
        super().__init__()
        self.form = form
        self.action = action

    def notify(self, args):
        try:
            if self.action == "destroy":
                self.form.clear_preview()
                _handlers.remove(self.form.handlers)
                self.form.handlers = None
            elif self.action == "preview":
                core.CommandEventArgs.cast(args).isValidResult = False
                self.form.preview(self.form.plan())
            else:
                self.form.clear_preview()
                plan = self.form.plan()
                if self.form.edit_mode.value:
                    from ..lib import assembly_copy

                    assembly_copy.reconfigure_bay(self.form.design, self.form.target[0], plan)
                else:
                    brace_bay.create(self.form.design, plan)
        except Exception as error:
            self.form.clear_preview()
            if self.action == "execute":
                args.executeFailed = True
                args.executeFailedMessage = str(error)
            elif self.action == "preview":
                self.form.set_status(str(error), error)
            if not isinstance(error, ValueError):
                self.form.app.log(f"[JHR] {COMMAND_NAME} · {self.action}\n" + traceback.format_exc(),
                                  core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)


class InputChanged(core.InputChangedEventHandler):
    def __init__(self, form, command):
        super().__init__()
        self.form = form
        self.command = command

    def notify(self, args):
        try:
            if args.input == self.form.edit_mode:
                self.form.change_mode()
                self.command.okButtonText = "Appliquer" if self.form.edit_mode.value else "Créer"
            elif args.input == self.form.existing:
                self.form.target = None
                if self.form.existing.selectionCount:
                    self.form.read_existing()
            elif args.input == self.form.scalloped:
                self.form.show_scallop_depth()
        except (ValueError, RuntimeError) as error:
            self.form.set_status(str(error), error)


class Created(core.CommandCreatedEventHandler):
    def notify(self, args):
        app = core.Application.get()
        command = args.command
        try:
            design = fusion.Design.cast(app.activeProduct)
            if not design:
                raise ValueError("Ouvrir une conception Fusion.")
            form = BraceBayForm(command, app, design)
            handlers = (
                (command.inputChanged, InputChanged(form, command)),
                (command.validateInputs, Validate(form)),
                (command.executePreview, Action(form, "preview")),
                (command.execute, Action(form, "execute")),
                (command.destroy, Action(form, "destroy")),
            )
            for event, handler in handlers:
                event.add(handler)
            _handlers.append(handlers)
            form.handlers = handlers
        except Exception as error:
            command.isOKButtonVisible = False
            app.userInterface.messageBox(str(error), COMMAND_NAME)


class SourceCommandFinished(core.ApplicationCommandEventHandler):
    def notify(self, args):
        if args.terminationReason != core.CommandTerminationReason.CompletedTerminationReason:
            return
        command = args.commandId.lower()
        # Ignorer les commandes de consultation, les annulations et le recalcul lui-même.
        source_commands = ("move", "sketch", "parameter", "editstructuralmember")
        if command in (COMMAND_ID.lower(), UPDATE_ID.lower()) or "undo" in command or "redo" in command:
            return
        if any(part in command for part in source_commands):
            app = core.Application.get()
            document = app.activeDocument
            if document:
                app.fireCustomEvent(UPDATE_EVENT, document.creationId)


class UpdateRequested(core.CustomEventHandler):
    def notify(self, args):
        global _pending
        app = core.Application.get()
        document = app.activeDocument
        ui = app.userInterface
        if not document or document.creationId != args.additionalInfo or ui.activeCommand != "SelectCommand":
            return
        design = fusion.Design.cast(app.activeProduct)
        if not design or design.designType != fusion.DesignTypes.ParametricDesignType:
            return
        try:
            candidate = brace_bay.pending_update(design)
            if candidate:
                _pending = (document, design, candidate)
                if not ui.commandDefinitions.itemById(UPDATE_ID).execute():
                    _pending = None
        except (ValueError, RuntimeError) as error:
            app.log(f"[JHR] Auto-contreventement à recalculer · {error}", core.LogLevels.WarningLogLevel)


class UpdateExecute(core.CommandEventHandler):
    def __init__(self, document, design, target):
        super().__init__()
        self.document, self.design, self.target = document, design, target

    def notify(self, args):
        app = core.Application.get()
        if app.activeDocument != self.document:
            return
        group, faces, record = self.target
        try:
            plan = brace_bay.evaluate(self.design, faces, record["profiles"], record["settings"])
            from ..lib import assembly_copy

            assembly_copy.reconfigure_bay(self.design, group, plan)
        except (ValueError, RuntimeError) as error:
            args.executeFailed = True
            args.executeFailedMessage = f"Auto-contreventement à recalculer · {error}"


class UpdateCreated(core.CommandCreatedEventHandler):
    def notify(self, args):
        global _pending
        target, _pending = _pending, None
        if target:
            command = args.command
            command.isRepeatable = False
            handler = UpdateExecute(*target)
            command.execute.add(handler)
            _auto_handlers[3:] = [handler]


def start():
    app = core.Application.get()
    ui = app.userInterface
    if ui.commandDefinitions.itemById(COMMAND_ID):
        return
    definition = ui.commandDefinitions.addButtonDefinition(
        COMMAND_ID, COMMAND_NAME,
        "Créer et paramétrer un X complet depuis deux faces de poteaux opposées.",
        addin_info.ribbon_icon("auto_contreventement"),
    )
    handler = Created()
    definition.commandCreated.add(handler)
    _handlers.append(handler)
    panel = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID)
    panel.controls.addCommand(definition).isPromoted = True
    update_definition = ui.commandDefinitions.addButtonDefinition(UPDATE_ID, "Actualiser le contreventement JHR", "")
    update_created = UpdateCreated()
    update_definition.commandCreated.add(update_created)
    requested = UpdateRequested()
    app.registerCustomEvent(UPDATE_EVENT).add(requested)
    finished = SourceCommandFinished()
    ui.commandTerminated.add(finished)
    _auto_handlers.extend((update_created, requested, finished))


def stop():
    global _pending
    app = core.Application.get()
    ui = app.userInterface
    if _auto_handlers:
        ui.commandTerminated.remove(_auto_handlers[2])
        app.unregisterCustomEvent(UPDATE_EVENT)
        _auto_handlers.clear()
    _pending = None
    panel = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID)
    control = panel and panel.controls.itemById(COMMAND_ID)
    if control:
        control.deleteMe()
    definition = ui.commandDefinitions.itemById(COMMAND_ID)
    if definition:
        definition.deleteMe()
    update_definition = ui.commandDefinitions.itemById(UPDATE_ID)
    if update_definition:
        update_definition.deleteMe()
    _handlers.clear()
