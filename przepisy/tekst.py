"""Tekst aktu prawnego z PDF-a i podział na jednostki (ETAP 61).

Jednostka to artykuł („Art. 15.”) albo paragraf („§ 4.”) — tak cytuje
się przepisy i tak je wyszukujemy. Podział opiera się na tym, że
jednostka zaczyna się na początku wiersza wielką literą: „Art. 15.”
Odesłania w treści piszemy małą literą („art. 15 ust. 2”) i nie mają
kropki po numerze, więc nie tną tekstu.

Ograniczenia (świadome, prosty kod):
- PDF musi mieć warstwę tekstową (skany bez OCR odrzucamy),
- przeniesienie wyrazu („zagospo-\\ndarowania”) sklejamy bez łącznika,
  więc rzadki łącznik na końcu wiersza w wyrazie złożonym („pieszo-”)
  zniknie — dla wyszukiwania to mniejsze zło.
"""

import re
import unicodedata

from pypdf import PdfReader
from pypdf.errors import PdfReadError

MAKS_STRON = 2000

# Nagłówki i stopki stron w tekstach z ISAP i Dziennika Ustaw.
_SMIECI = [
    re.compile(r"^©\s*Kancelaria Sejmu.*$"),
    re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    re.compile(r"^Dziennik Ustaw\s*[–-]\s*\d+\s*[–-]\s*Poz\.\s*\d+$"),
    re.compile(r"^Dziennik Urzędowy Województwa .*[–-]\s*\d+\s*[–-]\s*Poz\.\s*\d+$"),
    re.compile(r"^\d{1,4}$"),  # sam numer strony
]

_POCZATEK_JEDNOSTKI = re.compile(r"^(Art\.\s*\d+[a-z]*|§\s*\d+[a-z]*)\.(?=\s|$)")
_NAGLOWEK = re.compile(r"^(DZIAŁ|Dział|ROZDZIAŁ|Rozdział)\s+[\dIVXLCa-z]+\b")
# Wiersze, przed którymi zostawiamy nowy wiersz: ustępy „2.” i punkty „3)”, „a)”.
_NOWY_WIERSZ = re.compile(r"^(\d+[a-z]*\.|\d+[a-z]*\)|[a-z]\))\s")


class BladPdf(ValueError):
    """PDF nieczytelny, zaszyfrowany albo bez tekstu."""


# ---------- ETAP 253: polskie znaki z PDF-a ----------
# Część PDF-ów (np. z LaTeX-a, starszych edytorów) zapisuje literę i znak
# diakrytyczny osobno: „a˛”, „´s”, „˙z” — pypdf oddaje je jako dwa znaki,
# więc na ekranie są „dziwne literki”, a wyszukiwarka nie znajduje słowa.
# Ligatury („ﬁ”) i niewidoczne znaki (miękki łącznik) psują wyszukiwanie.

_NIEWIDOCZNE = dict.fromkeys(map(ord, "\u00ad\u200b\u200c\u200d\u2060\ufeff"), None)
_LIGATURY = str.maketrans({"ﬀ": "ff", "ﬁ": "fi", "ﬂ": "fl", "ﬃ": "ffi", "ﬄ": "ffl", "ﬅ": "st", "ﬆ": "st"})
# znak diakrytyczny „osobno” → litery, z którymi tworzy polską literę
_DIAKRYTYKI = {
    "\u02db": {"a": "ą", "e": "ę", "A": "Ą", "E": "Ę"},  # ogonek ˛
    "\u00b4": {"c": "ć", "n": "ń", "o": "ó", "s": "ś", "z": "ź", "C": "Ć", "N": "Ń", "O": "Ó", "S": "Ś", "Z": "Ź"},  # ´
    "\u02ca": {"c": "ć", "n": "ń", "o": "ó", "s": "ś", "z": "ź", "C": "Ć", "N": "Ń", "O": "Ó", "S": "Ś", "Z": "Ź"},  # ˊ
    "\u02d9": {"z": "ż", "Z": "Ż"},  # kropka ˙
}
_PARA_ZNAKOW = re.compile("([" + "".join(_DIAKRYTYKI) + "])([A-Za-z])|([A-Za-z])([" + "".join(_DIAKRYTYKI) + "])")


def _sklej_pare(m: re.Match) -> str:
    znak, litera = (m.group(1), m.group(2)) if m.group(1) else (m.group(4), m.group(3))
    return _DIAKRYTYKI[znak].get(litera, m.group(0))


def oczysc_tekst(tekst: str) -> str:
    """Tekst strony PDF po wyciągnięciu: polskie litery w jednym znaku
    (także z rozdzielonych znaków diakrytycznych i znaków łączących),
    ligatury rozpisane, bez niewidocznych znaków."""
    tekst = tekst.translate(_NIEWIDOCZNE).translate(_LIGATURY)
    tekst = _PARA_ZNAKOW.sub(_sklej_pare, tekst)
    return unicodedata.normalize("NFC", tekst)


def nieczytelne_znaki(tekst: str) -> int:
    """Ile znaków PDF nie dał się odczytać (znak zastępczy, prywatne kody fontu)."""
    return sum(1 for z in tekst if z == "\ufffd" or "\ue000" <= z <= "\uf8ff")


def strony_z_pdf(sciezka: str) -> list[str]:
    """Tekst każdej strony (indeks 0 = strona 1)."""
    try:
        czytnik = PdfReader(sciezka)
        if czytnik.is_encrypted:
            raise BladPdf("PDF jest zaszyfrowany — zapisz go bez hasła.")
        if len(czytnik.pages) > MAKS_STRON:
            raise BladPdf(f"PDF ma ponad {MAKS_STRON} stron.")
        strony = [oczysc_tekst(strona.extract_text() or "") for strona in czytnik.pages]
    except BladPdf:
        raise
    except (PdfReadError, ValueError, KeyError, TypeError) as e:
        raise BladPdf(f"Nie udało się odczytać PDF-a ({e.__class__.__name__}).") from None
    if not any(s.strip() for s in strony):
        raise BladPdf("PDF nie ma warstwy tekstowej (to skan?). Pobierz wersję tekstową, np. z ISAP.")
    return strony


def teksty_stron(sciezka: str, od: int, do: int) -> dict[int, str]:
    """Tekst wybranych stron (numeracja od 1) — bez czytania całego aktu."""
    try:
        czytnik = PdfReader(sciezka)
        do = min(do, len(czytnik.pages))
        return {nr: oczysc_tekst(czytnik.pages[nr - 1].extract_text() or "") for nr in range(max(1, od), do + 1)}
    except (PdfReadError, ValueError, KeyError, TypeError, OSError):
        return {}


def wiersze_strony(tekst: str) -> list[str]:
    """Wiersze strony bez pustych i bez nagłówków/stopek."""
    wiersze = [w.strip() for w in tekst.splitlines()]
    return [w for w in wiersze if w and not any(s.match(w) for s in _SMIECI)]


def _dopisz(tekst: str, wiersz: str) -> str:
    """Dokleja wiersz do tekstu jednostki, sklejając przeniesienia wyrazów."""
    if not tekst:
        return wiersz
    if re.search(r"\w-$", tekst) and wiersz[:1].islower():
        return tekst[:-1] + wiersz
    return tekst + ("\n" if _NOWY_WIERSZ.match(wiersz) else " ") + wiersz


def podziel(strony: list[str]) -> list[dict]:
    """Strony → jednostki [{oznaczenie, naglowek, strona_od, strona_do, tekst}].

    Tekst przed pierwszą jednostką (tytuł aktu) to jednostka „Tytuł”.
    naglowek — ostatni napotkany dział/rozdział z tytułem (dla orientacji);
    wiersze nagłówków nie wchodzą do tekstu jednostek.
    """
    jednostki: list[dict] = []
    biezaca = {"oznaczenie": "Tytuł", "naglowek": None, "strona_od": 1, "strona_do": 1, "tekst": ""}
    naglowek = None
    czeka_na_tytul = False  # „Rozdział 2” zwykle ma tytuł w następnym wierszu
    for nr, tekst_strony in enumerate(strony, start=1):
        for wiersz in wiersze_strony(tekst_strony):
            poczatek = _POCZATEK_JEDNOSTKI.match(wiersz)
            if _NAGLOWEK.match(wiersz):
                naglowek, czeka_na_tytul = wiersz, True
            elif czeka_na_tytul and not poczatek:
                naglowek, czeka_na_tytul = f"{naglowek} {wiersz}", False
            elif poczatek:
                czeka_na_tytul = False
                if biezaca["tekst"]:
                    jednostki.append(biezaca)
                oznaczenie = re.sub(r"^(Art\.|§)\s*", lambda m: m.group(1) + " ", poczatek.group(1))
                biezaca = {"oznaczenie": oznaczenie, "naglowek": naglowek, "strona_od": nr, "strona_do": nr, "tekst": wiersz}
            else:
                biezaca["tekst"] = _dopisz(biezaca["tekst"], wiersz)
                biezaca["strona_do"] = nr
    if biezaca["tekst"]:
        jednostki.append(biezaca)
    return jednostki
