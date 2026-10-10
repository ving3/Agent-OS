# -*- coding: utf-8 -*-
"""
Agentic OS — Point d'entree du serveur HTTP
"""
import os
import sys

# Ajouter le repertoire app au PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from http.server import HTTPServer
from config import HOST, PORT, DATA_DIR
from database import init_db, DB_PATH
from dashboard.router import AgenticOSHandler


def main():
    os.makedirs(DATA_DIR, exist_ok=True)
    init_db()

    server = HTTPServer((HOST, PORT), AgenticOSHandler)
    print(f"[Agentic OS] Dashboard + Auth en ecoute sur http://{HOST}:{PORT}")
    print(f"[Agentic OS] Base de donnees: {DB_PATH}")
    print(f"[Agentic OS] API OpenAI-compatible: http://{HOST}:{PORT}/v1")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[Agentic OS] Arret.")
        server.server_close()


if __name__ == "__main__":
    main()
