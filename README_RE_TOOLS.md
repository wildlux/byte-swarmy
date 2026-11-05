# Reverse Engineering Tools per byte-swarmy

Modulo Python che integra **Ghidra**, **Wireshark/tshark**, **radare2** e **capstone** nel swarm, esponendoli come tool per il worker.

## 📦 File generati

Tutti i file sono in `/home/z/my-project/download/`:

| File | Cosa fa |
|---|---|
| `re_tools.py` (627 righe) | Modulo Python con 9 tool RE |
| `requirements_re.txt` | Librerie pip da installare |
| `setup_re_tools.sh` (268 righe) | Script che installa i tool di sistema |
| `test_re_tools.py` | Test suite per verificare l'installazione |
| `README_RE_TOOLS.md` | Questo file |

## 🚀 Installazione (5 step)

### Step 1: Copia i file nel progetto

```bash
cd ~/Desktop/byte-swarmy

# Copia i 4 file scaricati nelle posizioni corrette
cp /path/to/download/re_tools.py          CORE/re_tools.py
cp /path/to/download/requirements_re.txt  requirements_re.txt
cp /path/to/download/setup_re_tools.sh    scripts/setup/re_tools.sh
cp /path/to/download/test_re_tools.py     tests/test_re_tools.py

chmod +x scripts/setup/re_tools.sh
```

### Step 2: Esegui lo script di setup

Lo script installa tutto: radare2, tshark, binutils, yara, Ghidra, e i pip packages.

```bash
./scripts/setup/re_tools.sh
```

Per saltare Ghidra (richiede Java 17+):

```bash
./scripts/setup/re_tools.sh --no-ghidra
```

Solo verifica (no install):

```bash
./scripts/setup/re_tools.sh --check
```

### Step 3: Verifica installazione

```bash
# Self-test del modulo
python3 CORE/re_tools.py --check

# Test suite completa
python3 tests/test_re_tools.py

# Prova su un binario reale
python3 CORE/re_tools.py --call binary_info /bin/ls
python3 CORE/re_tools.py --call extract_strings /bin/ls
python3 CORE/re_tools.py --call disassemble_capstone /bin/ls
```

### Step 4: Pip packages installati

Il file `requirements_re.txt` installa:

```bash
pip install -r requirements_re.txt
```

| Package | Cosa fa |
|---|---|
| `capstone` | Disassemblatore puro Python (x86, ARM, MIPS, AArch64) |
| `r2pipe` | Binding Python per radare2 |
| `pyshark` | Wrapper Python per tshark (Wireshark CLI) |
| `pefile` | Parser file PE/EXE Windows |
| `lief` | Parser multi-formato (ELF, PE, Mach-O) |
| `scapy` | Manipolazione pacchetti e pcap senza tshark |
| `yara-python` | Pattern matching per analisi malware |

### Step 5: (Opzionale) Integrazione nel worker

Per far usare questi tool al worker di byte-swarmy, aggiungi in `CORE/tools.py`:

```python
# In cima a CORE/tools.py
from CORE.re_tools import RE_TOOLS as _RE_TOOLS, call_re_tool

# Nel tool registry del worker (dove registra gli altri tool)
TOOL_REGISTRY.update({
    name: {
        "fn": lambda args, _n=name: call_re_tool(_n, args),
        "signature": info["signature"],
        "desc": info["desc"],
    }
    for name, info in _RE_TOOLS.items()
})

# Nel prompt del worker, aggiungi:
# "You also have access to Reverse Engineering tools:
#  - binary_info(path), extract_strings(path)
#  - disassemble_capstone(path, arch, mode), disassemble_radare2(path, address)
#  - decompile_ghidra(path, function_name)
#  - analyze_pcap(pcap_path), protocol_stats_pcap(pcap_path)
# Use these for reverse engineering tasks on binaries and pcap files."
```

## 🛠️ Tool esposti (9 totali)

### Binary analysis (binutils)

| Tool | Signature | Descrizione |
|---|---|---|
| `binary_info` | `binary_info(path)` | File type, ELF header, symbols, hash |
| `extract_strings` | `extract_strings(path, min_len=4, max_strings=200)` | Stringhe stampabili dal binario |

### Disassembly

| Tool | Signature | Descrizione |
|---|---|---|
| `disassemble_capstone` | `disassemble_capstone(path, arch='x86', mode='64', offset=0, count=50)` | Disassembly puro Python (no tool esterni) |
| `disassemble_radare2` | `disassemble_radare2(path, address=None, count=50)` | Disassembly con radare2 (più features) |
| `list_functions_radare2` | `list_functions_radare2(path)` | Lista funzioni trovate da radare2 |

### Decompilation

| Tool | Signature | Descrizione |
|---|---|---|
| `decompile_ghidra` | `decompile_ghidra(path, function_name=None, timeout=120)` | Decompila in pseudocodice C con Ghidra headless |

### Network analysis (Wireshark/tshark)

| Tool | Signature | Descrizione |
|---|---|---|
| `analyze_pcap` | `analyze_pcap(pcap_path, display_filter=None, packet_count=20)` | Primi N pacchetti con info protocollo |
| `protocol_stats_pcap` | `protocol_stats_pcap(pcap_path)` | Statistiche gerarchia protocolli |
| `pcap_conversations` | `pcap_conversations(pcap_path)` | Conversazioni TCP/UDP |

## 📋 Esempi d'uso

### Esempio 1: Analizza un binario Linux

```bash
python3 CORE/re_tools.py --call binary_info /bin/ls
python3 CORE/re_tools.py --call extract_strings /bin/ls
python3 CORE/re_tools.py --call list_functions_radare2 /bin/ls
python3 CORE/re_tools.py --call disassemble_capstone /bin/ls
```

### Esempio 2: Decompila con Ghidra

```bash
# Tutte le funzioni (max 30)
python3 -c "
from CORE.re_tools import call_re_tool
print(call_re_tool('decompile_ghidra', ['/bin/ls']))
"

# Solo una funzione specifica
python3 -c "
from CORE.re_tools import call_re_tool
print(call_re_tool('decompile_ghidra', ['/bin/ls', 'main']))
"
```

### Esempio 3: Analizza pcap di Wireshark

```bash
# Cattura 100 pacchetti su eth0 (richiede sudo)
sudo tshark -i eth0 -c 100 -w /tmp/capture.pcap

# Analizza
python3 CORE/re_tools.py --call analyze_pcap /tmp/capture.pcap
python3 CORE/re_tools.py --call protocol_stats_pcap /tmp/capture.pcap
python3 CORE/re_tools.py --call pcap_conversations /tmp/capture.pcap
```

### Esempio 4: Usa dal codice Python

```python
from CORE.re_tools import call_re_tool, check_re_environment, RE_TOOLS

# Verifica ambiente
env = check_re_environment()
print("Available tools:", {k: v for k, v in env.items() if v})

# Analizza un binario sospetto
binary_path = "/tmp/suspicious_binary"
info = call_re_tool("binary_info", [binary_path])
strings = call_re_tool("extract_strings", [binary_path, 6, 500])
functions = call_re_tool("list_functions_radare2", [binary_path])

# Decompila funzione main
main_decompiled = call_re_tool("decompile_ghidra", [binary_path, "main"])

print(info)
print(strings)
print(functions)
print(main_decompiled)
```

## 🔧 Requisiti di sistema

| Tool | Apt package | Note |
|---|---|---|
| `radare2` | `radare2` | `sudo apt install radare2` |
| `tshark` | `tshark` | `sudo apt install tshark` (appartiene a Wireshark) |
| `binutils` | `binutils` | `sudo apt install binutils` (file, readelf, nm, strings, objdump) |
| `yara` | `yara` | `sudo apt install yara` |
| `Ghidra` | (download) | NON in apt. Download da https://ghidra-sre.org/. Richiede Java 17+ |

Lo script `setup_re_tools.sh` installa tutto automaticamente.

## 🐛 Troubleshooting

### "ERROR: r2pipe not installed"
```bash
pip install r2pipe
sudo apt install radare2
```

### "ERROR: capstone not installed"
```bash
pip install capstone
```

### "ERROR: Ghidra not installed"
```bash
# Opzione A: usa lo script
./scripts/setup/re_tools.sh

# Opzione B: manuale
# 1. Installa Java 17
sudo apt install openjdk-17-jdk

# 2. Download Ghidra
wget https://github.com/NationalSecurityAgency/ghidra/releases/download/Ghidra_11.1.2_build/ghidra_11.1.2_PUBLIC_11.1.2_build.zip
unzip ghidra_*.zip -d /opt/
sudo ln -sf /opt/ghidra_*/support/analyzeHeadless /usr/local/bin/analyzeHeadless
```

### "ERROR: tshark not installed"
```bash
sudo apt install tshark
# Verifica
tshark --version
```

### "ERROR: pyshark failed"
Pyshark richiede tshark. Verifica:
```bash
which tshark
tshark --version
```

### Ghidra va in timeout
Binari troppo grandi. Aumenta timeout:
```python
result = call_re_tool("decompile_ghidra", [path, None, 300])  # 5 min
```

## 🎯 Test funzionali

Per verificare che tutto funzioni:

```bash
# 1. Self-test ambiente
python3 CORE/re_tools.py --check

# 2. Test suite completa
python3 tests/test_re_tools.py

# Output atteso:
# 9/9 test passati (100%)
# ✓ PASS  Environment check
# ✓ PASS  Tool registry
# ✓ PASS  Call unknown tool
# ✓ PASS  Non-existent file handling
# ✓ PASS  binary_info on /bin/ls
# ✓ PASS  extract_strings
# ✓ PASS  disassemble_capstone
# ✓ PASS  pcap analysis
# ✓ PASS  Tool registry consistency
```

## 📚 Risorse

- **Ghidra**: https://ghidra-sre.org/ | https://github.com/NationalSecurityAgency/ghidra
- **radare2**: https://www.radare.org/ | https://github.com/radareorg/radare2
- **Wireshark/tshark**: https://www.wireshark.org/ | `man tshark`
- **capstone**: https://www.capstone-engine.org/ | `pip install capstone`
- **pyshark**: https://github.com/KimiNewt/pyshark
- **r2pipe**: https://github.com/radareorg/radare2-r2pipe

## ⚠️ Note legali

- Usa questi tool **solo su binari e pcap che hai il diritto di analizzare**
- Non decompilare software proprietario senza autorizzazione
- Per analisi malware, usa un ambiente sandboxed (VM dedicata)
- Ghidra è distribuito da NSA sotto Apache 2.0 — uso libero

---

**Autori**: byte-swarmy RE module
**Versione**: 1.0
**Data**: 2026-11-05
