"""Entrega a tela principal e a logo para o navegador."""

from __future__ import annotations

from pathlib import Path

from flask import Blueprint, make_response, render_template, send_file

paginas_bp = Blueprint("paginas", __name__)
LOGO_PATH = Path(__file__).resolve().parent.parent / "logo" / "logo.png"


@paginas_bp.get("/")
def index():
    """Mostra a interface e evita que o navegador reutilize uma versão antiga."""
    response = make_response(render_template("index.html"))
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


@paginas_bp.get("/logo/logo.png")
def logo():
    """Entrega a mesma logo usada na interface e na etiqueta."""
    return send_file(LOGO_PATH, mimetype="image/png", max_age=0)
