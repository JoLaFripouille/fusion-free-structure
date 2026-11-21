import traceback

import adsk.core
import adsk.fusion

from .commands import (
    connect_purlins,
    copy_assembly,
    create_assembly,
    create_brace_bay,
    create_columns,
    create_cope,
    create_guardrail,
    create_joint,
    create_members,
    inspect_assembly,
    inspect_member,
    manage_custom_profiles,
    manage_settings,
    place_bolts,
    preview_angle_cleat,
    remove_assembly,
    segment_guardrail,
)
from .lib import addin_info, structural_materials, ui_layout


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        design = adsk.fusion.Design.cast(app.activeProduct)
        if design:
            result = structural_materials.ensure_required_materials(
                design,
                app.materialLibraries,
            )
            app.log(
                "{} Matériaux EI_JHR: {} existant(s), {} créé(s)."
                .format(
                    addin_info.LOG_PREFIX,
                    len(result.existing_names),
                    len(result.created_names),
                )
            )
        ui_layout.start(ui)
        create_members.start()
        create_columns.start()
        create_guardrail.start()
        segment_guardrail.start()
        create_joint.start()
        create_cope.start()
        preview_angle_cleat.start()
        create_assembly.start()
        create_brace_bay.start()
        connect_purlins.start()
        copy_assembly.start()
        remove_assembly.start()
        place_bolts.start()
        inspect_assembly.start()
        inspect_member.start()
        manage_custom_profiles.start()
        manage_settings.start()
    except Exception:
        if ui:
            ui.messageBox(
                "Échec du démarrage de {}:\n{}"
                .format(addin_info.DISPLAY_NAME, traceback.format_exc())
            )


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        manage_settings.stop()
        place_bolts.stop()
        inspect_assembly.stop()
        manage_custom_profiles.stop()
        inspect_member.stop()
        preview_angle_cleat.stop()
        remove_assembly.stop()
        copy_assembly.stop()
        connect_purlins.stop()
        create_brace_bay.stop()
        create_assembly.stop()
        create_cope.stop()
        create_joint.stop()
        segment_guardrail.stop()
        create_guardrail.stop()
        create_columns.stop()
        create_members.stop()
        ui_layout.stop(ui)
    except Exception:
        if ui:
            ui.messageBox(
                "Échec de l'arrêt de {}:\n{}"
                .format(addin_info.DISPLAY_NAME, traceback.format_exc())
            )
