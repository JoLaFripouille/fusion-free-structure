from __future__ import annotations

import adsk.core
import adsk.fusion

from . import path_frames, preview_geometry, rotation


PREVIEW_YELLOW = (255, 205, 0)


def _vector_tuple(vector):
    return (vector.x, vector.y, vector.z)


def _point_tuple(point):
    return (point.x, point.y, point.z)


def _frames_for_curve(curve):
    sample_count = 2
    if adsk.fusion.SketchArc.cast(curve):
        sample_count = max(12, min(64, int(curve.length / 5.0) + 2))
    return [
        (_point_tuple(point), _vector_tuple(x_axis), _vector_tuple(y_axis))
        for point, x_axis, y_axis in path_frames.frames_for_curve(
            curve,
            sample_count,
        )
    ]


class PreviewManager:
    """Gère un aperçu graphique sans entité ni historique Fusion."""

    def __init__(self):
        self._groups = []
        self._profile_contours = None
        self._profile_key = None

    def clear(self):
        for group in reversed(self._groups):
            if group and group.isValid:
                group.deleteMe()
        self._groups.clear()
        app = adsk.core.Application.get()
        if app and app.activeViewport:
            app.activeViewport.refresh()

    def update(
        self,
        root_component,
        curves,
        profile,
        anchor_code,
        rotation_radians=0.0,
        flip_x=False,
        flip_y=False,
    ):
        self.clear()
        if not curves:
            return
        profile_key = (str(profile.dxf_path), anchor_code)
        if self._profile_contours is None or self._profile_key != profile_key:
            self._profile_contours = preview_geometry.tessellate_profile_contours_cm(
                profile.dxf_path,
                anchor_mm=profile.anchor_mm(anchor_code),
            )
            self._profile_key = profile_key
        oriented_contours = rotation.orient_contours(
            self._profile_contours,
            rotation_radians,
            flip_x,
            flip_y,
        )

        mesh_color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(*PREVIEW_YELLOW, 255)
        )
        line_color = adsk.fusion.CustomGraphicsSolidColorEffect.create(
            adsk.core.Color.create(190, 130, 0, 255)
        )

        try:
            for curve in curves:
                frames = _frames_for_curve(curve)
                group = root_component.customGraphicsGroups.add()
                group.id = "EI_JHR_PROFILE_PREVIEW"
                self._groups.append(group)

                for contour in oriented_contours:
                    coordinates, triangles = preview_geometry.build_swept_side_mesh(
                        contour,
                        frames,
                    )
                    graphics_coordinates = adsk.fusion.CustomGraphicsCoordinates.create(coordinates)
                    mesh = group.addMesh(graphics_coordinates, triangles, [], [])
                    mesh.name = "Aperçu {} ancrage {} rotation {} deg miroirs X={} Y={}".format(
                        profile.designation,
                        anchor_code,
                        rotation.format_degrees(rotation_radians),
                        flip_x,
                        flip_y,
                    )
                    mesh.color = mesh_color
                    mesh.setOpacity(0.28, True)
                    mesh.isSelectable = False

                    wire_indices = preview_geometry.build_wire_indices(
                        len(contour),
                        len(frames),
                    )
                    lines = group.addLines(graphics_coordinates, wire_indices, False)
                    lines.name = "Contour aperçu {} ancrage {} rotation {} deg miroirs X={} Y={}".format(
                        profile.designation,
                        anchor_code,
                        rotation.format_degrees(rotation_radians),
                        flip_x,
                        flip_y,
                    )
                    lines.color = line_color
                    lines.weight = 2.0
                    lines.isSelectable = False
        except Exception:
            self.clear()
            raise

        app = adsk.core.Application.get()
        app.activeViewport.refresh()
