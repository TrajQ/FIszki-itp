"""Projekt inwentaryzacji: pola formularza i sprawdzanie pliku z telefonu (ETAP 65).

Pole formularza: {"nazwa", "typ", "opcje", "skala"} — typ „wybor” (lista
opcji), „wiele” (wielokrotny wybór — wartością jest lista opcji, ETAP 93),
„tekst”, „liczba” albo „tak_nie”. „skala” (tylko lista wyboru):
opcje są uporządkowane od najlepszej do najgorszej, więc mapa i raport
kolorują je od zielonego do czerwonego (ETAP 70). Wartości punktu to słownik
{nazwa pola: wartość}.

ETAP 166: „wymagane” (formularz na telefonie nie zapisze punktu bez tej
wartości) i dla liczby „min” / „max”. Klucze są w polu tylko wtedy, gdy
ustawione — projekty sprzed ETAPu 166 się nie zmieniają. Import pliku nie
odrzuca punktów z brakami (zebrane dane są cenniejsze niż reguła dopisana
później) — `braki` opisuje je w tabeli punktów.

Plik z telefonu (eksport formularza terenowego) to JSON:
{"format": "warsztat-teren", "wersja": 1, "projekt_klucz", "punkty": [
  {"uid", "lat", "lng", "dokladnosc_m", "czas", "wartosci", "uwagi", "zdjecie"}]}
gdzie zdjecie to JPEG jako data URL albo null. Wszystko przychodzi z
zewnątrz (plik przeniesiony z telefonu), więc sprawdzamy każde pole.
"""

import base64
import hashlib
import json
import math
import re
from datetime import datetime

TYPY_POL = {"wybor": "lista wyboru", "wiele": "wielokrotny wybór", "tekst": "tekst", "liczba": "liczba", "tak_nie": "tak / nie"}
TYPY_Z_OPCJAMI = ("wybor", "wiele")
# Rodzaj projektu (ETAP 93): inwentaryzacja (punkty na mapie) albo ankieta
# (odpowiedzi ludzi; położenie i zdjęcie opcjonalne, na pierwszym planie pytania).
RODZAJE = {"inwentaryzacja": "inwentaryzacja", "ankieta": "ankieta"}
MAKS_POL = 20
MAKS_OPCJI = 30
MAKS_DLUGOSC = 200  # nazwa pola, opcja, wartość tekstowa
MAKS_UWAGI = 2000
MAKS_PUNKTOW = 3000
MAKS_ZDJECIE_B = 4 * 1024 * 1024
# ETAP 219: kierunek zdjęcia — osiem stron świata, w stopniach od północy zgodnie z ruchem wskazówek
KIERUNKI = {0: "N", 45: "NE", 90: "E", 135: "SE", 180: "S", 225: "SW", 270: "W", 315: "NW"}
STRZALKI = {0: "↑", 45: "↗", 90: "→", 135: "↘", 180: "↓", 225: "↙", 270: "←", 315: "↖"}
FORMAT = "warsztat-teren"

# Wzory projektów — tylko propozycja pól, użytkownik może je zmienić.
WZORY = {
    "zielen": {
        "nazwa": "Inwentaryzacja zieleni",
        "pola": [
            {"nazwa": "obiekt", "typ": "wybor", "opcje": ["drzewo", "krzew", "grupa drzew", "żywopłot", "trawnik"]},
            {"nazwa": "gatunek", "typ": "tekst", "opcje": []},
            {"nazwa": "obwód pnia [cm]", "typ": "liczba", "opcje": []},
            {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "średni", "zły", "do usunięcia"], "skala": True},
        ],
    },
    "budynki": {
        "nazwa": "Stan zabudowy",
        "pola": [
            {"nazwa": "funkcja", "typ": "wybor", "opcje": ["mieszkaniowa", "usługowa", "mieszana", "przemysłowa", "gospodarcza", "pustostan"]},
            {"nazwa": "kondygnacje", "typ": "liczba", "opcje": []},
            {"nazwa": "stan techniczny", "typ": "wybor", "opcje": ["dobry", "średni", "zły", "ruina"], "skala": True},
            {"nazwa": "wartość kulturowa", "typ": "tak_nie", "opcje": []},
        ],
    },
    "ankieta": {
        "nazwa": "Ankieta: przestrzeń publiczna",
        "rodzaj": "ankieta",
        "pola": [
            {"nazwa": "jak często tu bywasz", "typ": "wybor", "opcje": ["codziennie", "kilka razy w tygodniu", "kilka razy w miesiącu", "rzadziej", "pierwszy raz"]},
            {"nazwa": "po co tu przychodzisz", "typ": "wiele", "opcje": ["przejście", "odpoczynek", "zakupy", "spotkania", "sport", "z dziećmi", "praca / nauka", "inne"]},
            {"nazwa": "czy czujesz się tu bezpiecznie", "typ": "wybor", "opcje": ["tak", "raczej tak", "raczej nie", "nie"], "skala": True},
            {"nazwa": "czego tu brakuje", "typ": "wiele", "opcje": ["ławek", "zieleni", "cienia", "oświetlenia", "toalet", "miejsc zabaw", "stojaków rowerowych", "koszy", "niczego"]},
            {"nazwa": "wiek", "typ": "wybor", "opcje": ["do 18", "19–35", "36–60", "61 i więcej"]},
        ],
    },
    "przestrzen": {
        "nazwa": "Przestrzeń publiczna",
        "pola": [
            {"nazwa": "element", "typ": "wybor", "opcje": ["ławka", "kosz", "oświetlenie", "stojak rowerowy", "plac zabaw", "przystanek", "bariera", "inne"]},
            {"nazwa": "stan", "typ": "wybor", "opcje": ["dobry", "średni", "zły"], "skala": True},
            {"nazwa": "dostępny dla wózka", "typ": "tak_nie", "opcje": []},
        ],
    },
}


class BladDanych(ValueError):
    """Niepoprawna definicja pól albo plik z telefonu."""


def sprawdz_tekst(wartosc, opis: str, maks: int = MAKS_DLUGOSC, wymagany: bool = True) -> str:
    tekst = " ".join(str(wartosc or "").split())
    if wymagany and not tekst:
        raise BladDanych(f"{opis}: pole nie może być puste.")
    if len(tekst) > maks:
        raise BladDanych(f"{opis}: najwyżej {maks} znaków.")
    return tekst


def sprawdz_pola(pola) -> list[dict]:
    """Definicja pól z formularza Warsztatu → poprawiona lista pól."""
    if not isinstance(pola, list) or not pola:
        raise BladDanych("Projekt potrzebuje co najmniej jednego pola.")
    if len(pola) > MAKS_POL:
        raise BladDanych(f"Najwyżej {MAKS_POL} pól.")
    wynik, nazwy = [], set()
    for i, p in enumerate(pola, start=1):
        if not isinstance(p, dict):
            raise BladDanych(f"Pole {i}: zły format.")
        nazwa = sprawdz_tekst(p.get("nazwa"), f"Pole {i}, nazwa")
        if nazwa.lower() in nazwy:
            raise BladDanych(f"Pole „{nazwa}” występuje dwa razy.")
        nazwy.add(nazwa.lower())
        typ = p.get("typ")
        if typ not in TYPY_POL:
            raise BladDanych(f"Pole „{nazwa}”: nieznany typ.")
        opcje = []
        if typ in TYPY_Z_OPCJAMI:
            opcje = [sprawdz_tekst(o, f"Pole „{nazwa}”, opcja") for o in (p.get("opcje") or []) if str(o or "").strip()]
            if len(opcje) < 2:
                raise BladDanych(f"Pole „{nazwa}”: lista wyboru potrzebuje co najmniej 2 opcji.")
            if len({o.lower() for o in opcje}) < len(opcje):
                raise BladDanych(f"Pole „{nazwa}”: opcje się powtarzają.")
            if len(opcje) > MAKS_OPCJI:
                raise BladDanych(f"Pole „{nazwa}”: najwyżej {MAKS_OPCJI} opcji.")
        pole = {"nazwa": nazwa, "typ": typ, "opcje": opcje, "skala": typ == "wybor" and p.get("skala") is True}
        if p.get("wymagane") is True:
            pole["wymagane"] = True
        if typ == "liczba":
            for granica in ("min", "max"):
                if p.get(granica) not in (None, ""):
                    pole[granica] = _liczba(p.get(granica), f"Pole „{nazwa}”, {granica}")
            if pole.get("min", -math.inf) > pole.get("max", math.inf):
                raise BladDanych(f"Pole „{nazwa}”: minimum większe niż maksimum.")
        wynik.append(pole)
    return wynik


def braki(wartosci: dict, pola: list[dict]) -> list[str]:
    """Opis wartości niezgodnych z regułami pól (ETAP 166): brak wymaganej,
    liczba spoza zakresu. Pusta lista — punkt w porządku."""
    wynik = []
    for p in pola:
        w = wartosci.get(p["nazwa"])
        if w in (None, "", []):
            if p.get("wymagane"):
                wynik.append(f"brak: {p['nazwa']}")
        elif p["typ"] == "liczba" and isinstance(w, (int, float)):
            if w < p.get("min", -math.inf) or w > p.get("max", math.inf):
                zakres = f"{p['min']:g}" if "min" in p else "…"
                zakres += f"–{p['max']:g}" if "max" in p else "–…"
                wynik.append(f"{p['nazwa']} poza zakresem {zakres}")
    return wynik


def _liczba(wartosc, opis: str) -> float:
    if isinstance(wartosc, bool):
        raise BladDanych(f"{opis}: to nie jest liczba.")
    try:
        liczba = float(wartosc)
    except (TypeError, ValueError):
        raise BladDanych(f"{opis}: to nie jest liczba.") from None
    if not math.isfinite(liczba):
        raise BladDanych(f"{opis}: to nie jest liczba.")
    return liczba


def _wartosci(surowe, pola: list[dict], opis: str) -> dict:
    """Wartości punktu zgodne z polami projektu; nieznane pola pomijamy
    (np. pole usunięte z projektu po pobraniu formularza)."""
    if not isinstance(surowe, dict):
        raise BladDanych(f"{opis}: wartości muszą być obiektem.")
    wynik = {}
    for p in pola:
        w = surowe.get(p["nazwa"])
        if w is None or w == "":
            continue
        if p["typ"] == "liczba":
            wynik[p["nazwa"]] = _liczba(w, f"{opis}, {p['nazwa']}")
        elif p["typ"] == "wiele":
            if not isinstance(w, list):
                raise BladDanych(f"{opis}, {p['nazwa']}: oczekiwano listy odpowiedzi.")
            wybrane = {sprawdz_tekst(x, f"{opis}, {p['nazwa']}", wymagany=False) for x in w}
            if nieznane := wybrane - set(p["opcje"]):
                raise BladDanych(f"{opis}, {p['nazwa']}: „{sorted(nieznane)[0]}” nie ma na liście opcji.")
            if wybrane:
                wynik[p["nazwa"]] = [o for o in p["opcje"] if o in wybrane]  # w kolejności opcji
        elif p["typ"] == "tak_nie":
            if not isinstance(w, bool):
                raise BladDanych(f"{opis}, {p['nazwa']}: oczekiwano tak/nie.")
            wynik[p["nazwa"]] = w
        else:
            tekst = sprawdz_tekst(w, f"{opis}, {p['nazwa']}", wymagany=False)
            if p["typ"] == "wybor" and tekst not in p["opcje"]:
                raise BladDanych(f"{opis}, {p['nazwa']}: „{tekst}” nie ma na liście opcji.")
            wynik[p["nazwa"]] = tekst
    return wynik


def _zdjecie(surowe, opis: str) -> bytes | None:
    if surowe in (None, ""):
        return None
    if not isinstance(surowe, str) or not surowe.startswith("data:image/jpeg;base64,"):
        raise BladDanych(f"{opis}: zdjęcie musi być w formacie JPEG.")
    try:
        dane = base64.b64decode(surowe.split(",", 1)[1], validate=True)
    except ValueError:
        raise BladDanych(f"{opis}: uszkodzone zdjęcie.") from None
    if len(dane) > MAKS_ZDJECIE_B:
        raise BladDanych(f"{opis}: zdjęcie większe niż 4 MB.")
    if not dane.startswith(b"\xff\xd8\xff"):
        raise BladDanych(f"{opis}: to nie jest plik JPEG.")
    return dane


def sprawdz_poprawke(dane, pola: list[dict]) -> dict:
    """Poprawka punktu z Warsztatu (ETAP 72): wartości pól, uwagi i
    opcjonalnie nowe położenie (przesunięcie na mapie)."""
    if not isinstance(dane, dict):
        raise BladDanych("Poprawka musi być obiektem.")
    wynik = {
        "wartosci": _wartosci(dane.get("wartosci") or {}, pola, "Punkt"),
        "uwagi": sprawdz_tekst(dane.get("uwagi"), "Uwagi", MAKS_UWAGI, wymagany=False),
    }
    if "lat" in dane or "lng" in dane:
        lat, lng = _liczba(dane.get("lat"), "Szerokość"), _liczba(dane.get("lng"), "Długość")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise BladDanych("Współrzędne poza zakresem.")
        wynik["lat"], wynik["lng"] = lat, lng
    if "zdjecie_opis" in dane:  # ETAP 219 — klucze opcjonalne, starsze wywołania ich nie wysyłają
        wynik["zdjecie_opis"] = sprawdz_tekst(dane.get("zdjecie_opis"), "Opis zdjęcia", wymagany=False)
    if "zdjecie_kierunek" in dane:
        wynik["zdjecie_kierunek"] = kierunek_zdjecia(dane.get("zdjecie_kierunek"), "Punkt")
    return wynik


def odczytaj_plik(dane, klucz_projektu: str, pola: list[dict]) -> list[dict]:
    """Plik z telefonu → punkty do zapisania. Cały plik albo nic:
    przy pierwszym błędzie BladDanych z numerem punktu."""
    if not isinstance(dane, dict) or dane.get("format") != FORMAT:
        raise BladDanych("To nie jest plik z formularza terenowego Warsztatu.")
    if dane.get("wersja") != 1:
        raise BladDanych("Nieobsługiwana wersja pliku — pobierz nowy formularz z Warsztatu.")
    if dane.get("projekt_klucz") != klucz_projektu:
        raise BladDanych(f"Plik należy do innego projektu („{sprawdz_tekst(dane.get('projekt_nazwa'), 'Projekt', wymagany=False) or '?'}”).")
    punkty = dane.get("punkty")
    if not isinstance(punkty, list):
        raise BladDanych("Plik nie zawiera listy punktów.")
    if len(punkty) > MAKS_PUNKTOW:
        raise BladDanych(f"Najwyżej {MAKS_PUNKTOW} punktów w jednym pliku.")
    wynik = []
    for i, p in enumerate(punkty, start=1):
        opis = f"Punkt {i}"
        if not isinstance(p, dict):
            raise BladDanych(f"{opis}: zły format.")
        uid = str(p.get("uid") or "")
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", uid):
            raise BladDanych(f"{opis}: brak identyfikatora punktu.")
        lat, lng = p.get("lat"), p.get("lng")
        if lat is None or lng is None:
            lat = lng = None  # punkt bez położenia (GPS niedostępny) — pokazujemy w tabeli
        else:
            lat, lng = _liczba(lat, f"{opis}, szerokość"), _liczba(lng, f"{opis}, długość")
            if not (-90 <= lat <= 90 and -180 <= lng <= 180):
                raise BladDanych(f"{opis}: współrzędne poza zakresem.")
        dokladnosc = p.get("dokladnosc_m")
        dokladnosc = None if dokladnosc is None else max(0.0, _liczba(dokladnosc, f"{opis}, dokładność"))
        try:
            czas = datetime.fromisoformat(str(p.get("czas")).replace("Z", "+00:00")).isoformat(timespec="seconds")
        except ValueError:
            raise BladDanych(f"{opis}: niepoprawny czas pomiaru.") from None
        wynik.append({
            "uid": uid,
            "lat": lat,
            "lng": lng,
            "dokladnosc_m": dokladnosc,
            "czas": czas,
            "wartosci": _wartosci(p.get("wartosci") or {}, pola, opis),
            "uwagi": sprawdz_tekst(p.get("uwagi"), f"{opis}, uwagi", MAKS_UWAGI, wymagany=False),
            "zdjecie": _zdjecie(p.get("zdjecie"), opis),
            # ETAP 219: opis i kierunek tylko przy zdjęciu (starsze formularze ich nie mają)
            "zdjecie_opis": sprawdz_tekst(p.get("zdjecie_opis"), f"{opis}, opis zdjęcia", wymagany=False) if p.get("zdjecie") else "",
            "zdjecie_kierunek": kierunek_zdjecia(p.get("zdjecie_kierunek"), opis) if p.get("zdjecie") else None,
        })
    return wynik


def kierunek_zdjecia(wartosc, opis: str) -> int | None:
    """Kierunek patrzenia aparatu: jedna z ośmiu stron świata (stopnie) albo brak."""
    if wartosc is None or wartosc == "":
        return None
    if isinstance(wartosc, bool) or not isinstance(wartosc, (int, str)) or str(wartosc).strip() not in {str(k) for k in KIERUNKI}:
        raise BladDanych(f"{opis}: kierunek zdjęcia musi być jedną z wartości {', '.join(map(str, KIERUNKI))} (stopnie od północy).")
    return int(wartosc)


def opis_kierunku(stopnie) -> str:
    """„↗ NE” do raportu i dymka; pusty tekst, gdy kierunku nie podano."""
    return f"{STRZALKI[stopnie]} {KIERUNKI[stopnie]}" if stopnie in KIERUNKI else ""


# ---------- import punktów z GeoJSON, np. z QGIS (ETAP 133) ----------

POLA_UWAG = ("uwagi", "opis", "notatka", "notes", "description")
POLA_CZASU = ("czas", "data", "time", "date", "timestamp")


def _wartosc_z_geojson(w, pole: dict):
    """Wartość atrybutu z innego programu → typ pola projektu (dalej _wartosci)."""
    if w is None or w == "":
        return None
    if pole["typ"] == "tak_nie" and not isinstance(w, bool):
        tekst = str(w).strip().casefold()
        if tekst in ("tak", "t", "1", "true", "yes", "y"):
            return True
        if tekst in ("nie", "n", "0", "false", "no"):
            return False
        return w  # _wartosci zgłosi błąd
    if pole["typ"] == "wiele" and isinstance(w, str):
        return [x.strip() for x in re.split(r"[;|,]", w) if x.strip()]
    if pole["typ"] == "liczba" and isinstance(w, str):
        return w.strip().replace(" ", "").replace(",", ".")
    if pole["typ"] in ("tekst", "wybor") and not isinstance(w, str):
        return str(w)
    return w


def odczytaj_geojson(dane, pola: list[dict]) -> tuple[list[dict], list[str]]:
    """FeatureCollection punktów (WGS84) → (punkty do zapisania, nazwy
    atrybutów bez pasującego pola). Atrybuty dopasowujemy do pól projektu po
    nazwie (bez wielkości liter); niedopasowane trafiają do uwag. Identyfikator
    punktu z położenia i atrybutów — ponowny import tego samego pliku pomija
    punkty, które już są."""
    if not isinstance(dane, dict) or dane.get("type") != "FeatureCollection" or not isinstance(dane.get("features"), list):
        raise BladDanych("To nie jest GeoJSON z kolekcją obiektów (FeatureCollection).")
    cechy = dane["features"]
    if len(cechy) > MAKS_PUNKTOW:
        raise BladDanych(f"Najwyżej {MAKS_PUNKTOW} punktów w jednym pliku.")
    po_nazwie = {p["nazwa"].strip().casefold(): p for p in pola}
    niedopasowane: set[str] = set()
    wynik = []
    for i, c in enumerate(cechy, start=1):
        opis = f"Obiekt {i}"
        geometria = (c or {}).get("geometry") or {}
        if geometria.get("type") != "Point":
            raise BladDanych(f"{opis}: tylko punkty (Point) — w QGIS zapisz warstwę punktową.")
        wsp = geometria.get("coordinates") or []
        if len(wsp) < 2:
            raise BladDanych(f"{opis}: brak współrzędnych.")
        lng, lat = _liczba(wsp[0], f"{opis}, długość"), _liczba(wsp[1], f"{opis}, szerokość")
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise BladDanych(f"{opis}: współrzędne nie wyglądają na stopnie (WGS84) — w QGIS zapisz plik w układzie EPSG:4326.")
        atrybuty = (c.get("properties") or {})
        if not isinstance(atrybuty, dict):
            raise BladDanych(f"{opis}: zły format atrybutów.")
        surowe, reszta, uwagi, czas = {}, [], "", None
        for klucz, w in atrybuty.items():
            k = str(klucz).strip().casefold()
            if k in po_nazwie:
                surowe[po_nazwie[k]["nazwa"]] = _wartosc_z_geojson(w, po_nazwie[k])
            elif k in POLA_UWAG and w not in (None, ""):
                uwagi = str(w)
            elif k in POLA_CZASU and w not in (None, ""):
                try:
                    czas = datetime.fromisoformat(str(w).replace("Z", "+00:00")).isoformat(timespec="seconds")
                except ValueError:
                    reszta.append(f"{klucz}: {w}")
            elif w not in (None, ""):
                niedopasowane.add(str(klucz))
                reszta.append(f"{klucz}: {w}")
        tekst_uwag = "; ".join(x for x in [uwagi, *reszta] if x)[:MAKS_UWAGI]
        uid = "gj_" + hashlib.sha1(json.dumps([round(lng, 7), round(lat, 7), atrybuty], sort_keys=True, ensure_ascii=False, default=str).encode()).hexdigest()[:24]
        wynik.append({
            "uid": uid, "lat": lat, "lng": lng, "dokladnosc_m": None,
            "czas": czas or datetime.now().isoformat(timespec="seconds"),
            "wartosci": _wartosci(surowe, pola, opis),
            "uwagi": sprawdz_tekst(tekst_uwag, f"{opis}, uwagi", MAKS_UWAGI, wymagany=False),
            "zdjecie": None,
        })
    return wynik, sorted(niedopasowane)
