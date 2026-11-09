"""
hf_weights.py — Scaricamento pesi GGUF da Hugging Face + registrazione Ollama.

Flusso (funziona anche offline di hub, usa solo stdlib):
1. L'utente incolla un link diretto alla pagina/modello HF (es.
   "https://huggingface.co/RikiyaT/Qwen3.5-0.8B-weight-space-programming"
   oppure ".../blob/main/model.gguf") o un repo_id corto ("OWNER/REPO").
2. Leggiamo la repo via API Hub (https://huggingface.co/api/models/...),
   elenchiamo i file e scegliamo il GGUF più adatto a macchine 4GB RAM
   (quantizzazione Q4_K_M di default).
3. Streaming download con callback di progresso + cancel.
4. Registrazione su Ollama: si crea un Modelfile con FROM <gguf> e si lancia
   `ollama create <nome> -f Modelfile`, così il modello compare in `ollama
   list` ed è utilizzabile da orchestrator/benchmark/harness.

Il nome "pesi" è voluto: scarichiamo i tensori del modello (GGUF), che lo
harness di weight-space programming (CORE/weight_space_harness.py) attacca
a un decoder quando valuta il modello su problemi da programmatore.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Callable

from CORE.constants import OLLAMA_HOST

from CORE.regex_controller import sanitize_name

from CORE.state_repository import load_json, save_json

BASE_DIR = Path(__file__).resolve().parent.parent
WEIGHT_SPACE_DIR = BASE_DIR / "data" / "models" / "hf_weights"
REGISTRY_FILE = "state/hf_weights_registry.json"

HF_HOST = "https://huggingface.co"

# Preferenza quantizzazioni: prima le Q4 (friendly 4GB), poi Q5, poi il resto
QUANT_ORDER = [
    "Q4_K_M", "Q4_K_S", "Q4", "Q4_0",
    "Q5_K_M", "Q5_K_S", "Q5_0",
    "Q3_K_M", "Q3_K_S",
    "Q6_K", "Q2_K", "Q8_0",
    "F16", "BF16", "F32",
]


# =====================================================================
# Parsing del link
# =====================================================================

def parse_hf_link(link: str) -> dict:
    """Estrae repo_id, revision e filename opzionale da un link HF.

    Accetta:
      - https://huggingface.co/OWNER/REPO
      - https://huggingface.co/OWNER/REPO/blob/main/file.gguf
      - https://huggingface.co/OWNER/REPO/resolve/main/file.gguf
      - OWNER/REPO (id corto)
    Ritorna {"repo_id", "revision", "filename"} (revision/filename = "" se assenti).
    Solleva ValueError su link non validi.
    """
    link = (link or "").strip()
    if not link:
        raise ValueError("Link vuoto")
    # id corto: OWNER/REPO (niente slash oltre a questo, niente schema)
    if re.fullmatch(r"[A-Za-z0-9][\w.-]*__[A-Za-z0-9][\w.-]*|[\w.-]+/[\w.-]+", link) and "://" not in link:
        repo_id, revision, filename = link, "main", ""
        return {"repo_id": repo_id, "revision": revision, "filename": filename}

    m = re.match(r"(?:https?://)?(?:www\.)?huggingface\.co/([^/?#]+)/([^/?#]+?)(?:\.git)?(?:/.*)?$", link)
    if not m:
        raise ValueError(
            f"Link HF non riconosciuto: {link!r}. Usa la pagina del modello "
            "(https://huggingface.co/NOME/REPO) o un file blob/resolve."
        )
    repo_id = f"{m.group(1)}/{m.group(2)}"
    revision = "main"
    filename = ""

    # .../blob/<rev>/<file> o .../resolve/<rev>/<file>
    mb = re.search(r"/(resolve|blob|raw)/(?P<rev>[^/]+)/([^/?#]+)", link)
    if mb:
        revision = mb.group("rev")
        filename = mb.group(3)
    # .../download/<file> (senza revision esplicita)
    md = re.search(r"/download/([^/?#]+)", link)
    if md and not filename:
        filename = md.group(1)

    return {"repo_id": repo_id, "revision": revision, "filename": filename}


# =====================================================================
# API repo: elenco file
# =====================================================================

def list_repo_files(repo_id: str, revision: str = "main", timeout: int = 20) -> list:
    """Elenca i file della repo [{'path': str, 'size': int}] via API Hub."""
    url = f"{HF_HOST}/api/models/{repo_id}/revision/{revision}?blobs=true"
    req = urllib.request.Request(url, headers={"User-Agent": "byte-swarmy/0.3"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    files = []
    for sib in data.get("siblings", []) or []:
        path = sib.get("rfilename") or sib.get("path") or ""
        size = sib.get("size") or 0
        if path:
            files.append({"path": path, "size": int(size or 0)})
    return files


def pick_gguf(files: list, max_gb: float = 4.5) -> Optional[dict]:
    """Sceglie il GGUF più adatto: quantizzazioni Q4/Q5 prima, poi le altre.

    Ritorna il dict file {'path','size'} o None se non ci sono GGUF.
    """
    ggufs = [f for f in files if str(f["path"]).lower().endswith(".gguf")]
    if not ggufs:
        return None
    # ordina per classe quantizzazione, poi preferisci i più piccoli
    def quant_rank(path: str) -> int:
        upper = str(path).upper()
        for i, q in enumerate(QUANT_ORDER):
            if q in upper:
                return i
        return len(QUANT_ORDER)

    ranked = sorted(ggufs, key=lambda f: (quant_rank(f["path"]), f["size"]))
    # preferisci un file entro il budget RAM; altrimenti il primo ranked comunque
    within = [f for f in ranked if f["size"] <= max_gb * (1024 ** 3)]
    chosen = within[0] if within else ranked[0]
    return chosen


def resolve_download(info: dict, files: Optional[list] = None) -> dict:
    """Ritorna {'url', 'filename', 'size'} del file da scaricare.

    - Se il link include già il file (blob/resolve), usa quello.
    - Altrimenti sceglie il miglior GGUF della repo.
    """
    repo_id, revision, filename = info["repo_id"], info["revision"] or "main", info.get("filename") or ""
    if filename:
        files = files or list_repo_files(repo_id, revision)
        size = next((f["size"] for f in files if f["path"] == filename), 0)
        url = f"{HF_HOST}/{repo_id}/resolve/{revision}/{filename}"
        return {"url": url, "filename": filename, "size": size}
    if files is None:
        files = list_repo_files(repo_id, revision)
    picked = pick_gguf(files)
    if not picked:
        gguf_names = [f["path"] for f in files if str(f["path"]).lower().endswith(".gguf")]
        raise ValueError(
            f"Nessun file GGUF in {repo_id}. BYTE-SWARMY importa solo pesi GGUF "
            "(quantizzati). File trovati: " + (", ".join(n for n in gguf_names[:8]) or str(len(files)) + " file non-GGUF")
        )
    url = f"{HF_HOST}/{repo_id}/resolve/{revision}/{picked['path']}"
    return {"url": url, "filename": picked["path"], "size": picked["size"]}


def download_file(url: str, dest_dir: Path,
                  progress_cb: Optional[Callable[[str, float], None]] = None,
                  should_cancel: Optional[Callable[[], bool]] = None,
                  chunk_size: int = 1024 * 1024,
                  token: str = "") -> Path:
    """Scarica url in dest_dir con progresso (0..1) e cancel.

    progress_cb(stage, fraction): stage in {'download'} , fraction 0..1
    (se size sconosciuto, fraction = -1 e lo stage recupera 'bytes').
    """
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    filename = url.split("/")[-1].split("?")[0]
    dest = dest_dir / filename
    tmp = dest.with_suffix(dest.suffix + ".part")

    headers = {"User-Agent": "byte-swarmy/0.3"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    partial = 0
    if tmp.exists():
        ost = tmp.stat().st_size
        headers["Range"] = f"bytes={ost}-"
        partial = ost

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            total = int(resp.headers.get("Content-Length", 0)) or -1
            total_effective = total if total < 0 else (partial + total if partial else total)
            mode = "ab" if partial else "wb"
            with open(tmp, mode) as f:
                downloaded = partial
                while True:
                    if should_cancel and should_cancel():
                        f.close()
                        raise CancelledError("Download annullato dall'utente")
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb:
                        if total_effective > 0:
                            progress_cb("download", min(1.0, downloaded / total_effective))
                        else:
                            progress_cb("bytes", downloaded)
    except urllib.error.HTTPError as e:
        if e.code == 416:  # range non valido → riparti pulito
            tmp.unlink(missing_ok=True)
            return download_file(url, dest_dir, progress_cb, should_cancel, chunk_size, token)
        if e.code in (401, 403):
            raise ValueError(
                f"Accesso negato ({e.code}) a {url}. Se il modello è gated, inserisci "
                "un token HF nelle impostazioni (HF_TOKEN)."
            ) from e
        raise
    except (urllib.error.URLError, TimeoutError) as e:
        raise ConnectionError(f"Errore di rete scaricando {url}: {e}") from e

    tmp.replace(dest)
    if progress_cb:
        progress_cb("done", 1.0)
    return dest


class CancelledError(RuntimeError):
    pass


# =====================================================================
# Registrazione su Ollama
# =====================================================================

def sanitized_model_name(repo_id: str, filename: str) -> str:
    """Nome modello Ollama: repo corto + quantizzazione (lowercase, sicuro)."""
    stem = Path(filename).stem.lower()
    quant = ""
    mu = stem.upper()
    for q in QUANT_ORDER:
        if q.lower() in mu:
            quant = q.lower().replace("_", "-")
            break
    short_repo = repo_id.split("/")[-1].lower()
    name = f"hfw_{short_repo}" + (f"-{quant}" if quant else "")
    # insieme legale ollama: [a-z0-9._-]
    return sanitize_name(name, maxlen=120)


def register_with_ollama(gguf_path: Path, model_name: str,
                         num_ctx: int = 3072, num_thread: int = 0,
                         host: str = OLLAMA_HOST,
                         timeout: int = 600) -> dict:
    """Crea un Modelfile FROM <gguf> e lancia `ollama create <name>`.

    Ritorna {"name", "gguf": str(path), "modelfile": str(path)}.
    """
    gguf_path = Path(gguf_path)
    if not gguf_path.exists():
        raise FileNotFoundError(f"File pesi non trovato: {gguf_path}")

    family_dir = WEIGHT_SPACE_DIR / model_name
    family_dir.mkdir(parents=True, exist_ok=True)
    modelfile = family_dir / "Modelfile"
    params = [f"FROM {gguf_path}", f"PARAMETER num_ctx {num_ctx}",
              "PARAMETER temperature 0.1"]
    if num_thread > 0:
        params.append(f"PARAMETER num_thread {num_thread}")
    modelfile.write_text("\n".join(params) + "\n", encoding="utf-8")

    if not shutil.which("ollama"):
        raise RuntimeError("Ollama non trovata nel PATH: impossibile registrare il modello.")
    cmd = ["ollama", "create", model_name, "-f", str(modelfile)]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if result.returncode != 0:
        raise RuntimeError(
            f"ollama create fallito (exit {result.returncode}): {result.stderr.strip()[:500]}"
        )
    return {"name": model_name, "gguf": str(gguf_path), "modelfile": str(modelfile)}


def is_ollama_up(host: str = OLLAMA_HOST, timeout: int = 4) -> bool:
    try:
        with urllib.request.urlopen(f"{host}/api/tags", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


# =====================================================================
# Registry (modelli già scaricati)
# =====================================================================

def load_registry() -> list:
    data = load_json(REGISTRY_FILE, {"models": []})
    if not isinstance(data, dict):
        return {"models": []}
    models = data.get("models", [])
    return models if isinstance(models, list) else []


def save_registry(models: list) -> None:
    save_json(REGISTRY_FILE, {"models": models})


def add_to_registry(entry: dict) -> list:
    models = load_registry()
    models = [m for m in models if m.get("name") != entry.get("name")]
    models.insert(0, entry)
    save_registry(models[:50])  # tieni solo gli ultimi 50
    return models


def gguf_meta(gguf_path: Path, max_kv: int = 40) -> dict:
    """Parser GGUF minimo: legge magic/version e i primi KV header.

    Ritorna dict con architettura/nome/parametri se presenti
    (general.architecture, general.name, ecc.). Serve a mostrare
    "cosa contiene il file dei pesi" senza librerie esterne.
    """
    vals: dict = {}
    try:
        with open(gguf_path, "rb") as f:
            magic = f.read(4)
            if magic != b"GGUF":
                return vals
            _version = int.from_bytes(f.read(4), "little")
            _tensors = int.from_bytes(f.read(8), "little")
            kv_count = int.from_bytes(f.read(8), "little")

            def _rd_str():
                n = int.from_bytes(f.read(4), "little")
                if n > 1024 * 1024:
                    raise ValueError("stringa troppo lunga")
                return f.read(n).decode("utf-8", "replace")

            def _rd_scalar(t):
                sizes = {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 10: 8}
                if t == 7:
                    return bool(f.read(1)[0])  # bool
                if t == 6:
                    b = f.read(8)
                    import struct
                    return struct.unpack("<d", b)[0]
                n = sizes.get(t, 4)
                b = f.read(n)
                import struct
                fmt = {0: "<B", 1: "<b", 2: "<H", 3: "<h", 4: "<I", 5: "<i", 10: "<d"}.get(t)
                if not fmt:
                    raise ValueError("tipo non gestito")
                return struct.unpack(fmt, b)[0]

            count = 0
            while count < min(kv_count, max_kv):
                key = _rd_str()
                vtype = int.from_bytes(f.read(4), "little")
                if vtype == 8:
                    val = _rd_str()
                elif vtype == 9:
                    base_t = int.from_bytes(f.read(4), "little")
                    n_elem = int.from_bytes(f.read(8), "little")
                    if base_t == 8:
                        first = _rd_str() if n_elem > 0 else ""
                        val = f"<array str[{n_elem}]>: {first[:60]}"
                    else:
                        f.seek(max(0, n_elem * {0: 1, 1: 1, 2: 2, 3: 2, 4: 4, 5: 4, 6: 4, 7: 1, 10: 8}.get(base_t, 4)), 1)
                        val = f"<array[{n_elem}] type={base_t}>"
                else:
                    val = _rd_scalar(vtype)
                if isinstance(val, (str, int)):
                    vals[key] = val[:80] if isinstance(val, str) else val
                count += 1
    except Exception:
        pass
    return {k: v for k, v in vals.items() if k.startswith("general.")}


def human_size(n: float) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
