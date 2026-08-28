from __future__ import annotations

import threading
import webbrowser

from flask import Flask

from config import HOST, PORT
from controllers.paginas_controller import paginas_bp
from controllers.etiquetas_controller import api_bp
from models.database import init_db


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(paginas_bp)
    app.register_blueprint(api_bp)
    return app


app = create_app()


if __name__ == "__main__":
    init_db()
    threading.Timer(1.2, lambda: webbrowser.open(f"http://{HOST}:{PORT}")).start()
    app.run(host=HOST, port=PORT, debug=False, threaded=True)
