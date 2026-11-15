"""utils.py — Funzioni di utilità (mini-repo per benchmark esterno).

Questo file è il bersaglio dei task di refactoring atomico della Cycle 59.
"""

import re


def parse_email(email):
    """Estrae il dominio da un indirizzo email.

    Ritorna il dominio dopo la '@', oppure None se l'email non e' valida.
    """
    if "@" not in email:
        return None
    return email.split("@")[-1]


def slugify(text):
    """Converte una stringa in uno slug URL-friendly.

    Sostituisce spazi con trattini, rimuove caratteri speciali,
    converte in minuscolo.
    """
    text = text.lower().strip()
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s-]+", "-", text)
    return text.strip("-")


def is_valid_password(password):
    """Verifica che una password abbia almeno 8 caratteri e una maiuscola."""
    if len(password) < 8:
        return False
    has_upper = any(c.isupper() for c in password)
    return has_upper


def format_currency(amount, symbol="$"):
    """Formatta un importo come valuta con due decimali."""
    return f"{symbol}{amount:.2f}"
