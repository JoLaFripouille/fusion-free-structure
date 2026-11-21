"""Préparation des perçages traversants d'un support de garde-corps."""

import math
from dataclasses import dataclass, field

import adsk.core as core
import adsk.fusion as fusion

from . import angle_cleat_creator, joint_geometry as geo


END_TOLERANCE_CM = .003


@dataclass
class Bore:
    center: tuple
    depth_cm: float


@dataclass
class DrillBatch:
    entry: object
    axis: tuple
    diameter_cm: float
    bores: list = field(default_factory=list)


def centers(plate):
    """Axes des fixations en millimètres, sur la face d'appui."""
    for u, v, _ in plate["holes"]:
        yield geo.add(plate["center"], geo.add(geo.scale(plate["u"], u), geo.scale(plate["v"], v)))


def _native_frame(face):
    native = face.nativeObject or face
    transform = None
    if occurrence := face.assemblyContext:
        transform = occurrence.transform2.copy()
        if not transform.invert():
            raise ValueError("Le repère natif de l'appui est introuvable.")
    return native, transform


def _coordinates(arr, transform, direction=False):
    cls = core.Vector3D if direction else core.Point3D
    value = cls.create(*arr)
    if transform and not value.transformBy(transform):
        raise ValueError("Le repère du perçage ne peut pas être converti.")
    return value.asArray()


def _exit_planes(entry, axis):
    result = []
    for face in entry.body.faces:
        if face == entry or not core.Plane.cast(face.geometry):
            continue
        point = face.pointOnFace
        ok, raw = face.evaluator.getNormalAtPoint(point)
        if ok and geo.dot(raw.asArray(), axis) > 1.-1e-6:
            result.append((point.asArray(), raw.asArray()))
    return result


def _solid_bore(manager, stock, center, axis, radius, measured):
    """Prouve que le cylindre ne traverse qu'une paroi pleine, même dans un tube."""
    start = geo.subtract(center, geo.scale(axis, END_TOLERANCE_CM))
    end = geo.add(center, geo.scale(axis, measured+END_TOLERANCE_CM))
    tool = manager.createCylinderOrCone(core.Point3D.create(*start), radius,
                                        core.Point3D.create(*end), radius)
    sample = manager.copy(stock)
    if not tool or not sample or not manager.booleanOperation(sample, tool, fusion.BooleanTypes.IntersectionBooleanType):
        return False
    expected = math.pi*radius**2*measured
    return sample.lumps.count == 1 and abs(sample.volume-expected) <= max(1e-5, expected*1e-5)


def _exit_depth(stock, center, axis, planes):
    inside = fusion.PointContainment.PointInsidePointContainment
    outside = fusion.PointContainment.PointOutsidePointContainment
    candidates = []
    for point, normal in planes:
        depth = geo.dot(geo.subtract(point, center), normal)/geo.dot(axis, normal)
        if depth > END_TOLERANCE_CM:
            near = core.Point3D.create(*geo.add(center, geo.scale(axis, depth-END_TOLERANCE_CM)))
            far = core.Point3D.create(*geo.add(center, geo.scale(axis, depth+END_TOLERANCE_CM)))
            if stock.pointContainment(near) == inside and stock.pointContainment(far) == outside:
                candidates.append(depth)
    return min(candidates, default=None)


def prepare(plan, faces, verify_volume=False):
    """Prépare les positions et mesure la première paroi plane pour chaque trou."""
    jobs = []
    manager = fusion.TemporaryBRepManager.get() if verify_volume else None
    frames = []
    for face in faces:
        native, transform = _native_frame(face)
        component = native.body.parentComponent
        root = component.parentDesign.rootComponent
        if component != root and root.allOccurrencesByComponent(component).count != 1:
            raise ValueError("L'appui est instancié plusieurs fois. Les perçages modifieraient toutes ses occurrences.")
        frames.append((native, transform))
    dia = plan["settings"]["hole_diameter_mm"]*.1
    for plate in plan["plates"]:
        entry, transform = frames[plate["segment"]]
        axis = geo.scale(_coordinates(plate["normal"], transform, direction=True), -1.)
        axis = geo.normalize(axis)
        planes = _exit_planes(entry, axis)
        for world in centers(plate):
            center = _coordinates(geo.scale(world, .1), transform)
            depth = _exit_depth(entry.body, center, axis, planes)
            if depth is None or (manager and not _solid_bore(manager, entry.body, center, axis, dia/2, depth)):
                raise ValueError(f"{plate['name']} : le trou Ø{dia*10:g} doit traverser une seule paroi à sortie plane.")
            batch = next((batch for batch in jobs if batch.entry == entry
                          and abs(batch.bores[0].depth_cm-depth) < 1e-4), None)
            if batch is None:
                batch = DrillBatch(entry, axis, dia)
                jobs.append(batch)
            if any(geo.length(geo.subtract(center, bore.center)) <= dia for bore in batch.bores):
                raise ValueError("Deux trous du support se recoupent. Écarter leurs axes avant de percer.")
            batch.bores.append(Bore(center, depth))
    return jobs


def validate_anchors(anchors, faces):
    if not anchors:
        return
    manager = fusion.TemporaryBRepManager.get()
    frames = [_native_frame(face) for face in faces]
    for anchor in anchors:
        face, transform = frames[anchor["segment"]]
        start = _coordinates(geo.scale(anchor["start"], .1), transform)
        end = _coordinates(geo.scale(anchor["center"], .1), transform)
        radius = anchor["diameter_mm"]*.05
        tool = manager.createCylinderOrCone(core.Point3D.create(*start), radius,
                                            core.Point3D.create(*end), radius)
        sample = manager.copy(face.body)
        expected = math.pi*radius**2*geo.length(geo.subtract(end, start))
        if (not tool or not sample or not manager.booleanOperation(sample, tool, fusion.BooleanTypes.IntersectionBooleanType)
                or sample.lumps.count != 1 or abs(sample.volume-expected) > max(1e-5, expected*1e-5)):
            raise ValueError(f"{anchor['name']} : la tige dépasse de l’enveloppe du support béton.")


def _check_bores(body, batch):
    cylinders = []
    for face in body.faces:
        cylinder = core.Cylinder.cast(face.geometry)
        if (not cylinder or abs(cylinder.radius-batch.diameter_cm/2) > 1e-4
                or abs(geo.dot(cylinder.axis.asArray(), batch.axis)) < 1.-1e-6):
            continue
        ends = [circle.center.asArray() for edge in face.edges if (circle := core.Circle3D.cast(edge.geometry))]
        if len(ends) == 2:
            cylinders.append((cylinder.origin.asArray(), ends))
    for bore in batch.bores:
        for origin, ends in cylinders:
            if geo.length(geo.cross(geo.subtract(origin, bore.center), batch.axis)) > 1e-4:
                continue
            actual = sorted(geo.dot(geo.subtract(end, bore.center), batch.axis) for end in ends)
            if abs(actual[0]) < 1e-4 and abs(actual[1]-bore.depth_cm) < 1e-4:
                break
        else:
            raise RuntimeError("Un trou du support ne débouche pas aux deux portées calculées.")


def apply(jobs, created):
    """Crée les perçages natifs et retrouve les deux bords de chaque débouché."""
    checked = []
    for batch in jobs:
        entry = batch.entry
        if not entry.isValid:
            raise ValueError("La face d'appui a changé pendant le perçage.")
        body = entry.body
        component = body.parentComponent
        sketch = component.sketches.add(entry)
        created.append(sketch)
        sketch.name = "JHR · Axes de perçage du garde-corps"
        profiles = angle_cleat_creator._add_cut_circles(
            sketch, [bore.center for bore in batch.bores], batch.diameter_cm,
        )
        extrudes = component.features.extrudeFeatures
        cut = extrudes.createInput(profiles, fusion.FeatureOperations.CutFeatureOperation)
        normal = sketch.xDirection.crossProduct(sketch.yDirection).asArray()
        side = (fusion.ExtentDirections.PositiveExtentDirection if geo.dot(normal, batch.axis) > 0
                else fusion.ExtentDirections.NegativeExtentDirection)
        value = core.ValueInput.createByReal(max(bore.depth_cm for bore in batch.bores)+END_TOLERANCE_CM)
        if not cut.setOneSideExtent(fusion.DistanceExtentDefinition.create(value), side):
            raise RuntimeError("Fusion refuse la profondeur des perçages du support.")
        cut.participantBodies = [body]
        feature = extrudes.add(cut)
        if not feature:
            raise RuntimeError("Fusion n’a pas créé les perçages du support.")
        created.append(feature)
        feature.name = f"JHR · Garde-corps Ø{10*batch.diameter_cm:g}"
        sketch.isVisible = False
        _check_bores(body, batch)
        checked.append((body, batch))
    for body, batch in checked:
        _check_bores(body, batch)
