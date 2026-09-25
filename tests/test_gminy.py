from mpzp.gminy import GMINA_PILOTAZOWA, znajdz_gmine


def test_znajduje_poznan():
    gmina = znajdz_gmine("306401")
    assert gmina is not None
    assert gmina.nazwa == "Poznań"
    assert gmina.pole_przeznaczenia == "symb_t"
    assert gmina.pole_geometrii == "shape"


def test_nieobslugiwana_gmina_zwraca_none():
    assert znajdz_gmine("999999") is None


def test_gmina_pilotazowa_to_poznan():
    assert GMINA_PILOTAZOWA.teryt_prefiks == "306401"
