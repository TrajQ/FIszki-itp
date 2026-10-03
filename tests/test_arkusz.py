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



# ---------- ETAP 189: ODS w Osiedlu, Terenie i Cenach ----------


def test_ods_osiedla_i_terenu(tmp_path):
    from app import create_app
    from test_osiedle import kolekcja, prostokat

    app = create_app(instance_path=str(tmp_path))
    with app.test_client() as c:
        k = c.post("/osiedle/koncepcje", json={"nazwa": "Wariant A"}).get_json()["id"]
        c.put(f"/osiedle/koncepcje/{k}", json={"geojson": kolekcja(prostokat(0, 0, 100, 100, "obszar"), prostokat(0, 0, 60, 100, "MW"),
                                                                   prostokat(10, 10, 20, 10, "budynek", kondygnacje=4)),
                                                "ustawienia": {"koszty": {"budowa_mw": 6500}, "plan": {"max_kondygnacje": 5}}})
        odp = c.get(f"/osiedle/koncepcje/{k}.ods")
        assert odp.mimetype == "application/vnd.oasis.opendocument.spreadsheet"
        _, doc = otworz(odp.data)
        nazwy = [t.getAttributeNS(NS_TABLE, "name") for t in doc.getElementsByTagNameNS(NS_TABLE, "table")]
        assert nazwy == ["Bilans", "Wskaźniki", "Program", "Koszty", "Budynki"]
        tekst = doc.toxml()
        assert "z budynków" in tekst and "plan: liczba kondygnacji max 5.0" in tekst and "Stawki wpisane" in tekst
        c.post("/teren/projekty", data={"nazwa": "Zieleń", "wzor": "zielen"})
        with app.app_context():
            from teren import baza
            baza.zapisz_punkty(1, [{"uid": "a0000001", "lat": 52.4, "lng": 16.9, "dokladnosc_m": 4, "czas": "2025-05-01T10:00",
                                    "wartosci": {"obiekt": "drzewo", "obwód pnia [cm]": 120.0}, "uwagi": "", "zdjecie": None}])
        _, doc = otworz(c.get("/teren/projekty/1.ods").data)
        assert 'office:value="120.0"' in doc.toxml() and "drzewo" in doc.toxml()
        assert c.get("/teren/projekty/1.csv").get_data(as_text=True).count("drzewo") == 1  # CSV jak dotąd
