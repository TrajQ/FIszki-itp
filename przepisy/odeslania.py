"""Klikalne odesłania w tekście aktu (ETAP 121).

„art. 15 ust. 2 pkt 6” w treści staje się odnośnikiem do artykułu 15
tego samego aktu (z podglądem jego początku w dymku). Odesłania do
innych aktów („art. 4 ustawy z dnia …”, „art. 10 Kodeksu …”) zostają
zwykłym tekstem — link prowadziłby do złego artykułu. Odesłania piszemy
małą literą (zasady techniki prawodawczej), więc nagłówki jednostek
(„Art. 15.”) nie są zamieniane.
"""

import re

from markupsafe import Markup, escape

_ODESLANIE = re.compile(r"(?<![\w.])(art\.|§)\s*(\d+[a-z]*)((?:\s+(?:ust\.|pkt|lit\.)\s*\d*[a-z]*\)?)*)")
# Po odesłaniu do innego aktu stoi jego nazwa: „ustawy z dnia …”, „ustawy o …”,
# „rozporządzenia Ministra …”, „Kodeksu …” — wtedy nie linkujemy. Samo „ustawy”
# (bez dalszej nazwy) to zwykle ta ustawa, np. „art. 15 ust. 2 ustawy.”
_INNY_AKT = re.compile(
    r"^[\s,]*(?:i\s+\d+[a-z]*\s+)?(?:"
    r"(?:ustaw|rozporządze|uchwał|dekret|obwieszczeni)\w*\s+(?:z\s+dnia|o\s|nr\s|\(|[–—-]\s|Rady|Ministra|Parlamentu|Prezesa|Komisji|Prezydenta)"
    r"|kodeks|k\.\s*p\.|konstytucj|dyrektyw|traktat|prawa\s+\w|ordynacji)",
    re.IGNORECASE)
DLUGOSC_PODGLADU = 160


def mapa_jednostek(jednostki: list[dict]) -> dict[str, dict]:
    """„art. 15” / „§ 3” (bez wielkości liter) → jednostka."""
    mapa = {}
    for j in jednostki:
        m = re.match(r"(Art\.|§)\s*(\d+[a-z]*)$", j["oznaczenie"])
        if m:
            mapa[f"{m.group(1).lower()} {m.group(2)}"] = j
    return mapa


def _podglad(tekst: str) -> str:
    tekst = " ".join(tekst.split())
    return tekst if len(tekst) <= DLUGOSC_PODGLADU else tekst[:DLUGOSC_PODGLADU].rsplit(" ", 1)[0] + " …"


def z_odeslaniami(tekst: str, mapa: dict[str, dict], biezaca_id: int | None = None) -> Markup:
    """Tekst jednostki jako bezpieczny HTML z odnośnikami do artykułów tego aktu."""
    czesci, poprzedni = [], 0
    for m in _ODESLANIE.finditer(tekst):
        cel = mapa.get(f"{m.group(1)} {m.group(2)}")
        if cel is None or cel.get("id") == biezaca_id or _INNY_AKT.match(tekst[m.end():m.end() + 60]):
            continue
        czesci.append(escape(tekst[poprzedni:m.start()]))
        czesci.append(Markup('<a class="odeslanie" href="#j{}" title="{}">{}</a>').format(cel["id"], _podglad(cel["tekst"]), m.group(0)))
        poprzedni = m.end()
    czesci.append(escape(tekst[poprzedni:]))
    return Markup("").join(czesci)
