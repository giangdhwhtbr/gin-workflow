import json

def serialize(obj) -> str:
    """
    Deterministically serializes a JSON-compatible Python object according to
    RFC 8785 JSON Canonicalization Scheme (JCS).
    Returns a UTF-8 encoded string.
    """
    if isinstance(obj, dict):
        # Dict keys must be strings. Sort lexicographically by UTF-16 code units.
        # In Python, standard string sorting (lexicographical order) matches UTF-16 code unit order
        # for all characters in the BMP.
        sorted_keys = sorted(obj.keys())
        parts = []
        for k in sorted_keys:
            if not isinstance(k, str):
                raise TypeError("JSON object keys must be strings")
            parts.append(f"{serialize(k)}:{serialize(obj[k])}")
        return "{" + ",".join(parts) + "}"
    
    elif isinstance(obj, list):
        parts = [serialize(item) for item in obj]
        return "[" + ",".join(parts) + "]"
    
    elif isinstance(obj, str):
        # json.dumps with ensure_ascii=False escapes backslashes, double quotes,
        # and control characters (ASCII 0-31) using lowercase hexadecimal strings (e.g. \u000a),
        # leaving all other characters unescaped. This conforms exactly to RFC 8785.
        return json.dumps(obj, ensure_ascii=False)
    
    elif isinstance(obj, bool):
        return "true" if obj else "false"
    
    elif obj is None:
        return "null"
    
    elif isinstance(obj, int) and not isinstance(obj, bool):
        # Python booleans are subclasses of int, so we must check them first.
        return str(obj)
    
    elif isinstance(obj, float):
        # We enforce integer-only numeric fields in our schema, but for completeness,
        # format floats using standard JSON representation.
        return json.dumps(obj)
    
    else:
        raise TypeError(f"Type {type(obj)} is not serializable in JCS")
