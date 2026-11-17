"""Conftest root — robustezza della collection pytest.

- Ignora tests/archiviati/ (esperimenti storici; un file lì dentro è
  troncato su disco e romperebbe l'exit code dell'intera run).
- Garantisce che la root del repo sia in sys.path anche quando pytest
  viene invocato da fuori (pytest /abs/path/byte-swarmy/tests).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

collect_ignore = ["tests/archiviati"]
