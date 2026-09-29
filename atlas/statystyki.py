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


def _para(w: dict) -> dict:
    return {"nazwa": w["nazwa"], "wartosc": w["wartosc"]}
