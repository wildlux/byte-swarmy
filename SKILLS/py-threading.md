---
id: py-threading
title: Python threading with join and Lock (single file)
keywords: thread, threading, concorrente, parallelo, parallel, lock, mutex, join, coda, queue, multiprocessing
---
# Recipe: threading with join and Lock (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. 3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import threading


def lavoro(n):
    """{{ WHAT ONE WORKER COMPUTES }}"""
    return {{ COMPUTATION }}


def main():
    results = []
    lock = threading.Lock()

    def worker(n):
        r = lavoro(n)
        with lock:
            results.append(r)

    threads = []
    for n in {{ INPUTS }}:
        t = threading.Thread(target=worker, args=(n,))
        t.start()
        threads.append(t)
    for t in threads:
        t.join()

    print(f"{{ MARKER }}")


if __name__ == "__main__":
    main()
```

RULES:
- - Replace EVERY {{...}} placeholder with real code. Example:
  `{{ MARKER }}` becomes `TOT={sum(results)}` so the line reads
  print(f"TOT={sum(results)}") — use the EXACT name and value the
  task requests.
- ALWAYS join() EVERY thread before printing results.
- Shared state (results) is guarded by a Lock — never touch it bare.
- NEVER rely on thread execution order; collect then combine.
- Producer/consumer patterns use queue.Queue, not bare lists.
- print() the exact markers the task requests.
