---
name: mobile-scaffold
description: Skill per creare scheletri di app iOS/Android partendo da template SwiftUI e Kotlin Compose curati, con gate strutturale offline. Usa quando l'utente chiede di creare un'app iOS, Android, mobile, una schermata SwiftUI o un Activity Compose.
---

# Scaffolding mobile — struttura, non build

Il modello 3b non deve inventare API SwiftUI/Compose. La policy è la stessa
di `py-gui-scaffold`: **riempire un template curato**, non generare la
struttura da zero.

## 1. Scegli il template

| File in `GUI/refs/templates/` | Quando usarlo |
|---|---|
| `mobile_ios.swift.tpl` | schermata iOS minima in SwiftUI (`ContentView`, `@State`) |
| `mobile_android.kt.tpl` | schermata Android minima in Kotlin + Jetpack Compose (`MainActivity`, `@Composable`) |

Sostituire solo i valori marcati `# SLOT:`. Nessun timestamp nei file.

## 2. Verifica i simboli con i ref statici

I simboli sono elencati in `GUI/refs/mobile/swiftui.md` e
`GUI/refs/mobile/android_compose.md`. `api_lookup(strict=True)` **non si
applica**: è un gate Python e non introspetta Swift/Kotlin.

- non aggiungere import o simboli fuori dai ref senza una nuova verifica;
- eseguire `.venv/bin/python tools/mobile_scaffold_check.py`;
- il report `RAG/DOCS/MOBILE_SCAFFOLD_REPORT.md` deve essere `PASS`.

## 3. Limiti da dire sempre

- Il gate controlla **struttura, import, costrutti e copertura dei ref**;
  **non compila** e non dimostra che l'app giri su un dispositivo.
- Xcode/iOS SDK e Android SDK non sono presenti in questo ambiente.
- L'asse radar Mobile è **2/4**: 3/4 richiede build reale e un task live
  con SDK/LLM, 🔒 bloccato finché le ventole non sono verificate (≤60 °C).
- Nessun `app.exec()`, nessun emulatore e nessuna rete nei test.
