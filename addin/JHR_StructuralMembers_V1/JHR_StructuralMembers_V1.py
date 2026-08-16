import traceback

import adsk.core

from .commands import create_members


def run(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        create_members.start()
    except Exception:
        if ui:
            ui.messageBox("Échec du démarrage de JHR Structural Members V1:\n{}".format(traceback.format_exc()))


def stop(context):
    ui = None
    try:
        app = adsk.core.Application.get()
        ui = app.userInterface
        create_members.stop()
    except Exception:
        if ui:
            ui.messageBox("Échec de l'arrêt de JHR Structural Members V1:\n{}".format(traceback.format_exc()))
