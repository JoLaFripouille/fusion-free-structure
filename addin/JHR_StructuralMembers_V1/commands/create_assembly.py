"""Dialogue natif Fusion du catalogue d’assemblages acier."""
from html import escape
import traceback

import adsk.core as core
import adsk.fusion as fusion

from ..lib import (
    addin_info, assembly_catalog as catalogue, assembly_geometry, assembly_operations, plate_preview,
    preview_visibility, ui_layout,
)

COMMAND_ID = "EI_JHR_CreatePlateAssembly"
FOOT_COMMAND_ID = "EI_JHR_CreateColumnBase"
EDIT_COMMAND_ID = "EI_JHR_EditAssembly"
FOOT_FAMILY = "Pieds de poteau"
TOOLS = (
    (FOOT_COMMAND_ID, FOOT_FAMILY, "Créer la platine de pied d’un poteau JHR.", "pied_de_poteau", FOOT_FAMILY),
    ("EI_JHR_BeamColumn", "Poutre-poteau", "Monter une poutre sur un poteau, avec platine ou jarret.",
     "poutre_poteau_jarret", "Poutre-poteau"),
    ("EI_JHR_BeamBeam", "Poutre-poutre", "Assembler deux poutres par plat d’âme, platine, éclisse ou faîtage.",
     "plat_ame_soude", "Poutre-poutre"),
    ("EI_JHR_BraceGussets", "Contreventements", "Créer les goussets de contreventement.",
     "contreventement_gousset", "Contreventements"),
    (COMMAND_ID, "Assemblages acier", "Tous les assemblages du catalogue.", "assemblages_platines", None),
)
FIXING_GROUPS = {"Perçages", "Boulonnerie", "Ancrages droits"}
OPTION_GROUPS = {"Cales fourchettes", "Goussets d’âme", "Goussets d’ailes", "Raidisseurs", "Préscellement"}
OPTIONAL_BASE_PARTS = {
    "Cales fourchettes": ("Poser des cales fourchettes", "shim", 3),
    "Goussets d’âme": ("Ajouter des goussets d’âme", "gusset", 6),
    "Goussets d’ailes": ("Ajouter des goussets d’ailes", "flange_gusset", 6),
    "Ancrages droits": ("Poser des ancrages droits", "anchor_diameter", 16),
    "Préscellement": ("Ajouter une platine de préscellement", "preset_thickness", 6),
}
CORNER_CHOICES = {"chamfer": ("Chanfreiner les coins", "Taille du chanfrein"),
                  "corner_radius": ("Arrondir les coins", "Rayon")}
HOLE_DIMENSIONS = (("gauge", "pitch"), ("hole_edge_x", "hole_edge_y"),
                   ("hole_edge_x", "pitch"), ("gauge", "hole_edge_y"))
PLATE_DIMENSIONS = (("width", "height", "offset_x", "offset_y"),
                    ("plate_x_minus", "plate_x_plus", "plate_y_minus", "plate_y_plus"))
_handlers = []


def _dimension_visibility(values):
    for mode, alternatives in (("hole_position", HOLE_DIMENSIONS), ("plate_position", PLATE_DIMENSIONS)):
        if mode in values:
            visible = alternatives[values[mode].selectedItem.index]
            for key in {field for combination in alternatives for field in combination}:
                yield key, key in visible


class AssemblyForm:
    def __init__(self, command, family=None, editing=False):
        command.isRepeatable = False
        command.isExecutedWhenPreEmpted = False
        command.setDialogInitialSize(465, 450)
        command.okButtonText = "Appliquer" if editing else "Créer"
        self.editing = editing
        self.edit_selection = self.edit_target = None
        self.bay_form = None
        self.editing_bay = False
        self.edit_error = ""
        self.loading = False
        self.app = core.Application.get()
        self.design = fusion.Design.cast(self.app.activeProduct)
        self.creation_id = self.app.activeDocument.creationId
        self.graphics = None
        self.visibility = preview_visibility.PreviewVisibility()
        inputs = command.commandInputs
        profiles = inputs.addTabCommandInput("profilesTab", "Assemblage" if editing else "Profils").children
        if editing:
            self.edit_selection = profiles.addSelectionInput(
                "editAssembly", "Assemblage à modifier", "Sélectionner une pièce de l’assemblage JHR.",
            )
            for kind in ("Occurrences", "SolidBodies", "Faces"):
                self.edit_selection.addSelectionFilter(kind)
            self.edit_selection.setSelectionLimits(1, 1)
        self.settings_tabs = {
            key: inputs.addTabCommandInput(key + "Tab", label)
            for key, label in (("geometry", "Platine" if family == FOOT_FAMILY else "Géométrie"),
                               ("fixings", "Fixations"), ("options", "Options"))
        }
        self.models = tuple(model for model in catalogue.TEMPLATES if family is None or model.family == family)
        self.family = family
        self.family_input = None
        if family is None:
            self.family_input = profiles.addDropDownCommandInput(
                "assemblyFamily", "Famille", core.DropDownStyles.TextListDropDownStyle,
            )
            for index, name in enumerate(dict.fromkeys(model.family for model in self.models)):
                self.family_input.listItems.add(name, index == 0)
            self.family_input.isVisible = not editing
        self.choices = profiles.addDropDownCommandInput(
            "type", "Type de pied" if family == FOOT_FAMILY else "Montage",
            core.DropDownStyles.TextListDropDownStyle,
        )
        self.choices.isEnabled = not editing
        self.role_hint = None
        if family != FOOT_FAMILY:
            self.role_hint = profiles.addTextBoxCommandInput("roles", "", "", 2, True)
            self.role_hint.isFullWidth = True
        self.selections = []
        for index in range(0 if editing else max(len(model.roles) for model in self.models)):
            name = "Poteau" if family == FOOT_FAMILY else f"Profil {index + 1}"
            select = profiles.addSelectionInput(f"member{index}", name, "Sélectionner un profil Structure JHR")
            select.addSelectionFilter("Occurrences")
            self.selections.append(select)
        self.alternate = profiles.addBoolValueInput("alternate", "Inverser le côté d’appui", True, "", False)
        self.alternate_end = profiles.addBoolValueInput(
            "alternateEnd", "Platine à l’autre extrémité du poteau", True, "", False,
        )
        self.options = {}
        self.corner_options = {}
        self.dimension_feedback = {}
        self.active_feedback = None
        self.report = inputs.addTextBoxCommandInput(
            "details", "", ("Sélectionner une pièce de l’assemblage JHR." if editing
                            else "Sélectionner les profils demandés pour afficher l’aperçu."), 3, True,
        )
        self.report.isFullWidth = True
        if editing:
            from .create_brace_bay import BraceBayForm

            # Fusion ne monte pas de nouveaux onglets après l’ouverture du dialogue.
            self.bay_form = BraceBayForm(command, self.app, self.design, embedded=True)
        self.set_models()
        self.update_visibility()

    def set_models(self):
        family = self.family if self.family_input is None else self.family_input.selectedItem.name
        self.templates = {model.label: model for model in self.models if model.family == family}
        self.choices.listItems.clear()
        for index, label in enumerate(self.templates):
            self.choices.listItems.add(label, index == 0)

    @property
    def template(self):
        return self.templates[self.choices.selectedItem.name]

    def load_edit_target(self):
        from ..lib import assembly_edit
        from . import create_brace_bay

        self.edit_target = None
        self.editing_bay = False
        self.edit_error = ""
        self.loading = True
        try:
            if self.edit_selection.selectionCount:
                entity = self.edit_selection.selection(0).entity
                if create_brace_bay.brace_bay.find_group(entity):
                    self.bay_form.target = None
                    self.bay_form.read_existing(entity)
                    self.editing_bay = True
                    return
                target = assembly_edit.read(self.design, entity)
                self.edit_target = target
                next(item for item in self.family_input.listItems
                     if item.name == target.template.family).isSelected = True
                self.set_models()
                next(item for item in self.choices.listItems
                     if item.name == target.template.label).isSelected = True
                if target.template.key not in self.options:
                    self.build_settings(target.template)
                self.load_edit_values(target)
        except (ValueError, RuntimeError) as error:
            self.edit_target = None
            self.edit_error = str(error)
        finally:
            self.loading = False
            self.update_visibility()

    def load_edit_values(self, target):
        values, _, switches = self.options[target.template.key]
        corners = self.corner_options[target.template.key]
        for key, (checkbox, _) in switches.items():
            checkbox.value = bool(target.parameters_mm.get(key))
        for key, checkbox in corners.items():
            checkbox.value = bool(target.parameters_mm.get(key))
        for _, fields in target.template.groups:
            for field in fields:
                value = target.parameters_mm.get(field.key, field.default)
                control = values[field.key]
                if field.choices:
                    control.listItems.item(int(value)).isSelected = True
                elif field.unit:
                    if value or field.key not in (*switches, *corners):
                        control.value = value * .1
                else:
                    control.value = int(value)
                control.isEnabled = target.writable
        for checkbox, _ in switches.values():
            checkbox.isEnabled = target.writable
        for checkbox in corners.values():
            checkbox.isEnabled = target.writable
        self.alternate.value = self.alternate_end.value = target.alternate

    def build_settings(self, model):
        values, groups, switches, corners = {}, [], {}, {}
        feedback = {}
        for index, (label, fields) in enumerate(model.groups):
            tab = "fixings" if label in FIXING_GROUPS else "options" if label in OPTION_GROUPS else "geometry"
            caption = {"Position": "Déport de la platine", "Angles": "Coins de la platine"}.get(label, label)
            group = self.settings_tabs[tab].children.addGroupCommandInput(f"{model.key}_{index}", caption)
            group.isExpanded = True
            groups.append((tab, group))
            children = group.children
            optional = OPTIONAL_BASE_PARTS.get(label) if model.family == FOOT_FAMILY else None
            if optional:
                title, main_key, _ = optional
                switches[main_key] = (
                    children.addBoolValueInput(f"{model.key}_{main_key}_enabled", title, True, "", False),
                    fields,
                )
            for field in fields:
                key = f"{model.key}_{field.key}"
                name = field.label.removesuffix(" (0 = aucune)").removesuffix(" (0 = aucun)") if optional else field.label
                if label == "Angles" and field.key in CORNER_CHOICES:
                    title, name = CORNER_CHOICES[field.key]
                    corners[field.key] = children.addBoolValueInput(
                        f"{key}_corner_finish", title, True, "", bool(field.default),
                    )
                if field.choices:
                    control = children.addDropDownCommandInput(
                        key, name, core.DropDownStyles.TextListDropDownStyle,
                    )
                    for option, choice in enumerate(field.choices):
                        control.listItems.add(choice, option == int(field.default))
                elif field.unit:
                    default = (field.default or 5) if field.key in corners else field.default
                    if optional and field.key == optional[1]:
                        default = optional[2]
                    elif optional and field.key in ("gusset_chamfer", "flange_gusset_chamfer"):
                        default = 8
                    control = children.addValueInput(
                        key, name, field.unit, core.ValueInput.createByString(f"{default:g} mm"),
                    )
                else:
                    control = children.addIntegerSpinnerCommandInput(
                        key, name, field.min_count, field.max_count, 1, int(field.default),
                    )
                values[field.key] = control
            message = children.addTextBoxCommandInput(f"{model.key}_{index}_error", "", "", 2, True)
            message.isFullWidth = True
            message.isVisible = False
            feedback.update({field.key: message for field in fields})
        self.options[model.key] = (values, groups, switches)
        self.corner_options[model.key] = corners
        self.dimension_feedback[model.key] = feedback

    def change_corner_finish(self, input_id):
        corners = self.corner_options[self.template.key]
        if any(toggle.id == input_id and toggle.value for toggle in corners.values()):
            for toggle in corners.values():
                if toggle.id != input_id and toggle.value:
                    toggle.value = False

    def update_visibility(self):
        if self.bay_form:
            self.bay_form.set_visible(self.editing_bay)
        if self.editing_bay:
            for control in self.settings_tabs.values():
                control.isVisible = False
            self.choices.isVisible = self.alternate.isVisible = self.alternate_end.isVisible = False
            self.role_hint.formattedText = "Auto-contreventement"
            return
        model = self.template
        for index, selection in enumerate(self.selections):
            visible = index < len(model.roles)
            if selection.isVisible != visible:
                selection.isVisible = visible
            selection.setSelectionLimits(int(visible), 1)
        ready = not self.editing or self.edit_target is not None
        if self.role_hint:
            self.role_hint.formattedText = (
                " · ".join(escape(o.name) for o in self.edit_target.occurrences) if self.edit_target
                else "" if self.editing
                else " · ".join(f"{index}. {role}" for index, role in enumerate(model.roles, 1))
            )
        side = model.key in ("shear_plate", "splice_web") or model.key.startswith("gusset_")
        self.choices.isVisible = ready
        self.alternate.isVisible = ready and side
        self.alternate_end.isVisible = ready and model.key.startswith("base_")
        if self.edit_target:
            self.alternate.isEnabled = self.edit_target.writable
            self.alternate_end.isEnabled = False
        if model.key not in self.options:
            self.build_settings(model)
        for key, (_, groups, _) in self.options.items():
            for _, group in groups:
                group.isVisible = key == model.key
        values, groups, switches = self.options[model.key]
        active_tabs = {tab for tab, _ in groups}
        for tab, control in self.settings_tabs.items():
            control.isVisible = ready and tab in active_tabs
        for toggle, fields in switches.values():
            for field in fields:
                values[field.key].isVisible = toggle.value
        for key, toggle in self.corner_options[model.key].items():
            values[key].isVisible = toggle.value
        for key, visible in _dimension_visibility(values):
            values[key].isVisible = visible
        if "plate_position" in values:
            offset = values["offset_x"]
            offset.parentCommandInput.isVisible = offset.isVisible
        if "weld_offset" in values:
            values["weld_offset"].isVisible = values["weld_position"].selectedItem.index == 2

    def plan(self):
        if self.app.activeDocument.creationId != self.creation_id:
            raise ValueError("La conception a changé pendant la commande.")
        if self.editing_bay:
            return self.bay_form.plan()
        if self.editing:
            if not self.edit_target:
                raise ValueError(self.edit_error or "Sélectionner une pièce de l’assemblage JHR.")
            if not self.edit_target.writable:
                raise ValueError(self.edit_target.reason)
        model = self.template
        selection = self.selections[:len(model.roles)]
        if any(s.selectionCount != 1 for s in selection):
            raise ValueError("Sélectionner les profils demandés.")
        values, _, switches = self.options[model.key]
        inactive = {field.key for toggle, fields in switches.values() if not toggle.value for field in fields}
        corners = self.corner_options[model.key]
        inactive.update(key for key, toggle in corners.items() if not toggle.value)
        parameters = {key: 0 for key in (*switches, *corners) if key in inactive}
        hidden = {key for key, visible in _dimension_visibility(values) if not visible}
        for _, fields in model.groups:
            for field in fields:
                if field.key in inactive:
                    continue
                control = values[field.key]
                if not getattr(control, "isValidExpression", True):
                    if field.key in hidden:
                        parameters[field.key] = field.default
                        continue
                    raise assembly_geometry.DimensionError((field.key,), "Vérifier la valeur saisie.")
                value = control.selectedItem.index if field.choices else control.value * (10 if field.unit else 1)
                if (field.key in switches or field.key in corners) and value <= 0:
                    raise assembly_geometry.DimensionError((field.key,), "La cote doit être supérieure à zéro.")
                parameters[field.key] = value
        alternate = ((self.alternate.isVisible and self.alternate.value)
                     or (self.alternate_end.isVisible and self.alternate_end.value))
        if self.editing:
            from ..lib import assembly_edit

            return assembly_edit.evaluate(self.design, self.edit_target, parameters, alternate)
        return assembly_operations.evaluate(
            self.design, model.key, [fusion.Occurrence.cast(s.selection(0).entity) for s in selection],
            parameters, alternate,
        )

    def clear_feedback(self):
        if self.active_feedback and self.active_feedback.isValid:
            self.active_feedback.isVisible = False
        self.active_feedback = None

    def show_error(self, error):
        message = escape(str(error))
        if self.editing_bay:
            self.bay_form.set_status(str(error), error)
            self.report.formattedText = self.bay_form.report.formattedText
            return
        if isinstance(error, assembly_geometry.DimensionError):
            key = self.template.key
            values, _, _ = self.options[key]
            for field in error.keys:
                control = values.get(field)
                if not control or not control.isVisible:
                    continue
                message = f"<b>{escape(control.name)}</b> · {message}"
                self.active_feedback = self.dimension_feedback[key][field]
                self.active_feedback.formattedText = f'<font color="#D43B3B">{message}</font>'
                self.active_feedback.isVisible = True
                break
        self.report.formattedText = f'<font color="#D43B3B">{message}</font>'

    def clear_preview(self):
        self.visibility.restore()
        if self.bay_form:
            self.bay_form.clear_preview()
        if self.graphics and self.graphics.isValid:
            self.graphics.deleteMe()
        self.graphics = None

    def preview(self, plan):
        self.clear_preview()
        if self.editing_bay:
            self.bay_form.preview(plan)
            return
        self.graphics = self.design.rootComponent.customGraphicsGroups.add()
        self.graphics.id = "EI_JHR_ASSEMBLY_PREVIEW"
        plate_preview.draw_plates(self.graphics, plan.plates)
        if self.editing and self.edit_target:
            self.visibility.hide(self.edit_target.group)
        self.app.activeViewport.refresh()


class Changed(core.InputChangedEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        if self.form.loading:
            return
        input_id = args.input.id
        if input_id == "editAssembly":
            self.form.load_edit_target()
            return
        if self.form.editing_bay:
            if input_id == "scalloped":
                self.form.bay_form.show_scallop_depth()
            return
        if input_id == "assemblyFamily":
            self.form.set_models()
        if input_id.endswith("_corner_finish"):
            self.form.change_corner_finish(input_id)
        if input_id in ("assemblyFamily", "type") or input_id.endswith(
            ("_weld_position", "_enabled", "_corner_finish", "_hole_position", "_plate_position"),
        ):
            self.form.update_visibility()


class Validate(core.ValidateInputsEventHandler):
    def __init__(self, form):
        super().__init__()
        self.form = form

    def notify(self, args):
        self.form.clear_feedback()
        try:
            plan = self.form.plan()
            if self.form.editing_bay:
                self.form.bay_form.set_status("Auto-contreventement · Aperçu")
                self.form.report.formattedText = self.form.bay_form.report.formattedText
                args.areInputsValid = True
                return
            self.form.report.formattedText = (
                f"Aperçu · {len(plan.plates)} pièce(s)"
                if plan.plates else "Aucune pièce à créer."
            )
            if plan.base_flush:
                thickness = f"{plan.settings_mm['thickness']:g}".replace(".", ",")
                self.form.report.formattedText += f" · Profil raccourci de {thickness} mm"
            if plan.template.family == FOOT_FAMILY:
                x, y = zip(*plan.plates[0].outline)
                self.form.report.formattedText += f" · Platine {(max(x)-min(x))*10:g} × {(max(y)-min(y))*10:g} mm"
            if plan.brace_gaps_cm:
                gaps = ", ".join(f"{gap*10:.1f}" for gap in plan.brace_gaps_cm)
                self.form.report.formattedText += f" · Jeux à l’appui en mm {gaps}"
            args.areInputsValid = True
        except (ValueError, FileNotFoundError) as error:
            self.form.clear_preview()
            self.form.show_error(error)
            args.areInputsValid = False
        except Exception:
            self.form.clear_preview()
            self.form.app.log("[JHR] Assemblages — préparation\n" + traceback.format_exc(),
                              core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)
            self.form.report.formattedText = "La préparation a échoué. Voir le journal Fusion."
            args.areInputsValid = False


class CommandAction(core.CommandEventHandler):
    def __init__(self, form, action):
        super().__init__()
        self.form, self.action = form, action

    def notify(self, args):
        try:
            if self.action == "destroy":
                self.form.clear_preview()
                _handlers.remove(self.form.handlers)
                self.form.handlers = None
            elif self.action == "activate":
                if self.form.edit_selection.selectionCount and not (self.form.edit_target or self.form.editing_bay):
                    self.form.load_edit_target()
            elif self.action == "preview":
                core.CommandEventArgs.cast(args).isValidResult = False
                self.form.preview(self.form.plan())
            else:
                self.form.clear_preview()
                plan = self.form.plan()
                if self.form.editing_bay:
                    from ..lib import brace_bay

                    brace_bay.reconfigure(self.form.design, self.form.bay_form.target[0], plan)
                elif self.form.editing:
                    from ..lib import assembly_edit

                    assembly_edit.apply(self.form.design, self.form.edit_target, plan)
                else:
                    assembly_operations.create(self.form.design, plan)
        except Exception as error:
            self.form.app.log(f"[JHR] Assemblages — {self.action}\n" + traceback.format_exc(),
                              core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)
            if self.action == "execute":
                args.executeFailed = True
                args.executeFailedMessage = str(error)
                self.form.app.userInterface.messageBox(str(error), "Structure JHR — Création interrompue")
            elif self.action == "preview":
                self.form.clear_preview()
                self.form.report.formattedText = f"Aperçu indisponible · {error}"


class Created(core.CommandCreatedEventHandler):
    def __init__(self, family, editing=False):
        super().__init__()
        self.family, self.editing = family, editing

    def notify(self, args):
        command = args.command
        try:
            form = AssemblyForm(command, self.family, self.editing)
            handlers = [
                (command.inputChanged, Changed(form)), (command.validateInputs, Validate(form)),
                (command.executePreview, CommandAction(form, "preview")),
                (command.execute, CommandAction(form, "execute")),
                (command.destroy, CommandAction(form, "destroy")),
            ]
            if self.editing:
                handlers.append((command.activate, CommandAction(form, "activate")))
            # Fusion retains the event but not its Python callback.
            for event, handler in handlers:
                event.add(handler)
            # The currently open form needs these references until its destroy event.
            _handlers.append(handlers)
            form.handlers = handlers
        except Exception as error:
            app = core.Application.get()
            app.log("[JHR] Assemblages — ouverture du dialogue\n" + traceback.format_exc(),
                    core.LogLevels.ErrorLogLevel, core.LogTypes.FileLogType)
            command.isOKButtonVisible = False
            app.userInterface.messageBox(str(error), "Structure JHR — Dialogue indisponible")


def start():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID)
    commands = (*TOOLS, (EDIT_COMMAND_ID, "Modifier un assemblage",
                         "Retrouver les réglages de l’assemblage depuis l’une de ses pièces.",
                         "assemblages_platines", None))
    for command_id, name, tooltip, icon, family in commands:
        if ui.commandDefinitions.itemById(command_id):
            continue
        definition = ui.commandDefinitions.addButtonDefinition(
            command_id, name, tooltip, str(addin_info.ADDIN_ROOT / "resources" / icon),
        )
        editing = command_id == EDIT_COMMAND_ID
        handler = Created(family, editing)
        definition.commandCreated.add(handler)
        _handlers.append(handler)
        target = ui_layout.panel(ui, ui_layout.MODIFY_PANEL_ID) if editing else panel
        target.controls.addCommand(definition).isPromoted = True


def stop():
    ui = core.Application.get().userInterface
    panel = ui_layout.panel(ui, ui_layout.ASSEMBLY_PANEL_ID)
    for command_id in (*(row[0] for row in TOOLS), EDIT_COMMAND_ID):
        target = ui_layout.panel(ui, ui_layout.MODIFY_PANEL_ID) if command_id == EDIT_COMMAND_ID else panel
        control = target and target.controls.itemById(command_id)
        if control:
            control.deleteMe()
        definition = ui.commandDefinitions.itemById(command_id)
        if definition:
            definition.deleteMe()
    _handlers.clear()
