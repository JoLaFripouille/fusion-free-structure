from __future__ import annotations

import json
import math
import os
import uuid
from dataclasses import dataclass
from pathlib import Path


SCHEMA_VERSION = 1
SETTINGS_FILENAME = "settings.json"
MM_TO_CM = 0.1
I_H_GROUP = "ih"
L_T_GROUP = "lt"
HOLLOW_GROUP = "hollow"
OTHER_GROUP = "other"
PROFILE_GROUPS = (I_H_GROUP, L_T_GROUP, HOLLOW_GROUP, OTHER_GROUP)

I_H_FAMILIES = frozenset(("IPE", "HEA", "HEB"))
L_T_FAMILIES = frozenset(("Corniere_Egale", "Corniere_Inegale", "Te_Egal"))
HOLLOW_FAMILIES = frozenset(("Tube_Carre", "Tube_Rectangulaire", "Tube_Rond"))


@dataclass(frozen=True)
class DefaultValues:
    straight_joint_ih_gap_mm: float = 0.0
    straight_joint_lt_gap_mm: float = 0.0
    straight_joint_hollow_gap_mm: float = 0.0
    straight_joint_other_gap_mm: float = 0.0
    cope_ih_vertical_mm: float = 1.0
    cope_ih_longitudinal_mm: float = 1.0
    cope_ih_support_mm: float = 1.0
    cope_lt_under_web_mm: float = 1.0
    cope_lt_root_relief_mm: float = 1.0
    cope_lt_longitudinal_mm: float = 1.0
    cope_lt_support_mm: float = 1.0

    def straight_joint_gap_mm(self, family_id):
        group = profile_group(family_id)
        return {
            I_H_GROUP: self.straight_joint_ih_gap_mm,
            L_T_GROUP: self.straight_joint_lt_gap_mm,
            HOLLOW_GROUP: self.straight_joint_hollow_gap_mm,
            OTHER_GROUP: self.straight_joint_other_gap_mm,
        }[group]


def factory_defaults():
    return DefaultValues()


def profile_group(family_id):
    family_id = str(family_id).strip()
    if family_id in I_H_FAMILIES:
        return I_H_GROUP
    if family_id in L_T_FAMILIES:
        return L_T_GROUP
    if family_id in HOLLOW_FAMILIES:
        return HOLLOW_GROUP
    return OTHER_GROUP


def default_data_root():
    appdata = str(os.environ.get("APPDATA", "")).strip()
    if not appdata:
        raise RuntimeError("Le dossier de données utilisateur APPDATA est introuvable.")
    return Path(appdata) / "EI_JHR" / "fusion-free-structure"


def settings_path(data_root=None):
    root = Path(data_root) if data_root is not None else default_data_root()
    return root / SETTINGS_FILENAME


def _distance(value, label):
    if isinstance(value, bool):
        raise ValueError("{} doit être une distance numérique.".format(label))
    try:
        result = float(value)
    except (TypeError, ValueError) as error:
        raise ValueError("{} doit être une distance numérique.".format(label)) from error
    if not math.isfinite(result) or result < 0.0:
        raise ValueError("{} doit être une distance positive ou nulle.".format(label))
    return result


def _payload(values):
    return {
        "schema_version": SCHEMA_VERSION,
        "defaults": {
            "straight_joint": {
                "ih": {"gap_mm": values.straight_joint_ih_gap_mm},
                "lt": {"gap_mm": values.straight_joint_lt_gap_mm},
                "hollow": {"gap_mm": values.straight_joint_hollow_gap_mm},
                "other": {"gap_mm": values.straight_joint_other_gap_mm},
            },
            "cope_ih": {
                "vertical_mm": values.cope_ih_vertical_mm,
                "longitudinal_mm": values.cope_ih_longitudinal_mm,
                "support_mm": values.cope_ih_support_mm,
            },
            "cope_lt": {
                "under_web_mm": values.cope_lt_under_web_mm,
                "root_relief_mm": values.cope_lt_root_relief_mm,
                "longitudinal_mm": values.cope_lt_longitudinal_mm,
                "support_mm": values.cope_lt_support_mm,
            },
        },
    }


def _parsed(payload):
    if not isinstance(payload, dict) or payload.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Le fichier de paramètres utilise une version inconnue.")
    try:
        defaults = payload["defaults"]
        straight = defaults["straight_joint"]
        cope_ih = defaults["cope_ih"]
        cope_lt = defaults["cope_lt"]
        return DefaultValues(
            straight_joint_ih_gap_mm=_distance(
                straight["ih"]["gap_mm"], "Jeu de jonction I/H"
            ),
            straight_joint_lt_gap_mm=_distance(
                straight["lt"]["gap_mm"], "Jeu de jonction cornières/T"
            ),
            straight_joint_hollow_gap_mm=_distance(
                straight["hollow"]["gap_mm"], "Jeu de jonction tubes"
            ),
            straight_joint_other_gap_mm=_distance(
                straight["other"]["gap_mm"], "Jeu de jonction autres profils"
            ),
            cope_ih_vertical_mm=_distance(
                cope_ih["vertical_mm"], "Jeu vertical du grugeage I/H"
            ),
            cope_ih_longitudinal_mm=_distance(
                cope_ih["longitudinal_mm"], "Jeu longitudinal du grugeage I/H"
            ),
            cope_ih_support_mm=_distance(
                cope_ih["support_mm"], "Jeu contre l'appui du grugeage I/H"
            ),
            cope_lt_under_web_mm=_distance(
                cope_lt["under_web_mm"], "Jeu sous l'âme du grugeage cornières/T"
            ),
            cope_lt_root_relief_mm=_distance(
                cope_lt["root_relief_mm"], "Jeu du congé du grugeage cornières/T"
            ),
            cope_lt_longitudinal_mm=_distance(
                cope_lt["longitudinal_mm"],
                "Jeu longitudinal du grugeage cornières/T",
            ),
            cope_lt_support_mm=_distance(
                cope_lt["support_mm"],
                "Jeu contre l'appui du grugeage cornières/T",
            ),
        )
    except (KeyError, TypeError) as error:
        raise ValueError("Le fichier de paramètres est incomplet.") from error


def load(data_root=None):
    path = settings_path(data_root)
    if not path.is_file():
        return factory_defaults()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("Le fichier de paramètres est illisible.") from error
    return _parsed(payload)


def load_or_factory(data_root=None):
    try:
        return load(data_root), ""
    except (OSError, RuntimeError, ValueError) as error:
        return factory_defaults(), str(error)


def save(values, data_root=None):
    validated = _parsed(_payload(values))
    path = settings_path(data_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name("{}.{}.tmp".format(path.name, uuid.uuid4().hex))
    try:
        temporary.write_text(
            json.dumps(_payload(validated), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()
    return path
