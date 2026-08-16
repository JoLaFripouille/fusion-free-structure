from __future__ import annotations

import json
from pathlib import Path


ADDIN_ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ADDIN_ROOT / "JHR_StructuralMembers_V1.manifest"


def _read_version():
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    version = str(manifest.get("version", "")).strip()
    if not version:
        raise ValueError("La version du complément est absente du manifeste.")
    return version


VERSION = _read_version()
DISPLAY_NAME = "Profil acier V{}".format(VERSION)
LOG_PREFIX = "[EI_JHR V{}]".format(VERSION)
