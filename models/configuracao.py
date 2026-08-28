from __future__ import annotations

import sqlite3
from contextlib import closing

from .database import db


def obter_todas(con: sqlite3.Connection | None = None) -> dict[str, str]:
    """Retorna todas as chaves de configuração como dict. Aceita uma conexão
    já aberta (para reaproveitar dentro de uma transação) ou abre e fecha
    a sua própria."""
    own = con is None
    con = con or db()
    try:
        return {r["chave"]: r["valor"] for r in con.execute("SELECT chave, valor FROM config")}
    finally:
        if own:
            con.close()


def salvar(valores: dict[str, str]) -> None:
    with closing(db()) as con:
        con.executemany("INSERT OR REPLACE INTO config(chave, valor) VALUES (?, ?)", valores.items())
        con.commit()


def atualizar_proximo_contador(con: sqlite3.Connection, novo_valor: int) -> None:
    """Usado dentro de uma transação já aberta (ver models/etiqueta.py)."""
    con.execute("UPDATE config SET valor=? WHERE chave='proximo_contador'", (str(novo_valor),))
