CONTENT = '''# BYTE-SWARMY

<p align="center">
  <img src="IMG/documentazione.jpeg" alt="BYTE-SWARMY — Swarm autonomo locale" width="720">
</p>

<p align="center">
  <strong>Sistema multi-agente autonomo, interamente locale, per macchine con 4 GB di RAM.</strong>
</p>

<p align="center">
  <a href="https://github.com/wildlux/byte-swarmy/actions"><img alt="CI" src="https://github.com/wildlux/byte-swarmy/actions/workflows/tests.yml/badge.svg"></a>
  <img alt="Version" src="https://img.shields.io/badge/version-0.1.0-blue">
  <img alt="License" src="https://img.shields.io/badge/license-MIT-green">
  <img alt="Python" src="https://img.shields.io/badge/python-3.11%2B-yellow">
  <img alt="Ollama" src="https://img.shields.io/badge/Ollama-required-orange">
  <img alt="RAM" src="https://img.shields.io/badge/RAM-4%20GB%20min-red">
  <img alt="Platform" src="https://img.shields.io/badge/platform-Linux-lightgrey">
  <img alt="Cloud" src="https://img.shields.io/badge/cloud-NOT%20needed-success">
</p>

<p align="center">
  <em>"The swarm works. You think elsewhere."</em>
</p>

---

> **Nessun cloud, nessuna GPU, nessuna dipendenza da servizi esterni:**
> solo Ollama, Python e file JSON. I worker eseguono task di programmazione,
> test e documentazione sotto il controllo di un orchestratore deterministico.

**Versione:** 0.1.0 · **Licenza:** MIT · **Piattaforma:** Linux

---

## Indice

- [Sicurezza](#sicurezza)
- [Panoramica](#panoramica)
- [Perché BYTE-SWARMY?](#perché-byte-swarmy)
- [Demo](#demo)
- [Architettura](#architettura)
- [Requisiti](#requisiti)
- [Installazione](#installazione)
- [Avvio rapido](#avvio-rapido)
- [Utilizzo](#utilizzo)
- [Come funziona](#come-funziona)
- [Sicurezza in profondità](#sicurezza-in-profondità)
- [Struttura del progetto](#struttura-del-progetto)
- [Sviluppo e test](#sviluppo-e-test)
- [Limiti noti](#limiti-noti)
- [Troubleshooting](#troubleshooting)
- [Compatibilità](#compatibilità)
- [Contribuire](#contribuire)
- [Licenza](#licenza)
- [Ringraziamenti](#ringraziamenti)

---

## Sicurezza

> **Regola 0 — la difesa è sempre attiva.**
> Ogni task è trattato come potenzialmente ostile (prompt injection). La policy
> di sicurezza è applicata nel codice a ogni chiamata di tool e **non può essere
> disattivata** da configurazione, prompt, task MCP o output del modello.

BYTE-SWARMY esegue codice generato da LLM piccoli con i permessi dell'utente che
avvia l'orchestratore. Le protezioni incluse bloccano i comandi più pericolosi,
ma **non sostituiscono un isolamento di sistema**:

- `run_bash` non usa una shell: allowlist, blacklist e path confinati in `project/`;
- `git push` / `pull` / `remote add|remove` sono disabilitati per i worker;
- ambiente sanificato (niente token, `SSH_AUTH_SOCK`, `HOME` reale);
- limiti di CPU, memoria, dimensione file e timeout sul process group;
- task MCP ricostruiti da zero e URL limitati a `http`/`https`;
- audit log con rotazione in `logs/security.log`.

Per dati reali è necessario aggiungere l'isolamento di sistema (utente dedicato,
cgroup, firewall):

```bash
./setup-hardening.sh                  # diagnostica, nessuna modifica
sudo ./setup-hardening.sh --all       # utente byteswarmy + cgroup + firewall
