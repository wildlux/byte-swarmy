"""Test di logica pura (senza Qt) per verificare il comportamento accordion.

Riproduce fedelmente la logica di CollapsibleSection._on_toggle,
set_expanded e CenterArea._on_accordion_toggled, ma in Python puro,
così possiamo verificare che la logica sia corretta senza istanziare Qt.
"""
from __future__ import annotations


class MockSignal:
    """Mock minimale di pyqtSignal(bool)."""
    def __init__(self):
        self._slots: list = []

    def connect(self, slot):
        self._slots.append(slot)

    def emit(self, value):
        for slot in self._slots:
            slot(value)


class CollapsibleSection:
    """Replica esatta della logica di CollapsibleSection (senza GUI)."""

    def __init__(self, title: str):
        self.title = title
        self._expanded = True
        self._sync_silent = False
        self.toggled = MockSignal()
        # Per simulare self.sender() in CenterArea
        self._last_emitter = None

    def _on_toggle(self):
        self._expanded = not self._expanded
        # In Qt, self.sender() nel receiver del segnale restituisce chi
        # ha emesso. Simuliamo passando self come emitter.
        if not self._sync_silent:
            self._last_emitter = self
            self.toggled.emit(self._expanded)

    def set_expanded(self, expanded: bool):
        if self._expanded == expanded:
            return
        self._sync_silent = True
        try:
            self._on_toggle()
        finally:
            self._sync_silent = False

    @property
    def is_expanded(self) -> bool:
        return self._expanded


class CenterArea:
    """Replica esatta della logica di CenterArea._on_accordion_toggled."""

    def __init__(self, sections: list[CollapsibleSection]):
        self._accordion_sections = sections
        # Simula la connessione del segnale toggled -> _on_accordion_toggled
        for s in sections:
            s.toggled.connect(self._on_accordion_toggled)

    def _on_accordion_toggled(self, expanded: bool):
        if not expanded:
            return
        # Trova il sender: la sezione con _last_emitter impostato
        sender = next(
            (s for s in self._accordion_sections if s._last_emitter is s),
            None,
        )
        for section in self._accordion_sections:
            if section is not sender and section._expanded:
                section.set_expanded(False)
        # Resetta il flag emitter dopo aver gestito
        for s in self._accordion_sections:
            s._last_emitter = None


def test_initial_state_collapsed():
    """Tutte le 5 sezioni devono partire collassate."""
    sections = [
        CollapsibleSection("Navigatore"),
        CollapsibleSection("Backup"),
        CollapsibleSection("Log"),
        CollapsibleSection("Integrità"),
        CollapsibleSection("Sicurezza"),
    ]
    for s in sections:
        s.set_expanded(False)

    ca = CenterArea(sections)

    states = [s.is_expanded for s in sections]
    print(f"  Stato iniziale: {states}")
    assert all(not st for st in states), f"Non tutte collassate: {states}"
    print("  OK: tutte e 5 le sezioni partono collassate")


def test_accordion_single_expansion():
    """Click su una sezione: solo quella si espande, le altre restano chiuse."""
    sections = [
        CollapsibleSection("Navigatore"),
        CollapsibleSection("Backup"),
        CollapsibleSection("Log"),
        CollapsibleSection("Integrità"),
        CollapsibleSection("Sicurezza"),
    ]
    for s in sections:
        s.set_expanded(False)
    ca = CenterArea(sections)

    sections[0]._on_toggle()
    states = [s.is_expanded for s in sections]
    print(f"  Dopo click Navigatore: {states}")
    assert states == [True, False, False, False, False], f"Stato errato: {states}"
    print("  OK: solo Navigatore espanso")


def test_accordion_swap():
    """Click su una seconda sezione: la prima si chiude, la seconda si apre."""
    sections = [
        CollapsibleSection("Navigatore"),
        CollapsibleSection("Backup"),
        CollapsibleSection("Log"),
        CollapsibleSection("Integrità"),
        CollapsibleSection("Sicurezza"),
    ]
    for s in sections:
        s.set_expanded(False)
    ca = CenterArea(sections)

    sections[0]._on_toggle()  # Navigatore
    sections[1]._on_toggle()  # Backup
    states = [s.is_expanded for s in sections]
    print(f"  Dopo click Navigatore poi Backup: {states}")
    assert states == [False, True, False, False, False], f"Stato errato: {states}"
    print("  OK: scambio Navigatore->Backup corretto")


def test_accordion_collapse_manual():
    """Click su una sezione gia aperta: si collassa, le altre non toccate."""
    sections = [
        CollapsibleSection("Navigatore"),
        CollapsibleSection("Backup"),
        CollapsibleSection("Log"),
        CollapsibleSection("Integrità"),
        CollapsibleSection("Sicurezza"),
    ]
    for s in sections:
        s.set_expanded(False)
    ca = CenterArea(sections)

    sections[2]._on_toggle()  # Log espansa
    sections[2]._on_toggle()  # Log collassata
    states = [s.is_expanded for s in sections]
    print(f"  Dopo doppio click su Log: {states}")
    assert states == [False, False, False, False, False], f"Stato errato: {states}"
    print("  OK: collasso manuale funzionante, nessuna side-effect")


def test_accordion_full_cycle():
    """Ciclo completo: Navigatore -> Backup -> Log -> Integrità -> Sicurezza."""
    sections = [
        CollapsibleSection("Navigatore"),
        CollapsibleSection("Backup"),
        CollapsibleSection("Log"),
        CollapsibleSection("Integrità"),
        CollapsibleSection("Sicurezza"),
    ]
    for s in sections:
        s.set_expanded(False)
    ca = CenterArea(sections)

    for i in range(5):
        sections[i]._on_toggle()
        states = [s.is_expanded for s in sections]
        expected = [False] * 5
        expected[i] = True
        assert states == expected, f"Step {i}: stato {states}, atteso {expected}"
    print("  OK: ciclo completo Navigatore->Backup->Log->Integrità->Sicurezza")


if __name__ == "__main__":
    print("Test 1: stato iniziale collassato")
    test_initial_state_collapsed()
    print()
    print("Test 2: espansione singola")
    test_accordion_single_expansion()
    print()
    print("Test 3: scambio tra sezioni")
    test_accordion_swap()
    print()
    print("Test 4: collasso manuale")
    test_accordion_collapse_manual()
    print()
    print("Test 5: ciclo completo")
    test_accordion_full_cycle()
    print()
    print("=" * 50)
    print("TUTTI I TEST DI LOGICA ACCORDION PASSANO")
