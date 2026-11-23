# Misura RPM esterna — procedura per sbloccare M3 (gate termico)

**Stato al 2026-11-22**: `data/state/fan_verified.json` assente, gate chiuso.
Questa procedura non inventa misure: serve un **tachometro fisico** e la tua
dichiarazione di operatore. Ho aggiunto il canale sicuro per registrarla
(`tools/blocker_probe.py --attest-rpm`), mantenendo il gate stretto.

## Perché i sensori non bastano (evidenza reale)

| Fatto | Valore misurato |
|---|---|
| Modello | HP Pavilion Power Laptop 15-cb0xx |
| Profilo nbfc selezionato | `HP Pavilion 17 Notebook PC` (**modello diverso**) |
| `nbfc status` → Current Fan Speed | `0.00` (percentuale, non RPM — Cycle 122) |
| `nbfc status` → Target Fan Speed | `0.00 %` al 2026-11-22 |
| `Auto Control Enabled` | `true` |
| `/sys/class/hwmon/hwmon*/fan*_input` | nessun nodo presente (verificato ancora il 2026-11-22) |
| `hwmon5` (`hp`) → `pwm1` | `N/A` — duty-cycle, **non** una misura di giri |
| `/sys/kernel/debug/ec/` | non accessibile |
| Temperatura CPU (coretemp) | 65,0 °C al momento dell'audit (sopra la soglia 60 °C del gate) |
| `tools/blocker_probe.py --check-fan` | `fan_verified.json: NON VALIDO` |

Audit del 2026-11-22: `find /sys -name 'fan*_input' -o -name 'fan*_rpm'` non
restituisce alcun nodo; `sensors` mostra solo `pwm1: N/A` per il chip `hp`.
Non esiste quindi alcuna sorgente RPM leggibile: il tachometro esterno resta
l'unico canale ammesso.

Il duty-cycle non è una misura dei giri: la decisione esplicita del
2026-11-22 vieta surrogati. `nbfc` attivo non dimostra che la ventola giri.
Dal Cycle 122 il probe accetta come RPM **solo valori con unità esplicita**
(`3200 RPM`): `Current Fan Speed : 50.00` di nbfc è una percentuale (0-100)
e non può più aprire il gate. Serve comunque la misura fisica esterna.

## Cosa serve

Un tachometro **ottico** (o un contagiri a paletta/induttivo) in grado di
leggere i giri della ventola CPU attraverso le griglie di aerazione. In
alternativa, uno strumento che esponga direttamente RPM: non sono ammessi
valori dedotti da duty, tensione, corrente o rumore.

## Procedura

### Via rapida — un solo comando (Cycle 136)

Dopo aver letto il tachometro, tutto il resto è automatico:

```bash
cd /home/wildlux/Desktop/byte-swarmy
./tools/attest_rpm.py
```

Lo script chiede RPM, strumento, metodo, operatore e note; poi scrive la
ricevuta in `data/state/rpm_attestation.json` (0600, gitignored), la valida
con le stesse regole del probe, rilegge la temperatura CPU **live** e scrive
`fan_verified.json` solo se RPM > 0 e 0 < T ≤ 60 °C. Stampa `Gate VALIDO`
e il comando successivo. Non accetta RPM da argomenti: il valore viene solo
digitato dall'operatore. Se la CPU è sopra 60 °C rifiuta e non scrive il gate.

I passi manuali qui sotto restano la via alternativa equivalente.

1. **Fai girare la ventola** in modo stabile (carico CPU moderato, non oltre
   la soglia termica; se la CPU supera 60 °C il tool rifiuterà comunque).
2. **Misura i RPM** con lo strumento esterno. Annota il valore intero.
3. **Subito dopo**, crea la ricevuta in `data/state/rpm_attestation.json`
   (gitignored, fuori dal tree versionato). Parti dal template
   `DOCS/rpm_attestation.example.json` e sostituisci i campi:

   ```json
   {
     "fan_rpm": 1800,
     "instrument": "tachometro ottico DT-6234B",
     "method": "lettura ottica su paletta ventola CPU attraverso griglia",
     "operator": "wildlux",
     "measured_at": "2026-11-22T16:50:00+00:00",
     "notes": "misura presa su 3 letture consecutive, valori 1780-1820 RPM"
   }
   ```

4. **Registra il gate** (il tool rilegge la temperatura dal vivo):

   ```bash
   cd /home/wildlux/Desktop/byte-swarmy
   .venv/bin/python tools/blocker_probe.py --attest-rpm data/state/rpm_attestation.json
   .venv/bin/python tools/blocker_probe.py --check-fan   # deve dire VALIDO
   ```

5. **Rigenera il report** con la nuova evidenza:

   ```bash
   .venv/bin/python tools/blocker_probe.py --out DOCS/BLOCKER_PROBE_REPORT.md
   ```

## Cosa valida il tool (nessun valore passato a mano)

Il tool NON ha un'opzione `--rpm`: passare un numero a mano è impossibile.
La ricevuta deve avere tutti i campi obbligatori, RPM in range fisico
300–6000, `measured_at` fresca (≤30 min) e non nel futuro, e il file deve
stare in `data/state/` o fuori dal repo. La temperatura è **sempre** riletta
da sysfs e deve essere `0 < temp_c <= 60`. Il duty resta registrato come
contesto (`fan_duty_pct_context_only`) e non entra nel gate.

Se la CPU è sopra 60 °C al momento della registrazione, il tool rifiuta e
non scrive nulla: in quel caso attendi il raffreddamento e ripeti la misura.

## Cosa sblocca (e cosa no)

Con il gate valido si sbloccano: C3, M7, SLOT-4/5, Fase C/F/G/H, D-16, P2-4,
P3-8 e le misure LLM. La **suite completa locale resta vietata**: M2/M6
richiedono il trigger CI su GitHub Actions, dove la diagnostica è già pronta.

Nessuna misura è stata inventata per preparare questa procedura: i valori
mostrati sono letture reali di `sensors` e `nbfc status`.
