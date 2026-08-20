from __future__ import annotations

import adsk.core
import adsk.fusion

from . import cope_geometry


COPE_PREVIEW_RED = (230, 35, 35)
COPE_PREVIEW_EDGE = (130, 0, 0)


class CopePreviewManager:
    """Affiche les deux volumes retirés sans créer de fonction Fusion."""

    def __init__(self):
        self._group = None

    def clear(self):
        if self._group and self._group.isValid:
            self._group.deleteMe()
        self._group = None
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()

    def update(self, root_component, evaluation):
        self.clear()
        group = root_component.customGraphicsGroups.add()
        group.id = "EI_JHR_COPE_PREVIEW"
        self._group = group
        mesh_color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(*COPE_PREVIEW_RED, 255)
        )
        line_color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(*COPE_PREVIEW_EDGE, 255)
        )
        try:
            for volume in evaluation.volumes:
                coordinates, triangles, wires = cope_geometry.volume_mesh(
                    volume,
                    evaluation.origin,
                    evaluation.profile_x_axis,
                    evaluation.profile_y_axis,
                    evaluation.axial_axis,
                )
                graphics_coordinates = adsk.fusion.CustomGraphicsCoordinates.create(
                    coordinates
                )
                mesh = group.addMesh(graphics_coordinates, triangles, [], [])
                mesh.name = "Aperçu rouge — {}".format(volume.name)
                mesh.color = mesh_color
                mesh.setOpacity(0.38, True)
                mesh.isSelectable = False

                lines = group.addLines(graphics_coordinates, wires, False)
                lines.name = "Contour — {}".format(volume.name)
                lines.color = line_color
                lines.weight = 2.0
                lines.isSelectable = False
        except Exception:
            self.clear()
            raise
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()
