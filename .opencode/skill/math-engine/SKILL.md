---
name: math-engine
description: Calcoli matematici complessi e simbolici (derivate, integrali, limiti, algebra, calcoli con simboli) con verifica deterministica. Usa quando l'utente chiede derivate, integrali, limiti, calcoli simbolici o calcoli complessi da report/formule.
---

# Math Engine — skill unica per calcoli matematici complessi

Flusso deterministico per: **formula matematica → calcolo simbolico/numerico →
verifica → esportazione (PDF/Excel/Word/SVG come da `research-report`)**.

## 1. Scopo

- Derivate (prima, seconde, calcolo automatico), integrali, limiti,
  algebra lineare, calcoli simbolici complessi.
- I calcoli sono **deterministici**: mai "facciamo finta" di un risultato.

## 2. Stack e scelte

- Simbolo: `sympy` se installabile; altrimenti derivazione analitica manuale
  passo-passo + calcolo numerico (`mpmath`/`fractions`) come fallback.
- Variabili dichiarate e fissate (nessuna ambiguità).
- Numerico: valutazione numerica con messa in virgola, precisione dichiarata.

## 3. Workflow

1. Formalizza la formula (in chiaro: funzione, variabili, dominio).
2. Calcolo (sympy o manuale/numerico).
3. **Verifica**: derivata → derivata seconda → derivata terza ≈ 0 (per derivate);
   limite; integrazione (differenziata di nuovo → ≈ 0).
4. Esporta: numerico → XLSX/CSV; simbolico → espressione nel report.

## 4. Quality gates

- Simboli noti e variabili dichiarate.
- Risultato verificato (riduzione del risultato).
- Numeri con precisione dichiarata (es. 15 cifre significative).

## 5. Comandi chiave

```bash
python -c "import sympy; print(sympy.__version__)"   # disponibilità
python - <<'PY'
import sympy as sp
x, y = sp.symbols('x y')
f = sp.sin(x) * sp.exp(x)
print(sp.diff(f, x))
PY
```

Se `sympy` non è installato: `pip install sympy` (o procedere con calcolo
analitico manuale + numerico).
