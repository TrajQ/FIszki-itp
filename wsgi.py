"""Punkt startu na serwerze (ETAP 251): gunicorn ładuje wsgi:app.

Lokalnie Warsztat startuje jak dotąd przez uruchom.sh / app.py. Na
serwerze kopia automatyczna jest codzienna z crona
(narzedzia/kopia_serwera.py), więc tu jej nie uruchamiamy.
"""

from app import create_app

app = create_app()
