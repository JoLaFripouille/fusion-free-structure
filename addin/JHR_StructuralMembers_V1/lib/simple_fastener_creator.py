"""Solides de présentation pour les vis, écrous et rondelles JHR."""
from __future__ import annotations

import json
import math

from . import bolt_specs, fastener_geometry as geo, timeline_groups


COUNTERSUNK_SOCKET_FLATS_MM = {12: 8., 16: 10., 20: 12., 24: 14.}


def dimensions(diameter_mm, length_mm, grip_cm, projection_mm=5., countersink=None, tapped=False, *,
               head=None, head_washer=None, nut_washer=None):
    diameter = geo._positive(diameter_mm, "Le diamètre")
    length = geo._positive(length_mm, "La longueur sous tête")
    grip = geo._positive(grip_cm, "Le serrage")
    projection = float(projection_mm)
    if not math.isfinite(projection) or projection < 0:
        raise ValueError("Le dépassement doit être positif ou nul et fini.")
    head = head or ("TF" if countersink else "H")
    if bool(countersink) != (head == "TF"):
        raise ValueError("La tête fraisée exige un perçage conique.")
    spec, socket = bolt_specs.modeled_spec(diameter, head)
    head_washer, nut_washer = geo.modeled_washer_options(head, tapped=tapped,
                                                        head_washer=head_washer, nut_washer=nut_washer)
    head_washer_mm = spec.washer_thickness_mm if head_washer else 0.
    nut_washer_mm = spec.washer_thickness_mm if nut_washer else 0.
    nut_height_mm = 0. if tapped else spec.nut_height_mm
    stack_mm = grip * 10 + head_washer_mm + nut_washer_mm + nut_height_mm
    minimum = stack_mm + projection
    if length + .00001 < minimum:
        raise ValueError("Vis trop courte : longueur minimale {:g} mm.".format(minimum))
    values = dict(spec=spec, length_cm=length * .1, grip_cm=grip,
                  washer_cm=spec.washer_thickness_mm * .1, head_height_cm=spec.head_height_mm * .1,
                  head_washer_cm=head_washer_mm * .1, nut_washer_cm=nut_washer_mm * .1,
                  nut_height_cm=nut_height_mm * .1,
                  tip_cm=(length - head_washer_mm) * .1, projection_mm=length - stack_mm,
                  socket_head=socket)
    if socket:
        values.update(head_height_cm=socket.height_mm * .1, socket_flats_mm=socket.flats_mm,
                      socket_depth_cm=socket.depth_mm * .1)
    if countersink:
        head_depth = countersink.head_depth(spec.nominal_diameter_mm * .1)
        rim_height = min(.06, countersink.depth_cm * .2)
        seat_slope = (countersink.opening_diameter_cm - countersink.diameter_cm) / (2 * countersink.depth_cm)
        values.update(head_height_cm=head_depth,
                      rim_radius_cm=countersink.opening_diameter_cm / 2 - rim_height * seat_slope,
                      socket_flats_mm=COUNTERSUNK_SOCKET_FLATS_MM[spec.nominal_diameter_mm],
                      socket_depth_cm=min(head_depth * .6, spec.nominal_diameter_mm * .03))
    return values


def build_shapes(diameter_mm, length_mm, grip_cm, projection_mm=5., countersink=None, tapped=False, *,
                 head=None, head_washer=None, nut_washer=None):
    """Corps temporaires orientés du côté tête vers l'écrou."""
    import adsk.core
    import adsk.fusion

    values = dimensions(diameter_mm, length_mm, grip_cm, projection_mm, countersink, tapped,
                        head=head, head_washer=head_washer, nut_washer=nut_washer)
    spec, grip = values['spec'], values['grip_cm']
    head_washer_cm, nut_washer_cm = values['head_washer_cm'], values['nut_washer_cm']
    manager = adsk.fusion.TemporaryBRepManager.get()
    difference = adsk.fusion.BooleanTypes.DifferenceBooleanType
    union = adsk.fusion.BooleanTypes.UnionBooleanType

    def boolean(body, tool, operation):
        if not manager.booleanOperation(body, tool, operation):
            raise RuntimeError("La construction native de la boulonnerie a échoué.")
        return body

    def cylinder(z0, z1, radius):
        return manager.createCylinderOrCone(adsk.core.Point3D.create(0, 0, z0), radius,
                                            adsk.core.Point3D.create(0, 0, z1), radius)

    def ring(z0, z1):
        return boolean(cylinder(z0, z1, spec.washer_outer_diameter_mm * .05),
                       cylinder(z0 - .001, z1 + .001, spec.washer_inner_diameter_mm * .05), difference)

    def hexagon(z0, z1, flats_mm):
        radius, half_flats = flats_mm / math.sqrt(3) * .1, flats_mm * .05
        body = cylinder(z0, z1, radius)
        big = max(radius * 6, (z1 - z0) * 2, 2.)
        for index in range(6):
            angle = index * math.pi / 3
            normal = adsk.core.Vector3D.create(math.cos(angle), math.sin(angle), 0)
            tangent = adsk.core.Vector3D.create(-normal.y, normal.x, 0)
            centre = adsk.core.Point3D.create(normal.x * (half_flats + big / 2),
                                             normal.y * (half_flats + big / 2), (z0 + z1) / 2)
            box = adsk.core.OrientedBoundingBox3D.create(centre, normal, tangent,
                                                        big, big, z1 - z0 + .02)
            boolean(body, manager.createBox(box), difference)
        return body

    shaft_radius = spec.nominal_diameter_mm * .05
    if countersink:
        head_depth = values['head_height_cm']
        screw = manager.createCylinderOrCone(
            adsk.core.Point3D.create(0, 0, 0), countersink.opening_diameter_cm / 2,
            adsk.core.Point3D.create(0, 0, head_depth), shaft_radius,
        )
        # Tronquer l'enveloppe du cône à rayon constant laisse le dessus
        # affleurant et conserve le contact avec la fraisure sous le pourtour.
        boolean(screw, cylinder(-.001, head_depth + .001, values['rim_radius_cm']),
                adsk.fusion.BooleanTypes.IntersectionBooleanType)
        boolean(screw, cylinder(head_depth - .001, values['tip_cm'], shaft_radius), union)
        boolean(screw, hexagon(-.001, values['socket_depth_cm'], values['socket_flats_mm']), difference)
    else:
        bearing = -head_washer_cm
        top = bearing - values['head_height_cm']
        socket = values['socket_head']
        if socket:
            radius = socket.diameter_mm * .05
            if socket.crown_mm:
                height = values['head_height_cm']
                crown = socket.crown_mm * .05
                # Calotte ajustée aux diamètres du dessus et de l'appui.
                centre = (radius**2 - crown**2 - height**2) / (2 * height)
                screw = manager.createSphere(adsk.core.Point3D.create(0, 0, bearing + centre),
                                             math.hypot(radius, centre))
                boolean(screw, cylinder(top, bearing, radius * 1.1),
                        adsk.fusion.BooleanTypes.IntersectionBooleanType)
            else:
                screw = cylinder(top, bearing, radius)
            boolean(screw, hexagon(top - .001, top + values['socket_depth_cm'], socket.flats_mm), difference)
        else:
            screw = hexagon(top, bearing, spec.head_across_flats_mm)
        boolean(screw, cylinder(bearing, values['tip_cm'], shaft_radius), union)
    parts = dict(vis=screw)
    if not tapped:
        nut_lo = grip + nut_washer_cm
        nut_hi = nut_lo + values['nut_height_cm']
        if nut_washer_cm:
            parts["rondelle_ecrou"] = ring(grip, nut_lo)
        nut = hexagon(nut_lo, nut_hi, spec.nut_across_flats_mm)
        boolean(nut, cylinder(nut_lo - .001, nut_hi + .001, spec.nominal_diameter_mm * .051), difference)
        parts["ecrou"] = nut
    if head_washer_cm:
        parts["rondelle_tete"] = ring(-head_washer_cm, 0)
    if not all(body and body.isSolid and body.lumps.count == 1 for body in parts.values()):
        raise RuntimeError("Une pièce de la boulonnerie n'est pas un solide unique.")
    return parts


def create_modeled_fasteners(design, placements, diameter_mm, length_mm, projection_mm=5.,
                             external_thread=None, thread_depth_cm=0., modeled_thread=False,
                             created_entities=None, *, head=None, assembly=None, ignored_assembly=None,
                             head_washer=None, nut_washer=None, bind_to_hole=None):
    """Insert one undoable batch using existing placement/duplicate conventions.

    Caller owns the explicit document guard and execute transaction. The binding
    callback receives the pose and its occurrence in the root context and returns
    the native joint created there.
    """
    import adsk.core
    import adsk.fusion
    from . import fastener_creator as creator

    root = design.rootComponent
    tapped = external_thread is not None
    head = head or ("TF" if placements and placements[0].countersink else "H")
    head_washer, nut_washer = geo.modeled_washer_options(head, tapped=tapped,
                                                        head_washer=head_washer, nut_washer=nut_washer)
    if any(bool(p.countersink) != (head == "TF") for p in placements):
        raise ValueError("Traiter séparément les perçages ronds ou oblongs et les fraisures.")
    occupied = creator.existing_positions(root, ignored_assembly=ignored_assembly)
    poses = []
    for p in placements:
        if not any(geo.same_position(p, old) for old in tuple(occupied) + tuple(poses)):
            poses.append(p)
    if not poses:
        return dict(created=0, occupied=len(placements), parts=0)
    def configuration_key(pose):
        seat = pose.countersink
        return (round(pose.grip_cm, 6),) + (
            tuple(round(value, 6) for value in (seat.diameter_cm, seat.opening_diameter_cm, seat.depth_cm))
            if seat else ()
        )

    shapes = {}
    for p in poses:
        key = configuration_key(p)
        if key not in shapes:
            shapes[key] = build_shapes(diameter_mm, length_mm, p.grip_cm, projection_mm, p.countersink, tapped,
                                       head=head, head_washer=head_washer, nut_washer=nut_washer)
    head = f"{head}-Taraudage" if tapped else head
    parent = assembly.component if assembly else root
    groups = (creator.assembly_hardware(assembly) if assembly else
              [o for o in root.occurrences if o.component.name.upper() == "VISSERIE"])
    if len(groups) > 1:
        raise ValueError("Plusieurs groupes VISSERIE existent ; choisir un groupe unique.")
    standalone = created_entities is None and assembly is None and not tapped
    timeline = design.timeline if standalone and design.designType == adsk.fusion.DesignTypes.ParametricDesignType else None
    start = timeline_groups.creation_start(timeline)
    group = groups[0] if groups else parent.occurrences.addNewComponent(adsk.core.Matrix3D.create())
    created_group = not groups
    if created_group:
        group.component.name = "VISSERIE"
        if assembly:
            group.component.attributes.add(creator.ATTRIBUTE_GROUP, "assembly_hardware", "1")
            group = group.createForAssemblyContext(assembly)
    job = None
    joints = []
    try:
        job = group.component.occurrences.addNewComponent(adsk.core.Matrix3D.create())
        lot_kind = "VIS" if head == "TF-Taraudage" else "BOULONS"
        job.component.name = "POSE JHR - {} {} M{:g}x{:g}".format(lot_kind, head, diameter_mm, length_mm)
        job_context = job.createForAssemblyContext(group) if bind_to_hole else None
        if bind_to_hole and not job_context:
            raise RuntimeError("Le lot de visserie est introuvable dans le contexte de l’assemblage.")

        def bind(pose, occurrence):
            if not bind_to_hole:
                return
            placed = occurrence.createForAssemblyContext(job_context)
            if not placed:
                raise RuntimeError("La fixation est introuvable dans le contexte de l’assemblage.")
            joint = bind_to_hole(pose, placed)
            if not joint or not joint.isValid:
                raise RuntimeError("La fixation n’a pas pu être liée au perçage.")
            joints.append(joint)

        inv = group.transform2.copy()
        if not inv.invert():
            raise ValueError("Le repère VISSERIE n'est pas inversible.")
        canonical = {}
        for pose in poses:
            key = configuration_key(pose)
            matrix = creator._frame_matrix(pose, inv)
            # Fusion remaps copied placements inside a nested group with a live joint.
            # New occurrences use the requested local transform in that context.
            if not assembly and key in canonical:
                occurrence = job.component.occurrences.addExistingComponent(canonical[key], matrix)
                if not occurrence:
                    raise RuntimeError("La répétition du boulon a échoué.")
                bind(pose, occurrence)
                continue
            occurrence = job.component.occurrences.addNewComponent(matrix)
            if not occurrence:
                raise RuntimeError("La fixation n'a pas pu être créée.")
            component = occurrence.component
            component.name = geo.configuration_name(diameter_mm, length_mm, head, pose.grip_cm,
                                                    head_washer=head_washer, nut_washer=nut_washer)
            component.description = ("Vis pour pièce taraudée." if tapped else
                                     "Pièces séparées sans filetage. Modèle de présentation JHR.")
            feature = None
            if design.designType == adsk.fusion.DesignTypes.ParametricDesignType:
                feature = component.features.baseFeatures.add()
                feature.name = "BOULONNERIE {} - MODELE SIMPLE".format(head)
                if not feature.startEdit():
                    raise RuntimeError("La fonction de base n'a pas pu être ouverte.")
            try:
                for role, shape in shapes[key].items():
                    body = component.bRepBodies.add(shape, feature) if feature else component.bRepBodies.add(shape)
                    if not body:
                        raise RuntimeError("Une pièce de boulonnerie n'a pas pu être ajoutée.")
                    body.name = role
            finally:
                if feature and not feature.finishEdit():
                    raise RuntimeError("La fonction de base n'a pas pu être terminée.")
            if tapped:
                from .tapped_fastener import add_thread

                screw = next(body for body in component.bRepBodies if body.name == "vis")
                shaft = max(
                    (face for face in screw.faces if adsk.core.Cylinder.cast(face.geometry)),
                    key=lambda face: face.area,
                )
                cylinder = adsk.core.Cylinder.cast(shaft.geometry)
                add_thread(shaft, external_thread, thread_depth_cm, at_high_end=cylinder.axis.z > 0,
                           modeled=modeled_thread)
            component.attributes.add(creator.ATTRIBUTE_GROUP, "configuration", json.dumps(dict(
                diameter_mm=diameter_mm, length_mm=length_mm, head=head, grip_cm=pose.grip_cm,
                projection_mm=projection_mm, screws=1, washers=int(head_washer) + int(nut_washer),
                head_washer=head_washer, nut_washer=nut_washer,
                nuts=0 if tapped else 1, model="JHR_tapped" if tapped else "JHR_simple_no_threads",
                separate_parts=True)))
            if not assembly:
                canonical[key] = component
            bind(pose, occurrence)
        if job.component.occurrences.count != len(poses):
            raise RuntimeError("Le nombre de boulons créés ne correspond pas aux positions.")
    except Exception as error:
        failed_joints = []
        for joint in reversed(joints):
            try:
                if joint.isValid and not joint.deleteMe():
                    failed_joints.append(joint)
            except RuntimeError:
                failed_joints.append(joint)
        removed = job is None or job.deleteMe()
        if created_group and removed:
            removed = bool(group.deleteMe())
        if not removed or any(joint.isValid for joint in failed_joints):
            raise RuntimeError("Insertion interrompue ; le nouveau lot n'a pas pu être retiré : {}".format(error)) from error
        raise
    if created_entities is not None:
        created_entities.append(group if created_group else job)
        created_entities.extend(joints)
    timeline_groups.group_creation(timeline, start, job.component.name)
    return dict(created=len(poses), occupied=len(placements) - len(poses),
                parts=sum(len(shapes[configuration_key(p)]) for p in poses))
