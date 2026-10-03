"""Etapy realizacji koncepcji osiedla (ETAP 196).

Użytkownik wpisuje przy terenie numer etapu (1–10). Dla każdego etapu kod
liczy to samo co dla całej koncepcji — powierzchnię terenów, powierzchnię
całkowitą, program (mieszkania, mieszkańcy, miejsca postojowe) i koszty ze
stawek — tylko z terenów tego etapu, oraz sumy narastające.

Zasady:
- każdy etap liczony osobno, więc miejsca postojowe muszą się zmieścić na
  terenach KS tego samego etapu (etap nie „pożycza” parkingu z następnego),
- koszt gruntu dotyczy całego obszaru opracowania — nie dzielimy go na
  etapy (zostaje w szacunku całości),
- tereny bez numeru tworzą grupę „bez etapu”, żeby suma zgadzała się z
  całością; mieszkania liczone w etapach mogą się różnić od całości o
  zaokrąglenia (część całkowita w każdym etapie).
"""

import math

from . import koszty as kosz
from . import program as prog

MAKS_ETAPOW = 10


class BladEtapu(ValueError):
    """Niepoprawny numer etapu przy terenie."""


def etap_terenu(funkcja: str, wlasciwosci: dict) -> int | None:
    """Numer etapu z właściwości terenu; None, gdy nie wpisano."""
    wartosc = wlasciwosci.get("etap")
    if wartosc is None or wartosc == "":
        return None
    try:
        liczba = float(wartosc)
    except (TypeError, ValueError):
        liczba = math.nan
    if isinstance(wartosc, bool) or not liczba.is_integer() or not 1 <= liczba <= MAKS_ETAPOW:
        raise BladEtapu(f"Teren {funkcja}: etap musi być liczbą całkowitą 1–{MAKS_ETAPOW}.")
    return int(liczba)


def etapy(tereny: list[dict], ustawienia: dict | None) -> dict | None:
    """Zestawienie etapów; None, gdy żaden teren nie ma numeru etapu.

    Tereny muszą mieć już pola pole_m2, parametry i etap (bilans.py)."""
    if not any(t["etap"] is not None for t in tereny):
        return None
    grupy: dict[int | None, list[dict]] = {}
    for t in tereny:
        grupy.setdefault(t["etap"], []).append(t)
    kolejnosc = sorted(k for k in grupy if k is not None) + ([None] if None in grupy else [])
    lista, koszt_narastajaco, mieszkania_narastajaco = [], 0, 0
    for nr in kolejnosc:
        czesc = grupy[nr]
        p = prog.program(czesc, None, ustawienia)
        k = kosz.koszty(czesc, None, ustawienia, p)
        pozycje = [x for x in (k or {}).get("pozycje", []) if x["klucz"] != "grunt"]
        koszt = sum(x["koszt"] for x in pozycje) if pozycje else None
        ile = kosz.ilosci(czesc, None, p)
        mieszkania_narastajaco += p["mieszkania"]
        koszt_narastajaco += koszt or 0
        lista.append({
            "etap": nr,
            "terenow": len(czesc),
            "powierzchnia_m2": round(sum(t["pole_m2"] for t in czesc), 1),
            "calkowita_m2": round(ile["calkowita_MW"] + ile["calkowita_MN"] + ile["calkowita_U"], 1),
            "mieszkania": p["mieszkania"],
            "mieszkancy": p["mieszkancy"],
            "miejsca_brakuje": p["miejsca_brakuje"],
            "koszt": koszt,
            "mieszkania_narastajaco": mieszkania_narastajaco,
            "koszt_narastajaco": koszt_narastajaco if koszt is not None else None,
        })
    return {"lista": lista, "bez_etapu": None in grupy}
