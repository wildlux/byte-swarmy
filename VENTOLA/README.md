# 🌀 VENTOLA

Controllo semplice delle ventole per notebook HP (testato su
HP Pavilion Power 15-cb0xx) via `nbfc` + `pkexec`.

## Avvio

```bash
./avvia.sh
```

(o doppio click su `avvia.sh` in Dolphin → "Esegui")

## Bottoni

| Bottone | Cosa fa |
|---------|---------|
| 🌀 **MAX 100%** | avvia il servizio nbfc e mette le ventole al massimo |
| 🌙 **AUTO** | torna al profilo automatico di nbfc |
| ⛔ **OFF 0%** | ferma le ventole |
| 🛑 **Stop servizio** | chiude il servizio nbfc |

Al primo comando KDE apre il suo dialog password (polkit/pkexec):
nessun terminale, nessun sudo da configurare.

## Da terminale (equivalente)

```bash
sudo nbfc start && sudo nbfc set -s 100   # ventole al massimo
sudo nbfc set -a                          # automatico
sudo nbfc set -s 0                        # spente
sudo nbfc stop                            # ferma il servizio
```

## Perché esiste

Il laptop ha subito un **blocco UEFI per surriscaldamento** durante i
run LLM (Cycle 73): la curva di default dell'EC è troppo conservativa
sotto carico sostenuto. Le ventole al massimo sono un **prerequisito**
dei run di byte-swarmy (`tools/swarm_refactor_session.py` ha una
guardia dura: mai inferenza se una zona termica ≥ 90°C).

La temperatura mostrata è la **max su tutte le zone termiche**
(comprese CPU e il sensore DPTF B0D4, reale e critico su questo
modello): verde < 60°C, arancione 60-80°C, rosso ≥ 80°C.
