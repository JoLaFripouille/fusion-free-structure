"""Mesure le bourrelet et le chanfrein des écrous dans Fusion, sans modifier le dessin."""

import importlib
import math
import sys

import adsk.core as C
import adsk.fusion as F


def run(_context):
    lib = next(name.rsplit(".", 1)[0] for name in sys.modules
               if name.endswith(".addin_info") and "StructuralMembers" in name)
    nut = importlib.import_module(lib + ".rivet_nut")
    geometry = nut.geometry
    origin = (0., 0., 0.)
    axis = (0., 0., 1.)
    p = C.Point3D.create
    count = 0
    for head in nut.HEADS:
        for diameter in nut.DIAMETERS_MM:
            for row in nut._specs(diameter, head):
                grip = row.grip_max_mm * .1
                countersink = None
                if row.countersink_depth_mm:
                    dia = nut._BORE_MM[diameter] * .1
                    deep = row.countersink_depth_mm * .1
                    countersink = geometry.CountersunkHole(origin, axis, dia, dia + 2 * deep, deep)
                position = geometry.Placement(origin, (1., 0., 0.), (0., 1., 0.), axis, grip, countersink)
                result = nut.build_shape(diameter, row, position)
                section = nut._blind_profile(diameter, row, grip)
                assert result.isSolid and result.lumps.count == 1, (head, diameter, row.reference)
                assert abs(result.boundingBox.maxPoint.z - section.tip_station) < 1e-5, ('tip',head,diameter,row.reference,result.boundingBox.maxPoint.z,section)
                tori = [surface for face in result.faces if (surface := C.Torus.cast(face.geometry))]
                assert any(abs(torus.origin.z - section.bulge_station) < 1e-5 and
                           abs(20 * (torus.majorRadius + torus.minorRadius) -
                               nut._MAX_BULGE_MM[diameter]) < 1e-4 for torus in tori), ('torus',head,diameter,row.reference,[(t.origin.z,t.majorRadius,t.minorRadius) for t in tori],section)
                for face in result.faces:
                    cone = C.Cone.cast(face.geometry)
                    if cone and abs(face.boundingBox.maxPoint.z - section.tip_station) < 1e-5:
                        assert abs(abs(cone.halfAngle) - math.pi / 4) < 1e-5, ('angle', head,diameter,row.reference,cone.halfAngle,section)
                        assert abs(face.boundingBox.minPoint.z - (section.tip_station - section.chamfer)) < 1e-5, ('cone bounds', head,diameter,row.reference,face.boundingBox.minPoint.z,section)
                        break
                else:
                    raise AssertionError(('rear chamfer not found', head, diameter))
                radius = section.sleeve_radius + section.bulge_minor_radius
                inside = F.PointContainment.PointInsidePointContainment
                assert result.pointContainment(p(radius - .001, 0., section.bulge_station)) == inside, ('torus envelope',head,diameter,row.reference,section)
                assert result.pointContainment(p(section.sleeve_radius - .25 * section.chamfer, 0.,
                                                  section.tip_station - .25 * section.chamfer)) != inside, ('chamfer material',head,diameter,row.reference,section)
                assert result.pointContainment(p(0., 0., section.tip_station - .01)) != inside, ('bore',head,diameter,row.reference,section)
                count += 1
    print('RIVKLE: {} references, torus and chamfer measured, open bore'.format(count))
