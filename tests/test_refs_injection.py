"""Test di regressione robustezza: iniezione ref + clarifier GUI.

Deterministici (zero LLM): replicano la selezione dei ref usando
Worker._build_refs_block con un harness minimo.

Copre:
  - mutua esclusione famiglie Qt (Cycle 85: bug PySide6+QApplication
    che riceveva pyqt6.md con pyqtSignal → crash garantito)
  - default Qt quando nessuna famiglia esplicita (QApplication → pyqt6)
  - nessun ref per task GUI vago
  - entrambi i ref per conversione esplicita pyqt<->pyside
  - clarifier: GUI vago → domanda; toolkit esplicito → nessuna domanda
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from CORE.worker import Worker  # noqa: E402


def make_fake_worker():
    """Harness minimo: solo ciò che _build_refs_block usa."""
    fake = types.SimpleNamespace()
    fake.tools = types.SimpleNamespace(project_root=Path("."))
    fake._REF_KEYWORDS = Worker._REF_KEYWORDS
    fake._REF_TRIGGERS = Worker._REF_TRIGGERS
    fake._REF_FAMILY_TRIGGERS = Worker._REF_FAMILY_TRIGGERS
    fake._REF_CONFLICTS = Worker._REF_CONFLICTS
    fake._REF_THRESHOLD = Worker._REF_THRESHOLD
    fake._build_refs_block = (
        lambda task: Worker._build_refs_block(fake, task))
    return fake


def injected(block: str) -> list[str]:
    """Estrae i path dei ref iniettati dal blocco."""
    out = []
    for line in block.splitlines():
        if line.startswith("--- ") and line.endswith(" ---"):
            out.append(line[4:-4])
    return out


def task(title: str, description: str = "") -> dict:
    return {"title": title, "description": description}


class TestMutuaEsclusioneFamiglieQt:
    def setup_method(self):
        self.w = make_fake_worker()

    def test_pyside_con_qapplication_non_riceve_pyqt6(self):
        """Il bug Cycle 85: QApplication è trigger condiviso ma la
        famiglia pyside è esplicita → pyqt6.md NON va iniettato."""
        block = self.w._build_refs_block(task(
            "Finestra PySide6", "usa QApplication, QMainWindow e Signal"))
        refs = injected(block)
        assert "GUI/refs/pyside6.md" in refs
        assert "GUI/refs/pyqt6.md" not in refs

    def test_pyqt_non_riceve_pyside6(self):
        block = self.w._build_refs_block(task(
            "Finestra PyQt6", "usa QApplication e pyqtSignal"))
        refs = injected(block)
        assert "GUI/refs/pyqt6.md" in refs
        assert "GUI/refs/pyside6.md" not in refs

    def test_qt_generico_default_pyqt6(self):
        """Nessuna famiglia esplicita ma QApplication presente →
        default PyQt6 (regola byte-swarmy)."""
        block = self.w._build_refs_block(task(
            "Finestra Qt", "usa QApplication e QMainWindow"))
        refs = injected(block)
        assert refs == ["GUI/refs/pyqt6.md"]

    def test_conversione_esplicita_inietta_entrambi(self):
        """Task di conversione: entrambe le famiglie esplicite →
        entrambi i ref (comportamento intenzionale)."""
        block = self.w._build_refs_block(task(
            "Converti app", "converti questa app pyqt6 in pyside6"))
        refs = injected(block)
        assert "GUI/refs/pyqt6.md" in refs
        assert "GUI/refs/pyside6.md" in refs

    def test_tkinter_solo_tkinter(self):
        block = self.w._build_refs_block(task(
            "App tkinter", "usa ttk.Button e mainloop"))
        refs = injected(block)
        assert refs == ["GUI/refs/tkinter.md"]

    def test_gui_vaga_nessun_ref_wm(self):
        block = self.w._build_refs_block(task(
            "Crea una GUI", "interfaccia con pulsante e layout"))
        assert injected(block) == []

    def test_toolset_api_ref(self):
        block = self.w._build_refs_block(task(
            "Usa i tool", "chiama read_file e write_file poi run_test"))
        refs = injected(block)
        assert "GUI/refs/toolset_api.md" in refs

    def test_no_crash_su_task_vuoto(self):
        assert self.w._build_refs_block(task("", "")) == "(nessuno)"


class TestClarifierGui:
    def test_gui_vaga_genera_domanda(self):
        from CORE.clarifier import detect_ambiguity
        qs = detect_ambiguity("Crea una finestra", "interfaccia grafica")
        ids = [q.id for q in qs]
        assert "Qgui" in ids

    def test_toolkit_esplicito_nessuna_domanda_gui(self):
        from CORE.clarifier import detect_ambiguity
        for desc in ("Crea finestra PyQt6",
                     "App PySide6 con Signal",
                     "App tkinter con ttk.Button"):
            qs = detect_ambiguity(desc, desc)
            assert "Qgui" not in [q.id for q in qs], desc

    def test_risposta_1_arricchisce_con_pyqt6(self):
        """Catena vago→domanda→risposta→ref: l'enriched description
        contiene 'PyQt6' → trigger ref pyqt6 al prossimo giro."""
        from CORE.clarifier import detect_ambiguity, parse_answer, clarify
        qs = detect_ambiguity("Crea una finestra", "interfaccia grafica")
        ans = parse_answer("1", qs)
        result = clarify("Crea una finestra", "interfaccia grafica", ans)
        assert "PyQt6" in result.enriched_description
        # la descrizione arricchita deve triggerare pyqt6 nel worker
        w = make_fake_worker()
        refs = injected(w._build_refs_block(task(
            result.enriched_title, result.enriched_description)))
        assert "GUI/refs/pyqt6.md" in refs
