# -*- coding: utf-8 -*-
"""
test_repo_hygiene.py — Test di igiene del repository (riusabile).

Verifica che la pulizia del progetto resti tale nel tempo:
- niente file one-shot / fix / backup (*.bak, fix_*, *_patch…);
- niente runtime artefatti tracciati in git (state/, logs/, backups/, *.db…);
- niente directory stray dentro GUI/ (GUI/logs, GUI/tasks, …);
- niente duplicati (intents.json alla root, qss fuori da GUI/theme/);
- .gitignore presente con le regole chiave, tasks/.gitkeep presente.

Uso:
    python -m unittest tests.test_repo_hygiene -v      # come test
    python tests/test_repo_hygiene.py                  # report leggibile

Il test è AUTO-CONTENUTO: solo pathlib + subprocess git.
I test git vengono saltati se git non è disponibile.
"""
from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path

# root = la directory che contiene tests/ (o la CWD se girato come script)
if __name__ == "__main__" and (Path.cwd() / ".git").exists():
    ROOT = Path.cwd()
else:
    ROOT = Path(__file__).resolve().parent.parent

# Cartelle di runtime/ambiente, ignorate in tutti i glob del repo
_ENV_DIRS = {".venv", "venv", "env", "ENV", ".git", "__pycache__",
             ".pytest_cache", ".mypy_cache", ".ruff_cache", ".idea",
             ".vscode", "node_modules"}

# Junk noto rimosso in passato: NON deve tornare sul filesystem
_KNOWN_JUNK = (
    "Archivio.zip", "ANALISI_SICUREZZA.txt", "STRUTTURA.txt",
    "feature7_timestral_tuner.py", "fix_timestral_advice_file.py",
    "intents.json",                       # la vera è INTENT/intents.json
    "https:⁄⁄github.com⁄wildlux⁄byte-swarmy.desktop",  # filename corrotto
    "DATABASE",                           # unita in tasks/
    "GUI/dark.qss", "GUI/light.qss",
    "GUI/integrate_theme.py", "GUI/feature_m1_anti_escape.py",
    "GUI/feature_m1_anti_escape (1).py",
    "GUI/tasks", "GUI/logs", "GUI/backups", "GUI/state", "GUI/project",
)

# Prefissi da one-shot (valgono su TUTTI i file del repo tranne .venv/.git)
_ONESHOT_PREFIXES = ("fix_", "redesign_", "apply_", "add_task_", "VECCHIA_")

# Runtime/non sorgenti che git non deve tracciare
GIT_TRACKED_BANNED_SUFFIX = (".db", ".sqlite", ".sqlite3", ".zip", ".bak")
GIT_TRACKED_BANNED_PREFIXES = ("state/", "logs/", "backups/",
                               "GUI/tasks/", "GUI/logs/", "GUI/state/",
                               "GUI/backups/", "GUI/project/")
GIT_TRACKED_TASKS = "tasks/"   # solo tasks/.gitkeep ammesso


def _iter_repo_files() -> list[Path]:
    """Tutti i file del progetto, saltando venv/git/cache."""
    out: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(ROOT)
        if any(part in _ENV_DIRS for part in rel.parts):
            continue
        out.append(path)
    return out


def _git_tracked() -> list[str]:
    """Elenco file tracciati (lista vuota se git non disponibile)."""
    try:
        out = subprocess.run(
            ["git", "ls-files"], cwd=str(ROOT),
            capture_output=True, text=True, timeout=15,
        )
        if out.returncode != 0:
            return []
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []


def _fail_items(test: unittest.TestCase, items: list, repair: str,
                limit: int = 15) -> None:
    """Fail con elenco leggibile e hint di riparazione."""
    preview = "\n  ".join(str(x) for x in sorted(items)[:limit])
    if len(items) > limit:
        preview += f"\n  … e altri {len(items) - limit}"
    test.fail(f"{len(items)} elementi da sistemare. {repair}\n  {preview}")


# ------------------------------------------------------------------
# 1. One-shot / backup / junk noto
# ------------------------------------------------------------------
class TestOneShotScripts(unittest.TestCase):

    def test_no_bak_files(self):
        baks = [p for p in _iter_repo_files() if ".bak" in p.name]
        if baks:
            _fail_items(self, baks,
                        "Cancella i backup:\n  find . -name '*.bak*'"
                        " -not -path './.venv/*' -delete")

    def test_no_oneshot_files(self):
        offenders = [p.relative_to(ROOT)
                     for p in _iter_repo_files()
                     if p.name.startswith(_ONESHOT_PREFIXES)
                     and p.name != "add_task.md"]   # doc cita il comando?
        if offenders:
            _fail_items(self, offenders,
                        "Script one-shot nel repo: cancellali o spostali "
                        "fuori dal repo (git rm se tracciati).")

    def test_no_known_junk_files_or_dirs(self):
        present = [name for name in _KNOWN_JUNK if (ROOT / name).exists()]
        if present:
            _fail_items(self, present,
                        "Junk noto (già rimosso in passato) è ricomparso: "
                        "elimina e verifica il .gitignore.")

    def test_no_corrupted_filenames(self):
        bad = [p.name for p in ROOT.iterdir()
               if "⁄" in p.name or p.name.startswith("https:")]
        if bad:
            _fail_items(self, bad, "Filename corrotti: rinomina o elimina.")


# ------------------------------------------------------------------
# 2. Runtime tracciato in git
# ------------------------------------------------------------------
class TestGitTrackedRuntime(unittest.TestCase):

    def test_no_runtime_tracked(self):
        tracked = _git_tracked()
        if not tracked:
            self.skipTest("git non disponibile")
        offenders = []
        for p in tracked:
            if p.endswith(GIT_TRACKED_BANNED_SUFFIX):
                offenders.append(p)
            elif p.startswith(GIT_TRACKED_BANNED_PREFIXES):
                offenders.append(p)
            elif p.startswith(GIT_TRACKED_TASKS) \
                    and not p.endswith(".gitkeep"):
                offenders.append(p)
            elif any(part in _ENV_DIRS for part in Path(p).parts):
                offenders.append(p)
        if offenders:
            _fail_items(self, offenders,
                        "Runtime tracciato in git: `git rm --cached <f>` "
                        "e aggiungi il pattern in .gitignore.")

    def test_tasks_gitkeep_exists(self):
        self.assertTrue((ROOT / "tasks" / ".gitkeep").exists(),
                        "tasks/ è runtime-ignored: serve tasks/.gitkeep.")

    def test_gitkeep_only_in_expected_dirs(self):
        tracked = _git_tracked()
        if not tracked:
            self.skipTest("git non disponibile")
        keep_dirs = {p.rsplit("/", 1)[0] for p in tracked
                     if p.endswith(".gitkeep")}
        extra = keep_dirs - {"tasks", "project"}
        self.assertFalse(extra,
                         f".gitkeep in dir inattese: {sorted(extra)}")

    def test_gitignore_covers_runtime(self):
        gi = ROOT / ".gitignore"
        self.assertTrue(gi.exists(), ".gitignore mancante")
        content = gi.read_text(encoding="utf-8", errors="replace")
        needed = ["state/", "logs/", "backups/", "__pycache__/",
                  ".venv/", "tasks/*"]
        missing = [n for n in needed if n not in content]
        self.assertFalse(missing,
                         f"Pattern mancanti nel .gitignore: {missing}")


# ------------------------------------------------------------------
# 3. Duplicati e struttura semplificata
# ------------------------------------------------------------------
class TestStructure(unittest.TestCase):

    def test_no_duplicate_intents_json_at_root(self):
        self.assertFalse((ROOT / "intents.json").exists(),
                         "intents.json alla root: la vera è "
                         "INTENT/intents.json.")

    def test_no_database_dir(self):
        self.assertFalse((ROOT / "DATABASE").exists(),
                         "DATABASE/ è stata unita in tasks/: ricrearla?")

    def test_gui_runtime_free(self):
        stray = [d for d in ("backups", "logs", "project", "state", "tasks")
                 if (ROOT / "GUI" / d).exists()]
        if stray:
            _fail_items(self, stray,
                        "Dir runtime dentro GUI/ (nascono avviando la GUI "
                        "con CWD sbagliato): cancellale.")

    def test_qss_only_in_theme_dir(self):
        gui = ROOT / "GUI"
        strays = list(gui.glob("*.qss")) if gui.exists() else []
        self.assertFalse(strays,
                         f"qss fuori da GUI/theme/: {strays}")

    def test_no_json_zip_at_root(self):
        offenders = [p.name for p in ROOT.iterdir()
                     if p.is_file() and p.suffix in (".json", ".zip")]
        self.assertFalse(offenders,
                         f"File .json/.zip inattesi alla root: {offenders}")

    def test_img_minimal(self):
        img = ROOT / "IMG"
        if not img.exists():
            return
        bad = [p.name for p in img.iterdir()
               if p.is_file()
               and ("Gemini_Generated" in p.name or p.stem.endswith("_2"))]
        self.assertFalse(bad,
                         f"Immagini derivate in IMG/: {bad}\n"
                         "Tieni solo documentazione.jpeg, icona.ico,"
                         " icona.png, logo.jpeg, SCHERMATE/.")


if __name__ == "__main__":
    print(f"Repo hygiene check → {ROOT}")
    print("=" * 60)
    unittest.main(verbosity=2)
