from __future__ import annotations

from flask import Blueprint, render_template

paginas_bp = Blueprint("paginas", __name__)


@paginas_bp.get("/")
def index():
    return render_template("index.html")
