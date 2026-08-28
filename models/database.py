from __future__ import annotations

import sqlite3
from contextlib import closing

from config import DATA_DIR, DB_PATH, BACKUP_DIR


def db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_PATH, timeout=30)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA synchronous=FULL")
    con.execute("PRAGMA foreign_keys=ON")
    return con


def init_db() -> None:
    DATA_DIR.mkdir(exist_ok=True)
    BACKUP_DIR.mkdir(exist_ok=True)
    with closing(db()) as con:
        con.executescript(
            """
            CREATE TABLE IF NOT EXISTS config (
                chave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS etiquetas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                contador INTEGER NOT NULL UNIQUE,
                identificador TEXT NOT NULL UNIQUE,
                criada_em TEXT NOT NULL,
                dados_json TEXT NOT NULL,
                qr_texto TEXT NOT NULL,
                zpl TEXT NOT NULL,
                destino TEXT NOT NULL,
                sucesso INTEGER NOT NULL,
                erro TEXT
            );
            CREATE INDEX IF NOT EXISTS idx_etiquetas_criada_em
                ON etiquetas(criada_em DESC);
            """
        )
        defaults = {
            "proximo_contador": "1",
            "filial": "04",
            "prefixo_contador": "TB",
            "largura_mm": "100",
            "comprimento_mm": "60",
            "dpi": "203",
            "impressora": "",
        }
        con.executemany(
            "INSERT OR IGNORE INTO config(chave, valor) VALUES (?, ?)",
            defaults.items(),
        )
        con.commit()
