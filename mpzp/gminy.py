"""Rejestr gmin obsługiwanych przez moduł mpzp.

Świadomie tylko `dict` w kodzie — jedna gmina pilotażowa (Poznań), bez
mechanizmu wtyczek/dynamicznej rejestracji (zob. spec ETAPu 3, sekcja
"Poza zakresem").
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Gmina:
    nazwa: str
    teryt_prefiks: str
    wfs_url: str
    type_name: str
    pole_przeznaczenia: str
    pole_geometrii: str


GMINY: dict[str, Gmina] = {
    "306401": Gmina(
        nazwa="Poznań",
        teryt_prefiks="306401",
        wfs_url=(
            "https://gis.mpu.pl/server/services/Hosted/"
            "ZbiorDanychPrzestrzennychMPZP/MapServer/WFSServer"
        ),
        type_name="ZbiorDanychPrzestrzennychMPZP:app.WydzieleniePlanistyczne.MPZP",
        pole_przeznaczenia="symb_t",
        pole_geometrii="shape",
    ),
}

GMINA_PILOTAZOWA = GMINY["306401"]


def znajdz_gmine(teryt_prefiks: str) -> Gmina | None:
    return GMINY.get(teryt_prefiks)
