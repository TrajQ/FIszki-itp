"""Godziny pracy z grafiku (ETAP 230).

Grafik to zwykle tabela miesiąca (np. z Google Docs): nad nią „Październik
2026”, w nagłówku dni tygodnia, w komórkach „16.”, imię i godziny
„15:30-20:00”. Z PDF-a tekst wychodzi komórka po komórce (dzień, imię,
godziny) albo wierszami tabeli (najpierw dni, potem imiona, potem godziny)
— obsługujemy oba układy.

Wszystkie liczby (godziny, suma, kwota) liczy ten moduł. Gemini najwyżej
przepisuje tekst ze zdjęcia (routes.py), a użytkownik widzi ten tekst i
może go poprawić przed liczeniem.
"""

import re
import unicodedata
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

MIESIACE = ["styczeń", "luty", "marzec", "kwiecień", "maj", "czerwiec", "lipiec", "sierpień", "wrzesień", "październik", "listopad", "grudzień"]
MIESIACE_DOPELNIACZ = ["stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca", "lipca", "sierpnia", "września", "października", "listopada", "grudnia"]
DNI_TYGODNIA = ("poniedziałek", "wtorek", "środa", "czwartek", "piątek", "sobota", "niedziela")
STAWKA_DOMYSLNA = Decimal("31.4")
MAKS_DLUGOSC_TEKSTU = 100_000

_GODZINY = r"(\d{1,2})[:.](\d{2})\s*[-–—]\s*(\d{1,2})[:.](\d{2})"
_TOKEN = re.compile(rf"(?P<godziny>{_GODZINY})|(?P<dzien>(?<![\d:.])\d{{1,2}}(?![\d:])\.?)|(?P<slowo>[^\W\d_]+)")


class BladGrafiku(ValueError):
    """Tekstu nie da się odczytać jako grafiku."""


@dataclass
class Zmiana:
    dzien: int
    imie: str
    od: str  # „15:30”
    do: str
    minuty: int
    miesiac_przesuniecie: int = 0  # -1: dzień z poprzedniego miesiąca w tabeli, 1: z następnego


def _bez_ogonkow(tekst: str) -> str:
    return "".join(z for z in unicodedata.normalize("NFD", tekst.lower()) if unicodedata.category(z) != "Mn").replace("ł", "l")


def miesiac_i_rok(tekst: str) -> tuple[int, int] | None:
    """„Pazdziernik 2026” / „październik 2026” / „października 2026” → (10, 2026)."""
    znormalizowany = _bez_ogonkow(tekst)
    nazwy = {_bez_ogonkow(n): i + 1 for i, n in enumerate(MIESIACE)} | {_bez_ogonkow(n): i + 1 for i, n in enumerate(MIESIACE_DOPELNIACZ)}
    for m in re.finditer(r"([a-z]+)\s+(\d{4})", znormalizowany):
        if m.group(1) in nazwy and 2000 <= int(m.group(2)) <= 2100:
            return nazwy[m.group(1)], int(m.group(2))
    return None


def _czas(godzina: str, minuta: str) -> int:
    g, m = int(godzina), int(minuta)
    if not (0 <= g <= 24 and 0 <= m < 60):
        raise BladGrafiku(f"Niepoprawna godzina {godzina}:{minuta}.")
    return g * 60 + m


def _tokeny(tekst: str) -> list[tuple[str, object]]:
    """Tekst od nagłówka z dniami tygodnia (jeśli jest — notatka nad tabelą,
    np. „o 17 pierwsza grupa”, nie pomyli się z dniem 17)."""
    znormalizowany = _bez_ogonkow(tekst)
    pozycje = [znormalizowany.find(_bez_ogonkow(d)) for d in DNI_TYGODNIA]
    pozycje = [p for p in pozycje if p >= 0]
    if pozycje:
        tekst = tekst[min(pozycje):]
    wynik = []
    for m in _TOKEN.finditer(tekst):
        if m.group("godziny"):
            g1, m1, g2, m2 = m.group(2, 3, 4, 5)
            wynik.append(("godziny", (f"{int(g1)}:{m1}", f"{int(g2)}:{m2}", _czas(g1, m1), _czas(g2, m2))))
        elif m.group("dzien"):
            dzien = int(m.group("dzien").rstrip("."))
            if 1 <= dzien <= 31:
                wynik.append(("dzien", dzien))
        else:
            slowo = m.group("slowo")
            if _bez_ogonkow(slowo) not in {_bez_ogonkow(d) for d in DNI_TYGODNIA}:
                wynik.append(("slowo", slowo))
    return wynik


def _serie(tokeny):
    serie = []
    for rodzaj, wartosc in tokeny:
        if serie and serie[-1][0] == rodzaj:
            serie[-1][1].append(wartosc)
        else:
            serie.append((rodzaj, [wartosc]))
    return serie


def odczytaj_zmiany(tekst: str) -> list[Zmiana]:
    """Wszystkie zmiany z grafiku (wszystkie osoby), w kolejności tabeli."""
    if len(tekst) > MAKS_DLUGOSC_TEKSTU:
        raise BladGrafiku("Tekst grafiku jest za długi.")
    serie = _serie(_tokeny(tekst))
    zmiany: list[Zmiana] = []
    dzien, imie = None, ""
    i = 0
    while i < len(serie):
        rodzaj, wartosci = serie[i]
        # układ wierszami: n dni, n imion (po jednym słowie), n godzin
        if rodzaj == "dzien" and len(wartosci) > 1 and i + 2 < len(serie) \
                and serie[i + 1][0] == "slowo" and serie[i + 2][0] == "godziny" \
                and len(serie[i + 1][1]) == len(wartosci) == len(serie[i + 2][1]):
            for d, osoba, g in zip(wartosci, serie[i + 1][1], serie[i + 2][1]):
                zmiany.append(_zmiana(d, osoba, g))
            dzien, imie = wartosci[-1], serie[i + 1][1][-1]
            i += 3
            continue
        if rodzaj == "dzien":
            dzien, imie = wartosci[-1], ""
        elif rodzaj == "slowo":
            imie = " ".join(wartosci)
        elif rodzaj == "godziny" and dzien is not None:
            for g in wartosci:
                zmiany.append(_zmiana(dzien, imie, g))
        i += 1
    _oznacz_miesiace(zmiany)
    return zmiany


def _zmiana(dzien: int, imie: str, godziny) -> Zmiana:
    od, do, start, koniec = godziny
    if koniec <= start:
        koniec += 24 * 60  # zmiana przez północ, np. 22:00-6:00
    return Zmiana(dzien, imie, od, do, koniec - start)


def _oznacz_miesiace(zmiany: list[Zmiana]) -> None:
    """Tabela miesiąca bywa uzupełniona dniami sąsiednich miesięcy
    (…, 29, 30, 1, 2, … albo 30, 31, 1, 2 na końcu). Spadek numeru dnia o
    więcej niż 20 to granica miesiąca."""
    przejscia = [k for k in range(1, len(zmiany)) if zmiany[k].dzien < zmiany[k - 1].dzien - 20]
    if not przejscia:
        return
    pierwsze_poprzedni = zmiany[0].dzien > 20  # tabela zaczyna się końcówką poprzedniego miesiąca
    przesuniecie = -1 if pierwsze_poprzedni else 0
    granice = set(przejscia)
    for k, z in enumerate(zmiany):
        if k in granice:
            przesuniecie += 1
        z.miesiac_przesuniecie = przesuniecie


def ta_sama_osoba(imie_w_grafiku: str, imie: str) -> bool:
    """Imię wśród słów komórki (bez wielkości liter i ogonków) — „patryk”,
    „Patryk (zastępstwo)” to ta sama osoba co „Patryk”."""
    return _bez_ogonkow(imie).strip() in _bez_ogonkow(imie_w_grafiku).split()


def godziny_tekst(minuty: int) -> str:
    """270 → „4,5”, 240 → „4”, 255 → „4,25”."""
    wynik = (Decimal(minuty) / 60).quantize(Decimal("0.01"), ROUND_HALF_UP).normalize()
    return format(wynik, "f").replace(".", ",")


def kwota_tekst(x: Decimal) -> str:
    tekst = format(x.quantize(Decimal("0.01"), ROUND_HALF_UP), ",.2f")
    return tekst.replace(",", " ").replace(".", ",")


def klucz_zmiany(z: Zmiana) -> str:
    """„16|15:30|20:00” — do wyłączenia zmiany z rozliczenia (ETAP 232)."""
    return f"{z.dzien}|{z.od}|{z.do}"


def rozliczenie(tekst: str, imie: str, stawka: Decimal = STAWKA_DOMYSLNA, miesiac: int | None = None, rok: int | None = None,
                pominiete: set[str] | None = None) -> dict:
    """Zmiany wskazanej osoby w miesiącu grafiku → linie jak w notatce,
    suma godzin i kwota (godziny × stawka). `pominiete` — klucze zmian
    wyłączonych ręcznie (np. zamiana z kimś); nie wchodzą do sumy."""
    if not imie.strip():
        raise BladGrafiku("Podaj imię, którego zmiany liczyć (tak jak w grafiku).")
    if stawka <= 0:
        raise BladGrafiku("Stawka musi być większa od zera.")
    rozpoznany = miesiac_i_rok(tekst)
    if miesiac is None or rok is None:
        if rozpoznany is None:
            raise BladGrafiku("Nie rozpoznano miesiąca — wybierz miesiąc i rok w formularzu.")
        miesiac, rok = rozpoznany
    if not 1 <= miesiac <= 12:
        raise BladGrafiku("Niepoprawny miesiąc.")
    wszystkie = odczytaj_zmiany(tekst)
    if not wszystkie:
        raise BladGrafiku("W tekście nie znaleziono zmian (dzień, imię, godziny np. 15:30-20:00).")
    moje = [z for z in wszystkie if ta_sama_osoba(z.imie, imie)]
    w_miesiacu = [z for z in moje if z.miesiac_przesuniecie == 0]
    pominiete_inny_miesiac = len(moje) - len(w_miesiacu)
    pominiete = pominiete or set()
    wszystkie_moje = w_miesiacu
    w_miesiacu = [z for z in w_miesiacu if klucz_zmiany(z) not in pominiete]
    linie = [f"{z.dzien} {MIESIACE_DOPELNIACZ[miesiac - 1]} {z.od}-{z.do} {godziny_tekst(z.minuty)}h" for z in w_miesiacu]
    minuty = sum(z.minuty for z in w_miesiacu)
    godziny = Decimal(minuty) / 60
    kwota = godziny * stawka
    suma = "+".join(godziny_tekst(z.minuty) for z in w_miesiacu)
    stawka_tekst = format(stawka.normalize(), "f").replace(".", ",")
    tekst_wyniku = "\n".join([f"{MIESIACE[miesiac - 1]} {rok}", *linie, "",
                              f"{suma}={godziny_tekst(minuty)}" if w_miesiacu else "brak zmian",
                              f"{godziny_tekst(minuty)} h × {stawka_tekst} zł = {kwota_tekst(kwota)} zł"])
    inne_osoby = sorted({z.imie for z in wszystkie if z.imie and not ta_sama_osoba(z.imie, imie)}, key=str.lower)
    return {
        "miesiac": miesiac,
        "rok": rok,
        "miesiac_z_tekstu": rozpoznany is not None,
        "zmiany": [{"dzien": z.dzien, "od": z.od, "do": z.do, "godziny": godziny_tekst(z.minuty), "klucz": klucz_zmiany(z),
                    "wliczona": klucz_zmiany(z) not in pominiete} for z in wszystkie_moje],
        "wliczonych": len(w_miesiacu),
        "minuty": minuty,  # do zapisu w historii (ETAP 232)
        "kwota_dokladna": str(kwota.quantize(Decimal("0.01"), ROUND_HALF_UP)),
        "godziny": godziny_tekst(minuty),
        "kwota": kwota_tekst(kwota),
        "stawka": stawka_tekst,
        "tekst": tekst_wyniku,
        "wszystkich_zmian": len(wszystkie),
        "pominiete_inny_miesiac": pominiete_inny_miesiac,
        "inne_osoby": inne_osoby,
    }
