"""Inicia o sistema web local e conecta todas as partes da aplicação."""

from __future__ import annotations

import threading
import webbrowser

from flask import Flask

from config import HOST, PORT
from controllers.paginas_controller import paginas_bp
from controllers.etiquetas_controller import api_bp
from models.database import init_db


def create_app() -> Flask:
    """Prepara o banco, cria o Flask e registra as páginas e a API."""
    init_db()
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 1 * 1024 * 1024
    app.register_blueprint(paginas_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()


if __name__ == "__main__":
    # Abre o navegador automaticamente e mantém o servidor local em execução.
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
