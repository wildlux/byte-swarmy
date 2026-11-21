#!/usr/bin/env python3
"""test_cloud_api.py — prova un provider cloud gratuito (Groq/Gemini/OpenRouter).

Uso:
    # 1) salva la chiave (una volta sola; finisce in state/cloud_api.json 0600)
    .venv/bin/python tools/test_cloud_api.py --provider groq --save-key "gsk_..."

    # 2) elenca i modelli disponibili
    .venv/bin/python tools/test_cloud_api.py --provider groq --list

    # 3) test di chat (modello scelto in automatico se --model è omesso)
    .venv/bin/python tools/test_cloud_api.py --provider groq \
        --prompt "Scrivi una funzione Python che somma due interi."

La chiave può anche arrivare da variabile d'ambiente:
GROQ_API_KEY / GEMINI_API_KEY / OPENROUTER_API_KEY.
"""

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from CORE import cloud_client as cc  # noqa: E402


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--provider", choices=sorted(cc.PROVIDERS),
                    default="groq")
    ap.add_argument("--model", default="", help="id modello (default: auto)")
    ap.add_argument("--prompt", default="Rispondi solo con: OK")
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--list", action="store_true", help="elenca i modelli")
    ap.add_argument("--save-key", default="", help="salva la chiave API")
    args = ap.parse_args()

    info = cc.provider_info(args.provider)
    if args.save_key:
        cc.save_api_key(args.provider, args.save_key)
        print(f"✅ Chiave salvata per {info['label']} in "
              f"{cc.KEYS_FILE} (permessi 0600).")
        return 0

    if not cc.has_api_key(args.provider):
        print(f"❌ Manca la chiave API per {info['label']}.\n"
              f"   Ottienila gratis su: {info['signup']}\n"
              f"   Poi: .venv/bin/python tools/test_cloud_api.py "
              f"--provider {args.provider} --save-key \"LA_TUA_CHIAVE\"")
        return 1

    try:
        models = cc.list_models(args.provider)
    except Exception as e:
        print(f"❌ Errore nel recupero modelli: {e}")
        return 2
    print(f"✅ {info['label']}: {len(models)} modelli disponibili")
    if args.list:
        for m in models:
            print("  -", m)
        return 0

    model = args.model or cc.pick_default_model(args.provider, models)
    if not model:
        print("❌ Nessun modello chat utilizzabile.")
        return 3
    print(f"🤖 Modello scelto: {model}")
    try:
        res = cc.chat(args.provider, model,
                      [{"role": "user", "content": args.prompt}],
                      max_tokens=args.max_tokens)
    except Exception as e:
        print(f"❌ Errore chat: {e}")
        return 4
    print(f"⏱️  {res['elapsed']:.2f}s · usage={res['usage']}")
    print("─" * 60)
    print(res["content"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
