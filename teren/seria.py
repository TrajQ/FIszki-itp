"""Zmiana stanu w czasie — kilka inwentaryzacji tego samego terenu (ETAP 240).

Rozszerzenie porównania dwóch projektów (porownanie.py, ETAP 157) na
serię 2–6 inwentaryzacji, np. stan zieleni co roku:

1. Kolejność: od najwcześniejszego pomiaru (czas pierwszego punktu),
   a bez punktów — wg terminu wyjścia w teren albo numeru projektu.
2. Zestawienie w czasie dla pól, które mają wszystkie projekty (ta sama
   nazwa i typ): udziały odpowiedzi w każdej inwentaryzacji, dla liczb
   średnia i mediana; dla pól na skali — pasek z udziałami (SVG).
3. Te same miejsca: łańcuchy punktów łączonych parami między KOLEJNYMI
   inwentaryzacjami (wzajemnie najbliższe w promieniu PROG_M, jak w
   porównaniu dwóch). Dla pól na skali: przebieg wartości w miejscu i
   ocena pierwszy → ostatni pomiar (lepiej / gorzej / bez zmian).
"""

from .porownanie import PROG_M, pary, wspolne_pola
from .raport import kolor_skali, zestawienie

MIN_PROJEKTOW, MAKS_PROJEKTOW = 2, 6


class BladSerii(ValueError):
    """Zły wybór projektów do serii."""


def uloz(projekty: list[dict], punkty: dict[int, list[dict]]) -> list[dict]:
    """Projekty od najwcześniejszego pomiaru; z datą „od” każdego."""
    if not MIN_PROJEKTOW <= len(projekty) <= MAKS_PROJEKTOW:
        raise BladSerii(f"Wybierz od {MIN_PROJEKTOW} do {MAKS_PROJEKTOW} inwentaryzacji.")
    if len({p["id"] for p in projekty}) != len(projekty):
        raise BladSerii("Każdą inwentaryzację wybierz tylko raz.")

    def klucz(p):
        czasy = [pt["czas"] for pt in punkty[p["id"]] if pt.get("czas")]
        return (min(czasy) if czasy else (p.get("termin") or "9999"), p["id"])

    wynik = []
    for p in sorted(projekty, key=klucz):
        czasy = [pt["czas"] for pt in punkty[p["id"]] if pt.get("czas")]
        wynik.append({**p, "data": (min(czasy)[:10] if czasy else p.get("termin")), "liczba_punktow": len(punkty[p["id"]])})
    return wynik


def pola_wspolne(projekty: list[dict]) -> list[dict]:
    """Pola, które mają wszystkie projekty serii (nazwa i typ), w kolejności z pierwszego."""
    pola = projekty[0]["pola"]
    for p in projekty[1:]:
        pola = wspolne_pola(pola, p["pola"])
    return pola


def zestawienie_w_czasie(pola: list[dict], punkty_kolejno: list[list[dict]]) -> list[dict]:
    """Dla każdego wspólnego pola: wiersze wartości z udziałem w każdej inwentaryzacji."""
    zestawienia = [zestawienie(pola, punkty) for punkty in punkty_kolejno]
    wynik = []
    for i, pole in enumerate(pola):
        pozycje = [z[i] for z in zestawienia]
        wpis = {"nazwa": pole["nazwa"], "typ": pole["typ"], "skala": bool(pole.get("skala")), "pozycje": pozycje}
        if "rozklad" in pozycje[0]:
            wpis["wiersze"] = [
                {"wartosc": r["wartosc"], "kolor": r["kolor"], "w_czasie": [poz["rozklad"][j] for poz in pozycje],
                 "zmiana_pp": pozycje[-1]["rozklad"][j]["procent"] - pozycje[0]["rozklad"][j]["procent"]}
                for j, r in enumerate(pozycje[0]["rozklad"])
            ]
        elif pole["typ"] == "liczba":
            wpis["statystyki"] = [poz.get("statystyki") for poz in pozycje]
        wynik.append(wpis)
    return wynik


def lancuchy(punkty_kolejno: list[list[dict]], prog_m: float = PROG_M) -> list[list[dict | None]]:
    """Łańcuchy „to samo miejsce”: element k to punkt z k-tej inwentaryzacji albo None.

    Punkt bez pary w poprzedniej inwentaryzacji zaczyna nowy łańcuch;
    łańcuch bez kontynuacji kończy się (None do końca). Zostają tylko
    łańcuchy z co najmniej dwoma punktami.
    """
    n = len(punkty_kolejno)
    otwarte = {id(p): [p] + [None] * (n - 1) for p in punkty_kolejno[0]}  # klucz: ostatni punkt łańcucha
    wszystkie = list(otwarte.values())
    for k in range(1, n):
        nowe = {}
        polaczone = {id(pb): pa for pa, pb, _ in pary(punkty_kolejno[k - 1], punkty_kolejno[k], prog_m)}
        for pb in punkty_kolejno[k]:
            pa = polaczone.get(id(pb))
            if pa is not None and id(pa) in otwarte:
                lancuch = otwarte[id(pa)]
            else:
                lancuch = [None] * n
                wszystkie.append(lancuch)
            lancuch[k] = pb
            nowe[id(pb)] = lancuch
        otwarte = nowe
    return [ln for ln in wszystkie if sum(p is not None for p in ln) >= 2]


def zmiany_w_czasie(pola: list[dict], lancuchy_: list[list[dict | None]]) -> list[dict]:
    """Dla pól na skali: przebieg wartości w każdym miejscu i ocena pierwszy → ostatni pomiar."""
    wynik = []
    for pole in pola:
        if pole["typ"] != "wybor" or not pole.get("skala"):
            continue
        opcje = pole["opcje"]  # od najlepszej do najgorszej
        kolory = {o: kolor_skali(i, len(opcje)) for i, o in enumerate(opcje)}
        miejsca, lepiej, gorzej, bez_zmian = [], 0, 0, 0
        for lancuch in lancuchy_:
            przebieg = [(p["wartosci"].get(pole["nazwa"]) if p is not None else None) for p in lancuch]
            znane = [w for w in przebieg if w in opcje]
            if len(znane) < 2:
                continue
            roznica = opcje.index(znane[-1]) - opcje.index(znane[0])
            ocena = "lepiej" if roznica < 0 else "gorzej" if roznica > 0 else "bez zmian"
            lepiej += roznica < 0
            gorzej += roznica > 0
            bez_zmian += roznica == 0
            miejsca.append({
                "numery": [p["nr"] if p is not None else None for p in lancuch],
                "przebieg": [{"wartosc": w, "kolor": kolory.get(w)} if w in opcje else None for w in przebieg],
                "ocena": ocena,
            })
        # najpierw pogorszenia — to one wymagają reakcji
        miejsca.sort(key=lambda m: {"gorzej": 0, "lepiej": 1, "bez zmian": 2}[m["ocena"]])
        wynik.append({"nazwa": pole["nazwa"], "lepiej": lepiej, "gorzej": gorzej, "bez_zmian": bez_zmian, "miejsca": miejsca})
    return wynik


def paski_svg(wpis: dict, szerokosc: int = 600) -> str:
    """Poziome paski udziałów odpowiedzi — jeden na inwentaryzację (numer 1, 2…).
    Tylko liczby i kolory z kodu; nazwy wartości są w legendzie HTML."""
    wiersze = wpis["wiersze"]
    n = len(wiersze[0]["w_czasie"])
    wys_paska, odstep, lewy = 22, 8, 28
    wysokosc = n * (wys_paska + odstep)
    czesci = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {szerokosc} {wysokosc}" width="{szerokosc}" height="{wysokosc}" font-family="sans-serif" font-size="12">']
    for k in range(n):
        y = k * (wys_paska + odstep)
        czesci.append(f'<text x="{lewy - 8}" y="{y + 15}" text-anchor="end" fill="#6e6e73">{k + 1}</text>')
        x = float(lewy)
        for w in wiersze:
            dl = (szerokosc - lewy) * w["w_czasie"][k]["procent"] / 100
            if dl <= 0:
                continue
            czesci.append(f'<rect x="{x:.1f}" y="{y}" width="{dl:.1f}" height="{wys_paska}" fill="{w["kolor"]}"/>')
            if dl >= 34:
                czesci.append(f'<text x="{x + dl / 2:.1f}" y="{y + 15}" text-anchor="middle" fill="#ffffff">{round(w["w_czasie"][k]["procent"])}%</text>')
            x += dl
    czesci.append("</svg>")
    return "".join(czesci)
