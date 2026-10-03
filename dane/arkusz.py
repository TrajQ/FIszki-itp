"""Zapis arkusza OpenDocument (.ods) bez zewnętrznych bibliotek (ETAP 188).

Format, nie usługa — jak dane/dxf.py (D-130). Plik .ods to ZIP: pierwszy
plik `mimetype` (bez kompresji), `META-INF/manifest.xml` i `content.xml`
z tabelą. Liczby zapisujemy jako liczby (office:value-type="float"), więc
LibreOffice Calc i Excel liczą na nich od razu — w odróżnieniu od CSV nie
trzeba wybierać separatora ani kodowania. Nagłówek jest pogrubiony, a
kolumny mają szerokość dobraną do najdłuższego tekstu.

Użycie: arkusz_ods([{"nazwa": "Ranking", "wiersze": [["gmina", "wartość"], ["Kraków", 804237.0]],
                      "przypisy": ["Źródło: GUS BDL"]}])
"""

import io
import math
import zipfile
from xml.sax.saxutils import escape, quoteattr

MIMETYPE = "application/vnd.oasis.opendocument.spreadsheet"
MAKS_SZEROKOSC_ZN = 60

_MANIFEST = f"""<?xml version="1.0" encoding="UTF-8"?>
<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">
 <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="{MIMETYPE}"/>
 <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>
</manifest:manifest>"""

_NAGLOWEK = """<?xml version="1.0" encoding="UTF-8"?>
<office:document-content xmlns:office="urn:oasis:names:tc:opendocument:xmlns:office:1.0"
 xmlns:style="urn:oasis:names:tc:opendocument:xmlns:style:1.0" xmlns:text="urn:oasis:names:tc:opendocument:xmlns:text:1.0"
 xmlns:table="urn:oasis:names:tc:opendocument:xmlns:table:1.0" xmlns:fo="urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0"
 office:version="1.2">
<office:automatic-styles>
 <style:style style:name="pogrubiony" style:family="table-cell"><style:text-properties fo:font-weight="bold"/></style:style>
 <style:style style:name="przypis" style:family="table-cell"><style:text-properties fo:font-style="italic" fo:color="#6e6e73"/></style:style>
{kolumny}
</office:automatic-styles>
<office:body><office:spreadsheet>
"""


class BladArkusza(ValueError):
    pass


def _komorka(wartosc, styl: str | None = None) -> str:
    atrybut_stylu = f' table:style-name="{styl}"' if styl else ""
    if wartosc is None or wartosc == "":
        return f"<table:table-cell{atrybut_stylu}/>"
    if isinstance(wartosc, bool):
        wartosc = "tak" if wartosc else "nie"
    if isinstance(wartosc, (int, float)):
        if not math.isfinite(wartosc):
            return f"<table:table-cell{atrybut_stylu}/>"
        return f'<table:table-cell office:value-type="float" office:value="{wartosc!r}"{atrybut_stylu}><text:p>{wartosc}</text:p></table:table-cell>'
    tekst = str(wartosc)
    akapity = "".join(f"<text:p>{escape(linia)}</text:p>" for linia in tekst.split("\n"))
    return f'<table:table-cell office:value-type="string"{atrybut_stylu}>{akapity}</table:table-cell>'


def _szerokosci(wiersze: list[list]) -> list[float]:
    """Szerokość kolumny w cm z najdłuższego tekstu (ok. 0,22 cm na znak)."""
    liczba = max((len(w) for w in wiersze), default=0)
    wynik = []
    for k in range(liczba):
        znakow = max((len(str(w[k])) for w in wiersze if k < len(w) and w[k] is not None), default=4)
        wynik.append(round(0.6 + 0.22 * min(max(znakow, 4), MAKS_SZEROKOSC_ZN), 2))
    return wynik


def arkusz_ods(arkusze: list[dict]) -> bytes:
    """[{"nazwa", "wiersze": [[komórki]], "naglowek": True, "przypisy": [tekst]}] → bajty pliku .ods.
    Pierwszy wiersz to nagłówek (pogrubiony), chyba że naglowek=False."""
    if not arkusze:
        raise BladArkusza("Arkusz musi mieć co najmniej jedną tabelę.")
    style_kolumn, tabele = [], []
    for nr, a in enumerate(arkusze):
        nazwa = str(a.get("nazwa") or f"Arkusz{nr + 1}")[:31]
        wiersze = [list(w) for w in a.get("wiersze") or []]
        czesci = [f"<table:table table:name={quoteattr(nazwa)}>"]
        for k, cm in enumerate(_szerokosci(wiersze)):
            styl = f"k{nr}_{k}"
            style_kolumn.append(f' <style:style style:name="{styl}" style:family="table-column"><style:table-column-properties style:column-width="{cm}cm"/></style:style>')
            czesci.append(f'<table:table-column table:style-name="{styl}"/>')
        for i, w in enumerate(wiersze):
            styl = "pogrubiony" if i == 0 and a.get("naglowek", True) else None
            czesci.append("<table:table-row>" + "".join(_komorka(x, styl) for x in w) + "</table:table-row>")
        if a.get("przypisy"):
            czesci.append("<table:table-row><table:table-cell/></table:table-row>")  # pusty wiersz przed przypisami
            czesci += ["<table:table-row>" + _komorka(p, "przypis") + "</table:table-row>" for p in a["przypisy"]]
        czesci.append("</table:table>")
        tabele.append("".join(czesci))
    tresc = _NAGLOWEK.format(kolumny="\n".join(style_kolumn)) + "".join(tabele) + "</office:spreadsheet></office:body></office:document-content>"
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr(zipfile.ZipInfo("mimetype"), MIMETYPE, compress_type=zipfile.ZIP_STORED)  # pierwszy i bez kompresji (wymóg ODF)
        z.writestr("META-INF/manifest.xml", _MANIFEST)
        z.writestr("content.xml", tresc)
    return bufor.getvalue()
