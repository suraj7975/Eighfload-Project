"""Validate a projected output dict against the field types declared in
the config (or the default schema). Lightweight, dependency-free."""

_TYPE_CHECKS = {
    "string": lambda v: isinstance(v, str),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "object": lambda v: isinstance(v, dict),
    "string[]": lambda v: isinstance(v, list) and all(isinstance(i, str) for i in v),
    "object[]": lambda v: isinstance(v, list) and all(isinstance(i, dict) for i in v),
}


def validate(output, config):
    """Returns list[str] of validation errors (empty list = valid)."""
    errors = []
    fields = config.get("fields", [])
    for f in fields:
        path = f["path"]
        if path not in output:
            if f.get("required"):
                errors.append(f"missing required field '{path}'")
            continue
        value = output[path]
        if value is None:
            if f.get("required"):
                errors.append(f"required field '{path}' is null")
            continue
        expected_type = f.get("type")
        check = _TYPE_CHECKS.get(expected_type)
        if check and not check(value):
            errors.append(f"field '{path}' expected type {expected_type}, got {type(value).__name__}")
    return errors
