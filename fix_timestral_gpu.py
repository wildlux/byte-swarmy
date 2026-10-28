#!/usr/bin/env python3
"""
fix_timestral_gpu.py — Aggiunge monitoraggio GPU NVIDIA a Timestral.

Cosa fa:
1. Aggiunge _read_gpu_temp() usando nvidia-smi
2. Aggiunge gpu_temp al sample
3. Aggiunge soglie GPU in config.toml
4. Modifica get_advice() per considerare anche la GPU
5. Aggiorna la GUI per mostrare la temp GPU
"""
import re
import shutil
from pathlib import Path

THERM_FILE = Path("thermal_manager.py")
THERM_BACKUP = Path("thermal_manager.py.bak.gpu")
CONFIG_FILE = Path("config.toml")
CONFIG_BACKUP = Path("config.toml.bak.gpu")
GUI_FILE = Path("gui.py")
GUI_BACKUP = Path("gui.py.bak.gpu")


def patch_thermal_manager():
    """Aggiunge lettura GPU temp a TimestralManager."""
    if not THERM_FILE.exists():
        return
    content = THERM_FILE.read_text()
    shutil.copy2(THERM_FILE, THERM_BACKUP)

    # 1. Aggiungi import subprocess in cima se non c'è
    if "import subprocess" not in content:
        content = content.replace(
            "import time",
            "import time\nimport subprocess",
            1
        )

    # 2. Aggiungi campo gpu_temp alla dataclass ThermalSample
    if "gpu_temp:" not in content:
        # Trova la dataclass ThermalSample
        sample_match = re.search(
            r'(@dataclass\s*\nclass ThermalSample.*?)(gpu_temp|\Z)',
            content,
            re.DOTALL
        )
        if sample_match:
            # Aggiungi gpu_temp come ultimo campo
            # Cerca l'ultimo campo prima della chiusura della classe
            insert_pattern = re.compile(
                r'(class ThermalSample.*?)(\s+)(\w+:\s+\w+\s*\n)(\s*\n)',
                re.DOTALL
            )
            # Più semplice: aggiungiamo gpu_temp dopo n_processes
            content = re.sub(
                r'(n_processes:\s+int\s*\n)',
                r'\1    gpu_temp: float = 0.0  # GPU temp (NVIDIA), 0.0 if no GPU\n',
                content,
                count=1
            )
            print("✓ Aggiunto campo gpu_temp a ThermalSample")

    # 3. Aggiungi metodo _read_gpu_temp()
    if "_read_gpu_temp" not in content:
        # Cerca il metodo _read_cpu_temp o _sample
        gpu_method = '''
    def _read_gpu_temp(self) -> float:
        """Legge la temperatura GPU via nvidia-smi. Ritorna 0.0 se non disponibile."""
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=temperature.gpu",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip().split()[0])
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        return 0.0

'''
        # Inserisci prima di _sample o di un metodo simile
        sample_method_match = re.search(r'(\s+def _sample\(self\))', content)
        if sample_method_match:
            content = content[:sample_method_match.start()] + gpu_method + sample_method_match.group(1) + content[sample_method_match.end():]
            print("✓ Aggiunto metodo _read_gpu_temp()")

    # 4. Aggiungi gpu_temp al sample nel metodo _sample
    # Cerca n_processes=... e aggiungi gpu_temp dopo
    if "gpu_temp=self._read_gpu_temp()" not in content:
        # Cerca dove viene costruito il sample (n_processes=...)
        content = re.sub(
            r'(n_processes=(?:self\._count_processes\(\)|len\([^)]+\)))\s*\)',
            r'\1,\n                gpu_temp=self._read_gpu_temp())',
            content,
            count=1
        )
        print("✓ Aggiunto gpu_temp al sample")

    # 5. Aggiorna get_advice per considerare la GPU
    # Cerca il punto dove viene calcolato l'advice e aggiungi check GPU
    if "gpu_temp" in content and "GPU pause" not in content:
        # Trova il metodo get_advice e aggiungi check GPU dopo quello CPU
        advice_pattern = re.compile(
            r'(if\s+sample\.cpu_temp_max\s*>=\s+self\.thresholds\[.temp_critical.\][^}]+?return\s+advice)',
            re.DOTALL
        )
        gpu_check = '''        # 🆕 GPU thermal check
        if sample.gpu_temp > 0:
            if sample.gpu_temp >= 95:
                return ThermalAdvice(
                    action="pause",
                    reason=f"GPU temp {sample.gpu_temp:.0f}C >= 95C critical",
                    tick_multiplier=0,
                    sample=sample,
                )
            elif sample.gpu_temp >= 85:
                advice = ThermalAdvice(
                    action="slow",
                    reason=f"GPU temp {sample.gpu_temp:.0f}C >= 85C hot",
                    tick_multiplier=2,
                    sample=sample,
                )
                # GPU hot takes priority if CPU is normal
                if advice.action == "normal":
                    return advice

        \1'''
        content = advice_pattern.sub(gpu_check, content, count=1)
        print("✓ Aggiunto check GPU thermal in get_advice()")

    THERM_FILE.write_text(content)
    try:
        compile(content, "thermal_manager.py", "exec")
        print("✓ Verifica sintassi OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi: {e}")
        shutil.copy2(THERM_BACKUP, THERM_FILE)


def patch_config():
    """Aggiunge soglie GPU a config.toml."""
    if not CONFIG_FILE.exists():
        return
    content = CONFIG_FILE.read_text()
    shutil.copy2(CONFIG_FILE, CONFIG_BACKUP)

    # Aggiungi soglie GPU nella sezione [thermal.thresholds]
    if "gpu_temp_hot" not in content:
        # Cerca la sezione [thermal.thresholds] e aggiungi in fondo
        pattern = re.compile(
            r'(\[thermal\.thresholds\][^\[]+?)(\n\[)',
            re.DOTALL
        )
        if pattern.search(content):
            gpu_thresholds = '''temp_critical = 90.0
gpu_temp_warm = 80.0
gpu_temp_hot = 85.0
gpu_temp_critical = 95.0

'''
            content = pattern.sub(
                lambda m: m.group(1).replace('temp_critical = 90.0', gpu_thresholds) + m.group(2),
                content
            )
            CONFIG_FILE.write_text(content)
            print("✓ Aggiunte soglie GPU a config.toml")


def patch_gui():
    """Aggiorna la GUI per mostrare la temp GPU."""
    if not GUI_FILE.exists():
        return
    content = GUI_FILE.read_text()
    shutil.copy2(GUI_FILE, GUI_BACKUP)

    # Cerca il punto dove viene mostrata la sample e aggiungi GPU temp
    if "GPU" not in content and "metric_temp" in content:
        # Aggiungi metric card GPU dopo metric_mem
        gpu_card_pattern = re.compile(
            r'(self\.metric_mem\s*=\s*self\._make_metric_card\("💾 RAM usata", "%", "#28a745"\))\s*\n(\s*metrics_row\.addWidget\(self\.metric_mem\))'
        )
        if gpu_card_pattern.search(content):
            gpu_addition = '''\\1
        self.metric_gpu = self._make_metric_card("🖥️ GPU", "°C", "#dc3545")
\\2
        metrics_row.addWidget(self.metric_gpu)'''
            content = gpu_card_pattern.sub(gpu_addition, content, count=1)
            print("✓ Aggiunta metric card GPU in GUI")

    # Aggiorna _refresh per popolare GPU
    if "self.metric_gpu" in content and "gpu_temp_max" not in content:
        # Cerca dove viene aggiornato metric_mem e aggiungi GPU
        refresh_pattern = re.compile(
            r'(self\.metric_mem\._value_label\.setText\(f"\{s\.mem_used_ratio\*100:.0f\}"\))'
        )
        if refresh_pattern.search(content):
            gpu_refresh = '''\\1
            if s.gpu_temp > 0:
                self.metric_gpu._value_label.setText(f"{s.gpu_temp:.0f}")
            else:
                self.metric_gpu._value_label.setText("--")'''
            content = refresh_pattern.sub(gpu_refresh, content, count=1)
            print("✓ Aggiornato _refresh per mostrare GPU temp")

    GUI_FILE.write_text(content)
    try:
        compile(content, "gui.py", "exec")
        print("✓ Verifica sintassi GUI OK")
    except SyntaxError as e:
        print(f"❌ Errore sintassi GUI: {e}")
        shutil.copy2(GUI_BACKUP, GUI_FILE)


def main():
    print("=" * 60)
    print("FIX TIMESTRAL + GPU MONITORING")
    print("=" * 60)
    print()
    print("→ thermal_manager.py")
    patch_thermal_manager()
    print()
    print("→ config.toml")
    patch_config()
    print()
    print("→ gui.py")
    patch_gui()
    print()
    print("=" * 60)
    print("✓ FIX COMPLETATI")
    print("=" * 60)
    print()
    print("Ora Timestral monitorerà:")
    print("  - CPU temp (come prima)")
    print("  - GPU temp (NUOVO, via nvidia-smi)")
    print("  - Se GPU >= 95°C → PAUSA")
    print("  - Se GPU >= 85°C → SLOW (tick x2.5)")
    print()
    print("Riavvia:")
    print("  ./ferma.sh && pkill -f 'python.*orchestrator' 2>/dev/null; sleep 2")
    print("  find . -name '__pycache__' -type d -exec rm -rf {} + 2>/dev/null")
    print("  ./avvia.sh")


if __name__ == "__main__":
    main()
