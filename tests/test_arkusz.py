"""Zapis arkusza OpenDocument bez zależności (ETAP 188)."""

import io
import zipfile
from xml.dom import minidom

import pytest

from dane.arkusz import MIMETYPE, BladArkusza, arkusz_ods

NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"
NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"


def otworz(dane: bytes):
    z = zipfile.ZipFile(io.BytesIO(dane))
    return z, minidom.parseString(z.read("content.xml"))


def test_struktura_ods():
    z, doc = otworz(arkusz_ods([{"nazwa": "Ranking", "wiersze": [["gmina", "wartość"], ["Kraków & <Nowa Huta>", 804237.5], ["Wieliczka", None]],
                                  "przypisy": ["Źródło: GUS"]}, {"wiersze": [["a"], [True]]}]))
    info = z.infolist()[0]
    assert info.filename == "mimetype" and info.compress_type == zipfile.ZIP_STORED and z.read("mimetype").decode() == MIMETYPE
    assert "META-INF/manifest.xml" in z.namelist()
    minidom.parseString(z.read("META-INF/manifest.xml"))
    tabele = doc.getElementsByTagNameNS(NS_TABLE, "table")
    assert [t.getAttributeNS(NS_TABLE, "name") for t in tabele] == ["Ranking", "Arkusz2"]
    komorki = tabele[0].getElementsByTagNameNS(NS_TABLE, "table-cell")
    liczba = [k for k in komorki if k.getAttributeNS(NS_OFFICE, "value-type") == "float"]
    assert len(liczba) == 1 and liczba[0].getAttributeNS(NS_OFFICE, "value") == "804237.5"
    tekst = "".join(n.toxml() for n in komorki[2].childNodes)
    assert "Kraków &amp; &lt;Nowa Huta&gt;" in tekst  # escapowanie
    assert komorki[0].getAttributeNS(NS_TABLE, "style-name") == "pogrubiony"
    assert "Źródło: GUS" in doc.toxml() and "tak" in tabele[1].toxml()
    with pytest.raises(BladArkusza):
        arkusz_ods([])

