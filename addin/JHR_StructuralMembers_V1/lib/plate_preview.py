"""Aperçu graphique des tôles et de leurs perçages, sans historique Fusion."""
from math import cos, sin, tau

import adsk.core as core
import adsk.fusion as fusion

from . import joint_geometry as geo


def _face(manager, plate, offset):
    def point(xy):
        return core.Point3D.create(*geo.add(plate.point(*xy), offset))

    outline = plate.outline
    arcs = dict(plate.arcs)
    boundary = [
        core.Arc3D.createByThreePoints(point(start), point(arcs[i]), point(end))
        if i in arcs else core.Line3D.create(point(start), point(end))
        for i, (start, end) in enumerate(zip(outline, outline[1:] + outline[:1]))
    ]
    normal = core.Vector3D.create(*plate.normal)
    contours = [boundary, *([core.Circle3D.createByCenter(point((x, y)), normal, diameter / 2)]
                            for x, y, diameter in plate.holes)]
    wires = [manager.createWireFromCurves(curves)[0] for curves in contours]
    if any(not wire for wire in wires):
        raise RuntimeError(f"Contour d’aperçu introuvable pour {plate.name}.")
    face = manager.createFaceFromPlanarWires(wires)
    if not face:
        raise RuntimeError(f"Face d’aperçu introuvable pour {plate.name}.")
    return face


def draw_plates(graphics, plates, *, fill_rgb=(255, 205, 0), edge_rgb=(190, 130, 0)):
    """Dessine les deux faces, les chants et les deux lèvres de chaque trou."""
    manager = fusion.TemporaryBRepManager.get()
    fill = fusion.CustomGraphicsSolidColorEffect.create(core.Color.create(*fill_rgb, 255))
    edge = fusion.CustomGraphicsSolidColorEffect.create(core.Color.create(*edge_rgb, 255))
    for plate in plates:
        offset = geo.scale(plate.normal, plate.thickness_cm)
        for depth in ((0., 0., 0.), offset):
            face = graphics.addBRepBody(_face(manager, plate, depth))
            face.name = f"Face · {plate.name}"
            face.color = fill
            face.setOpacity(0.28, True)
            face.isSelectable = False
        outlines = [plate.display_outline()]
        for x, y, diameter in plate.holes:
            radius = diameter / 2
            outlines.append(tuple((x + radius * cos(step * tau / 24), y - radius * sin(step * tau / 24))
                                  for step in range(24)))
        points, triangles, edges = [], [], []
        for index, outline in enumerate(outlines):
            start = len(points)
            base = [plate.point(x, y) for x, y in outline]
            points.extend(base)
            points.extend(geo.add(point, offset) for point in base)
            count = len(base)
            for i in range(count):
                a, b = start + i, start + (i + 1) % count
                c, d = a + count, b + count
                triangles.extend((a, b, d, a, d, c))
                edges.extend((a, b, c, d))
                if index == 0:
                    edges.extend((a, c))
        coords = fusion.CustomGraphicsCoordinates.create([value for point in points for value in point])
        mesh = graphics.addMesh(coords, triangles, [], [])
        mesh.name = f"Chants · {plate.name}"
        mesh.color = fill
        mesh.setOpacity(0.28, True)
        mesh.isSelectable = False
        lines = graphics.addLines(coords, edges, False)
        lines.name = f"Bords et perçages · {plate.name}"
        lines.color = edge
        lines.weight = 2.0
        lines.isSelectable = False
