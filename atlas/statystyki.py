"""Statystyki opisowe i podział na klasy — liczone tutaj, nie przez model.

Zasada z CLAUDE.md: liczby przychodzą z danych. Gemini dostaje gotowe
fakty z tego modułu i ma je tylko opisać słowami.
"""

import statistics

LICZBA_KLAS = 5


def statystyki(wartosci: list[dict]) -> dict:
    """wartosci: [{"nazwa": str, "wartosc": float, ...}] → słownik statystyk."""
    if not wartosci:
        return {"liczba_gmin": 0}

    posortowane = sorted(wartosci, key=lambda w: w["wartosc"])
    liczby = [w["wartosc"] for w in posortowane]
    return {
        "liczba_gmin": len(liczby),
        "min": _para(posortowane[0]),
        "max": _para(posortowane[-1]),
        "srednia": statistics.fmean(liczby),
        "mediana": statistics.median(liczby),
        "najnizsze": [_para(w) for w in posortowane[:3]],
        "najwyzsze": [_para(w) for w in reversed(posortowane[-3:])],
    }


def progi_klas(liczby: list[float], liczba_klas: int = LICZBA_KLAS) -> list[float]:
    """Progi klas kwantylowych (każda klasa ma podobną liczbę gmin).

    Zwraca rosnące, unikalne górne granice klas bez ostatniej (maksimum).
    Przy małej liczbie różnych wartości klas może być mniej.
    """
    if len(set(liczby)) < 2:
        return []
    kwantyle = statistics.quantiles(liczby, n=liczba_klas, method="inclusive")
    progi = []
    for prog in kwantyle:
        if prog not in progi and min(liczby) <= prog < max(liczby):
            progi.append(prog)
    return progi


def format_liczby(liczba: float) -> str:
    """Polski zapis liczby: spacja tysięcy, przecinek dziesiętny, max 2 miejsca."""
    if float(liczba).is_integer():
        tekst = f"{int(liczba):,}"
    else:
        tekst = f"{liczba:,.2f}".rstrip("0").rstrip(".")
    return tekst.replace(",", " ").replace(".", ",")


def fakty_do_opisu(zmienna: dict, rok: int, wojewodztwo: str, stat: dict) -> list[str]:
    """Lista zdań-faktów z liczbami w polskim zapisie — wejście dla Gemini."""
    jednostka = f" {zmienna['jednostka']}" if zmienna.get("jednostka") else ""

    def z_jednostka(liczba):
        return f"{format_liczby(liczba)}{jednostka}"

    fakty = [
        f"Wskaźnik: {zmienna['nazwa']}",
        f"Jednostka: {zmienna.get('jednostka') or 'brak'}",
        f"Rok: {rok}",
        f"Obszar: gminy województwa {wojewodztwo}",
        f"Liczba gmin z danymi: {stat['liczba_gmin']}",
        f"Wartość najwyższa: {stat['max']['nazwa']} — {z_jednostka(stat['max']['wartosc'])}",
        f"Wartość najniższa: {stat['min']['nazwa']} — {z_jednostka(stat['min']['wartosc'])}",
        f"Mediana: {z_jednostka(stat['mediana'])}",
        f"Średnia arytmetyczna (nieważona) gmin: {z_jednostka(stat['srednia'])}",
        "3 gminy o najwyższej wartości: "
        + "; ".join(f"{w['nazwa']} ({z_jednostka(w['wartosc'])})" for w in stat["najwyzsze"]),
        "3 gminy o najniższej wartości: "
        + "; ".join(f"{w['nazwa']} ({z_jednostka(w['wartosc'])})" for w in stat["najnizsze"]),
    ]
    return fakty


# Klasy zmiany procentowej (kartogram rozbieżny): stałe i symetryczne
# wokół zera, żeby „spadek” i „wzrost” były porównywalne między wskaźnikami.
PROGI_ZMIANY_PROC = [-10.0, -2.0, 2.0, 10.0]


def porownaj(gminy: list[dict], gminy_bazowe: list[dict]) -> list[dict]:
    """Zmiana między rokiem bazowym a badanym dla gmin obecnych w obu latach.

    zmiana_proc jest None, gdy wartość bazowa to 0 (dzielenie przez zero).
    Wynik posortowany malejąco po zmianie procentowej (None na końcu).
    """
    bazowe = {g["teryt"]: g["wartosc"] for g in gminy_bazowe}
    wynik = []
    for g in gminy:
        if g["teryt"] not in bazowe:
            continue
        baza = bazowe[g["teryt"]]
        wynik.append(
            {
                **g,
                "wartosc_bazowa": baza,
                "zmiana": g["wartosc"] - baza,
                "zmiana_proc": None if baza == 0 else (g["wartosc"] - baza) / abs(baza) * 100,
            }
        )
    wynik.sort(key=lambda g: (g["zmiana_proc"] is None, -(g["zmiana_proc"] or 0)))
    return wynik


def statystyki_zmiany(porownanie: list[dict]) -> dict:
    procenty = [g["zmiana_proc"] for g in porownanie if g["zmiana_proc"] is not None]
    if not procenty:
        return {"liczba_gmin": len(porownanie)}
    z_procentem = [g for g in porownanie if g["zmiana_proc"] is not None]
    return {
        "liczba_gmin": len(porownanie),
        "wzrosty": sum(1 for g in porownanie if g["zmiana"] > 0),
        "spadki": sum(1 for g in porownanie if g["zmiana"] < 0),
        "bez_zmian": sum(1 for g in porownanie if g["zmiana"] == 0),
        "mediana_zmiany_proc": statistics.median(procenty),
        # Tylko prawdziwy wzrost/spadek: gdy wszystkie gminy urosły,
        # „największego spadku” nie ma (None), a nie „najmniejszy wzrost”.
        "najwiekszy_wzrost": _para_zmiany(z_procentem[0]) if z_procentem[0]["zmiana_proc"] > 0 else None,
        "najwiekszy_spadek": _para_zmiany(z_procentem[-1]) if z_procentem[-1]["zmiana_proc"] < 0 else None,
    }


def fakty_zmiany(rok_bazowy: int, rok: int, stat: dict) -> list[str]:
    if "mediana_zmiany_proc" not in stat:
        return []
    wz, sp = stat["najwiekszy_wzrost"], stat["najwiekszy_spadek"]
    fakty = [
        f"Porównanie z rokiem: {rok_bazowy}",
        f"Liczba gmin porównanych: {stat['liczba_gmin']}",
        f"Gminy ze wzrostem wartości od {rok_bazowy} do {rok}: {stat['wzrosty']}",
        f"Gminy ze spadkiem wartości od {rok_bazowy} do {rok}: {stat['spadki']}",
        f"Mediana zmiany procentowej: {format_liczby(stat['mediana_zmiany_proc'])}%",
    ]
    if wz:
        fakty.append(f"Największy wzrost procentowy: {wz['nazwa']} ({format_liczby(wz['zmiana_proc'])}%)")
    if sp:
        fakty.append(f"Największy spadek procentowy: {sp['nazwa']} ({format_liczby(sp['zmiana_proc'])}%)")
    return fakty


def _para_zmiany(g: dict) -> dict:
    return {"nazwa": g["nazwa"], "zmiana_proc": g["zmiana_proc"], "zmiana": g["zmiana"]}


def zmiana_w_szeregu(szereg: list[dict]) -> dict | None:
    """Zmiana od pierwszego do ostatniego roku szeregu (bezwzględna i %)."""
    if len(szereg) < 2:
        return None
    pierwszy, ostatni = szereg[0], szereg[-1]
    return {
        "od": pierwszy["rok"],
        "do": ostatni["rok"],
        "zmiana": ostatni["wartosc"] - pierwszy["wartosc"],
        "zmiana_proc": None
        if pierwszy["wartosc"] == 0
        else (ostatni["wartosc"] - pierwszy["wartosc"]) / abs(pierwszy["wartosc"]) * 100,
    }


def _para(w: dict) -> dict:
    return {"nazwa": w["nazwa"], "wartosc": w["wartosc"]}
