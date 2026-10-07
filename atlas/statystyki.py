"""Statystyki opisowe i podział na klasy — liczone tutaj, nie przez model.

Zasada z CLAUDE.md: liczby przychodzą z danych. Gemini dostaje gotowe
fakty z tego modułu i ma je tylko opisać słowami.
"""

import statistics

LICZBA_KLAS = 5
MIN_KLAS, MAKS_KLAS = 3, 7
METODY_KLASYFIKACJI = {
    "kwantyle": "kwantyle (równe liczebności)",
    "rowne": "równe przedziały",
    "jenks": "naturalne przerwy (Jenks)",
    "odchylenie": "odchylenie standardowe",
}


def statystyki(wartosci: list[dict]) -> dict:
    """wartosci: [{"nazwa": str, "wartosc": float, ...}] → słownik statystyk."""
    if not wartosci:
        return {"liczba_gmin": 0}

    posortowane = sorted(wartosci, key=lambda w: w["wartosc"])
    liczby = [w["wartosc"] for w in posortowane]
    return {
        "liczba_gmin": len(liczby),
        "min": _para(posortowane[0]),
        "max": _para(posortowane[-1]),
        "srednia": statistics.fmean(liczby),
        "mediana": statistics.median(liczby),
        "najnizsze": [_para(w) for w in posortowane[:3]],
        "najwyzsze": [_para(w) for w in reversed(posortowane[-3:])],
        "zroznicowanie": zroznicowanie(liczby),
        "histogram": histogram(liczby),
    }


# ---------- Wskaźniki względne (ETAP 29) ----------

DOZWOLONE_MNOZNIKI = (1, 100, 1000, 10000)


def podziel(licznik: list[dict], mianownik: list[dict], mnoznik: int) -> list[dict]:
    """Wskaźnik względny: licznik / mianownik × mnożnik dla gmin z obiema
    wartościami (np. mieszkania oddane na 1000 mieszkańców). Gminy z
    mianownikiem 0 pomijamy — iloraz byłby nieokreślony."""
    mian = {g["teryt"]: g["wartosc"] for g in mianownik}
    return [
        {**g, "wartosc": g["wartosc"] / mian[g["teryt"]] * mnoznik}
        for g in licznik
        if mian.get(g["teryt"]) not in (None, 0)
    ]


# ---------- Iloraz lokalizacji (ETAP 153) ----------

# Stałe klasy LQ — ta sama skala na każdej mapie; 0,8–1,2 to „jak w województwie”
PROGI_LQ = [0.5, 0.8, 1.2, 2.0]
OPISY_LQ = ["wyraźnie poniżej (< 0,5)", "poniżej (0,5–0,8)", "jak w województwie (0,8–1,2)", "powyżej (1,2–2)", "wyraźnie powyżej (> 2)"]


def iloraz_lokalizacji(licznik: list[dict], mianownik: list[dict]) -> dict | None:
    """LQ_i = (x_i / X_i) / (Σx / ΣX) — o ile udział zjawiska w gminie jest
    większy niż w całym województwie (np. pracujący w przemyśle wśród
    pracujących ogółem). Sumy z gmin, które mają obie wartości i X_i > 0.
    None, gdy nie ma czego liczyć."""
    mian = {g["teryt"]: g["wartosc"] for g in mianownik}
    pary = [(g["teryt"], g["wartosc"], mian[g["teryt"]]) for g in licznik if mian.get(g["teryt"]) not in (None, 0)]
    suma_x, suma_m = sum(x for _, x, _ in pary), sum(m for _, _, m in pary)
    if not pary or not suma_x or not suma_m:
        return None
    udzial = suma_x / suma_m
    gminy = []
    for teryt, x, m in pary:
        lq = (x / m) / udzial
        gminy.append({"teryt": teryt, "lq": lq, "klasa": sum(1 for p in PROGI_LQ if lq >= p)})
    return {"udzial_wojewodztwa": udzial, "gminy": gminy, "progi": PROGI_LQ, "opisy": OPISY_LQ}


def podziel_szeregi(licznik: list[dict], mianownik: list[dict], mnoznik: int) -> list[dict]:
    """To samo dla szeregu czasowego jednej gminy (łączenie po roku)."""
    mian = {p["rok"]: p["wartosc"] for p in mianownik}
    return [
        {"rok": p["rok"], "wartosc": p["wartosc"] / mian[p["rok"]] * mnoznik}
        for p in licznik
        if mian.get(p["rok"]) not in (None, 0)
    ]


# ---------- Miary zróżnicowania (ETAP 28) ----------

# Ocena współczynnika zmienności — skala stosowana w polskich
# podręcznikach statystyki społeczno-ekonomicznej.
PROGI_CV = [(25, "słabe"), (45, "przeciętne"), (100, "silne")]
LICZBA_PRZEDZIALOW = 10


def zroznicowanie(liczby: list[float]) -> dict:
    """Miary zróżnicowania wartości w gminach.

    Gminy traktujemy jako całą populację województwa (nie próbę), dlatego
    odchylenie standardowe jest populacyjne (pstdev).
    """
    wynik = {"odchylenie_std": statistics.pstdev(liczby) if len(liczby) > 1 else 0.0}
    if len(liczby) >= 4:
        q1, _, q3 = statistics.quantiles(liczby, n=4, method="inclusive")
        wynik.update(q1=q1, q3=q3, rozstep_kwartylowy=q3 - q1)
    srednia = statistics.fmean(liczby)
    if srednia != 0:
        cv = 100 * wynik["odchylenie_std"] / abs(srednia)
        wynik["wspolczynnik_zmiennosci"] = cv
        wynik["ocena_zmiennosci"] = next((o for prog, o in PROGI_CV if cv < prog), "bardzo silne")
    if min(liczby) > 0:
        wynik["max_do_min"] = max(liczby) / min(liczby)
    if min(liczby) >= 0 and sum(liczby) > 0:
        wynik["gini"] = gini(liczby)
    return wynik


def gini(liczby: list[float]) -> float:
    """Współczynnik Giniego (0 = równy rozkład, 1 = wszystko w jednej gminie).

    Wzór na posortowanych wartościach: G = Σ (2i − n − 1)·x_i / (n · Σx).
    """
    x = sorted(liczby)
    n = len(x)
    return sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(x)) / (n * sum(x))


def histogram(liczby: list[float], przedzialy: int = LICZBA_PRZEDZIALOW) -> list[dict]:
    """Liczba gmin w przedziałach równej szerokości (ostatni domknięty)."""
    lo, hi = min(liczby), max(liczby)
    if lo == hi:
        return [{"od": lo, "do": hi, "liczba": len(liczby)}]
    szer = (hi - lo) / przedzialy
    liczniki = [0] * przedzialy
    for v in liczby:
        liczniki[min(int((v - lo) / szer), przedzialy - 1)] += 1
    return [{"od": lo + i * szer, "do": lo + (i + 1) * szer, "liczba": n} for i, n in enumerate(liczniki)]


def progi_klas(liczby: list[float], liczba_klas: int = LICZBA_KLAS) -> list[float]:
    """Progi klas kwantylowych (każda klasa ma podobną liczbę gmin).

    Zwraca rosnące, unikalne górne granice klas bez ostatniej (maksimum).
    Przy małej liczbie różnych wartości klas może być mniej.
    """
    if len(set(liczby)) < 2:
        return []
    kwantyle = statistics.quantiles(liczby, n=liczba_klas, method="inclusive")
    progi = []
    for prog in kwantyle:
        if prog not in progi and min(liczby) <= prog < max(liczby):
            progi.append(prog)
    return progi


# ---------- metody klasyfikacji (ETAP 40) ----------
# Wszystkie zwracają rosnące górne granice klas bez maksimum — tak jak
# progi_klas — więc mapa i legenda działają dla każdej metody tak samo.


def _tylko_wewnatrz(progi: list[float], liczby: list[float]) -> list[float]:
    wynik = []
    for prog in sorted(progi):
        if min(liczby) <= prog < max(liczby) and prog not in wynik:
            wynik.append(prog)
    return wynik


def progi_rowne(liczby: list[float], liczba_klas: int) -> list[float]:
    """Równe przedziały: rozstęp podzielony na liczba_klas części."""
    if len(set(liczby)) < 2:
        return []
    najmniejsza, najwieksza = min(liczby), max(liczby)
    krok = (najwieksza - najmniejsza) / liczba_klas
    return _tylko_wewnatrz([najmniejsza + i * krok for i in range(1, liczba_klas)], liczby)


def progi_odchylenia(liczby: list[float], liczba_klas: int) -> list[float]:
    """Klasy szerokości jednego odchylenia standardowego wokół średniej.

    Dla nieparzystej liczby klas środkowa klasa to średnia ± 0,5σ, dla
    parzystej średnia jest granicą. Granice poza zakresem danych odpadają.
    """
    if len(set(liczby)) < 2:
        return []
    srednia = statistics.fmean(liczby)
    sigma = statistics.pstdev(liczby)
    return _tylko_wewnatrz([srednia + sigma * (i - liczba_klas / 2) for i in range(1, liczba_klas)], liczby)


def progi_jenks(liczby: list[float], liczba_klas: int) -> list[float]:
    """Naturalne przerwy Jenksa (optymalne, programowanie dynamiczne Fishera).

    Szukamy podziału posortowanych wartości na klasy o najmniejszej sumie
    kwadratów odchyleń od średnich klas (SDCM). Złożoność O(k·n²) — dla
    gmin jednego województwa (do ~320) to ułamek sekundy.
    """
    wartosci = sorted(liczby)
    n = len(wartosci)
    k = min(liczba_klas, len(set(wartosci)))
    if k < 2:
        return []
    # sumy prefiksowe → SDCM dowolnego przedziału w O(1)
    s1 = [0.0]
    s2 = [0.0]
    for v in wartosci:
        s1.append(s1[-1] + v)
        s2.append(s2[-1] + v * v)

    def sdcm(i: int, j: int) -> float:  # wartości[i:j]
        suma = s1[j] - s1[i]
        return (s2[j] - s2[i]) - suma * suma / (j - i)

    nieskonczonosc = float("inf")
    # koszt[c][j] — najlepszy podział pierwszych j wartości na c klas
    koszt = [[nieskonczonosc] * (n + 1) for _ in range(k + 1)]
    podzial = [[0] * (n + 1) for _ in range(k + 1)]
    koszt[0][0] = 0.0
    for c in range(1, k + 1):
        for j in range(c, n + 1):
            for i in range(c - 1, j):
                kandydat = koszt[c - 1][i] + sdcm(i, j)
                if kandydat < koszt[c][j]:
                    koszt[c][j], podzial[c][j] = kandydat, i
    granice = []
    j = n
    for c in range(k, 1, -1):
        j = podzial[c][j]
        granice.append(wartosci[j - 1])  # górna granica klasy c-1
    return _tylko_wewnatrz(granice, liczby)


def klasyfikuj(liczby: list[float], metoda: str = "kwantyle", liczba_klas: int = LICZBA_KLAS) -> dict:
    """Progi wybraną metodą + liczebności klas + GVF (jakość podziału)."""
    if metoda not in METODY_KLASYFIKACJI:
        raise ValueError("Nieznana metoda klasyfikacji.")
    if not MIN_KLAS <= liczba_klas <= MAKS_KLAS:
        raise ValueError(f"Liczba klas od {MIN_KLAS} do {MAKS_KLAS}.")
    funkcja = {
        "kwantyle": progi_klas,
        "rowne": progi_rowne,
        "jenks": progi_jenks,
        "odchylenie": progi_odchylenia,
    }[metoda]
    progi = funkcja(liczby, liczba_klas) if liczby else []
    return {
        "metoda": metoda,
        "nazwa_metody": METODY_KLASYFIKACJI[metoda],
        "klasy": liczba_klas,
        "progi": progi,
        "liczebnosci": liczebnosci_klas(liczby, progi),
        "gvf": gvf(liczby, progi),
    }


def liczebnosci_klas(liczby: list[float], progi: list[float]) -> list[int]:
    """Ile wartości w każdej klasie (klasa i: (progi[i-1], progi[i]])."""
    wynik = [0] * (len(progi) + 1)
    for v in liczby:
        i = 0
        while i < len(progi) and v > progi[i]:
            i += 1
        wynik[i] += 1
    return wynik


def gvf(liczby: list[float], progi: list[float]) -> float | None:
    """Goodness of Variance Fit: 1 − SDCM/SDAM, od 0 do 1.

    Mówi, jaką część zmienności wartości „wyjaśnia” podział na klasy:
    blisko 1 — klasy dobrze grupują podobne gminy.
    """
    if len(liczby) < 2:
        return None
    srednia = statistics.fmean(liczby)
    sdam = sum((v - srednia) ** 2 for v in liczby)
    if sdam == 0:
        return None
    klasy: list[list[float]] = [[] for _ in range(len(progi) + 1)]
    for v in liczby:
        i = 0
        while i < len(progi) and v > progi[i]:
            i += 1
        klasy[i].append(v)
    sdcm = sum(sum((v - statistics.fmean(k)) ** 2 for v in k) for k in klasy if k)
    return 1 - sdcm / sdam


def format_liczby(liczba: float) -> str:
    """Polski zapis liczby: spacja tysięcy, przecinek dziesiętny, max 2 miejsca."""
    if float(liczba).is_integer():
        tekst = f"{int(liczba):,}"
    else:
        tekst = f"{liczba:,.2f}".rstrip("0").rstrip(".")
    return tekst.replace(",", " ").replace(".", ",")


# ETAP 216: odmiana nazwy jednostek w faktach: (mianownik l.mn., dopełniacz l.mn.)
JEDNOSTKI_OPISU = {"gminy": ("gminy", "gmin"), "powiaty": ("powiaty", "powiatów")}


def fakty_do_opisu(zmienna: dict, rok: int, wojewodztwo: str, stat: dict, poziom: str = "gminy") -> list[str]:
    """Lista zdań-faktów z liczbami w polskim zapisie — wejście dla Gemini."""
    jednostka = f" {zmienna['jednostka']}" if zmienna.get("jednostka") else ""
    mn, dop = JEDNOSTKI_OPISU[poziom]

    def z_jednostka(liczba):
        return f"{format_liczby(liczba)}{jednostka}"

    fakty = [
        f"Wskaźnik: {zmienna['nazwa']}",
        f"Jednostka: {zmienna.get('jednostka') or 'brak'}",
        f"Rok: {rok}",
        f"Obszar: {mn} województwa {wojewodztwo}",
        f"Liczba {dop} z danymi: {stat['liczba_gmin']}",
        f"Wartość najwyższa: {stat['max']['nazwa']} — {z_jednostka(stat['max']['wartosc'])}",
        f"Wartość najniższa: {stat['min']['nazwa']} — {z_jednostka(stat['min']['wartosc'])}",
        f"Mediana: {z_jednostka(stat['mediana'])}",
        f"Średnia arytmetyczna (nieważona) {dop}: {z_jednostka(stat['srednia'])}",
        *_fakty_zroznicowania(stat.get("zroznicowanie", {})),
        f"3 {mn} o najwyższej wartości: "
        + "; ".join(f"{w['nazwa']} ({z_jednostka(w['wartosc'])})" for w in stat["najwyzsze"]),
        f"3 {mn} o najniższej wartości: "
        + "; ".join(f"{w['nazwa']} ({z_jednostka(w['wartosc'])})" for w in stat["najnizsze"]),
    ]
    return fakty


# Klasy zmiany procentowej (kartogram rozbieżny): stałe i symetryczne
# wokół zera, żeby „spadek” i „wzrost” były porównywalne między wskaźnikami.
PROGI_ZMIANY_PROC = [-10.0, -2.0, 2.0, 10.0]


def porownaj(gminy: list[dict], gminy_bazowe: list[dict]) -> list[dict]:
    """Zmiana między rokiem bazowym a badanym dla gmin obecnych w obu latach.

    zmiana_proc jest None, gdy wartość bazowa to 0 (dzielenie przez zero).
    Wynik posortowany malejąco po zmianie procentowej (None na końcu).
    """
    bazowe = {g["teryt"]: g["wartosc"] for g in gminy_bazowe}
    wynik = []
    for g in gminy:
        if g["teryt"] not in bazowe:
            continue
        baza = bazowe[g["teryt"]]
        wynik.append(
            {
                **g,
                "wartosc_bazowa": baza,
                "zmiana": g["wartosc"] - baza,
                "zmiana_proc": None if baza == 0 else (g["wartosc"] - baza) / abs(baza) * 100,
            }
        )
    wynik.sort(key=lambda g: (g["zmiana_proc"] is None, -(g["zmiana_proc"] or 0)))
    return wynik


def statystyki_zmiany(porownanie: list[dict]) -> dict:
    procenty = [g["zmiana_proc"] for g in porownanie if g["zmiana_proc"] is not None]
    if not procenty:
        return {"liczba_gmin": len(porownanie)}
    z_procentem = [g for g in porownanie if g["zmiana_proc"] is not None]
    return {
        "liczba_gmin": len(porownanie),
        "wzrosty": sum(1 for g in porownanie if g["zmiana"] > 0),
        "spadki": sum(1 for g in porownanie if g["zmiana"] < 0),
        "bez_zmian": sum(1 for g in porownanie if g["zmiana"] == 0),
        "mediana_zmiany_proc": statistics.median(procenty),
        # Tylko prawdziwy wzrost/spadek: gdy wszystkie gminy urosły,
        # „największego spadku” nie ma (None), a nie „najmniejszy wzrost”.
        "najwiekszy_wzrost": _para_zmiany(z_procentem[0]) if z_procentem[0]["zmiana_proc"] > 0 else None,
        "najwiekszy_spadek": _para_zmiany(z_procentem[-1]) if z_procentem[-1]["zmiana_proc"] < 0 else None,
    }


def fakty_zmiany(rok_bazowy: int, rok: int, stat: dict) -> list[str]:
    if "mediana_zmiany_proc" not in stat:
        return []
    wz, sp = stat["najwiekszy_wzrost"], stat["najwiekszy_spadek"]
    fakty = [
        f"Porównanie z rokiem: {rok_bazowy}",
        f"Liczba gmin porównanych: {stat['liczba_gmin']}",
        f"Gminy ze wzrostem wartości od {rok_bazowy} do {rok}: {stat['wzrosty']}",
        f"Gminy ze spadkiem wartości od {rok_bazowy} do {rok}: {stat['spadki']}",
        f"Mediana zmiany procentowej: {format_liczby(stat['mediana_zmiany_proc'])}%",
    ]
    if wz:
        fakty.append(f"Największy wzrost procentowy: {wz['nazwa']} ({format_liczby(wz['zmiana_proc'])}%)")
    if sp:
        fakty.append(f"Największy spadek procentowy: {sp['nazwa']} ({format_liczby(sp['zmiana_proc'])}%)")
    return fakty


def _para_zmiany(g: dict) -> dict:
    return {"nazwa": g["nazwa"], "zmiana_proc": g["zmiana_proc"], "zmiana": g["zmiana"]}


def zmiana_w_szeregu(szereg: list[dict]) -> dict | None:
    """Zmiana od pierwszego do ostatniego roku szeregu (bezwzględna i %)."""
    if len(szereg) < 2:
        return None
    pierwszy, ostatni = szereg[0], szereg[-1]
    return {
        "od": pierwszy["rok"],
        "do": ostatni["rok"],
        "zmiana": ostatni["wartosc"] - pierwszy["wartosc"],
        "zmiana_proc": None
        if pierwszy["wartosc"] == 0
        else (ostatni["wartosc"] - pierwszy["wartosc"]) / abs(pierwszy["wartosc"]) * 100,
    }


# ---------- Korelacja dwóch wskaźników (ETAP 25) ----------

# Progi siły związku dla |r| — typowa skala z podręczników statystyki.
PROGI_SILY = [(0.1, "brak związku"), (0.3, "słaba"), (0.5, "umiarkowana"), (0.7, "silna")]


def _rangi(liczby: list[float]) -> list[float]:
    """Rangi z uśrednianiem remisów (potrzebne do rho Spearmana)."""
    kolejnosc = sorted(range(len(liczby)), key=lambda i: liczby[i])
    rangi = [0.0] * len(liczby)
    i = 0
    while i < len(kolejnosc):
        j = i
        while j + 1 < len(kolejnosc) and liczby[kolejnosc[j + 1]] == liczby[kolejnosc[i]]:
            j += 1
        srednia = (i + j) / 2 + 1
        for k in range(i, j + 1):
            rangi[kolejnosc[k]] = srednia
        i = j + 1
    return rangi


def _pearson(x: list[float], y: list[float]) -> float | None:
    if len(set(x)) < 2 or len(set(y)) < 2:
        return None  # stała wartość — korelacja nieokreślona
    return statistics.correlation(x, y)


def opis_sily(r: float | None) -> str:
    if r is None:
        return "nie da się policzyć (jeden ze wskaźników jest stały)"
    for prog, opis in PROGI_SILY:
        if abs(r) < prog:
            return opis if opis == "brak związku" else f"{opis}, {'dodatnia' if r > 0 else 'ujemna'}"
    return f"bardzo silna, {'dodatnia' if r > 0 else 'ujemna'}"


# ---------- mapa dwuzmiennowa (ETAP 236) ----------

# Paleta 3 × 3 J. Stevensa („pink–blue”): wiersz = klasa Y (0 nisko), kolumna = klasa X.
# Lewy dolny róg — oba niskie (szary), prawy górny — oba wysokie (ciemny).
KOLORY_DWUZMIENNOWE = [
    ["#e8e8e8", "#e4acac", "#c85a5a"],
    ["#b0d5df", "#ad9ea5", "#985356"],
    ["#64acbe", "#627f8c", "#574249"],
]
MIN_GMIN_DWUZMIENNOWEJ = 6


def _klasa_tercylowa(v: float, progi: list[float]) -> int:
    return 0 if v <= progi[0] else 1 if v <= progi[1] else 2


def dwuzmiennowa(punkty: list[dict]) -> dict:
    """Punkty {teryt, x, y} (z `korelacja`) → klasy 3 × 3 z tercyli każdego
    wskaźnika osobno, kolor gminy i liczebność każdej z 9 klas."""
    if len(punkty) < MIN_GMIN_DWUZMIENNOWEJ:
        raise ValueError(f"Mapa dwuzmiennowa potrzebuje co najmniej {MIN_GMIN_DWUZMIENNOWEJ} gmin z oboma wskaźnikami.")
    progi_x = statistics.quantiles([p["x"] for p in punkty], n=3, method="inclusive")
    progi_y = statistics.quantiles([p["y"] for p in punkty], n=3, method="inclusive")
    klasy, liczebnosc = {}, [[0] * 3 for _ in range(3)]
    for p in punkty:
        ix, iy = _klasa_tercylowa(p["x"], progi_x), _klasa_tercylowa(p["y"], progi_y)
        klasy[p["teryt"]] = [ix, iy]
        liczebnosc[iy][ix] += 1
    return {
        "progi_x": progi_x,
        "progi_y": progi_y,
        "klasy": klasy,
        "kolory": {t: KOLORY_DWUZMIENNOWE[iy][ix] for t, (ix, iy) in klasy.items()},
        "liczebnosc": liczebnosc,
        "paleta": KOLORY_DWUZMIENNOWE,
    }


def korelacja(gminy_x: list[dict], gminy_y: list[dict]) -> dict:
    """Korelacja dwóch wskaźników na gminach obecnych w obu zestawach."""
    y_po_teryt = {g["teryt"]: g["wartosc"] for g in gminy_y}
    punkty = [
        {"teryt": g["teryt"], "nazwa": g["nazwa"], "x": g["wartosc"], "y": y_po_teryt[g["teryt"]]}
        for g in gminy_x
        if g["teryt"] in y_po_teryt
    ]
    wynik = {"n": len(punkty), "punkty": punkty}
    if len(punkty) < 3:
        wynik.update(pearson=None, spearman=None, r2=None, regresja=None, opis="za mało gmin z obiema wartościami (min. 3)")
        return wynik

    x = [p["x"] for p in punkty]
    y = [p["y"] for p in punkty]
    r = _pearson(x, y)
    rho = _pearson(_rangi(x), _rangi(y))
    regresja = None
    if len(set(x)) >= 2:
        nachylenie, wyraz_wolny = statistics.linear_regression(x, y)
        regresja = {"nachylenie": nachylenie, "wyraz_wolny": wyraz_wolny}
    wynik.update(
        pearson=r,
        spearman=rho,
        r2=None if r is None else r * r,
        regresja=regresja,
        opis=opis_sily(r),
    )
    return wynik


def _fakty_zroznicowania(z: dict) -> list[str]:
    fakty = []
    if "wspolczynnik_zmiennosci" in z:
        fakty.append(
            f"Współczynnik zmienności: {format_liczby(z['wspolczynnik_zmiennosci'])}% "
            f"(zróżnicowanie {z['ocena_zmiennosci']})"
        )
    if "gini" in z:
        fakty.append(f"Współczynnik Giniego: {format_liczby(z['gini'])}")
    return fakty


def _para(w: dict) -> dict:
    return {"nazwa": w["nazwa"], "wartosc": w["wartosc"]}
