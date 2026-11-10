"""
GUI/backup_code_logs.py — Pannello backup con log Git per categoria.

Estratto da GUI/control_center.py (classe BackupCodeLogs).
"""

from __future__ import annotations

from PyQt6.QtWidgets import (
    QFrame, QLabel, QStackedWidget, QTabBar, QTextEdit, QVBoxLayout,
)


class BackupCodeLogs(QFrame):
    """Pannello backup con log Git divisi per categoria (GitHub, GitLab, Git)."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("backup_logs")
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        header = QLabel("<b>💾 Backup Code — Git Logs</b>")
        header.setStyleSheet("padding:8px 12px; font-size:12px;")
        lay.addWidget(header)

        self.tab_bar = QTabBar()
        self.tab_bar.setExpanding(False)
        self.tab_bar.setMovable(False)
        self.tab_bar.addTab("🐙 GitHub")
        self.tab_bar.addTab("🦊 GitLab")
        self.tab_bar.addTab("📂 Git")
        self.tab_bar.setStyleSheet(
            "QTabBar::tab { padding:6px 12px; margin:2px; font-size:11px; }"
        )
        self.tab_bar.currentChanged.connect(self._on_tab_changed)
        lay.addWidget(self.tab_bar)

        self.log_stack = QStackedWidget()
        self.logs = {}
        categories = ["github", "gitlab", "git"]
        colors = {"github": "#89b4fa", "gitlab": "#f38ba8", "git": "#fab387"}

        for cat in categories:
            log_widget = QTextEdit()
            log_widget.setReadOnly(True)
            # Stile dal tema app-level (QTextEdit nei .qss).
            sample = self._get_sample_log(cat, colors[cat])
            log_widget.setPlainText(sample)
            self.logs[cat] = log_widget
            self.log_stack.addWidget(log_widget)

        lay.addWidget(self.log_stack, stretch=1)

    def _get_sample_log(self, category, color):
        samples = {
            "github": f"[{color}] 2026-11-01 11:40:15 [INFO]  Push to main branch\n"
                     f"[{color}] 2026-11-01 11:40:16 [INFO]  CI pipeline triggered\n"
                     f"[{color}] 2026-11-01 11:40:18 [DEBUG] Running tests (3/15)\n"
                     f"[{color}] 2026-11-01 11:40:22 [SUCCESS] All tests passed\n",
            "gitlab": f"[{color}] 2026-11-01 11:38:10 [INFO]  MR !42 merged\n"
                     f"[{color}] 2026-11-01 11:38:12 [INFO]  Pipeline #1234 started\n"
                     f"[{color}] 2026-11-01 11:38:45 [WARNING] Coverage dropped to 82%\n"
                     f"[{color}] 2026-11-01 11:39:01 [SUCCESS] Deployment to staging\n",
            "git": f"[{color}] 2026-11-01 11:35:00 [INFO]  Commit: a1b2c3d - Fix bug in parser\n"
                  f"[{color}] 2026-11-01 11:35:01 [INFO]  Branch: feature/usb-reverse\n"
                  f"[{color}] 2026-11-01 11:35:02 [DEBUG] 3 files changed, +45 -12\n"
                  f"[{color}] 2026-11-01 11:42:00 [INFO]  Pull from origin/main successful\n",
        }
        return samples.get(category, "")

    def _on_tab_changed(self, index):
        self.log_stack.setCurrentIndex(index)
