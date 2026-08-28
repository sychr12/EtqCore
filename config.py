from __future__ import annotations

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "dados"
DB_PATH = DATA_DIR / "etiquetas.db"
BACKUP_DIR = DATA_DIR / "backups"

HOST = "localhost"
PORT = 8080
