import json
from typing import Any


def parse_json_object_payload(raw_payload: str) -> dict[str, Any]:
    parsed_payload = json.loads(raw_payload)
    if not isinstance(parsed_payload, dict):
        raise ValueError("SQS message body must be a JSON object")
    return parsed_payload
