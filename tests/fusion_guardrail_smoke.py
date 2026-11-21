"""Essai natif à exécuter sur un document Fusion d'essai sans nom."""

import importlib
import os
import sys
import types
import uuid

import adsk.core as core
import adsk.fusion as fusion


EXPECTED_DOCUMENT_ID = "f70252dd-266d-4b62-a33a-4ceb94634830"
SOURCE_DIR = ""
RUN_FIXINGS = False
FIXTURE_OFFSET_CM = 0.
Y_UP = False


def run(_context):
    app = core.Application.get()
    doc = app.activeDocument
    design = fusion.Design.cast(app.activeProduct)
    assert doc.creationId == EXPECTED_DOCUMENT_ID and not doc.isSaved
    assert app.userInterface.activeCommand == "SelectCommand"
    assert design.timeline.markerPosition == design.timeline.count
    root = design.rootComponent

    if SOURCE_DIR:
        sys.dont_write_bytecode = True
        package = types.ModuleType("jhr_guardrail_smoke_source_" + uuid.uuid4().hex)
        package.__path__ = [os.path.join(SOURCE_DIR, "addin", "JHR_StructuralMembers_V1", "lib")]
        sys.modules[package.__name__] = package
        lib = package.__name__
    else:
        lib = next(name.rsplit(".", 1)[0] for name in sys.modules
                   if name.endswith(".addin_info") and "StructuralMembers" in name)
    mcp = importlib.import_module(lib + ".mcp_operations")
    geo = importlib.import_module(lib + ".joint_geometry")
    P = core.Point3D.create
    V = core.Vector3D.create
    up = (0., 1., 0.) if Y_UP else (0., 0., 1.)
    sideways = geo.cross(up, (1., 0., 0.))
    axis_index = 1 if Y_UP else 2
    transverse_index = 2 if Y_UP else 1
    layout_plane = root.xYConstructionPlane if Y_UP else root.xZConstructionPlane

    def support(name, origin, u, v, length, low, high, thickness=1.2):
        outward = geo.cross(u, v)
        matrix = core.Matrix3D.create()
        matrix.setWithCoordinateSystem(P(*geo.subtract(origin, geo.scale(outward, thickness))),
                                       V(*u), V(*v), V(*outward))
        occurrence = root.occurrences.addNewComponent(matrix)
        component = occurrence.component
        component.name = name
        sketch = component.sketches.add(component.xYConstructionPlane)
        sketch.sketchCurves.sketchLines.addTwoPointRectangle(P(0., low, 0.), P(length, high, 0.))
        feature = component.features.extrudeFeatures.addSimple(
            sketch.profiles.item(0), core.ValueInput.createByReal(thickness),
            fusion.FeatureOperations.NewBodyFeatureOperation,
        )
        sketch.isVisible = False
        assert feature.bodies.count == 1
        world = feature.bodies.item(0).createForAssemblyContext(occurrence)
        face = max(world.faces, key=lambda item: geo.dot(item.pointOnFace.asArray(), outward))
        assert abs(geo.dot(geo.subtract(face.pointOnFace.asArray(), origin), outward)) < .0001
        return face

    def path(sketch, first, last):
        return sketch.sketchCurves.sketchLines.addByTwoPoints(
            sketch.modelToSketchSpace(P(*first)), sketch.modelToSketchSpace(P(*last)),
        )

    prefix = "JHR ESSAI - Garde-corps acier"
    x = (10800. if RUN_FIXINGS else 9600.) + FIXTURE_OFFSET_CM
    first, joint = (x, 0., 0.), (x+140., 0., 0.)
    last = geo.add((x+300., 0., 0.), geo.scale(up, 45.))
    sketch = root.sketches.add(layout_plane)
    sketch.name = prefix + " / palier et rampant"
    along = geo.normalize(geo.subtract(last, joint))
    a = support(prefix+" / dessus palier", first, (1., 0., 0.), sideways, 140., -8., 8.)
    b = support(prefix+" / dessus rampant", joint, along, sideways, geo.length(geo.subtract(last, joint)), -8., 8.)
    top_paths = [path(sketch, first, joint).entityToken, path(sketch, joint, last).entityToken]

    def verify(paths, faces, settings, expected_rails):
        tokens = [face.entityToken for face in faces]
        bodies = [face.body.nativeObject or face.body for face in faces]
        before = [body.volume for body in bodies]
        count = root.occurrences.count
        plan = mcp.create_guardrail(doc.creationId, paths, tokens, settings, preview=True)
        assert plan["settings"]["vertical_axis"] == ("Y" if Y_UP else "Z")
        assert root.occurrences.count == count
        assert len(plan["posts"]) == 4 and len(plan["plates"]) == 4
        expected_support = 16 if settings.get("drill_support") else 0
        expected_anchors = 16 if settings.get("support") == "concrete" else 0
        assert len(plan["support_holes"]) == expected_support and len(plan["anchors"]) == expected_anchors
        assert all(abs(hole["depth_mm"]-12) < .01 for hole in plan["support_holes"])
        result = mcp.create_guardrail(doc.creationId, paths, tokens, settings)
        group = next(fusion.Occurrence.cast(entity) for entity in design.findEntityByToken(result["assembly"])
                     if fusion.Occurrence.cast(entity))
        assert result["posts"] == result["plates"] == 4
        assert result["rails"] == expected_rails and result["holes"] == 16
        assert result["support_holes"] == expected_support and result["anchors"] == expected_anchors
        delta = sum(before) - sum(body.volume for body in bodies)
        assert abs(delta - expected_support*3.141592653589793*.7**2*1.2) < .005, delta
        posts = [part.bRepBodies.item(0) for part in group.childOccurrences
                 if part.component.name.startswith("Poteau")]
        assert len(posts) == len(plan["posts"])
        for body, post in zip(posts, plan["posts"]):
            for point, normal in post["tip_planes"]:
                origin = geo.scale(point, .1)
                assert any(
                    (plane := core.Plane.cast(face.geometry))
                    and abs(geo.dot(plane.normal.asArray(), normal)) > .99999
                    and abs(geo.dot(geo.subtract(face.pointOnFace.asArray(), origin), normal)) < 1e-4
                    for face in body.faces
                ), f"{post['name']} : plan de tête absent"
        plinths = [part for part in group.childOccurrences if part.component.name.startswith("Plinthe")]
        assert len(plinths) == (len(paths) if settings.get("kickplate", True) else 0)
        for part in plinths:
            limits = part.bRepBodies.item(0).boundingBox
            assert abs((limits.maxPoint.asArray()[transverse_index]-limits.minPoint.asArray()[transverse_index])
                       *10-6) < .001
        if settings["mounting"] == "top" and plinths:
            assert abs(plinths[0].bRepBodies.item(0).boundingBox.minPoint.asArray()[axis_index]*10
                       - plan["settings"]["kickplate_clearance_mm"]) < .001
        for part in group.childOccurrences:
            body = part.bRepBodies.item(0)
            assert part.bRepBodies.count == 1 and body.isSolid and body.lumps.count == 1
            if part.component.name.startswith("Platine"):
                assert sum(bool(core.Cylinder.cast(face.geometry)) for face in body.faces) == 4
            if part.component.name.startswith("Ancrage"):
                assert sum(bool(core.Cylinder.cast(face.geometry)) for face in body.faces) == 1
        try:
            mcp.create_guardrail(doc.creationId, paths, tokens, settings)
        except ValueError as exc:
            assert "ce parcours" in str(exc)
        else:
            raise AssertionError("Un doublon de garde-corps a été créé.")
        print(settings["mounting"], result)

    verify(top_paths, [a, b], {"mounting": "top", "drill_support": RUN_FIXINGS}, 6)
    first, last = (x+350., 0., 0.), (x+650., 0., 0.)
    sketch = root.sketches.add(layout_plane)
    sketch.name = prefix + " / pose latérale"
    web = support(prefix+" / âme", first, (1., 0., 0.), up, 300., -16., 0.)
    side_paths = [path(sketch, first, last).entityToken]
    verify(side_paths, [web], {"mounting": "side", "drill_support": RUN_FIXINGS, "kickplate": False}, 2)
    if RUN_FIXINGS:
        first, last = (x+700., 0., 0.), (x+1000., 0., 0.)
        sketch = root.sketches.add(layout_plane)
        sketch.name = prefix + " / ancrages béton"
        slab = support(prefix+" / dalle", first, (1., 0., 0.), sideways, 300., -8., 8., 14.)
        concrete = path(sketch, first, last).entityToken
        verify([concrete], [slab], {"mounting": "top", "support": "concrete"}, 3)
    assert not doc.isSaved
