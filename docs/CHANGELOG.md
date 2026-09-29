# Changelog

## ETAP 1 — 2026-09-24
- Dodano szkielet aplikacji Flask z czterema niezależnymi blueprintami
  (atlas, mpzp, fiszki, dostepnosc) jako placeholderami.
- Dodano stronę startową z listą modułów.
- Dodano konfigurację przez `.env`, `requirements.txt`, `.gitignore`.
- Dodano testy smoke (pytest).
- Dodano `DECISIONS.md` (D-001) i `docs/PROGRESS.md`.

## ETAP 2 — 2026-09-24
- Dodano moduł fiszki: upload PDF, widok PDF-a z zaznaczaniem tekstu
  (pdf.js wektorowany lokalnie), tworzenie fiszek hybrydowo (Gemini
  proponuje szkic na podstawie zaznaczonego fragmentu, użytkownik
  poprawia przed zapisem), kotwica w źródle (strona + podświetlony
  fragment), usuwanie fiszek.
- Dodano warstwę `dane/gemini.py` (pierwsze użycie Gemini w projekcie).
- Dodano bazę sqlite3 modułu fiszki (`pdfy`, `fiszki`).
- Dodano zależność `google-genai` (`requirements.txt`).
- Dodano `DECISIONS.md` D-002, D-003, D-004.
- Dodano testy modułu fiszki (Gemini mockowany, bez realnych wywołań API).

## ETAP 3 — 2026-09-25
- Dodano moduł mpzp: klik na mapie Leaflet znajduje działkę ewidencyjną
  (ULDK) i sprawdza jej przeznaczenie w planie miejscowym gminy Poznań
  (WFS).
- Dodano warstwę `dane/uldk.py` (klient krajowej usługi ULDK).
- Dodano `mpzp/gminy.py` (rejestr gmin, na start tylko Poznań) i
  `mpzp/wfs.py` (klient WFS z lokalnym indeksem przestrzennym
  `shapely.STRtree`).
- Dodano endpointy `GET /mpzp/sprawdz` i `POST /mpzp/odswiez`.
- Dodano zależności `requests` i `shapely` (`requirements.txt`).
- Dodano Leaflet 1.9.4 wektorowany lokalnie (`mpzp/static/leaflet/`).
- Dodano `DECISIONS.md` D-005, D-006.
- Dodano testy modułu mpzp (ULDK i WFS mockowane, bez realnych wywołań
  sieciowych).

## ETAP 4 — 2026-09-29
- Dodano edycję pytania i odpowiedzi fiszki (`PUT /fiszki/<pdf_id>/fiszki/<id>`,
  przycisk „edytuj” w liście fiszek).
- Dodano eksport fiszek z PDF-a do CSV (`/fiszki/<pdf_id>/eksport.csv`).
- Dodano eksport fiszek do Anki jako TSV (`/fiszki/<pdf_id>/eksport.txt`).
- Naprawiono wczytywanie PDF-a: wywołanie `getDocument` dostosowane do
  pdf.js 6.x.
- Usunięto przypadkowy gitlink `FIszki-itp` (zagnieżdżone repozytorium).
- Naprawiono pusty podgląd PDF-a: pdf.js 6.3.289 w wersji legacy
  (z polyfillami dla starszych przeglądarek); błąd wczytania PDF-a
  wyświetlany na stronie.
- Dodano `uruchom.sh`, `zainstaluj_ikone.sh` i `docs/URUCHOMIENIE.md`.
- Dodano `DECISIONS.md` D-007, D-008 (zastąpiona), D-009, D-010.
- Dodano testy edycji i eksportu.

## ETAP 5 — 2026-09-29
- Dodano wspólny szablon `templates/base.html` z paskiem nawigacji.
- Przepisano `static/style.css` (styl Apple, grid/flexbox, tryb ciemny).
- Odświeżono wygląd strony głównej, fiszek i mpzp.
- `/mpzp/sprawdz` zwraca dodatkowo `wydzielenie.przeznaczenie`.
- Lista PDF-ów w fiszkach pokazuje liczbę fiszek.
- Dodano `DECISIONS.md` D-011.

## ETAP 6 — 2026-09-29
- Dodano powtórki fiszek w systemie Leitnera (5 pudełek): sesja z
  kartą, skróty klawiszowe, pasek postępu, link do źródła.
- Dodano tabelę `powtorki` i endpointy `/fiszki/powtorka*`.
- Lista plików pokazuje liczbę fiszek do powtórki i rozkład pudełek.
- Dodano `DECISIONS.md` D-012 i testy powtórek.

## ETAP 7 — 2026-09-29
- Dodano moduł atlas: wskaźniki GUS BDL dla gmin województwa,
  kartogram (granice PRG), kafelki statystyk, ranking gmin, opis przez
  Gemini ze sprawdzaniem liczb.
- Dodano warstwę `dane/bdl.py` i `opisz_wskaznik` w `dane/gemini.py`.
- Dodano `atlas/baza.py` (cache BDL), `atlas/granice.py`,
  `atlas/statystyki.py`.
- Przeniesiono Leaflet do `static/leaflet/`.
- Dodano `GUS_BDL_API_KEY` do `config.py`.
- Dodano `DECISIONS.md` D-013, D-014 i testy atlasu.

## ETAP 8 — 2026-09-29
- Dodano moduł dostępność: wgrywanie gotowych wyników (CSV na siatce
  H3), mapa heksagonów, klasy czasu dojścia, udziały i powierzchnie w
  zasięgu 5/10/15 min.
- Dodano syntetyczny plik przykładowy i skrypt, który go generuje.
- Dodano zależność `h3` (`requirements.txt`).
- Poprawiono kolor przycisków zoomu mapy w trybie ciemnym.
- `uruchom.sh` doinstalowuje zależności po aktualizacji; dodano
  `README.md`.
- Dodano `DECISIONS.md` D-015 i testy modułu.

## ETAP 9 — 2026-09-29
- MPZP: opis symbolu przeznaczenia ze słownika (orientacyjny).
- MPZP: wyszukiwanie działki po identyfikatorze (`/mpzp/dzialka`).
- MPZP: historia ostatnio sprawdzonych działek (`/mpzp/historia`,
  baza `instance/mpzp/mpzp.db`).
- Dodano `DECISIONS.md` D-016 i testy.

## ETAP 10 — 2026-09-29
- Atlas: porównanie z rokiem bazowym (zmiana %, kartogram rozbieżny,
  ranking zmian, fakty zmiany w opisie).
- Atlas: eksport tabeli gmin do CSV (`/atlas/eksport.csv`).
- Poprawiono przybliżenie kartogramu przy pierwszym wczytaniu.
- Dodano `DECISIONS.md` D-017 i testy.

## ETAP 11 — 2026-09-29
- Fiszki: wyszukiwarka we wszystkich plikach (`/fiszki/szukaj`).
- Fiszki: eksport wszystkich fiszek do CSV i Anki.
- Fiszki: usuwanie PDF-a razem z fiszkami i powtórkami.
- Dodano `DECISIONS.md` D-018 i testy.

## ETAP 12 — 2026-09-29
- Dodano ochronę przed zapytaniami z obcych stron (sprawdzanie `Host`
  oraz `Origin`/`Referer` dla metod zmieniających stan) — `ochrona.py`.
- Dodano nagłówki bezpieczeństwa (`X-Frame-Options`,
  `X-Content-Type-Options`, `Referrer-Policy`).
- Dodano `DECISIONS.md` D-019 i testy.

## ETAP 13 — 2026-09-29
- Dostępność: wskaźnik łączny (czas do wszystkich usług naraz) i
  „najsłabsze ogniwo” (`/dostepnosc/plik/<nazwa>/laczny`).
- Dodano `DECISIONS.md` D-020 i testy.

## ETAP 14 — 2026-09-29
- Strona główna: podsumowania modułów na kartach.
- Dodano ikonę aplikacji (`static/favicon.svg`).
- Dodano `DECISIONS.md` D-021 i testy.

## ETAP 15 — 2026-09-29
- Naprawiono 7 błędów znalezionych w przeglądzie kodu (dostępność:
  `.CSV`, wskaźnik łączny bez pełnych komórek, powtórzone kolumny;
  MPZP: wyścig kliknięć; atlas: „największy spadek” przy samych
  wzrostach, cache pustych wyników; `uruchom.sh` bez `PORT`).
- Dodano testy regresji.

## ETAP 16 — 2026-09-29
- MPZP: wyszukiwanie działki po nazwie obrębu i numerze z listą
  podpowiedzi (`/mpzp/podpowiedzi`, ULDK `GetParcelByIdOrNr`).
- Dodano `DECISIONS.md` D-023 i testy.

## ETAP 17 — 2026-09-29
- `main` zaktualizowany do najnowszej wersji (wcześniej zatrzymany na
  ETAPie 3).
- Czytelne komunikaty o błędach sieci (`dane/siec.py`).
- Poprawiono podwójną kropkę w komunikacie Gemini.

## ETAP 18 — 2026-09-29
- Fiszki: propozycje kilku fiszek z całej strony (Gemini), tylko z
  cytatem sprawdzonym w tekście strony.
- Fiszki: statystyki nauki (seria dni, aktywność 30 dni, skuteczność).
- Naprawiono „Pokaż w źródle” dla fragmentów z kilku linii.
- Dodano `DECISIONS.md` D-025 i testy.

## ETAP 19 — 2026-09-29
- Atlas: profil gminy (miejsce, różnica od mediany, zmiana w czasie,
  wykres liniowy SVG, tabela wartości) — `/atlas/gmina/<bdl_id>`.
- Dodano `DECISIONS.md` D-026 i testy.

## ETAP 20 — 2026-09-29
- MPZP: powierzchnia działki, podział na przeznaczenia (m², %),
  raport działki do wydruku (`/mpzp/raport`).
- Dodano `DECISIONS.md` D-027 i testy.

## ETAP 21 — 2026-09-29
- Dostępność: udziały w zasięgu liczone w mieszkańcach (kolumna
  `ludnosc`).
- Dostępność: porównanie scenariuszy przed/po (`/dostepnosc/porownanie`),
  mapa zmian czasu dojścia.
- Drugi syntetyczny plik przykładowy (scenariusz „nowa szkoła”).
- Dodano `DECISIONS.md` D-028 i testy.

## ETAP 22 — 2026-09-29
- MPZP: naprawa niepoprawnych geometrii z WFS (brak błędu 500 przy
  podziale działki).
- Fiszki: niezapisane propozycje ze strony nie przepadają przy błędzie.
- Dodano testy regresji.

## ETAP 23 — 2026-09-29
- MPZP: kalkulator wskaźników zabudowy ze sprawdzaniem zgodności z
  planem (`/mpzp/kalkulator`).
- Dodano `DECISIONS.md` D-030 i testy.

## ETAP 24 — 2026-09-29
- Eksport GeoJSON do QGIS z atlasu, mpzp i dostępności.
- Dodano `DECISIONS.md` D-031 i testy.

## ETAP 25 — 2026-09-29
- Atlas: korelacja dwóch wskaźników (r Pearsona, rho Spearmana, R²,
  wykres rozrzutu z linią regresji) — `/atlas/korelacja`.
- Dodano `DECISIONS.md` D-032 i testy.

## ETAP 26 — 2026-09-29
- Fiszki: quiz ABCD z własnych fiszek (`/fiszki/quiz`).
- Fiszki: lista najtrudniejszych fiszek z dziennika powtórek.
- Dodano `DECISIONS.md` D-033 i testy.

## ETAP 27 — 2026-09-29
- Naprawiono 6 błędów z przeglądu ETAPów 23–26 (korelacja, kalkulator
  zabudowy, quiz).

## ETAP 28 — 2026-09-29
- Atlas: miary zróżnicowania (σ, współczynnik zmienności, kwartyle,
  max/min, Gini) i histogram rozkładu gmin.
- Dodano `DECISIONS.md` D-035 i testy.

## ETAP 29 — 2026-09-29
- Atlas: wskaźniki względne — dowolny wskaźnik podzielony przez drugi z
  mnożnikiem (np. na 1000 mieszkańców), we wszystkich widokach.
- Dodano `DECISIONS.md` D-036 i testy.

## ETAP 30 — 2026-09-29
- MPZP: kalkulator skali mapy (długości, powierzchnie, dobór skali do
  arkusza) — `/mpzp/skala`.
- Dodano `DECISIONS.md` D-037 i testy.

## ETAP 31 — 2026-09-29
- Fiszki: karty do druku, wycięcia i złożenia (`/fiszki/druk`).
- Dodano `DECISIONS.md` D-038 i test.

## ETAP 32 — 2026-09-29
- Kopia zapasowa danych użytkownika jako ZIP (`/kopia-zapasowa`) z
  instrukcją przywracania.
- Dodano `DECISIONS.md` D-039 i test.

## ETAP 33 — 2026-09-29
- Naprawiono 4 błędy z przeglądu ETAPów 28–32 (mianownik w atlasie,
  margines i liczby nieskończone w kalkulatorach, stare wyniki skali).

## ETAP 34 — 2026-09-29
- Atlas: białe tło mapy i szare województwa z PRG z nazwami zamiast
  kafelków OSM („Access blocked”); endpoint `/atlas/tlo-wojewodztw`.
- MPZP i Dostępność: kafelki OSM wysyłają nagłówek Referer (koniec
  „Access blocked”), przełącznik podkładu: OSM / ortofotomapa GUGiK /
  bez podkładu (wybór zapamiętywany w przeglądarce).
- Dodano `DECISIONS.md` D-041 i 3 testy.

## ETAP 35 — 2026-09-29
- MPZP w całej Polsce: gminy bez WFS pytają krajową integrację planów
  GUGiK (KIMPZP, `mpzp/krajowe.py`) — symbol przeznaczenia rozpoznany z
  atrybutów, tytuł planu, linki do dokumentów, wszystkie atrybuty; to
  samo w raporcie do druku.
- Mapa MPZP: nakładki „Plany miejscowe (cała Polska)” i „Działki
  ewidencyjne” (WMS GUGiK); endpoint `/mpzp/warstwy-krajowe`.
- Przełącznik warstw Leafleta w stylu aplikacji (także tryb ciemny).
- Dodano `DECISIONS.md` D-042 i 13 testów.

## ETAP 36 — 2026-09-29
- MPZP: współrzędne klikniętego punktu w WGS84, PL-1992 i PL-2000 (z
  przyciskiem „Kopiuj”), `mpzp/uklady.py`.
- MPZP: pomiar odległości i powierzchni na mapie (przycisk z linijką,
  „Cofnij punkt”, Esc kończy), `POST /mpzp/pomiar`.
- MPZP: link „Geoportal ↗” — działka w geoportal.gov.pl.
- Dodano `DECISIONS.md` D-043 i 16 testów.

## ETAP 37 — 2026-09-29
- Naprawiono 4 problemy z przeglądu ETAPów 34–36: nazwa wybranego
  województwa na kartogramie przy spóźnionym tle, raport błędu KIMPZP
  w formacie tekstowym brany za „brak planu”, zbyt długi adres WMS przy
  bardzo wielu warstwach, eksport GeoJSON bez przeznaczenia dla gmin
  bez WFS.

## ETAP 38 — 2026-09-29
- Dostępność: krzywa dostępności (udział powierzchni i mieszkańców w
  zasięgu 0–60 min) z suwakiem własnego progu.
- Dostępność: „Luki w dostępności” — 10 komórek poza zasięgiem 15 min z
  największą liczbą mieszkańców; klik przybliża mapę.
- Dostępność: klik w heksagon pokazuje wszystkie wskaźniki komórki
  (`/dostepnosc/plik/<nazwa>/komorka/<h3>`).
- Dodano `DECISIONS.md` D-044 i 6 testów.

## ETAP 39 — 2026-09-29
- Fiszki: ocena „Trudne” (klawisze 1/2/3), fiszka zostaje w pudełku i
  wraca jutro.
- Fiszki: tryb „Najpierw wpisuję odpowiedź” (Ctrl+Enter — sprawdź,
  wspólne słowa podświetlone), zapamiętywany w przeglądarce.
- Fiszki: „Przed egzaminem” — wszystkie fiszki pliku albo wszystkie,
  losowo, bez zmiany harmonogramu.
- Fiszki: prognoza powtórek na najbliższe 7 dni na stronie modułu;
  skuteczność liczy „trudne” jako zapamiętane.
- Dodano `DECISIONS.md` D-045 i 5 testów.

## ETAP 40 — 2026-09-29
- Atlas: wybór metody klasyfikacji (kwantyle, Jenks, równe przedziały,
  odchylenie standardowe) i liczby klas 3–7; GVF i liczebność klas w
  legendzie; endpoint `/atlas/klasy`.
- Atlas: 7-stopniowa skala kolorów.
- Atlas: szybki wybór popularnych wskaźników (frazy do wyszukiwarki BDL).
- Dodano `DECISIONS.md` D-046 i 5 testów.

## ETAP 41 — 2026-09-29
- Atlas: autokorelacja przestrzenna — I Morana (p z 999 permutacji, z,
  interpretacja) i klastry LISA (HH, LL, HL, LH) jako tryb mapy z legendą
  i liczebnościami; endpoint `/atlas/autokorelacja`.
- Dodano `atlas/autokorelacja.py`, `DECISIONS.md` D-047 i 5 testów
  (wartość wzorcowa z PySAL).

## ETAP 42 — 2026-09-29
- Atlas: „Mapa do druku ↗” — kartogram A4 z legendą (liczebności klas),
  podziałką, strzałką północy, źródłem i metodą klasyfikacji; pobieranie
  SVG albo druk do PDF; działa dla trybów wartość, zmiana i klastry LISA.
- Autokorelacja: wynik niezależny od kolejności danych (ten sam na
  ekranie i na wydruku).
- Dodano `atlas/mapa_svg.py`, `DECISIONS.md` D-048 i 4 testy.

## ETAP 43 — 2026-09-29
- MPZP: wymiary działki — długości boków podpisane na mapie (od
  przybliżenia 17), szerokość × głębokość, obwód, liczba boków, zwartość.
- MPZP: obszar analizowany do decyzji WZ — wybór boku frontu (podświetlony
  na mapie), bufor max(3 × front, 50 m) z powierzchnią.
- Dodano `DECISIONS.md` D-049 i 5 testów.

## ETAP 44 — 2026-09-29
- MPZP: „Moje działki” — gwiazdka w panelu działki, notatka zapisywana
  automatycznie, lista w panelu bocznym (klik → działka na mapie),
  eksport CSV, notatka w raporcie do druku.
- Dodano `DECISIONS.md` D-050 i 8 testów.

## ETAP 45 — 2026-09-29
- MPZP: strona „Symbole planu” — rozszyfrowanie symbolu (np. 3MN/U),
  tabela oznaczeń z grupami i filtrem.
- Słownik zwyczajowych oznaczeń (MU, ML, UC, UO, UZ, UK, UT, UP, ZN, ZI,
  KS, IT, O, PG) z wyraźną etykietą „zwyczajowe” w panelu działki.
- Dodano `DECISIONS.md` D-051 i 2 testy.
