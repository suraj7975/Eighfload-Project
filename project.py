"""Projection layer. Takes one canonical profile (internal record) and a
runtime config, and produces the requested output shape. Keeps a clean
separation: this module never mutates the canonical record, only reads it.

Config shape (see assignment example):
{
  "fields": [
     {"path": "full_name", "type": "string", "required": true},
     {"path": "primary_email", "from": "emails[0]", "type": "string", "required": true},
     {"path": "phone", "from": "phones[0]", "type": "string", "normalize": "E164"},
     {"path": "skills", "from": "skills[].name", "type": "string[]", "normalize": "canonical"}
  ],
  "include_confidence": true,
  "include_provenance": false,
  "on_missing": "null" | "omit" | "error"
}
"""

DEFAULT_CONFIG = {
    "fields": [
        {"path": "candidate_id", "from": "candidate_id", "type": "string", "required": True},
        {"path": "full_name", "from": "full_name", "type": "string"},
        {"path": "emails", "from": "emails", "type": "string[]"},
        {"path": "phones", "from": "phones", "type": "string[]"},
        {"path": "location", "from": "location", "type": "object"},
        {"path": "links", "from": "links", "type": "object"},
        {"path": "headline", "from": "headline", "type": "string"},
        {"path": "years_experience", "from": "years_experience", "type": "number"},
        {"path": "skills", "from": "skills", "type": "object[]"},
        {"path": "experience", "from": "experience", "type": "object[]"},
        {"path": "education", "from": "education", "type": "object[]"},
    ],
    "include_confidence": True,
    "include_provenance": True,
    "on_missing": "null",
}


class MissingRequiredFieldError(Exception):
    pass


def _resolve_path(profile, path_expr):
    """Resolve a small subset of dotted/indexed/wildcard paths, e.g.
    'emails[0]', 'skills[].name', 'location.city'."""
    if path_expr.endswith("[].name"):
        base = path_expr[: -len("[].name")]
        items = profile.get(base)
        if not items:
            return None
        return [it.get("name") for it in items if isinstance(it, dict) and "name" in it]

    if "[" in path_expr and path_expr.endswith("]"):
        base, idx_str = path_expr[:-1].split("[")
        items = profile.get(base)
        if not items:
            return None
        try:
            idx = int(idx_str)
        except ValueError:
            return None
        return items[idx] if -len(items) <= idx < len(items) else None

    parts = path_expr.split(".")
    cur = profile
    for p in parts:
        if cur is None:
            return None
        cur = cur.get(p) if isinstance(cur, dict) else None
    return cur


def _apply_normalize(value, normalize):
    if normalize is None or value is None:
        return value
    if normalize == "E164":
        return value  # already E.164 from the normalization stage
    if normalize == "canonical":
        return value  # skills already canonicalized upstream
    return value


def project(profile, config=None):
    """Returns (output_dict, warnings:list[str])."""
    cfg = config or DEFAULT_CONFIG
    fields = cfg.get("fields", DEFAULT_CONFIG["fields"])
    on_missing = cfg.get("on_missing", "null")
    out = {}
    warnings = []

    for f in fields:
        path = f["path"]
        from_expr = f.get("from", path)
        required = f.get("required", False)
        normalize = f.get("normalize")

        value = _resolve_path(profile, from_expr)
        value = _apply_normalize(value, normalize)

        is_missing = value is None or value == [] or value == {}
        if is_missing:
            if required:
                if on_missing == "error":
                    raise MissingRequiredFieldError(f"required field '{path}' is missing")
                warnings.append(f"required field '{path}' is missing")
            if on_missing == "omit" and not required:
                continue
            out[path] = None if on_missing != "omit" else None
        else:
            out[path] = value

    if cfg.get("include_confidence", True):
        out["overall_confidence"] = profile.get("overall_confidence")
    if cfg.get("include_provenance", True):
        out["provenance"] = profile.get("provenance")

    return out, warnings
