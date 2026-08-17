from __future__ import annotations

import adsk.core
import adsk.fusion

from . import joint_geometry


CUT_PREVIEW_ORANGE = (255, 140, 0)
CUT_PREVIEW_EDGE = (180, 55, 0)


class JointPreviewManager:
    """Affiche uniquement le plan de coupe, sans créer d'entité CAO."""

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
        points = joint_geometry.plane_square(
            evaluation.cut_point,
            evaluation.preview_normal,
            evaluation.preview_half_size_cm,
        )
        coordinates = [value for point in points for value in point]
        graphics_coordinates = adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
        group = root_component.customGraphicsGroups.add()
        group.id = "EI_JHR_JOINT_PREVIEW"
        self._group = group
        try:
            mesh = group.addMesh(
                graphics_coordinates,
                [0, 1, 2, 0, 2, 3],
                [],
                [],
            )
            mesh.name = "Aperçu du plan de coupe de jonction"
            mesh.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
                adsk.core.Color.create(*CUT_PREVIEW_ORANGE, 255)
            )
            mesh.setOpacity(0.35, True)
            mesh.isSelectable = False

            lines = group.addLines(
                graphics_coordinates,
                [0, 1, 1, 2, 2, 3, 3, 0],
                False,
            )
            lines.name = "Contour du plan de coupe de jonction"
            lines.color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
                adsk.core.Color.create(*CUT_PREVIEW_EDGE, 255)
            )
            lines.weight = 2.0
            lines.isSelectable = False
        except Exception:
            self.clear()
            raise

        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()
