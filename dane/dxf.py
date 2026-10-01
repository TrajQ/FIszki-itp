"""Zapis rysunku do pliku DXF (AutoCAD R12, tekstowy) — ETAP 122.

DXF R12 to najprostsza, najstarsza wersja formatu: otworzy ją każdy
program CAD (AutoCAD, BricsCAD, ZWCAD, LibreCAD, QCAD) i QGIS. Piszemy go
sami (pary „kod grupy / wartość” w kolejnych wierszach), bez nowej
zależności — potrzebne są tylko warstwy, zamknięte polilinie i teksty.

Współrzędne podaje wywołujący — w układzie geodezyjnym (np. PL-2000) w
metrach, w konwencji CAD: X = wschód, Y = północ (odwrotnie niż x, y w
geodezji). Nazwy warstw i teksty tylko ASCII: R12 nie ma jednolitego
kodowania polskich znaków.
"""

import re

# kolory AutoCAD (ACI) dla nazw używanych w modułach
KOLORY_ACI = {"czerwony": 1, "zolty": 2, "zielony": 3, "cyjan": 4, "niebieski": 5, "magenta": 6,
              "bialy": 7, "szary": 8, "jasnoszary": 9, "pomaranczowy": 30, "brazowy": 34}


def nazwa_ascii(tekst: str) -> str:
    """Nazwa warstwy / tekst bez polskich znaków i znaków specjalnych (R12)."""
    zamiany = str.maketrans("ąćęłńóśźżĄĆĘŁŃÓŚŹŻ", "acelnoszzACELNOSZZ")
    return re.sub(r"[^A-Za-z0-9_\-. ]", "_", tekst.translate(zamiany))[:200]


def _para(kod: int, wartosc) -> str:
    if isinstance(wartosc, float):
        wartosc = f"{wartosc:.3f}"  # milimetry wystarczą
    return f"{kod:>3}\n{wartosc}\n"


def dxf(warstwy: dict[str, int], obiekty: list[dict]) -> str:
    """warstwy: {nazwa: kolor ACI}; obiekty: {"warstwa", "wielobok": [(x, y), …]}
    (zamknięta polilinia) albo {"warstwa", "tekst", "punkt": (x, y), "wysokosc"}."""
    czesci = [_para(0, "SECTION"), _para(2, "HEADER"), _para(9, "$ACADVER"), _para(1, "AC1009"), _para(0, "ENDSEC"),
              _para(0, "SECTION"), _para(2, "TABLES"), _para(0, "TABLE"), _para(2, "LAYER"), _para(70, len(warstwy))]
    for nazwa, kolor in warstwy.items():
        czesci += [_para(0, "LAYER"), _para(2, nazwa_ascii(nazwa)), _para(70, 0), _para(62, kolor), _para(6, "CONTINUOUS")]
    czesci += [_para(0, "ENDTAB"), _para(0, "ENDSEC"), _para(0, "SECTION"), _para(2, "ENTITIES")]
    for o in obiekty:
        warstwa = nazwa_ascii(o["warstwa"])
        if "wielobok" in o:
            punkty = list(o["wielobok"])
            if len(punkty) > 1 and punkty[0] == punkty[-1]:
                punkty = punkty[:-1]  # zamknięcie zapisuje flaga 70 = 1
            czesci += [_para(0, "POLYLINE"), _para(8, warstwa), _para(66, 1), _para(10, 0.0), _para(20, 0.0), _para(30, 0.0), _para(70, 1)]
            for x, y in punkty:
                czesci += [_para(0, "VERTEX"), _para(8, warstwa), _para(10, float(x)), _para(20, float(y)), _para(30, 0.0)]
            czesci += [_para(0, "SEQEND"), _para(8, warstwa)]
        else:
            x, y = o["punkt"]
            czesci += [_para(0, "TEXT"), _para(8, warstwa), _para(10, float(x)), _para(20, float(y)), _para(30, 0.0),
                       _para(40, float(o.get("wysokosc", 2.5))), _para(1, nazwa_ascii(o["tekst"])), _para(72, 1),
                       _para(11, float(x)), _para(21, float(y)), _para(31, 0.0)]
    czesci += [_para(0, "ENDSEC"), _para(0, "EOF")]
    return "".join(czesci)
