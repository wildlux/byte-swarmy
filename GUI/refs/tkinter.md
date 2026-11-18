# Modulo: external
# Tkinter — cheat sheet (byte-swarmy)

Tkinter è nella stdlib (no pip). Per GUI native più moderne: `ttk` (tema).

## App minima
```python
import tkinter as tk
from tkinter import ttk

root = tk.Tk()
root.title("Titolo")
root.geometry("400x300")

label = ttk.Label(root, text="0")
label.pack(pady=10)

def incrementa():
    n = int(label["text"]) + 1
    label.config(text=str(n))

btn = ttk.Button(root, text="Incrementa", command=incrementa)
btn.pack()

root.mainloop()
```

## Widget ttk (preferiti a tk per look moderno)
- `ttk.Label(parent, text=...)`
- `ttk.Button(parent, text=..., command=...)`
- `ttk.Entry(parent)` — `.get()` per leggere
- `ttk.Combobox(parent, values=[...])`
- `ttk.Checkbutton(parent, text=..., variable=var)`
- `ttk.Spinbox(parent, from_=0, to=100)`
- `ttk.Frame(parent)` — contenitore

## Layout
- `widget.pack(side=tk.LEFT, padx=5, pady=5)` — impila
- `widget.grid(row=0, column=0, padx=5, pady=5)` — griglia
- `widget.place(x=10, y=10)` — assoluto (evitare)
- `ttk.Frame` + pack/grid dentro per composizione

## Variabili (binding automatico)
```python
var = tk.StringVar(value="0")
entry = ttk.Entry(root, textvariable=var)
label = ttk.Label(root, textvariable=var)
```
Tipi: `StringVar`, `IntVar`, `DoubleVar`, `BooleanVar`.

## Threading (NON bloccare mainloop)
```python
import threading
def lavoro():
    # pesante
    root.after(0, lambda: label.config(text="fatto"))
threading.Thread(target=lavoro, daemon=True).start()
```
MAI chiamare `time.sleep` nel thread GUI. Usa `root.after(ms, fn)` per schedulare.

## Dialog
```python
from tkinter import messagebox, filedialog
messagebox.showinfo("Titolo", "Messaggio")
messagebox.showwarning("Attenzione", "...")
path = filedialog.askopenfilename()
path = filedialog.asksaveasfilename()
```

## Errori comuni
- Dimenticare `root.mainloop()` → finestra non appare
- Mescolare `pack` e `grid` nello stesso parent → crash
- Bloccare il main thread → finestra "non risponde"
- Usare `tk.Button` invece di `ttk.Button` → look vecchio
- Non passare `command` al Button → non fa nulla
