"""models/user.py — Modello utente (mini-repo per benchmark esterno)."""


class User:
    """Rappresenta un utente del sistema."""

    def __init__(self, username, email, role="user"):
        self.username = username
        self.email = email
        self.role = role

    def is_admin(self):
        """Ritorna True se l'utente ha ruolo admin."""
        return self.role == "admin"

    def can_edit(self, other_username):
        """Ritorna True se puo' modificare il profilo di other_username."""
        return self.is_admin() or self.username == other_username

    def to_dict(self):
        """Converte l'utente in dizionario."""
        return {
            "username": self.username,
            "email": self.email,
            "role": self.role,
        }
