# Modulo: csv
# API Ref — csv (versione 1.0)
# Versione: csv==1.0

Generato da tools/gen_api_refs.py (deterministico, zero LLM).
Validabile con: .venv/bin/python tools/validate_refs.py <questo file>

## Simboli pubblici

- `Dialect()`
  - Describe a CSV dialect.
- `DictReader(f, fieldnames=None, restkey=None, restval=None, dialect='excel', *args, **kwds)`
- `DictWriter(f, fieldnames, restval='', extrasaction='raise', dialect='excel', *args, **kwds)`
- `Error`
  - Common base class for all non-exit exceptions.
- `QUOTE_ALL`
  - int([x]) -> integer
- `QUOTE_MINIMAL`
  - int([x]) -> integer
- `QUOTE_NONE`
  - int([x]) -> integer
- `QUOTE_NONNUMERIC`
  - int([x]) -> integer
- `QUOTE_NOTNULL`
  - int([x]) -> integer
- `QUOTE_STRINGS`
  - int([x]) -> integer
- `Sniffer()`
  - "Sniffs" the format of a CSV file (i.e. delimiter, quotechar)
- `StringIO(initial_value='', newline='\n')`
  - Text I/O implementation using an in-memory buffer.
- `excel()`
  - Describe the usual properties of Excel-generated CSV files.
- `excel_tab()`
  - Describe the usual properties of Excel-generated TAB-delimited files.
- `field_size_limit`
  - Sets an upper limit on parsed fields.
- `get_dialect(name)`
  - Return the dialect instance associated with name.
- `list_dialects()`
  - Return a list of all known dialect names.
- `reader(iterable, /, dialect='excel', **fmtparams)`
  - Return a reader object that will process lines from the given iterable.
- `register_dialect(name, /, dialect='excel', **fmtparams)`
  - Create a mapping from a string name to a CVS dialect.
- `types`
  - Define names for built-in types that aren't directly accessible as a builtin.
- `unix_dialect()`
  - Describe the usual properties of Unix-generated CSV files.
- `unregister_dialect(name)`
  - Delete the name/dialect mapping associated with a string name.
- `writer(fileobj, /, dialect='excel', **fmtparams)`
  - Return a writer object that will write user data on the given file object.

## Firme verificate via inspect

# Firma: `Dialect()`
# Firma: `DictReader(f, fieldnames, restkey, restval, dialect, args, kwds)`
# Firma: `DictWriter(f, fieldnames, restval, extrasaction, dialect, args, kwds)`
# Firma: `Sniffer()`
# Firma: `StringIO(initial_value, newline)`
# Firma: `excel()`
# Firma: `excel_tab()`
# Firma: `get_dialect(name)`
# Firma: `list_dialects()`
# Firma: `reader(iterable, dialect, fmtparams)`
# Firma: `register_dialect(name, dialect, fmtparams)`
# Firma: `unix_dialect()`
# Firma: `unregister_dialect(name)`
# Firma: `writer(fileobj, dialect, fmtparams)`
