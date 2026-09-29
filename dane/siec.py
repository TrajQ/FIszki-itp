"""Czytelne komunikaty o błędach sieci dla użytkownika.

Surowy tekst wyjątku z `requests` („HTTPSConnectionPool(host=…): Max
retries exceeded… ProxyError…”) nic nie mówi komuś, kto chce tylko
sprawdzić działkę. Tu zamieniamy go na jedno zdanie po polsku.
"""

import requests


def opis_bledu_sieci(blad: requests.RequestException) -> str:
    if isinstance(blad, requests.Timeout):
        return "usługa nie odpowiedziała na czas — spróbuj ponownie za chwilę"
    if isinstance(blad, requests.ConnectionError):
        return "brak połączenia z usługą — sprawdź internet albo spróbuj później"
    if isinstance(blad, requests.HTTPError) and blad.response is not None:
        return f"usługa zwróciła błąd {blad.response.status_code} — spróbuj później"
    return str(blad)[:200]
