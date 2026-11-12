---
id: pyqt6-threading
title: PyQt6 QThread worker (single file)
keywords: qthread, thread, worker, job, progresso, progress, cancellazione, cancellation, pool, qthreadpool, threading
---
# Recipe: PyQt6 QThread worker (single file)

STEPS (follow in order):
1. Create project/main.py using the TEMPLATE below.
2. Replace ONLY the {{...}} placeholders. Do NOT add extra features.
3. done=true with a one-line result.

TEMPLATE (keep every line that has no {{...}} exactly as-is):
```python
import sys
import time
from PyQt6.QtCore import QThread, pyqtSignal
from PyQt6.QtWidgets import QApplication


class Worker(QThread):
    finished = pyqtSignal()

    def run(self):
        time.sleep(0.01)
        self.finished.emit()

    def cancel(self):
        pass


def main():
    app = QApplication(sys.argv)
    worker = Worker()
    worker.start()
    worker.wait(5000)
    print("DONE=ok")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

RULES:
- ONE file only: project/main.py. Standard library + PyQt6 only.
- ALWAYS import QThread and pyqtSignal from PyQt6.QtCore.
- NEVER use PyQt5 or PySide2 — only PyQt6.
- The worker MUST inherit from QThread and override run().
- Use worker.wait() to block until the thread finishes.
- In test mode (no display), call sys.exit(0) after the thread finishes.
- Replace EVERY {{...}} placeholder with real code.
- Print DONE=ok when the thread finishes.