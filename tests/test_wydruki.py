"""Wspólna stopka stron do druku (ETAP 142)."""

import pathlib
import re

from app import create_app

KATALOG = pathlib.Path(__file__).resolve().parent.parent


def test_kazda_strona_do_druku_ma_stopke():
    """Strona z przyciskiem „Drukuj” musi mieć stopkę z _wydruk.html."""
    strony = [p for p in KATALOG.glob("*/templates/**/*.html") if "window.print()" in p.read_text(encoding="utf-8")]
    assert len(strony) >= 10
    bez_stopki = [str(p.relative_to(KATALOG)) for p in strony if "stopka_wydruku(" not in p.read_text(encoding="utf-8")]
    assert bez_stopki == []


def test_stopka_na_wydruku(tmp_path):
    app = create_app(instance_path=str(tmp_path))
    app.config.update(TESTING=True)
    with app.test_client() as c:
        c.post("/teren/projekty", data={"nazwa": "Zieleń"})
        html = c.get("/teren/projekty/1/raport").get_data(as_text=True)
    stopka = re.search(r'<footer class="stopka-wydruku">(.*?)</footer>', html, re.S).group(1)
    assert "Warsztat · moduł Teren" in stopka and "Źródło: pomiary w terenie" in stopka
    assert re.search(r"Wygenerowano \d\d\.\d\d\.\d{4}, \d\d:\d\d", stopka)
