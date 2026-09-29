"""Porównanie dwóch wersji aktu prawnego (ETAP 77).

Jednostki (artykuły, paragrafy) łączymy po oznaczeniu („Art. 15”). Dla
każdej: dodana (jest tylko w nowej wersji), usunięta (tylko w starej),
zmieniona albo bez zmian. W zmienionej pokazujemy różnice słowo po
słowie (difflib z biblioteki standardowej). Białe znaki nie są zmianą —
PDF-y różnych wydań łamią wiersze inaczej.
"""

import difflib
import re

_TOKEN = re.compile(r"\S+")


def _slowa(tekst: str) -> list[str]:
    return _TOKEN.findall(tekst)


def roznice_slow(stary: str, nowy: str) -> list[dict]:
    """Odcinki [{"typ": "=" | "-" | "+", "tekst"}] — usunięte i dodane słowa."""
    a, b = _slowa(stary), _slowa(nowy)
    odcinki = []
    for op, a1, a2, b1, b2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if op == "equal":
            odcinki.append({"typ": "=", "tekst": " ".join(a[a1:a2])})
            continue
        if a2 > a1:
            odcinki.append({"typ": "-", "tekst": " ".join(a[a1:a2])})
        if b2 > b1:
            odcinki.append({"typ": "+", "tekst": " ".join(b[b1:b2])})
    return odcinki


def porownaj(stare: list[dict], nowe: list[dict]) -> dict:
    """Jednostki starej i nowej wersji → {"jednostki": [...], "liczby": {...}}.

    Kolejność: jak w nowej wersji, usunięte wstawione za jednostką, która
    w starej wersji je poprzedzała.
    """
    stare_po = {j["oznaczenie"]: j for j in stare if j["oznaczenie"] != "Tytuł"}
    nowe_po = {j["oznaczenie"]: j for j in nowe if j["oznaczenie"] != "Tytuł"}
    wynik = []
    for j in nowe:
        o = j["oznaczenie"]
        if o == "Tytuł":
            continue
        if o not in stare_po:
            wynik.append({"oznaczenie": o, "status": "dodana", "nowa": j, "stara": None})
            continue
        s = stare_po[o]
        if _slowa(s["tekst"]) == _slowa(j["tekst"]):
            wynik.append({"oznaczenie": o, "status": "bez zmian", "nowa": j, "stara": s})
        else:
            wynik.append({"oznaczenie": o, "status": "zmieniona", "nowa": j, "stara": s, "roznice": roznice_slow(s["tekst"], j["tekst"])})

    # usunięte: za ostatnią wspólną jednostką, która je poprzedzała w starej wersji
    poprzednia = None
    wstawki: dict[str | None, list[dict]] = {}
    for j in stare:
        o = j["oznaczenie"]
        if o == "Tytuł":
            continue
        if o in nowe_po:
            poprzednia = o
        else:
            wstawki.setdefault(poprzednia, []).append({"oznaczenie": o, "status": "usunięta", "nowa": None, "stara": j})
    ulozone = list(wstawki.get(None, []))
    for pozycja in wynik:
        ulozone.append(pozycja)
        ulozone.extend(wstawki.get(pozycja["oznaczenie"], []))

    liczby = {s: sum(1 for p in ulozone if p["status"] == s) for s in ("zmieniona", "dodana", "usunięta", "bez zmian")}
    return {"jednostki": ulozone, "liczby": liczby}
