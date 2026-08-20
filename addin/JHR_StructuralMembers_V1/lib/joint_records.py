from __future__ import annotations

import json
from dataclasses import dataclass


ATTRIBUTE_GROUP = "EI_JHR_StructuralJoint"
RECORD_PREFIX = "operation_"
RECORD_SCHEMA_VERSION = 2


@dataclass(frozen=True)
class JointRecord:
    name: str
    payload: dict


def next_record_name(existing_names):
    used = set()
    for name in existing_names:
        if not str(name).startswith(RECORD_PREFIX):
            continue
        suffix = str(name)[len(RECORD_PREFIX):]
        if suffix.isdigit():
            used.add(int(suffix))
    index = 1
    while index in used:
        index += 1
    return "{}{:04d}".format(RECORD_PREFIX, index)


def encode_record(payload):
    data = dict(payload)
    data["schema_version"] = RECORD_SCHEMA_VERSION
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def decode_record(name, value):
    if not str(name).startswith(RECORD_PREFIX):
        return None
    try:
        payload = json.loads(str(value))
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    return JointRecord(name=str(name), payload=payload)


def records_from_attributes(attributes):
    records = []
    for attribute in attributes:
        record = decode_record(attribute.name, attribute.value)
        if record:
            records.append(record)
    return tuple(records)
