"""Notatki do pliku tekstowego (ETAP 209).

Plik Markdown — czyta się go jak zwykły tekst w Notatniku, a w Obsidianie,
Typorze albo na GitHubie wygląda jak dokument: nagłówek aktu, przy każdej
jednostce jej oznaczenie i strona PDF, tekst przepisu jako cytat i
notatka pod spodem. Tekst i notatki przepisujemy bez zmian.
"""

from datetime import date


def _cytat(tekst: str) -> str:
    return "\n".join(f"> {w}" if w.strip() else ">" for w in tekst.strip().splitlines())


def _jednostka(j: dict, notatka: str | None, z_tekstem: bool) -> list[str]:
    naglowek = j["oznaczenie"] + (f" — {j['naglowek']}" if j.get("naglowek") else "")
    wiersze = [f"### {naglowek} (s. {j['strona_od']})", ""]
    if z_tekstem:
        wiersze += [_cytat(j["tekst"]), ""]
    if notatka:
        wiersze += [notatka.strip(), ""]
    return wiersze


def plik_markdown(tytul: str, akty: list[dict], z_tekstem: bool = True) -> str:
    """akty: [{"nazwa", "jednostki": [{oznaczenie, naglowek, strona_od, tekst, notatka}]}]."""
    wiersze = [f"# {tytul}", "", f"Wyeksportowano z aplikacji Warsztat (moduł Przepisy) {date.today().isoformat()}.", ""]
    for akt in akty:
        wiersze += [f"## {akt['nazwa']}", ""]
        for j in akt["jednostki"]:
            wiersze += _jednostka(j, j.get("notatka"), z_tekstem)
    return "\n".join(wiersze).rstrip() + "\n"
