# 📱 Mobile scaffold — verifica strutturale (F1)

_Generato deterministicamente da `tools/mobile_scaffold_check.py` — zero LLM, zero rete, zero GPU, zero timestamp._

Questo gate verifica **solo struttura e copertura dei ref**. Non compila Swift/Kotlin e non dimostra che un'app giri su un dispositivo: per questo l'asse Mobile resta 2/4, non 4/4.

| Piattaforma | Template | Ref | SLOT | Import | Costrutti | Simboli | Build |
|---|---|---|---|---|---|---|---|
| Android / Jetpack Compose | `mobile_android.kt.tpl` | `android_compose.md` | ✅ | ✅ | ✅ | ✅ | ⚠️ non verificata (`ASSENTE`) |
| iOS / SwiftUI | `mobile_ios.swift.tpl` | `swiftui.md` | ✅ | ✅ | ✅ | ✅ | ⚠️ non verificata (`ASSENTE`) |

## Dettagli

### Android / Jetpack Compose — PASS

- Nessuna anomalia strutturale rilevata.

### iOS / SwiftUI — PASS

- Nessuna anomalia strutturale rilevata.

## Limite onesto

- `api_lookup(strict=True)` è un gate Python: qui non si applica. I simboli mobile sono **statici**, verificati solo come presenza nei ref curati `GUI/refs/mobile/`.
- La build richiede Xcode/iOS SDK e Android SDK, assenti in questo ambiente. Nessun verdetto di compilabilità.
- Il collaudo con LLM resta 🔒 bloccato finché le ventole non sono verificate (≤60 °C).
