"""Run with Fusion's Python API, outside a command, in a disposable document.

Not an offline unittest: exercises real DXF import, timeline indices, joints and
recomputation. Never edits or saves the document that was active before the test.
"""
import importlib
import importlib.util
import logging
from pathlib import Path
import sys
import uuid

import adsk.core
import adsk.fusion


def run(_context: str):
    app = adsk.core.Application.get()
    original = app.activeDocument
    assert app.userInterface.activeCommand == "SelectCommand"
    root = Path(__file__).resolve().parents[1] / "addin" / "JHR_StructuralMembers_V1" / "lib"
    package = "jhr_timeline_test_" + uuid.uuid4().hex
    spec = importlib.util.spec_from_file_location(
        package, root / "__init__.py", submodule_search_locations=[str(root)]
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules[package] = module
    spec.loader.exec_module(module)
    builder = importlib.import_module(package + ".member_builder")
    catalog = importlib.import_module(package + ".profile_catalog")
    materials = importlib.import_module(package + ".physical_materials")
    grouping = importlib.import_module(package + ".timeline_groups")
    grouping._LOG.addHandler(logging.StreamHandler(sys.stdout))
    joints = importlib.import_module(package + ".joint_builder")
    doc = app.documents.add(adsk.core.DocumentTypes.FusionDesignDocumentType)
    try:
        doc.name = "JHR_TEST_TIMELINE_TEMPORAIRE"
        design = adsk.fusion.Design.cast(app.activeProduct)
        design.designType = adsk.fusion.DesignTypes.ParametricDesignType
        root_component = design.rootComponent
        skeleton = root_component.sketches.add(root_component.xYConstructionPlane)
        paths = []
        for start, end in (((0, 0), (20, 0)), ((10, -20), (10, 0)),
                           ((40, 0), (60, 0)), ((60, 0), (60, 20))):
            paths.append(skeleton.sketchCurves.sketchLines.addByTwoPoints(
                adsk.core.Point3D.create(*start, 0), adsk.core.Point3D.create(*end, 0)
            ))
        choice = materials.default_choice(materials.discover_steel_materials(
            app.materialLibraries, design.materials
        ))
        material = materials.resolve_material(app.materialLibraries, choice, design.materials)
        profile = catalog.default_profile(catalog.discover_profiles())

        def create(path):
            occurrence = builder.create_member(
                root_component, path, profile, "C", physical_material=material,
                material_choice=choice
            )
            group = occurrence.timelineObject.parentGroup
            assert group and group.name == occurrence.component.name
            assert group.isCollapsed and group.count == 4
            return occurrence

        first = create(paths[0])
        assert not skeleton.timelineObject.parentGroup
        assert paths[0].endSketchPoint.move(adsk.core.Vector3D.create(10, 0, 0))
        assert design.computeAll()
        body = first.component.bRepBodies.item(0)
        assert abs(body.boundingBox.maxPoint.x - body.boundingBox.minPoint.x - 30) < 1e-4
        print("PASS: member group, skeleton excluded, length 200 -> 300 mm")

        def add_operations(occurrence):
            planes = occurrence.component.constructionPlanes
            plane_input = planes.createInput()
            assert plane_input.setByOffset(occurrence.component.xYConstructionPlane,
                                           adsk.core.ValueInput.createByReal(1))
            plane = planes.add(plane_input)
            sketch = occurrence.component.sketches.add(plane)
            return plane, sketch

        adjacent = add_operations(first)
        group = grouping.group_operations(first, adjacent, "Essai adjacent")
        assert group and group.name == first.component.name and group.count == 6
        assert group.isCollapsed
        print("PASS: adjacent extension, collapsed child indices handled")
        second = create(paths[1])
        foreign_group = second.timelineObject.parentGroup
        foreign_group.isCollapsed = False
        marker = design.timeline.markerPosition
        group = grouping.group_operations(first, add_operations(first), "Essai distant")
        assert group and group.name.endswith("Essai distant") and group.isCollapsed
        assert first.timelineObject.parentGroup.count == 6
        assert not foreign_group.isCollapsed
        assert design.timeline.markerPosition > marker  # only the two new features
        print("PASS: non-adjacent operations separate, other expanded group preserved")

        evaluation = joints.evaluate_straight_joint(design, first, second, 0.0)
        created = joints.create_straight_joint(evaluation)
        assert created and all(entity.timelineObject.parentGroup for entity in created)
        assert design.computeAll()
        print("PASS: real straight joint grouped and recomputed")
        third, fourth = create(paths[2]), create(paths[3])
        evaluation = joints.evaluate_miter_joint(design, third, fourth)
        created = joints.create_miter_joint(evaluation)
        assert created and all(entity.timelineObject.parentGroup for entity in created)
        assert design.computeAll()
        print("PASS: real miter grouped and recomputed")

        def check_health(item):
            if item.isGroup:
                for i in range(item.count):
                    check_health(item.item(i))
            else:
                assert item.healthState not in (
                    adsk.fusion.FeatureHealthStates.ErrorFeatureHealthState,
                    adsk.fusion.FeatureHealthStates.WarningFeatureHealthState,
                ), (item.name, item.errorOrWarningMessage)

        for index in range(design.timeline.count):
            check_health(design.timeline.item(index))
        fourth.timelineObject.parentGroup.isCollapsed = False
        grouping.release_member_group(fourth)
        assert not fourth.timelineObject.parentGroup
        single_entities = add_operations(third)[:1]
        single = grouping.group_operations(third, single_entities, "Opération seule")
        assert single is None and single_entities[0].isValid
        print("PASS: isolated single operation retained (Fusion requires two items)")
        print("PASS: native timeline health and non-destructive ungrouping")
        print("FUSION_TIMELINE_SMOKE_PASS", app.version)
    finally:
        doc.close(False)  # only this test's disposable document
        if original and original.isValid:
            original.activate()
