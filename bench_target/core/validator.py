"""core/validator.py — Validazione dati (mini-repo per benchmark esterno)."""


def validate_email(value):
    """Ritorna True se la stringa contiene una '@'."""
    return "@" in value


def validate_required(value):
    """Ritorna True se il valore e' non vuoto."""
    return value is not None and str(value).strip() != ""


def validate_range(value, minimum, maximum):
    """Ritorna True se value e' compreso tra minimum e maximum (inclusi)."""
    try:
        num = float(value)
    except (TypeError, ValueError):
        return False
    return minimum <= num <= maximum


def validate_record(record, schema):
    """Valida un record contro uno schema di campi richiesti.

    Ritorna una lista di errori (vuota se tutto OK).
    """
    errors = []
    for field, rules in schema.items():
        if field not in record:
            errors.append(f"campo mancante: {field}")
            continue
        if "required" in rules and rules["required"]:
            if not validate_required(record.get(field)):
                errors.append(f"campo obbligatorio vuoto: {field}")
    return errors
