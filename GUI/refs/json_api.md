# Modulo: json
# API Ref — json (versione 2.0.9)
# Versione: json==2.0.9

Generato da tools/gen_api_refs.py (deterministico, zero LLM).
Validabile con: .venv/bin/python tools/validate_refs.py <questo file>

## Simboli pubblici

- `JSONDecodeError(msg, doc, pos)`
  - Subclass of ValueError with the following additional properties:
- `JSONDecoder(*, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, strict=True, object_pairs_hook=None)`
  - Simple JSON <https://json.org> decoder
- `JSONEncoder(*, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, sort_keys=False, indent=None, separators=None, default=None)`
  - Extensible JSON <https://json.org> encoder for Python data structures.
- `codecs`
  - codecs -- Python Codec Registry, API and helpers.
- `decoder`
  - Implementation of JSONDecoder
- `detect_encoding(b)`
- `dump(obj, fp, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False, **kw)`
  - Serialize ``obj`` as a JSON formatted stream to ``fp`` (a
- `dumps(obj, *, skipkeys=False, ensure_ascii=True, check_circular=True, allow_nan=True, cls=None, indent=None, separators=None, default=None, sort_keys=False, **kw)`
  - Serialize ``obj`` to a JSON formatted ``str``.
- `encoder`
  - Implementation of JSONEncoder
- `load(fp, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)`
  - Deserialize ``fp`` (a ``.read()``-supporting file-like object containing
- `loads(s, *, cls=None, object_hook=None, parse_float=None, parse_int=None, parse_constant=None, object_pairs_hook=None, **kw)`
  - Deserialize ``s`` (a ``str``, ``bytes`` or ``bytearray`` instance
- `scanner`
  - JSON token scanner

## Firme verificate via inspect

# Firma: `JSONDecodeError(msg, doc, pos)`
# Firma: `JSONDecoder(object_hook, parse_float, parse_int, parse_constant, strict, object_pairs_hook)`
# Firma: `JSONEncoder(skipkeys, ensure_ascii, check_circular, allow_nan, sort_keys, indent, separators, default)`
# Firma: `detect_encoding(b)`
# Firma: `dump(obj, fp, skipkeys, ensure_ascii, check_circular, allow_nan, cls, indent, separators, default, sort_keys, kw)`
# Firma: `dumps(obj, skipkeys, ensure_ascii, check_circular, allow_nan, cls, indent, separators, default, sort_keys, kw)`
# Firma: `load(fp, cls, object_hook, parse_float, parse_int, parse_constant, object_pairs_hook, kw)`
# Firma: `loads(s, cls, object_hook, parse_float, parse_int, parse_constant, object_pairs_hook, kw)`
