Come si avvia
bash

cd /home/z/my-project/download/ai-civ
python add_task.py --from-file tasks/first-task.json
nohup python orchestrator.py > logs/stdout.log 2>&1 &
echo $! > state/orchestrator.pid
Poi stacchi e vai a fare altro. Per fermare: kill -TERM $(cat state/orchestrator.pid).

Punti chiave del design
Loop sequenziale: niente thread, niente asyncio. Tick → safety check → maintenance → dispatch → sleep 30s.
Routing deterministico prima dell'LLM: keyword match → worker diretto, bypassa il planner e risparmia token.
Stato = file JSON: coda, memorie, heartbeat. Tutto ispezionabile, tutto ripristinabile.
Write transazionale: write_file passa per tmp/ poi rename atomico — nessuno stato inconsistente se l'agente crasha a metà.
Memory compaction: dopo 50 eventi, l'orchestratore stesso riassume in 300 token → long_term. Evita contesti che esplodono.
Safety valves: RAM >80% → pausa; disco <1GB → pausa; 10 fallimenti → stuck; SIGTERM → shutdown pulito con unload modelli.
Prossimi passi consigliati
Prova con un task minuscolo (tipo "scrivi hello world in C") per validare il loop end-to-end prima di lanciare roba seria.
Tweaka temperature del worker dopo le prime esecuzioni: 0.2 va bene per coding routinario, alza a 0.3 se vedi che si impunta sullo stesso bug.
Aggiungi un test runner come hook post-commit (rule #1 per evitare che gli agenti facciano regressioni mentre sei via).
Se vuoi, posso generare anche una TUI curses per monitorare la coda in tempo reale, o un set di 5-6 task iniziali che ricostruiscono lo stack minimo (editor → shell → http server → db kv) in ordine di dipendenza.
