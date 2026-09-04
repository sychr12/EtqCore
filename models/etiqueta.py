"""Operações do histórico: inserir etiquetas, marcar resultado e fazer backup."""

from __future__ import annotations

import json
import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .database import db
from config import BACKUP_DIR


def obter_ultima() -> sqlite3.Row | None:
    """Busca os dados da etiqueta mais recente para restaurar o formulário."""
    with closing(db()) as con:
        return con.execute(
            "SELECT identificador, dados_json FROM etiquetas ORDER BY id DESC LIMIT 1"
        ).fetchone()


def inserir_lote(
    con: sqlite3.Connection,
    itens: list[dict],
    destino: str,
    dados_originais: dict,
) -> list[dict]:
    """Insere um lote de etiquetas dentro de uma transação já aberta (BEGIN
    IMMEDIATE feito pelo controller/service que orquestra a geração).
    `itens` é uma lista de {contador, identificador, qr, zpl}.
    Retorna a lista com o `id` de cada linha inserida."""
    criada_em = datetime.now().isoformat(timespec="seconds")
    serializado = json.dumps(dados_originais, ensure_ascii=False)
    resultado = []
    for item in itens:
        cur = con.execute(
            "INSERT INTO etiquetas(contador, identificador, criada_em, dados_json, qr_texto, zpl, destino, sucesso) "
            "VALUES (?,?,?,?,?,?,?,0)",
            (item["contador"], item["identificador"], criada_em, serializado, item["qr"], item["zpl"], destino),
        )
        resultado.append({**item, "id": cur.lastrowid})
    return resultado


def marcar_resultado(itens: list[dict], sucesso: bool, erro: str | None) -> None:
    """Registra se o arquivo foi gerado/impresso ou se ocorreu algum erro."""
    with closing(db()) as con:
        con.executemany(
            "UPDATE etiquetas SET sucesso=?, erro=? WHERE id=?",
            ((1 if sucesso else 0, erro, item["id"]) for item in itens),
        )
        con.commit()


def listar_historico(limite: int = 200) -> list[dict]:
    """Devolve as últimas etiquetas em um formato pronto para a interface."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas ORDER BY id DESC LIMIT ?",
            (limite,),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_por_periodo(ano: int, mes: int) -> list[dict]:
    """Busca todas as etiquetas de um mês, sem limitar a quantidade."""
    inicio = f"{ano:04d}-{mes:02d}-01"
    fim = f"{ano + 1:04d}-01-01" if mes == 12 else f"{ano:04d}-{mes + 1:02d}-01"
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas WHERE criada_em >= ? AND criada_em < ? ORDER BY criada_em, id",
            (inicio, fim),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_por_ano(ano: int) -> list[dict]:
    """Busca todas as etiquetas registradas durante um ano."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT id, contador, identificador, criada_em, dados_json, destino, sucesso, erro "
            "FROM etiquetas WHERE criada_em >= ? AND criada_em < ? ORDER BY criada_em, id",
            (f"{ano:04d}-01-01", f"{ano + 1:04d}-01-01"),
        ).fetchall()
    resultado = []
    for row in rows:
        item = dict(row)
        item["dados"] = json.loads(item.pop("dados_json"))
        resultado.append(item)
    return resultado


def listar_periodos() -> list[dict]:
    """Informa os anos e meses que possuem etiquetas no histórico."""
    with closing(db()) as con:
        rows = con.execute(
            "SELECT substr(criada_em,1,4) AS ano, substr(criada_em,6,2) AS mes, COUNT(*) AS total "
            "FROM etiquetas GROUP BY ano, mes ORDER BY ano DESC, mes DESC"
        ).fetchall()
    return [dict(row) for row in rows]


def obter_zpl(label_id: int) -> sqlite3.Row | None:
    """Recupera o arquivo de impressão de uma etiqueta específica."""
    with closing(db()) as con:
        return con.execute(
            "SELECT identificador, zpl FROM etiquetas WHERE id=?", (label_id,)
        ).fetchone()


def validar_desfazer_ultima(label_id: int) -> dict:
    """Confere se o registro é o último e se o contador pode voltar sem conflito."""
    with closing(db()) as con:
        row = con.execute(
            "SELECT id, contador, identificador FROM etiquetas ORDER BY contador DESC LIMIT 1"
        ).fetchone()
        if not row or row["id"] != label_id:
            raise ValueError("Somente a etiqueta mais recente pode ser desfeita.")
        next_row = con.execute(
            "SELECT valor FROM config WHERE chave='proximo_contador'"
        ).fetchone()
        if not next_row or int(next_row["valor"]) != int(row["contador"]) + 1:
            raise ValueError("O contador já avançou e não pode voltar com segurança.")
        return dict(row)


def desfazer_ultima(label_id: int) -> dict:
    """Apaga a última etiqueta e devolve seu número ao contador atomicamente."""
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        row = con.execute(
            "SELECT id, contador, identificador FROM etiquetas ORDER BY contador DESC LIMIT 1"
        ).fetchone()
        if not row or row["id"] != label_id:
            con.rollback()
            raise ValueError("Outra etiqueta foi criada. Atualize o histórico antes de desfazer.")
        next_row = con.execute(
            "SELECT valor FROM config WHERE chave='proximo_contador'"
        ).fetchone()
        if not next_row or int(next_row["valor"]) != int(row["contador"]) + 1:
            con.rollback()
            raise ValueError("O contador não pode voltar com segurança.")
        con.execute("DELETE FROM etiquetas WHERE id=?", (label_id,))
        con.execute(
            "UPDATE config SET valor=? WHERE chave='proximo_contador'",
            (str(row["contador"]),),
        )
        con.commit()
        return dict(row)


def apagar_todo_historico() -> int:
    """Apaga todos os registros e reinicia o contador dentro de uma transação."""
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        total = int(con.execute("SELECT COUNT(*) FROM etiquetas").fetchone()[0])
        con.execute("DELETE FROM etiquetas")
        con.execute(
            "UPDATE config SET valor='1' WHERE chave='proximo_contador'"
        )
        con.commit()
        return total


def validar_exclusao_intervalo(inicio: int, fim: int, proximo: int) -> int:
    """Valida o intervalo e impede que o novo contador alcance registros mantidos."""
    if inicio < 1 or fim < inicio or proximo < 1:
        raise ValueError("Informe um intervalo e um próximo número válidos.")
    with closing(db()) as con:
        total = int(con.execute(
            "SELECT COUNT(*) FROM etiquetas WHERE contador BETWEEN ? AND ?",
            (inicio, fim),
        ).fetchone()[0])
        if total == 0:
            raise ValueError("Nenhuma etiqueta foi encontrada nesse intervalo.")
        maximo_mantido = con.execute(
            "SELECT MAX(contador) FROM etiquetas WHERE contador NOT BETWEEN ? AND ?",
            (inicio, fim),
        ).fetchone()[0]
        if maximo_mantido is not None and proximo <= int(maximo_mantido):
            raise ValueError(
                f"O próximo número deve ser maior que {maximo_mantido}, pois existem etiquetas mantidas até esse número."
            )
        return total


def apagar_intervalo(inicio: int, fim: int, proximo: int) -> int:
    """Apaga um intervalo inclusivo e define o próximo contador atomicamente."""
    with closing(db()) as con:
        con.execute("BEGIN IMMEDIATE")
        total = int(con.execute(
            "SELECT COUNT(*) FROM etiquetas WHERE contador BETWEEN ? AND ?",
            (inicio, fim),
        ).fetchone()[0])
        maximo_mantido = con.execute(
            "SELECT MAX(contador) FROM etiquetas WHERE contador NOT BETWEEN ? AND ?",
            (inicio, fim),
        ).fetchone()[0]
        if total == 0:
            con.rollback()
            raise ValueError("Nenhuma etiqueta foi encontrada nesse intervalo.")
        if maximo_mantido is not None and proximo <= int(maximo_mantido):
            con.rollback()
            raise ValueError("O próximo número entraria em conflito com etiquetas mantidas.")
        con.execute("DELETE FROM etiquetas WHERE contador BETWEEN ? AND ?", (inicio, fim))
        con.execute("UPDATE config SET valor=? WHERE chave='proximo_contador'", (str(proximo),))
        con.commit()
        return total


def gerar_backup() -> Path:
    """Copia o banco em uso para a pasta de backups sem corrompê-lo."""
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    target: Path = BACKUP_DIR / f"etiquetas-{stamp}.db"
    with closing(db()) as source, closing(sqlite3.connect(target)) as dest:
        source.backup(dest)
    return target
