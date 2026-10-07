"""Notatki jako plik Word (.docx) — budowany ręcznie, bez nowej biblioteki
(ETAP 231, decyzja autora; jak GeoPackage w ETAPie 213).

DOCX to ZIP z kilkoma plikami XML (Office Open XML): treść w
word/document.xml, wygląd w word/styles.xml, punktory w numbering.xml,
stopka z numerem strony w footer1.xml. Style mają standardowe nazwy
(Title, Heading1…), więc Word pokazuje nagłówki w okienku nawigacji, a
spis treści da się wstawić jednym kliknięciem.

Wygląd: A4, Calibri 11 pt, granatowe nagłówki z cienką linią, streszczenie
na jasnym tle, ramki z akcentem z lewej, tabela pojęć z naprzemiennym
tłem, „Do zapamiętania” na zielonym tle, stopka „tytuł · strona X z Y”.
"""

import io
import re
import zipfile
from datetime import datetime, timezone
from xml.sax.saxutils import escape

GRANAT = "1F3864"
NIEBIESKI = "2E75B6"
JASNY_NIEBIESKI = "EAF1FB"
LINIA = "B4C6E7"
SZARY = "595959"
TEKST = "262626"
ZIELONY = "548235"
JASNY_ZIELONY = "E2F0D9"
WIERSZ_TABELI = "F3F6FB"

_NIEDOZWOLONE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f￾￿]")


def _x(tekst: str) -> str:
    """Tekst do XML: znaki sterujące usunięte (Word odrzuca taki plik), <&> zamienione."""
    return escape(_NIEDOZWOLONE.sub("", str(tekst)))


def _runy(tekst: str, wlasciwosci: str = "") -> str:
    """„Ważne **słowo** w zdaniu” → przebiegi tekstu, fragmenty w ** pogrubione."""
    wynik = []
    for i, kawalek in enumerate(re.split(r"\*\*(.+?)\*\*", tekst)):
        if not kawalek:
            continue
        # kolejność elementów w rPr jest w schemacie stała: pogrubienie przed kolorem i rozmiarem
        rpr = ("<w:b/>" if i % 2 and "<w:b/>" not in wlasciwosci else "") + wlasciwosci
        wynik.append(f'<w:r>{f"<w:rPr>{rpr}</w:rPr>" if rpr else ""}<w:t xml:space="preserve">{_x(kawalek)}</w:t></w:r>')
    return "".join(wynik)


def _akapit(tekst: str, styl: str | None = None, pPr: str = "", rPr: str = "") -> str:
    styl_xml = f'<w:pStyle w:val="{styl}"/>' if styl else ""
    return f"<w:p><w:pPr>{styl_xml}{pPr}</w:pPr>{_runy(tekst, rPr)}</w:p>"


def _panel(kolor_tla: str, kolor_linii: str) -> str:
    """Tło i gruba linia z lewej — kolejne akapity z tym samym panelem Word łączy w jedną ramkę."""
    return (f'<w:pBdr><w:left w:val="single" w:sz="24" w:space="8" w:color="{kolor_linii}"/></w:pBdr>'
            f'<w:shd w:val="clear" w:color="auto" w:fill="{kolor_tla}"/><w:ind w:left="170" w:right="113"/>')


def _punkt(tekst: str) -> str:
    return _akapit(tekst, "Lista", '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="1"/></w:numPr>')


def _komorka(tresc: str, szerokosc: int, tlo: str | None = None) -> str:
    shd = f'<w:shd w:val="clear" w:color="auto" w:fill="{tlo}"/>' if tlo else ""
    return f'<w:tc><w:tcPr><w:tcW w:w="{szerokosc}" w:type="dxa"/>{shd}</w:tcPr>{tresc}</w:tc>'


def _tabela_pojec(pojecia: list[dict]) -> str:
    szer = (2700, 6326)
    obramowanie = "".join(f'<w:{k} w:val="single" w:sz="4" w:space="0" w:color="{LINIA}"/>' for k in ("top", "bottom", "insideH"))
    wiersze = [
        "<w:tr><w:trPr><w:tblHeader/></w:trPr>"
        + _komorka(_akapit("Pojęcie", "Tabela", rPr='<w:b/><w:color w:val="FFFFFF"/>'), szer[0], GRANAT)
        + _komorka(_akapit("Znaczenie", "Tabela", rPr='<w:b/><w:color w:val="FFFFFF"/>'), szer[1], GRANAT) + "</w:tr>"
    ]
    for i, p in enumerate(pojecia):
        tlo = WIERSZ_TABELI if i % 2 else None
        wiersze.append("<w:tr><w:trPr><w:cantSplit/></w:trPr>"
                       + _komorka(_akapit(p["pojecie"], "Tabela", rPr=f'<w:b/><w:color w:val="{GRANAT}"/>'), szer[0], tlo)
                       + _komorka(_akapit(p["definicja"], "Tabela"), szer[1], tlo) + "</w:tr>")
    return (f'<w:tbl><w:tblPr><w:tblW w:w="{sum(szer)}" w:type="dxa"/><w:tblBorders>{obramowanie}</w:tblBorders>'
            '<w:tblLayout w:type="fixed"/><w:tblCellMar><w:top w:w="80" w:type="dxa"/><w:left w:w="120" w:type="dxa"/>'
            '<w:bottom w:w="80" w:type="dxa"/><w:right w:w="120" w:type="dxa"/></w:tblCellMar></w:tblPr>'
            f'<w:tblGrid><w:gridCol w:w="{szer[0]}"/><w:gridCol w:w="{szer[1]}"/></w:tblGrid>{"".join(wiersze)}</w:tbl>')


def _tresc(n: dict, zrodlo: str) -> str:
    czesci = [_akapit(n["tytul"], "Title")]
    if n["podtytul"]:
        czesci.append(_akapit(n["podtytul"], "Subtitle"))
    if n["streszczenie"]:
        czesci.append(_akapit(n["streszczenie"], "Streszczenie", _panel(JASNY_NIEBIESKI, NIEBIESKI)))
    for s in n["sekcje"]:
        czesci.append(_akapit(s["naglowek"], "Heading1"))
        for b in s["bloki"]:
            if b["typ"] == "akapit":
                czesci.append(_akapit(b["tekst"]))
            elif b["typ"] == "lista":
                czesci += [_punkt(p) for p in b["punkty"]]
            elif b["typ"] == "ramka":
                panel = _panel(JASNY_NIEBIESKI, NIEBIESKI)
                czesci.append(_akapit(b["tytul"], "RamkaTytul", panel))
                czesci.append(_akapit(b["tekst"], "Ramka", panel))
    if n["pojecia"]:
        czesci.append(_akapit("Pojęcia", "Heading1"))
        czesci.append(_tabela_pojec(n["pojecia"]))
        czesci.append(_akapit(""))
    if n["do_zapamietania"]:
        panel = _panel(JASNY_ZIELONY, ZIELONY)
        czesci.append(_akapit("Do zapamiętania", "ZapamietajTytul", panel))  # keepNext — w stylu
        czesci += [_akapit("✓  " + p, "Zapamietaj", panel) for p in n["do_zapamietania"]]
    if n["nieczytelne"]:
        czesci.append(_akapit("Nie udało się odczytać", "Heading2"))
        czesci += [_punkt(p) for p in n["nieczytelne"]]
    czesci.append(_akapit(zrodlo, "Zrodlo"))
    sekcja = ('<w:sectPr><w:footerReference w:type="default" r:id="rIdStopka"/>'
              '<w:pgSz w:w="11906" w:h="16838"/>'
              '<w:pgMar w:top="1247" w:right="1247" w:bottom="1247" w:left="1247" w:header="567" w:footer="567" w:gutter="0"/></w:sectPr>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
            'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
            f'<w:body>{"".join(czesci)}{sekcja}</w:body></w:document>')


def _styl(id_: str, nazwa: str, pPr: str = "", rPr: str = "", nastepny: str = "Normal", poziom: int | None = None) -> str:
    konspekt = f'<w:outlineLvl w:val="{poziom}"/>' if poziom is not None else ""
    return (f'<w:style w:type="paragraph" w:styleId="{id_}"><w:name w:val="{nazwa}"/><w:basedOn w:val="Normal"/>'
            f'<w:next w:val="{nastepny}"/><w:qFormat/><w:pPr>{pPr}{konspekt}</w:pPr><w:rPr>{rPr}</w:rPr></w:style>')


def _style() -> str:
    linia_pod = f'<w:pBdr><w:bottom w:val="single" w:sz="6" w:space="4" w:color="{LINIA}"/></w:pBdr>'
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:eastAsia="Calibri" w:cs="Calibri"/>'
            f'<w:color w:val="{TEKST}"/><w:sz w:val="22"/><w:szCs w:val="22"/><w:lang w:val="pl-PL"/></w:rPr></w:rPrDefault>'
            '<w:pPrDefault><w:pPr><w:spacing w:after="120" w:line="288" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
            '<w:pPr><w:jc w:val="both"/></w:pPr></w:style>'
            + _styl("Title", "Title", f'{linia_pod}<w:spacing w:after="80"/><w:jc w:val="left"/>',
                    f'<w:b/><w:color w:val="{GRANAT}"/><w:sz w:val="52"/><w:szCs w:val="52"/>', "Subtitle")
            + _styl("Subtitle", "Subtitle", '<w:spacing w:after="240"/><w:jc w:val="left"/>',
                    f'<w:color w:val="{SZARY}"/><w:sz w:val="26"/><w:szCs w:val="26"/>')
            + _styl("Heading1", "heading 1", f'<w:keepNext/><w:keepLines/>{linia_pod}<w:spacing w:before="360" w:after="120"/><w:jc w:val="left"/>',
                    f'<w:b/><w:color w:val="{GRANAT}"/><w:sz w:val="30"/><w:szCs w:val="30"/>', poziom=0)
            + _styl("Heading2", "heading 2", '<w:keepNext/><w:spacing w:before="240" w:after="80"/><w:jc w:val="left"/>',
                    f'<w:b/><w:color w:val="{NIEBIESKI}"/><w:sz w:val="24"/><w:szCs w:val="24"/>', poziom=1)
            + _styl("Streszczenie", "Streszczenie", '<w:spacing w:before="120" w:after="240"/>', f'<w:i/><w:color w:val="{SZARY}"/>')
            + _styl("Lista", "Lista punktowana", '<w:spacing w:after="60"/><w:jc w:val="left"/>')
            + _styl("RamkaTytul", "Ramka — tytuł", '<w:keepNext/><w:spacing w:before="160" w:after="0"/><w:jc w:val="left"/>',
                    f'<w:b/><w:color w:val="{NIEBIESKI}"/><w:sz w:val="20"/><w:szCs w:val="20"/>')
            + _styl("Ramka", "Ramka", '<w:spacing w:after="200"/>')
            + _styl("ZapamietajTytul", "Do zapamiętania — tytuł", '<w:keepNext/><w:spacing w:before="360" w:after="0"/><w:jc w:val="left"/>',
                    f'<w:b/><w:color w:val="{ZIELONY}"/><w:sz w:val="26"/><w:szCs w:val="26"/>')
            + _styl("Zapamietaj", "Do zapamiętania", '<w:spacing w:after="40"/><w:jc w:val="left"/>')
            + _styl("Tabela", "Tekst w tabeli", '<w:spacing w:after="0" w:line="264" w:lineRule="auto"/><w:jc w:val="left"/>',
                    '<w:sz w:val="20"/><w:szCs w:val="20"/>')
            + _styl("Zrodlo", "Źródło", '<w:spacing w:before="480"/><w:jc w:val="left"/>',
                    '<w:color w:val="8C8C8C"/><w:sz w:val="16"/><w:szCs w:val="16"/>')
            + _styl("Stopka", "Stopka", '<w:spacing w:after="0"/><w:jc w:val="center"/>',
                    '<w:color w:val="8C8C8C"/><w:sz w:val="16"/><w:szCs w:val="16"/>')
            + "</w:styles>")


NUMERACJA = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
             '<w:abstractNum w:abstractNumId="0"><w:multiLevelType w:val="singleLevel"/>'
             '<w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/>'
             f'<w:pPr><w:ind w:left="397" w:hanging="284"/></w:pPr><w:rPr><w:b/><w:color w:val="{NIEBIESKI}"/></w:rPr></w:lvl>'
             '</w:abstractNum><w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num></w:numbering>')


def _stopka(tytul: str) -> str:
    pole = lambda kod: (f'<w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> {kod} </w:instrText></w:r>'
                        '<w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>1</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r>')
    return ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:pStyle w:val="Stopka"/></w:pPr>'
            f'<w:r><w:t xml:space="preserve">{_x(tytul[:80])} · strona </w:t></w:r>{pole("PAGE")}'
            f'<w:r><w:t xml:space="preserve"> z </w:t></w:r>{pole("NUMPAGES")}</w:p></w:ftr>')


TYPY = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>'
        '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>'
        '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>'
        '<Override PartName="/word/settings.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml"/>'
        '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>'
        '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.core-properties+xml"/>'
        '<Override PartName="/docProps/app.xml" ContentType="application/vnd.openxmlformats-officedocument.extended-properties+xml"/>'
        '</Types>')
RELACJE = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
           '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
           '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>'
           '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/core-properties" Target="docProps/core.xml"/>'
           '<Relationship Id="rId3" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/extended-properties" Target="docProps/app.xml"/>'
           '</Relationships>')
RELACJE_DOKUMENTU = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     '<Relationship Id="rIdStyle" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>'
                     '<Relationship Id="rIdNum" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>'
                     '<Relationship Id="rIdUst" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/settings" Target="settings.xml"/>'
                     '<Relationship Id="rIdStopka" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>'
                     '</Relationships>')
USTAWIENIA = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
              '<w:settings xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
              '<w:defaultTabStop w:val="708"/><w:characterSpacingControl w:val="doNotCompress"/>'
              '</w:settings>')


def notatki_docx(n: dict, zrodlo: str, teraz: datetime | None = None) -> bytes:
    """Notatka (praca/notatki.oczysc) → bajty pliku .docx."""
    teraz = (teraz or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    rdzen = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
             'xmlns:dc="http://purl.org/dc/elements/1.1/" xmlns:dcterms="http://purl.org/dc/terms/" '
             'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">'
             f'<dc:title>{_x(n["tytul"])}</dc:title><dc:creator>Warsztat</dc:creator><dc:language>pl-PL</dc:language>'
             f'<dcterms:created xsi:type="dcterms:W3CDTF">{teraz}</dcterms:created>'
             f'<dcterms:modified xsi:type="dcterms:W3CDTF">{teraz}</dcterms:modified></cp:coreProperties>')
    aplikacja = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Properties xmlns="http://schemas.openxmlformats.org/officeDocument/2006/extended-properties"><Application>Warsztat</Application></Properties>')
    bufor = io.BytesIO()
    with zipfile.ZipFile(bufor, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", TYPY)  # pierwszy plik w archiwum — tak jak w plikach z Worda
        z.writestr("_rels/.rels", RELACJE)
        z.writestr("word/document.xml", _tresc(n, zrodlo))
        z.writestr("word/styles.xml", _style())
        z.writestr("word/numbering.xml", NUMERACJA)
        z.writestr("word/settings.xml", USTAWIENIA)
        z.writestr("word/footer1.xml", _stopka(n["tytul"]))
        z.writestr("word/_rels/document.xml.rels", RELACJE_DOKUMENTU)
        z.writestr("docProps/core.xml", rdzen)
        z.writestr("docProps/app.xml", aplikacja)
    return bufor.getvalue()
