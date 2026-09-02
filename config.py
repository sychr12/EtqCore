"""Caminhos e endereço padrão usados por todo o programa."""

from __future__ import annotations

from pathlib import Path

# Arquivos permanentes ficam dentro da própria pasta do projeto.
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "dados"
DB_PATH = DATA_DIR / "etiquetas.db"
BACKUP_DIR = DATA_DIR / "backups"
# As planilhas ficam fora do código para poderem ser copiadas, sincronizadas
# ou apontadas para uma pasta compartilhada de outra máquina.
REPORTS_DIR = Path.home() / "Documents" / "Relatorios Etiquetas"

HOST = "localhost"
PORT = 8080
