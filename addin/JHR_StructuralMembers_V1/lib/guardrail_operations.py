"""Lecture des appuis et création du garde-corps dans Fusion."""

import json
import math

import adsk.core as core
import adsk.fusion as fusion

from . import assembly_geometry, assembly_operations, guardrail_fixings, guardrail_layout as layout
from . import joint_geometry as geo, physical_materials, timeline_groups


ATTRIBUTE_GROUP = "EI_JHR_Guardrail"


def _mm(point):
    return geo.scale(point.asArray(), 10.)


def _point(point):
    return core.Point3D.create(*geo.scale(point, .1))


def _line(entity):
    edge = fusion.BRepEdge.cast(entity)
    sketch = fusion.SketchLine.cast(entity)
    line = core.Line3D.cast(edge.geometry) if edge else sketch.worldGeometry if sketch else None
    if not line:
        raise ValueError("Le parcours doit suivre des lignes d'esquisse ou arêtes droites.")
    return _mm(line.startPoint), _mm(line.endPoint)


def _ends(paths):
    result = [_line(entity) for entity in paths]
    if len(result) > 1 and any(layout._dist(result[0][0], end) <= layout.TOL for end in result[1]):
        result[0] = tuple(reversed(result[0]))
    for index in range(1, len(result)):
        start, end = result[index]
        previous = result[index-1][1]
        if layout._dist(end, previous) <= layout.TOL:
            start, end = end, start
        if layout._dist(start, previous) > layout.TOL:
            raise ValueError("Sélectionner les segments dans l'ordre d'un parcours continu.")
        result[index] = start, end
    return result


def _project_to_face(start, end, face, mounting, up):
    if not face or not face.isValid or not face.body.isSolid:
        raise ValueError("L'appui doit être une face d'un corps solide.")
    if not core.Plane.cast(face.geometry):
        raise ValueError("La face d'appui doit être plane.")
    point = face.pointOnFace
    ok, normal = face.evaluator.getNormalAtPoint(point)
    if not ok:
        raise ValueError("La direction extérieure de l'appui est introuvable.")
    normal = geo.normalize(normal.asArray())
    anchor = _mm(point)
    direction = up if mounting == "top" else normal
    factor = geo.dot(direction, normal)
    if factor < 1e-6:
        raise ValueError("Sélectionner le dessus de l'appui pour une pose à la française.")
    if abs(geo.dot(normal, geo.normalize(geo.subtract(end, start)))) > 1e-5:
        raise ValueError("Chaque segment doit suivre la direction de sa face d'appui.")

    def project(p):
        return geo.add(p, geo.scale(direction, geo.dot(geo.subtract(anchor, p), normal)/factor))

    return project(start), project(end), normal


def _check_drill_land(plate, face):
    inside = fusion.PointContainment.PointInsidePointContainment
    normal, u, v = (plate[key] for key in ("normal", "u", "v"))
    occurrence = face.assemblyContext
    inverse = None
    if occurrence:
        inverse = occurrence.transform2.copy()
        if not inverse.invert():
            raise ValueError("Le repère de l’appui n’est pas inversible.")
        face = face.nativeObject
    body = face.body
    for x, y, diameter in plate["holes"]:
        center = geo.add(plate["center"], geo.add(geo.scale(u, x), geo.scale(v, y)))
        for i in range(17):
            theta = i*math.pi/8
            radius = 0. if i == 16 else diameter/2+0.25
            offset = geo.add(geo.scale(u, radius*math.cos(theta)), geo.scale(v, radius*math.sin(theta)))
            point = geo.add(center, offset)
            inner = geo.add(point, geo.scale(normal, -.05))
            q = _point(inner)
            if inverse:
                q.transformBy(inverse)
            if body.pointContainment(q) != inside:
                raise ValueError(f"{plate['name']} : un trou déborde de la matière sur l’appui {plate['segment']+1}.")


def _evaluate(paths, faces, settings, verify_volume=False):
    paths, faces = tuple(paths), tuple(faces)
    if not paths or len(faces) not in (1, len(paths)):
        raise ValueError("Sélectionner la face commune ou une face d'appui par segment.")
    if len(faces) == 1:
        faces *= len(paths)
    cfg = layout._settings(settings)
    ends = _ends(paths)
    axis = cfg["vertical_axis"]
    axes = (axis,)
    if axis == "auto":
        orientation = core.Application.get().preferences.generalPreferences.defaultModelingOrientation
        y_up = core.DefaultModelingOrientations.YUpModelingOrientation
        axes = ("Y", "Z") if orientation == y_up else ("Z", "Y")
    for index, axis in enumerate(axes):
        cfg["vertical_axis"] = axis
        up = layout.VERTICAL_AXES[axis]
        try:
            segments = [_project_to_face(start, end, face, cfg["mounting"], up)
                        for (start, end), face in zip(ends, faces)]
            layout._frames(segments, cfg)
        except ValueError:
            if index == len(axes)-1:
                raise
        else:
            break
    plan = layout.plan_guardrail(segments, cfg)
    for plate in plan["plates"]:
        _check_drill_land(plate, faces[plate["segment"]])
    jobs = guardrail_fixings.prepare(plan, faces, verify_volume) if cfg["drill_support"] else []
    plan["support_holes"] = [dict(diameter_mm=batch.diameter_cm*10, depth_mm=bore.depth_cm*10)
                             for batch in jobs for bore in batch.bores]
    if verify_volume:
        guardrail_fixings.validate_anchors(plan["anchors"], faces)
    return plan, jobs


def evaluate(paths, faces, settings=None):
    """Calcule sans modifier le document et contrôle les appuis des perçages."""
    plan, _ = _evaluate(paths, faces, settings)
    return plan


def _box(manager, center, u, v, width, depth, height):
    obb = core.OrientedBoundingBox3D.create(
        _point(center), core.Vector3D.create(*u), core.Vector3D.create(*v),
        width*.1, depth*.1, height*.1,
    )
    return manager.createBox(obb)


def _difference(manager, target, cutter, label):
    if not manager.booleanOperation(target, cutter, fusion.BooleanTypes.DifferenceBooleanType):
        raise ValueError(f"{label} : Fusion n’a pas pu terminer l’ajustage.")


def _boxes_overlap(a, b):
    return all(lo_a < hi_b and lo_b < hi_a for lo_a, hi_a, lo_b, hi_b in zip(
        a.minPoint.asArray(), a.maxPoint.asArray(), b.minPoint.asArray(), b.maxPoint.asArray(),
    ))


def _member_body(manager, item, start, end, *, outer=False, clearance=0.):
    """Reprend la construction BRep de Fusion Fabrication pour les profils usuels."""
    section = item["section"]
    axis = item["direction"]
    center = geo.scale(geo.add(start, end), .5)
    length = layout._dist(start, end)
    width = section["width_mm"]+2*clearance
    depth = section["depth_mm"]+2*clearance
    wall = section["wall_mm"]
    kind = section["type"]
    if kind in ("round_tube", "round_solid"):
        radius = width*.05
        body = manager.createCylinderOrCone(_point(start), radius, _point(end), radius)
        if outer or kind == "round_solid":
            return body
        core_radius = radius-wall*.1
        core_start = geo.subtract(start, geo.scale(axis, .1))
        core_end = geo.add(end, geo.scale(axis, .1))
        hollow = manager.createCylinderOrCone(_point(core_start), core_radius, _point(core_end), core_radius)
    else:
        body = _box(manager, center, item["u"], item["v"], width, depth, length)
        if outer or kind == "flat":
            return body
        hollow = _box(manager, center, item["u"], item["v"], width-2*wall, depth-2*wall, length+.2)
    _difference(manager, body, hollow, item["name"])
    return body


def _trim(manager, body, point, normal, extent, label):
    basis = min(((1., 0., 0.), (0., 1., 0.), (0., 0., 1.)),
                key=lambda axis: abs(geo.dot(axis, normal)))
    u = geo.normalize(geo.cross(basis, normal))
    v = geo.cross(normal, u)
    center = geo.add(point, geo.scale(normal, extent/2))
    cutter = _box(manager, center, u, v, extent, extent, extent)
    _difference(manager, body, cutter, label)


def _rail_body(manager, rail, *, outer=False, clearance=0.):
    start, end, axis = (rail[key] for key in ("start", "end", "direction"))
    section = rail["section"]
    offset = max(section["width_mm"], section["depth_mm"])+2*clearance
    first, last = rail.get("start_plane"), rail.get("end_plane")
    body = _member_body(manager, rail,
                        geo.subtract(start, geo.scale(axis, offset)) if first else start,
                        geo.add(end, geo.scale(axis, offset)) if last else end,
                        outer=outer, clearance=clearance)
    extent = 4*(layout._dist(start, end)+offset)
    if first:
        _trim(manager, body, start, geo.scale(first, -1.), extent, rail["name"])
    if last:
        _trim(manager, body, end, last, extent, rail["name"])
    return body


def _low_rail_parts(manager, rail, posts, section_index):
    """Coupe la lisse basse entre les faces des poteaux plats."""
    up = posts[0]["direction"]
    direction = rail["direction"]
    run = geo.normalize(geo.subtract(direction, geo.scale(up, geo.dot(direction, up))))
    start, end = (geo.dot(rail[key], run) for key in ("start", "end"))
    intervals = []
    left = start
    for post in posts:
        center = geo.dot(post["start"], run)
        half = post["section"]["depth_mm"]/2
        if center+half <= start or center-half >= end:
            continue
        if center-half-left > layout.TOL:
            intervals.append((left, center-half))
        left = max(left, center+half)
    if end-left > layout.TOL:
        intervals.append((left, end))
    solid = _rail_body(manager, rail)
    extent = 4*(layout._dist(rail["start"], rail["end"])+rail["section"]["width_mm"])
    parts = []
    for index, (lo, hi) in enumerate(intervals, start=1):
        label = f"Lisse basse · tronçon {section_index+1}, pièce {index}"
        body = manager.copy(solid)
        if lo > start+layout.TOL:
            point = geo.add(rail["start"], geo.scale(run, lo-start))
            _trim(manager, body, point, geo.scale(run, -1.), extent, label)
        if hi < end-layout.TOL:
            point = geo.add(rail["start"], geo.scale(run, hi-start))
            _trim(manager, body, point, run, extent, label)
        parts.append((label, body))
    return parts


def _build_bodies(plan):
    manager = fusion.TemporaryBRepManager.get()
    results, cutters = [], []
    for index, rails in enumerate(plan["rails"]):
        group = []
        for rail_index, rail in enumerate(rails):
            if rail["name"] == "Lisse basse" and plan["settings"]["model"] == "barreaude":
                results.extend(_low_rail_parts(manager, rail, plan["posts"], index))
                continue
            name = rail["name"] if len(plan["rails"]) == 1 else f"{rail['name']} · tronçon {index+1}"
            results.append((name, _rail_body(manager, rail)))
            if rail["name"] == "Plinthe":
                continue
            clearance = plan["settings"]["clearance_mm"] if rail_index else 0.
            group.append((rail_index == 0, _rail_body(manager, rail, outer=True, clearance=clearance)))
        cutters.append(group)
    for post in plan["posts"]:
        start, end, axis = (post[key] for key in ("start", "end", "direction"))
        extra = max(post["section"]["width_mm"], post["section"]["depth_mm"])
        tip = post["tip_planes"]
        top = geo.add(end, geo.scale(axis, extra)) if tip else end
        body = _member_body(manager, post, geo.subtract(start, geo.scale(axis, extra)), top)
        extent = 4*(layout._dist(start, top)+extra)
        _trim(manager, body, start, geo.scale(post["foot_normal"], -1.), extent, post["name"])
        for point, normal in tip:
            _trim(manager, body, point, normal, extent, post["name"])
        i = post["segment"]
        bounds = body.boundingBox
        for adjacent in cutters[max(0, i-1):i+2]:
            for handrail, tool in adjacent:
                if not (handrail and tip) and _boxes_overlap(bounds, tool.boundingBox):
                    _difference(manager, body, tool, post["name"])
        results.append((post["name"], body))
    for anchor in plan["anchors"]:
        radius = anchor["diameter_mm"]*.05
        body = manager.createCylinderOrCone(_point(anchor["start"]), radius, _point(anchor["end"]), radius)
        results.append((anchor["name"], body))
    for bar in plan.get("bars", ()):
        start, end, axis = (bar[key] for key in ("start", "end", "direction"))
        section = bar["section"]
        extra = max(section["width_mm"], section["depth_mm"])
        body = _member_body(manager, bar, geo.subtract(start, geo.scale(axis, extra)),
                            geo.add(end, geo.scale(axis, extra)))
        extent = 4*(layout._dist(start, end)+extra)
        _trim(manager, body, start, bar["bottom_normal"], extent, bar["name"])
        _trim(manager, body, end, bar["top_normal"], extent, bar["name"])
        results.append((bar["name"], body))
    for name, body in results:
        if not body or not body.isSolid or body.lumps.count != 1 or body.volume <= 1e-8:
            raise ValueError(f"{name} : l’ajustage ne donne pas un solide unique. Vérifier les sections et les jeux.")
    return results


def _add_solid(parent, name, body, material):
    occurrence = parent.occurrences.addNewComponent(core.Matrix3D.create())
    component = occurrence.component
    component.name = name
    base = component.features.baseFeatures.add()
    if not base.startEdit():
        raise RuntimeError(f"Impossible d'éditer {name}.")
    try:
        raw = component.bRepBodies.add(body, base)
        if not raw:
            raise RuntimeError(f"Impossible de créer le solide de {name}.")
        raw.name = name
        if material:
            raw.material = material
    finally:
        base.finishEdit()
    if base.bodies.count != 1:
        raise RuntimeError(f"{name} doit avoir un corps unique.")
    component.attributes.add(ATTRIBUTE_GROUP, "piece_name", name)
    return occurrence


def _check_existing(design, paths):
    for marker in design.findAttributes(ATTRIBUTE_GROUP, "definition"):
        other = json.loads(marker.value)["paths"]
        if (len(other) == len(paths)
                and all(any(path == entity for token in other for entity in design.findEntityByToken(token))
                        for path in paths)):
            raise ValueError("Un garde-corps Structure JHR utilise déjà ce parcours.")


def create(design, paths, faces, settings=None):
    """Prépare les solides avant l'écriture et enlève le groupe en cas d'échec."""
    _check_existing(design, paths)
    plan, cuts = _evaluate(paths, faces, settings, verify_volume=True)
    path_tokens = [path.entityToken for path in paths]
    face_tokens = [face.entityToken for face in faces]
    bodies = _build_bodies(plan)
    libraries = core.Application.get().materialLibraries
    material = physical_materials.resolve_material(
        libraries, physical_materials.default_choice(
            physical_materials.discover_steel_materials(libraries, design.materials)), design.materials,
    )
    start = timeline_groups.creation_start(design.timeline)
    group = design.rootComponent.occurrences.addNewComponent(core.Matrix3D.create())
    if not group:
        raise RuntimeError("Fusion n’a pas créé le groupe de garde-corps.")
    cut_entities = []
    try:
        component = group.component
        component.name = ("JHR - Garde-corps barreaudé" if plan["settings"]["model"] == "barreaude"
                          else "JHR - Garde-corps acier")
        for name, body in bodies:
            _add_solid(component, name, body, material)
        for plate in plan["plates"]:
            part = assembly_geometry.rectangle(
                plate["name"], geo.scale(plate["center"], .1), plate["u"], plate["v"],
                plate["along_mm"]*.1, plate["across_mm"]*.1, plate["thickness_mm"]*.1,
                [geo.scale(hole, .1) for hole in plate["holes"]],
            )
            assembly_operations._create_plate(component, part, material)
        guardrail_fixings.apply(cuts, cut_entities)
        component.attributes.add(ATTRIBUTE_GROUP, "definition", json.dumps(dict(
            paths=path_tokens, faces=face_tokens,
            settings=plan["settings"], support_features=[entity.entityToken for entity in cut_entities
                                                          if fusion.ExtrudeFeature.cast(entity)],
        )))
    except Exception as error:
        failures = []
        for entity in reversed([group] + cut_entities):
            try:
                if entity and entity.isValid and not entity.deleteMe():
                    failures.append(entity.name)
            except Exception:
                failures.append("opération du garde-corps")
        if failures:
            raise RuntimeError("Retrait incomplet des opérations : " + ", ".join(failures)) from error
        raise
    timeline_groups.group_creation(design.timeline, start, component.name)
    return group, plan


def segment_guardrail(design, selected_post, mode="halves", gap_mm=0., added_thickness_mm=5.,
                      preview=False, **fastener_options):
    """Prépare le tronçonnage au droit d'un poteau Structure JHR."""
    from . import guardrail_segmentation

    return guardrail_segmentation.segment_guardrail(
        design, selected_post, mode, gap_mm, added_thickness_mm, preview=preview, **fastener_options,
    )
