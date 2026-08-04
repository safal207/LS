"""JSON Schema validation and CLI for CrossThreadEvent v0.1."""

from __future__ import annotations

import argparse
import json
from importlib.resources import files
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator

from .cross_thread import CrossThreadEvent


def load_schema() -> Mapping[str, Any]:
    schema_path = files("ls_agent_trust.schemas").joinpath(
        "cross-thread-event-v0.1.schema.json"
    )
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_event_document(document: Mapping[str, Any]) -> CrossThreadEvent:
    validator = Draft202012Validator(load_schema())
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        details = "; ".join(
            f"{'.'.join(map(str, error.path)) or '<root>'}: {error.message}"
            for error in errors
        )
        raise ValueError(f"CrossThreadEvent schema validation failed: {details}")
    return CrossThreadEvent.from_dict(document)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("event", type=Path, help="Path to a CrossThreadEvent JSON file")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> None:
    args = parse_args(argv)
    document = json.loads(args.event.read_text(encoding="utf-8"))
    event = validate_event_document(document)
    print(
        json.dumps(
            {
                "valid": True,
                "event_id": event.event_id,
                "event_type": event.event_type.value,
                "subject": event.subject,
            },
            indent=2,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
