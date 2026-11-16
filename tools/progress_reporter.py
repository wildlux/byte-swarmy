#!/usr/bin/env python3
"""tools/progress_reporter.py — Reporter di avanzamento RUSABILE.

Ogni --every secondi legge il log di un processo lungo (driver, build,
qualunque job che scriva su un file), conta le UNITÀ completate, stima
il tempo rimanente con la media REALE delle ultime completazioni e
appende una riga di stato su un file, così l'utente vede sempre il
tempo in azione senza doverlo chiedere.

Riusabilità: funziona con QUALSISSI log — servono solo 3 regex:
  --start-regex  marker di "unità iniziata" (per dire COSA è in corso)
  --done-regex   marker di "unità completata" (per contarle)
  --finish-regex marker di "job finito" (per terminare il reporter)

Uso (esempio reale, driver benchmark a sessioni fredde):
    .venv/bin/python tools/progress_reporter.py \
        --log /tmp/opencode/bench_cold_sessions2.txt \
        --pid 16357 \
        --total 8 --every 120 \
        --out state/bench_progress.txt \
        --label "benchmark sessioni fredde"

Per guardare lo stato in diretta:
    tail -f state/bench_progress.txt

L'ETA si affina da solo: finché non c'è almeno una unità completata
mostra la stima a priori (--eta-guess); dopo, usa la media reale.
"""

import argparse
import glob
import re
import sys
import time
from datetime import datetime
from pathlib import Path


def max_temp() -> float:
    """Temperatura CPU attuale (stessa fonte del benchmark e del driver)."""
    m = 0.0
    for p in glob.glob("/sys/class/thermal/thermal_zone*/temp"):
        try:
            m = max(m, float(Path(p).read_text().strip()) / 1000.0)
        except Exception:
            pass
    return m


def _count(text: str, pattern: str) -> int:
    try:
        return len(re.findall(pattern, text))
    except re.error:
        return text.count(pattern)


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Reporter di avanzamento riusabile: ETA su file.")
    ap.add_argument("--log", required=True,
                    help="file di log del processo da monitorare")
    ap.add_argument("--out", default="state/bench_progress.txt",
                    help="file di stato su cui appendere le righe (default: "
                         "state/bench_progress.txt)")
    ap.add_argument("--pid", type=int, default=0,
                    help="PID del processo monitorato: se muore, il "
                         "reporter scrive 'processo terminato' ed esce")
    ap.add_argument("--total", type=int, default=8,
                    help="numero totale di unità (default 8)")
    ap.add_argument("--every", type=int, default=120,
                    help="secondi tra una riga di stato e l'altra (default 120)")
    ap.add_argument("--label", default="job",
                    help="etichetta leggibile nella riga di stato")
    ap.add_argument("--start-regex", default=r"=== (?:sessione|task) (\S+?)(?: ===|$)",
                    help="regex dell'unità iniziata (gruppo 1 = id)")
    ap.add_argument("--done-regex", default=r"external benchmark results salvati in",
                    help="regex dell'unità completata (default: la riga JSON "
                         "del benchmark, UNA per sessione — la riga di "
                         "riepilogo contiene la stessa parola e conterebbe "
                         "doppio)")
    ap.add_argument("--finish-regex", default=r"\[driver\] DONE",
                    help="regex del job completato (ferma il reporter)")
    ap.add_argument("--eta-guess", type=float, default=15.0,
                    help="minuti per unità stimati a priori, prima del "
                         "primo dato reale (default 15)")
    ap.add_argument("--max-cycles", type=int, default=0,
                    help="0 = infinito (default); >0 = si ferma dopo N cicli "
                         "(utile per i test)")
    args = ap.parse_args()

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    def write(line: str) -> None:
        """Appende la riga di stato e la stampa anche a video."""
        ts = datetime.now().strftime("%H:%M:%S")
        full = f"{ts} | {line}"
        with out_path.open("a", encoding="utf-8") as f:
            f.write(full + "\n")
        print(full, flush=True)

    write(f"AVVIO reporter '{args.label}' — log={args.log}, "
          f"obiettivo {args.total} unità, una riga ogni {args.every}s")

    # Storia delle completazioni: [(istante, count)] per calcolare la
    # media REALE tra completazioni successive.
    history: list[tuple[float, int]] = []
    cycles = 0
    started_at = time.time()

    while True:
        cycles += 1
        now = time.time()

        # --- legge il log ------------------------------------------------
        log_path = Path(args.log)
        if not log_path.exists():
            write(f"'{args.label}' | log non ancora creato ({args.log}) | "
                  f"CPU {max_temp():.1f}°C")
        else:
            try:
                text = log_path.read_text(encoding="utf-8", errors="replace")
            except Exception as e:
                text = ""
                write(f"'{args.label}' | ERRORE lettura log: {e}")

            done = _count(text, args.done_regex)
            history.append((now, done))
            history = history[-400:]  # limita memoria

            # --- job finito? -------------------------------------------------
            if args.finish_regex and _count(text, args.finish_regex):
                elapsed = (now - started_at) / 60.0
                write(f"'{args.label}' COMPLETATO: {done}/{args.total} unità "
                      f"in {elapsed:.0f} min di monitoraggio | "
                      f"CPU {max_temp():.1f}°C")
                return 0

            # --- unità in corso ----------------------------------------------
            starts = re.findall(args.start_regex, text)
            current = starts[-1] if starts else "-"
            # minuti dall'ultimo aumento di count (cioè dall'ultima unità finita)
            last_done_at = next((t for t, c in reversed(history) if c == done),
                                now)
            current_min = (now - last_done_at) / 60.0

            # --- ETA: media reale se disponibile, altrimenti stima a priori ---
            real_min: list[float] = []
            for i in range(1, len(history)):
                t0, c0 = history[i - 1]
                t1, c1 = history[i]
                if c1 > c0:
                    real_min.append((t1 - t0) / 60.0)
            per_unit = (sum(real_min[-5:]) / len(real_min[-5:])) \
                if real_min else args.eta_guess

            remaining = max(0, args.total - done)
            eta_min = per_unit * remaining
            eta_at = datetime.fromtimestamp(
                now + eta_min * 60).strftime("%H:%M")

            extra = ""
            if args.pid:
                try:
                    Path(f"/proc/{args.pid}")
                except FileNotFoundError:
                    write(f"'{args.label}' | PROCESSO {args.pid} TERMINATO "
                          f"senza marker DONE — completate {done}/{args.total}")
                    return 0
                extra = f" | pid {args.pid} vivo"

            write(f"'{args.label}' | completate {done}/{args.total} | "
                  f"in corso {current} (da {current_min:.0f} min) | "
                  f"rimanenti ~{eta_min:.0f} min (fine ~{eta_at}) | "
                  f"media {per_unit:.1f} min/unità | "
                  f"CPU {max_temp():.1f}°C{extra}")

        if args.max_cycles and cycles >= args.max_cycles:
            write(f"reporter fermato dopo {cycles} cicli (max-cycles)")
            return 0
        time.sleep(args.every)


if __name__ == "__main__":
    raise SystemExit(main())
