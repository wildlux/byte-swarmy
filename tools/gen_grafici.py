#!/usr/bin/env python3
"""Genera DOCS/grafici/miglioramenti.svg — grafici deterministici (zero LLM).

Dati hard-coded dalla storia del progetto (DOCS/IMPLEMENTED.md):
  A. Difetti corretti nell'audit Cycle 85, per categoria
  B. Meccanismi di robustezza/anti-allucinazione attivi per versione (cumulativo)
  C. Crescita della suite di test (Cycle 75 vs Cycle 85)

Rigenera con:  .venv/bin/python tools/gen_grafici.py
Deterministico: stesso input → stesso SVG byte-per-byte (nessun timestamp).

Dal Cycle 94 ciclo e conteggio meccanismi NON sono più hard-coded: sono
letti da DOCS/IMPLEMENTED.md e DOCS/MIGLIORAMENTI.md, così il pulsante
"🔄 Rigenera" nella GUI mostra davvero un cambiamento quando i documenti
cambiano. I valori del radar restano giudizi espliciti (non derivabili).
"""
import re
from pathlib import Path
import sys
from xml.sax.saxutils import escape

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
OUT = ROOT / "DOCS" / "grafici" / "miglioramenti.svg"
SKILLS_DIR = ROOT / ".opencode" / "skill"


def skill_count() -> int:
    """Numero di skill operative nel repo (SKILL.md)."""
    return len(list(SKILLS_DIR.glob("*/SKILL.md")))


def auto_skill_count() -> int:
    """Skill con parole chiave per l'attivazione automatica in Chat."""
    try:
        from CORE.auto_skill import KEYWORDS
        return len(KEYWORDS)
    except Exception:
        return 0


def auto_tool_count() -> int:
    """Tool con parole chiave per l'attivazione automatica in Chat."""
    try:
        from CORE.auto_tool import TOOL_KEYWORDS
        return len(TOOL_KEYWORDS)
    except Exception:
        return 0


def tool_count() -> int:
    """Numero di tool selezionabili nel banco Chat."""
    try:
        from CORE.tools import TOOL_SIGNATURES
        return len(TOOL_SIGNATURES)
    except Exception:
        return 30


def label_count() -> int:
    """Numero di etichette di default."""
    try:
        from CORE.labels import DEFAULT_LABELS
        return len(DEFAULT_LABELS)
    except Exception:
        return 17


def cloud_provider_count() -> int:
    """Provider cloud gratuiti supportati dal banco di test."""
    try:
        from CORE.cloud_client import PROVIDERS
        return len(PROVIDERS)
    except Exception:
        return 3


def missing_docstring_count() -> int:
    """File .py in CORE/GUI/tools senza docstring di modulo (goal: 0)."""
    import ast
    count = 0
    for base in ("CORE", "GUI", "tools"):
        for path in sorted((ROOT / base).glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            if ast.get_docstring(tree) is None:
                count += 1
    return count


def latest_cycle() -> int:
    """Cycle più alto registrato in DOCS/IMPLEMENTED.md (fail-open: 0)."""
    text = (ROOT / "DOCS" / "IMPLEMENTED.md").read_text(encoding="utf-8")
    cycles = [int(n) for n in re.findall(
        r"(?im)^#{1,3}\s*Cycle\s+(\d+)", text)]
    return max(cycles) if cycles else 0


def mechanism_count() -> int:
    """Meccanismi attivi: tabella B + novità in DOCS/MIGLIORAMENTI.md."""
    text = (ROOT / "DOCS" / "MIGLIORAMENTI.md").read_text(encoding="utf-8")
    try:
        section_b = text.split("## B. ", 1)[1].split("\n---\n", 1)[0]
        recent = text.split("### Novità 2026-11-22", 1)[1].split(
            "\n---\n", 1)[0]
    except IndexError:
        return 0
    numbered = sum(1 for line in section_b.splitlines()
                   if re.match(r"^\|\s*\d+\s*\|", line))
    rows = [line for line in recent.splitlines() if line.startswith("|")]
    # header + separator row
    return numbered + max(0, len(rows) - 2)


W = 940
MARGIN_L = 245          # spazio etichette barre orizzontali
MARGIN_R = 70
BAR_H = 26
ROW_GAP = 14

# Palette deterministica
C_RED = "#dc2626"
C_ORANGE = "#f59e0b"
C_BLUE = "#2563eb"
C_GREEN = "#16a34a"
C_PURPLE = "#9333ea"
C_GRAY = "#64748b"
C_LIGHT = "#e2e8f0"

FONT = "DejaVu Sans, sans-serif"

# ── Dati Chart A: difetti per categoria (audit Cycle 85) ─────────────
CHART_A = [
    ("Funzionalità silent-dead", 6, C_RED),
    ("NameError mascherati", 4, C_ORANGE),
    ("Anti-allucinazione (ref/docs)", 2, C_PURPLE),
    ("Infra test / collection", 2, C_BLUE),
    ("Parità GUI (back_btn)", 1, C_GREEN),
]

# ── Dati Chart B: meccanismi cumulativi per versione ─────────────────
# Storico fino a v0.3.31+; il punto finale è calcolato da mechanism_count()
# (lista completa in DOCS/MIGLIORAMENTI.md).
CHART_B = [
    ("v0.3.18", 1),   # 70: regola parita' GUI
    ("v0.3.20", 2),   # 72: runner v2 + fix keywords skill
    ("v0.3.22", 3),   # 75: verify_cycle.sh end-to-end
    ("v0.3.24", 4),   # 77: ventole + max-run-sec
    ("v0.3.25", 7),   # 79: PROTECTED_FILES + shrink guard + test gate
    ("v0.3.26", 8),   # 81: GUI/refs + list_refs
    ("v0.3.27", 10),  # 82-83: refs condizionali + trigger WM
    ("v0.3.28", 11),  # 84: clarifier ask-if-vague
    ("v0.3.30", 16),  # 85: audit robustezza (mutua esclusione, sandbox
                      #      argv, run_test_suite reale, test ermetici...)
    ("v0.3.31+", 26), # 85i-85k: metrica primo colpo, gate per-slot,
                      #      assembler, import-check, corpus feedback,
                      #      best-of-N, watchdog backoff, clarifier +3,
                      #      refs interni, validate_refs, Zero Warning
]
# Cycle 87-93: inventario regex, subagent, A1-A4, B1-B3, C1-C2, D1.
MECHANISMS = mechanism_count()

# ── Dati Chart C: suite di test ──────────────────────────────────────
CHART_C = [
    ("Test passati", 756, 888),
    ("Subtests passati", 0, 1055),
]
C75_COLOR = C_GRAY
C85_COLOR = C_BLUE


def hbar_section(items, x0, x1, top, title, subtitle, unit=""):
    """Sezione di barre orizzontali. Ritorna (svg_str, y_dopo)."""
    parts = [f'<text x="{x0 - 225}" y="{top}" font-family="{FONT}" '
             f'font-size="16" font-weight="bold" fill="#0f172a">'
             f'{escape(title)}</text>']
    if subtitle:
        parts.append(f'<text x="{x0 - 225}" y="{top + 20}" '
                     f'font-family="{FONT}" font-size="11.5" '
                     f'fill="{C_GRAY}">{escape(subtitle)}</text>')

    max_v = max(v for _, v, *_ in items) or 1
    y = top + 34
    bar_x0 = x0 + 4
    usable = x1 - bar_x0
    for label, value, *rest in items:
        color = rest[0] if rest else C_BLUE
        # etichetta
        parts.append(f'<text x="{x0 - 225}" y="{y + BAR_H * 0.72}" '
                     f'font-family="{FONT}" font-size="12.5" '
                     f'fill="#334155">{escape(label)}</text>')
        # sfondo barra
        w_max = usable
        parts.append(f'<rect x="{bar_x0}" y="{y}" width="{w_max}" '
                     f'height="{BAR_H}" rx="4" fill="{C_LIGHT}"/>')
        # barra
        w = int(round(w_max * value / max_v)) if max_v else 0
        w = max(w, 3)
        parts.append(f'<rect x="{bar_x0}" y="{y}" width="{w}" '
                     f'height="{BAR_H}" rx="4" fill="{color}"/>')
        # valore
        suffix = f" {unit}" if unit else ""
        parts.append(f'<text x="{bar_x0 + w + 8}" y="{y + BAR_H * 0.72}" '
                     f'font-family="{FONT}" font-size="12.5" '
                     f'font-weight="bold" fill="#0f172a">'
                     f'{value}{suffix}</text>')
        y += BAR_H + ROW_GAP
    return "\n".join(parts), y + 8


def step_section(points, x0, x1, top, title, subtitle, y_max):
    """Grafico a gradini cumulativo con punti etichettati."""
    parts = [f'<text x="{x0 - 225}" y="{top}" font-family="{FONT}" '
             f'font-size="16" font-weight="bold" fill="#0f172a">'
             f'{escape(title)}</text>']
    if subtitle:
        parts.append(f'<text x="{x0 - 225}" y="{top + 20}" '
                     f'font-family="{FONT}" font-size="11.5" '
                     f'fill="{C_GRAY}">{escape(subtitle)}</text>')

    y_top = top + 42
    y_bot = y_top + 130
    plot_w = x1 - x0
    n = len(points)

    def px(i):
        return x0 + int(plot_w * i / (n - 1)) if n > 1 else x0

    def py(v):
        return y_bot - int(130 * v / y_max)

    # griglia orizzontale
    for gv in range(0, y_max + 1, 4):
        yy = py(gv)
        parts.append(f'<line x1="{x0}" y1="{yy}" x2="{x1}" y2="{yy}" '
                     f'stroke="{C_LIGHT}" stroke-width="1"/>')
        parts.append(f'<text x="{x0 - 26}" y="{yy + 4}" '
                     f'font-family="{FONT}" font-size="10" '
                     f'fill="{C_GRAY}">{gv}</text>')

    # polyline a gradini + punti
    coords = [(px(i), py(v)) for i, (_, v) in enumerate(points)]
    path = []
    for i, (xx, yy) in enumerate(coords):
        if i == 0:
            path.append(f"M {xx} {yy}")
        else:
            path.append(f"L {xx} {coords[i - 1][1]}")  # gradino orizzontale
            path.append(f"L {xx} {yy}")                # salita
    step_path = " ".join(path)
    parts.append(f'<path d="{step_path}" fill="none" stroke="{C_GREEN}" '
                 f'stroke-width="2.5"/>')
    for i, (ver, v) in enumerate(points):
        xx, yy = coords[i]
        parts.append(f'<circle cx="{xx}" cy="{yy}" r="4" fill="{C_GREEN}"/>')
        parts.append(f'<text x="{xx}" y="{yy - 10}" font-family="{FONT}" '
                     f'font-size="11" font-weight="bold" fill="#166534" '
                     f'text-anchor="middle">{v}</text>')
        parts.append(f'<text x="{xx}" y="{y_bot + 18}" font-family="{FONT}" '
                     f'font-size="10.5" fill="{C_GRAY}" '
                     f'text-anchor="middle">{escape(ver)}</text>')
    return "\n".join(parts), y_bot + 40


def grouped_section(rows, x0, x1, top, title, subtitle):
    """Barre raggruppate: per ogni metrica, barra Cycle75 + barra Cycle85."""
    parts = [f'<text x="{x0 - 225}" y="{top}" font-family="{FONT}" '
             f'font-size="16" font-weight="bold" fill="#0f172a">'
             f'{escape(title)}</text>']
    if subtitle:
        parts.append(f'<text x="{x0 - 225}" y="{top + 20}" '
                     f'font-family="{FONT}" font-size="11.5" '
                     f'fill="{C_GRAY}">{escape(subtitle)}</text>')

    max_v = max(max(a, b) for _, a, b in rows) or 1
    y = top + 40
    bar_x0 = x0 + 4
    usable = x1 - bar_x0
    half = (BAR_H - 4) // 2 or 8
    for label, v75, v85 in rows:
        parts.append(f'<text x="{x0 - 225}" y="{y + half + 4}" '
                     f'font-family="{FONT}" font-size="12.5" '
                     f'fill="#334155">{escape(label)}</text>')
        for j, (v, col, tag) in enumerate(
                [(v75, C75_COLOR, "Cycle 75"), (v85, C85_COLOR, "Cycle 85")]):
            yy = y + j * (half + 3)
            parts.append(f'<rect x="{bar_x0}" y="{yy}" width="{usable}" '
                         f'height="{half}" rx="3" fill="{C_LIGHT}"/>')
            w = max(int(round(usable * v / max_v)), 3)
            parts.append(f'<rect x="{bar_x0}" y="{yy}" width="{w}" '
                         f'height="{half}" rx="3" fill="{col}"/>')
            parts.append(f'<text x="{bar_x0 + w + 8}" y="{yy + half - 2}" '
                         f'font-family="{FONT}" font-size="10.5" '
                         f'font-weight="bold" fill="#0f172a">{v}</text>')
        y += BAR_H + 8 + 6
    # legenda
    ly = y + 2
    parts.append(f'<rect x="{bar_x0}" y="{ly}" width="12" height="12" '
                 f'rx="2" fill="{C75_COLOR}"/>')
    parts.append(f'<text x="{bar_x0 + 18}" y="{ly + 10}" '
                 f'font-family="{FONT}" font-size="11" fill="{C_GRAY}">'
                 f'Cycle 75 (v0.3.22)</text>')
    parts.append(f'<rect x="{bar_x0 + 150}" y="{ly}" width="12" height="12" '
                 f'rx="2" fill="{C85_COLOR}"/>')
    parts.append(f'<text x="{bar_x0 + 168}" y="{ly + 10}" '
                 f'font-family="{FONT}" font-size="11" fill="{C_GRAY}">'
                 f'Cycle 85 (v0.3.30)</text>')
    return "\n".join(parts), ly + 26


def ladder_section(items, x0, x1, top, title, subtitle):
    """Scala di seniorità: 4 livelli, barre crescenti 1/4→4/4.

    items: (label, level 1..4, state) con state in
    {done, current, next, goal}.
    """
    parts = [f'<text x="{x0 - 285}" y="{top}" font-family="{FONT}" '
             f'font-size="16" font-weight="bold" fill="#0f172a">'
             f'{escape(title)}</text>']
    if subtitle:
        parts.append(f'<text x="{x0 - 285}" y="{top + 20}" '
                     f'font-family="{FONT}" font-size="11.5" '
                     f'fill="{C_GRAY}">{escape(subtitle)}</text>')

    y = top + 34
    bar_x0 = x0 + 4
    usable = x1 - bar_x0 - 110  # spazio per l'etichetta di stato a destra
    for label, level, state in items:
        parts.append(f'<text x="{x0 - 285}" y="{y + BAR_H * 0.72}" '
                     f'font-family="{FONT}" font-size="12.5" '
                     f'fill="#334155">{escape(label)}</text>')
        frac = level / 4
        parts.append(f'<rect x="{bar_x0}" y="{y}" width="{usable}" '
                     f'height="{BAR_H}" rx="4" fill="{C_LIGHT}"/>')
        if state == "done":
            fill, opacity, dash = "#94a3b8", "1.0", ""
            right = "livello 1/4"
        elif state == "current":
            fill, opacity, dash = C_BLUE, "1.0", ""
            right = "livello 2/4"
        elif state == "next":
            fill, opacity, dash = C_BLUE, "0.30", "6,4"
            right = "target 3/4"
        else:  # goal
            fill, opacity, dash = C_GREEN, "0.30", "6,4"
            right = "GOAL 4/4"
        w = max(int(usable * frac), 3)
        parts.append(f'<rect x="{bar_x0}" y="{y}" width="{w}" '
                     f'height="{BAR_H}" rx="4" fill="{fill}" '
                     f'fill-opacity="{opacity}"/>')
        if dash:
            parts.append(f'<rect x="{bar_x0}" y="{y}" width="{w}" '
                         f'height="{BAR_H}" rx="4" fill="none" '
                         f'stroke="{"#16a34a" if state == "goal" else C_BLUE}" '
                         f'stroke-width="1.5" stroke-dasharray="{dash}"/>')
        # etichetta di stato a destra
        col = "#0f172a"
        weight = "normal"
        if state == "current":
            right = "◀ siamo qui · 2/4"
            col = C_BLUE
            weight = "bold"
        elif state == "goal":
            right = "★ GOAL · 4/4"
            col = "#166534"
            weight = "bold"
        parts.append(f'<text x="{bar_x0 + usable + 8}" '
                     f'y="{y + BAR_H * 0.72}" font-family="{FONT}" '
                     f'font-size="11.5" font-weight="{weight}" '
                     f'fill="{col}">{escape(right)}</text>')
        y += BAR_H + ROW_GAP
    return "\n".join(parts), y + 8


def radar_section(axes, oggi, goal, cx, cy, R, top, title, subtitle):
    """Grafico a ragnatela: capacità su 8 assi, oggi vs goal.

    axes: etichette; oggi/goal: valori per asse (0..4).
    """
    import math
    n = len(axes)
    parts = [f'<text x="20" y="{top}" font-family="{FONT}" '
             f'font-size="16" font-weight="bold" fill="#0f172a">'
             f'{escape(title)}</text>']
    if subtitle:
        parts.append(f'<text x="20" y="{top + 20}" '
                     f'font-family="{FONT}" font-size="11.5" '
                     f'fill="{C_GRAY}">{escape(subtitle)}</text>')

    def pt(k, v):
        ang = math.radians(-90 + k * (360 / n))
        r = R * v / 4
        return cx + r * math.cos(ang), cy + r * math.sin(ang)

    # anelli della ragnatela
    for gv in range(1, 5):
        ring = " ".join(
            f"{px:.1f},{py:.1f}" for px, py in (pt(k, gv) for k in range(n)))
        parts.append(f'<polygon points="{ring}" fill="none" '
                     f'stroke="{C_LIGHT}" stroke-width="1"/>')
    # raggi
    for k in range(n):
        px, py = pt(k, 4)
        parts.append(f'<line x1="{cx}" y1="{cy}" x2="{px:.1f}" '
                     f'y2="{py:.1f}" stroke="{C_LIGHT}" stroke-width="1"/>')
        # etichetta asse
        lx, ly = pt(k, 4.75)
        anch = "middle"
        if lx > cx + 10:
            anch = "start"
        elif lx < cx - 10:
            anch = "end"
        dy = 4 if abs(ly - cy) < R * 0.9 else (12 if ly < cy else 16)
        parts.append(f'<text x="{lx:.1f}" y="{ly + dy:.1f}" '
                     f'font-family="{FONT}" font-size="12" fill="#334155" '
                     f'text-anchor="{anch}">{escape(axes[k])}</text>')

    def poly(vals, fill, stroke, dash="", width="2", opacity="1"):
        pts = " ".join(
            f"{px:.1f},{py:.1f}" for px, py in
            (pt(k, vals[k]) for k in range(n)))
        extra = f' stroke-dasharray="{dash}"' if dash else ""
        return (f'<polygon points="{pts}" fill="{fill}" '
                f'fill-opacity="0.25" stroke="{stroke}" stroke-width="{width}"'
                f'{extra} stroke-opacity="{opacity}"/>')

    parts.append(poly(goal, C_GREEN, C_GREEN, dash="6,4"))
    parts.append(poly(oggi, C_BLUE, C_BLUE, width="2.5"))
    for k in range(n):
        px, py = pt(k, oggi[k])
        parts.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="3.5" '
                     f'fill="{C_BLUE}"/>')

    # legenda
    ly = cy + R + 52
    parts.append(f'<rect x="{cx - 120}" y="{ly}" width="12" height="12" '
                 f'rx="2" fill="{C_BLUE}" fill-opacity="0.25" '
                 f'stroke="{C_BLUE}" stroke-width="2"/>')
    parts.append(f'<text x="{cx - 102}" y="{ly + 10}" font-family="{FONT}" '
                 f'font-size="11.5" fill="{C_GRAY}">'
                 f'oggi (Cycle {latest_cycle()})</text>')
    parts.append(f'<rect x="{cx + 10}" y="{ly}" width="12" height="12" '
                 f'rx="2" fill="{C_GREEN}" fill-opacity="0.25" '
                 f'stroke="{C_GREEN}" stroke-width="2" '
                 f'stroke-dasharray="6,4"/>')
    parts.append(f'<text x="{cx + 28}" y="{ly + 10}" font-family="{FONT}" '
                 f'font-size="11.5" fill="{C_GRAY}">'
                 f'goal middle senior</text>')
    return "\n".join(parts), ly + 30


def build_svg() -> str:
    sections = []

    # Titolo
    sections.append(
        f'<text x="20" y="38" font-family="{FONT}" font-size="20" '
        f'font-weight="bold" fill="#0f172a">byte-swarmy — Miglioramenti '
        f'implementati (Cycle 70 → {latest_cycle()} — Nov 2026)</text>')
    sections.append(
        f'<text x="20" y="60" font-family="{FONT}" font-size="12" '
        f'fill="{C_GRAY}">Generato deterministicamente da '
        f'tools/gen_grafici.py — dati: DOCS/IMPLEMENTED.md</text>')

    x0 = MARGIN_L
    x1 = W - MARGIN_R

    y = 92
    s, y = hbar_section(
        CHART_A, x0, x1, y,
        "A. Audit robustezza Cycle 85 — 15 difetti corretti, per categoria",
        "Rilevati da pyflakes + pytest + smoke sandbox; tutti corretti e su "
        "GitHub (commit 4a1cb1a / 0bb4998 / 72e1b71)")
    sections.append(s)

    y += 24
    s, y = step_section(
        CHART_B[:-1] + [("v0.3.34+", MECHANISMS)], x0, x1, y,
        "B. Meccanismi di robustezza e anti-allucinazione attivi "
        "(cumulativo)",
        f"Elenco completo dei {MECHANISMS} meccanismi in "
        "DOCS/MIGLIORAMENTI.md",
        y_max=max(16, MECHANISMS))
    sections.append(s)

    y += 24
    s, y = grouped_section(
        CHART_C, x0, x1, y,
        "C. Crescita della suite di test (run completa)",
        "Durata: 387s (Cycle 75) → 1031s (ultima run completa, 2026-11-19); "
        "888 test + 1055 subtest, 0 warning")
    sections.append(s)

    y += 24
    s, y = ladder_section(
        [("Junior — 3b nudo (baseline C72: 0/4 task GUI)", 1, "done"),
         ("Junior+ — sistema v0.3.34 (meccanismi attivi)", 2, "current"),
         ("Middle — ≥50% primo colpo, GUI ≥50%", 3, "next"),
         ("Middle Senior — GOAL ≥70%, 0 warning", 4, "goal")],
        x0 + 60, x1, y,
        "D. Scala di seniorità del sistema — GOAL: almeno middle senior",
        "Il modello 3b non diventerà un senior; il SISTEMA (modello + "
        "meccanismi) sì — criteri misurabili in DOCS/MIGLIORAMENTI.md")
    sections.append(s)

    y += 24
    s, y = radar_section(
        ["Task GUI (creazione)", "Modifiche minime", "Refactoring mecc.",
         "Gate / verifica", "Fedeltà API", "Chiarimenti ambigui",
         "Architettura", "Memoria / contesto"],
        [1, 3, 4, 4, 3, 3, 2, 3],
        [3, 3, 4, 4, 4, 3, 2, 4],
        cx=W // 2, cy=y + 205, R=130, top=y,
        title="E. Radar capacità — dove siamo deboli (→ todo.md)",
        subtitle="Scala 0–4 per asse; i gap verso il poligono verde "
                 "sono la roadmap prioritaria in todo.md")
    sections.append(s)

    y += 24
    s, y = hbar_section(
        [("Skill operative nel repo", skill_count(), C_PURPLE)],
        x0, x1, y,
        "F. Skill operative attive — famiglia di skill del sistema",
        "Tutte versionate in .opencode/skill/: planner, refs API/kernel, "
        "CAD/3D, Linux, SQL, report, grafica, git, summarizer")
    sections.append(s)

    y += 24
    s, y = hbar_section(
        [("Tool selezionabili in Chat", tool_count(), C_BLUE),
         ("Skill attivabili in Chat", skill_count(), C_PURPLE),
         ("Skill con auto-keyword", auto_skill_count(), C_GREEN),
         ("Tool con auto-keyword", auto_tool_count(), C_GREEN),
         ("Etichette default", label_count(), C_GREEN),
         ("Provider cloud gratuiti", cloud_provider_count(), C_ORANGE),
         ("File senza docstring (goal 0)", missing_docstring_count(), C_RED)],
        x0, x1, y,
        "G. Novità Nov 2026 — banco di test e organizzazione",
        "Chat con tools/skill on-off, auto-skill e auto-tool per parole chiave, "
        "client Groq/Gemini/OpenRouter, etichette (rinomina/colore/elimina), "
        "dotfile, cartelle ordinate (TOOLS/), 0 docstring mancanti")
    sections.append(s)

    y += 10
    sections.append(
        f'<text x="20" y="{y}" font-family="{FONT}" font-size="11" '
        f'fill="{C_GRAY}">Nota: i "subtests" sono asserzioni per-elemento '
        f'(subTest pytest) — non tracciati al Cycle 75.</text>')

    inner = "\n".join(sections)
    total_h = y + 40
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" '
        f'height="{total_h}" viewBox="0 0 {W} {total_h}">\n'
        f'<rect width="{W}" height="{total_h}" fill="#ffffff"/>\n'
        f'{inner}\n</svg>\n'
    )


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    svg = build_svg()
    # Validazione well-formed (fail-fast se l'SVG è rotto)
    import xml.dom.minidom
    xml.dom.minidom.parseString(svg)
    OUT.write_text(svg, encoding="utf-8")
    print(f"scritto {OUT.relative_to(ROOT)} ({len(svg)} byte, "
          f"well-formed OK)")


if __name__ == "__main__":
    main()
