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

## ETAP 46 — 2026-09-29
- Naprawiono 2 problemy z przeglądu ETAPów 43–45: usunięcie gwiazdki
  tuż po zmianie notatki mogło przywrócić działkę (spóźniony zapis),
  uszkodzona geometria w obszarze analizowanym dawała błąd 500.

## ETAP 47 — 2026-09-29
- Dostępność: „Wstaw usługi — szybki model” — punkty klikane na mapie
  (klik w punkt usuwa), nazwa usługi, parametry (prędkość, krętość),
  siatka z bieżącego pliku albo nowa dla widocznego obszaru; wynik
  zapisywany jako nowy plik, gotowy do wszystkich analiz i porównania
  scenariuszy.
- Dostępność: „Obszary obsługi” — mieszkańcy i czas dojścia na placówkę,
  numerowane punkty na mapie.
- Mapa dostępności zostaje w oknie przy przewijaniu panelu.
- Dodano `dostepnosc/model.py`, `DECISIONS.md` D-052 i 12 testów.

## ETAP 48 — 2026-09-29
- Dostępność: „Raport do druku ↗” — mapa A4 (SVG do pobrania) z legendą,
  podziałką, północą, punktami usług i źródłem oraz tabele: udział w
  zasięgu 5–30 min (powierzchnia i mieszkańcy), najsłabsze ogniwo,
  obszary obsługi, luki; druk do PDF (mapa na pierwszej stronie).
- Dodano `dostepnosc/druk.py`, `DECISIONS.md` D-053 i 3 testy.

## ETAP 49 — 2026-09-29
- Dostępność: „Dodaj do istniejących usług z pliku” w szybkim modelu —
  nowa placówka obok obecnych, wynik gotowy do porównania scenariuszy;
  obszary obsługi pokazują mieszkańców, którzy zyskali; podpowiedzi
  nazw usług z pliku.
- Dodano `DECISIONS.md` D-054 i 3 testy.

## ETAP 50 — 2026-09-29
- Fiszki: tematy (np. „kolokwium 1”) — przy edycji i dla nowych fiszek,
  etykiety na liście, lista tematów na stronie fiszek z powtórką, trybem
  „przed egzaminem”, quizem i drukiem tylko z danego tematu.
- Zapis nowej fiszki sprawdza odpowiedź serwera (wcześniej błąd zapisu
  zamykał formularz bez komunikatu).
- Dodano `fiszki/tematy.py`, `DECISIONS.md` D-055 i 4 testy.

## ETAP 51 — 2026-09-29
- Fiszki: egzaminy — nazwa, data i zakres (temat, plik albo wszystko);
  karta z liczbą dni, paskiem „utrwalone” i planem „ok. N dziennie”,
  skróty do powtórki i trybu „przed egzaminem” z zakresu.
- Fiszki: pasek „utrwalone %” przy każdym pliku.
- Powtórka: przełącznik „Odwróć: odpowiedź → pytanie” (zapamiętany).
- Dodano `fiszki/egzaminy.py`, `DECISIONS.md` D-056 i 7 testów.

## ETAP 52 — 2026-09-29
- Atlas: „Na tle kraju” — ranking 16 województw dla tego samego
  wskaźnika i roku (także względnego), z miejscem wybranego województwa
  i medianą; `/atlas/wojewodztwa-porownanie`.
- Dodano `DECISIONS.md` D-057 i 2 testy.

## ETAP 53 — 2026-09-29
- MPZP: „Porównaj” w „Moich działkach” — 2–4 działki obok siebie, szkice
  w tej samej skali z podziałką, wymiary, zwartość, przeznaczenie,
  obszar analizowany WZ, notatki, linki do raportów.
- Dodano `geometria.szkice_w_jednej_skali`, `DECISIONS.md` D-058 i 2 testy.

## ETAP 54 — 2026-09-29
- Fiszki: „Importuj fiszki z pliku” na stronie PDF-a — Anki (.txt),
  Quizlet, CSV (także własny eksport z kotwicą); temat dla importu,
  pomijanie duplikatów, lista błędnych wierszy.
- Fiszki bez kotwicy (import) — etykieta „import” zamiast strony, bez
  „Pokaż w źródle” i pustego cytatu w powtórce.
- Dodano `fiszki/importer.py`, `DECISIONS.md` D-059 i 6 testów.

## ETAP 55 — 2026-09-29
- Dostępność: „Wczytaj punkty z pliku CSV” w szybkim modelu — punkty
  (z nazwami) na mapie do przejrzenia, pominięte wiersze z opisem;
  nazwy placówek w obszarach obsługi i w raporcie do druku.
- Naprawiono przy okazji (wyłapane testem): nazwa punktu nadpisywała
  nazwę zapisanego pliku w odpowiedzi serwera.
- Dodano `model.punkty_z_csv`, `DECISIONS.md` D-060 i 3 testy.

## ETAP 56 — 2026-09-29
- Porządki w kodzie (bez zmian funkcji): trasy MPZP, Fiszek i Atlasu
  podzielone na pliki tematyczne (`trasy_*.py`), wspólne `mpzp/liczby.py`,
  usunięte nieużywane importy w kodzie i testach, mapa kodu w README.
- Dodano `DECISIONS.md` D-061.

## ETAP 57 — 2026-09-29
- Nowy moduł **Osiedle** (menu, karta na stronie głównej): koncepcje
  osiedla rysowane na mapie — obszar opracowania i tereny MN, MW, U, ZP,
  KD, KS, WS (wielobok, prostokąt, edycja, usuwanie, zmiana funkcji
  kliknięciem), automatyczny zapis, bilans terenu z paskiem i kontrolami,
  eksport GeoJSON, podkłady OSM/ortofotomapa.
- Dodano Leaflet.draw 1.0.4 (`static/leaflet-draw/`), `DECISIONS.md`
  D-063 i 9 testów.

## ETAP 58 — 2026-09-29
- Osiedle: parametry zaznaczonego terenu (zabudowa %, kondygnacje,
  PBC %, puste = wartość typowa), karta „Wskaźniki zabudowy” —
  powierzchnia zabudowy i całkowita, wskaźnik zabudowy, intensywność,
  PBC, najwyższa zabudowa — z polami ustaleń planu i zgodnością ✓/✗,
  kontrola terenów, na których zabudowa + PBC przekraczają 100%.
- Dodano `osiedle/wskazniki.py`, `DECISIONS.md` D-064 i 9 testów.

## ETAP 59 — 2026-09-29
- Osiedle: karta „Program osiedla” — mieszkania MW i domy MN,
  mieszkańcy, gęstość, powierzchnia usług, miejsca postojowe (potrzeba
  i miejsca na terenach KS z ostrzeżeniem o braku), dzieci w wieku
  przedszkolnym i szkolnym z liczbą oddziałów, zieleń na mieszkańca;
  założenia do zmiany w panelu, zapisywane z koncepcją.
- Dodano `osiedle/program.py`, `DECISIONS.md` D-065 i 2 testy.

## ETAP 60 — 2026-09-29
- Osiedle: raport koncepcji do druku/PDF (szkic z legendą, podziałką i
  północą, bilans, wskaźniki, zgodność z planem, program, założenia),
  szkic SVG do pobrania, porównanie 2–4 wariantów obok siebie ze
  szkicami w jednej skali; linki „Raport” i „Porównaj warianty”.
- Dodano `osiedle/rysunek_svg.py`, `osiedle/trasy_druk.py`,
  `DECISIONS.md` D-066 i 2 testy.

## ETAP 61 — 2026-09-29
- Nowy moduł **Przepisy** (menu, karta na stronie głównej): wgrywanie
  aktów prawnych w PDF, podział na artykuły i paragrafy z rozdziałami,
  strona aktu ze spisem (filtr „idź do”) i odnośnikiem do strony PDF,
  wyszukiwarka pełnotekstowa bez polskich znaków i z odmianą, frazy w
  cudzysłowie, „art. 15” / „§ 4”, podświetlone trafienia, zmiana nazwy
  i usuwanie aktu.
- Dodano zależność `pypdf`, `DECISIONS.md` D-067 i 6 testów.

## ETAP 62 — 2026-09-29
- Przepisy: panel „Zapytaj” — odpowiedź Gemini wyłącznie z wybranych
  artykułów, z dosłownymi cytatami sprawdzanymi w tekście (fałszywe
  odrzucane), odnośnik do artykułu i strony PDF, odrzucanie odpowiedzi
  z liczbami spoza przepisów, lista artykułów, które widział model,
  historia pytań z usuwaniem, zastrzeżenie „nie porada prawna”.
- Dodano `przepisy/pytania.py`, `dane/gemini.py: odpowiedz_z_przepisow`,
  `DECISIONS.md` D-068 i 6 testów.

## ETAP 63 — 2026-09-29
- Atlas: **Raport gminy** — wybór województwa i gminy, zestaw wskaźników
  raportu z wyszukiwarki BDL (kolejność, usuwanie, przeliczenie przez
  inny wskaźnik), tabela: rok, wartość, zmiana w 10 lat, miejsce w
  województwie, mediana województwa, wykres trendu; charakterystyka
  gminy przez Gemini ze sprawdzaniem liczb; wersja do druku/PDF; link
  „Raport tej gminy” z profilu gminy na mapie.
- Dodano `atlas/raport.py`, `atlas/trasy_raport.py`,
  `bdl.gminy_wojewodztwa`, `gemini.opisz_gmine`, `DECISIONS.md` D-069
  i 5 testów.

## ETAP 64 — 2026-09-29
- MPZP: **Kronika zmian** — ortofotomapy archiwalne GUGiK w miejscu
  działki: suwak lat z odtwarzaniem, dwa lata obok siebie na
  zsynchronizowanych mapach, granica działki z ULDK; lata odczytywane z
  opisu usługi WMS (wymiar czasu albo warstwy z rokiem); link z panelu
  działki i z nagłówka MPZP.
- Dodano `dane/ortofoto.py`, `mpzp/trasy_kronika.py`, ustawienie
  `ORTO_ARCHIWALNA_WMS` (`.env.example`), `DECISIONS.md` D-070 i 7 testów.

## ETAP 65 — 2026-09-29
- Nowy moduł **Teren** (menu, karta na stronie głównej): projekty
  inwentaryzacji z polami formularza (wzory: zieleń, stan zabudowy,
  przestrzeń publiczna, albo własne), samodzielny formularz HTML na
  telefon działający bez internetu (GPS z dokładnością, pola, zdjęcie,
  uwagi, pamięć w telefonie, eksport/udostępnienie pliku), import pliku
  bez dublowania punktów, mapa punktów z kolorem wg pola i legendą,
  dymki ze zdjęciem, tabela, eksport GeoJSON i CSV, edycja pól.
- Dodano `DECISIONS.md` D-071 i 12 testów.

## ETAP 66 — 2026-09-29
- Przegląd i porządki po ETAPach 57–65 (bez nowych funkcji).
- Naprawiono: w Osiedlu przełączenie koncepcji tuż po zmianie rysunku
  mogło zapisać pusty rysunek do poprzedniej koncepcji; zaległy zapis
  wysyła się teraz przed przełączeniem i przy wyjściu ze strony.
- Menu w wąskim oknie przewija się w poziomie (strona nie jest szersza
  niż okno); sprawdzone na 1300, 700 i 390 px dla stron nowych modułów.
- Usunięcie aktu w Przepisach usuwa pytania z historii, które go
  cytowały.
- Zaktualizowane teksty: strona główna (siedem narzędzi, opisy kart),
  instrukcja w kopii zapasowej, opis danych użytkownika.
- Dodano `DECISIONS.md` D-072.

## ETAP 67 — 2026-09-29
- Osiedle: warstwa „Punkty z inwentaryzacji” — wybór projektu z modułu
  Teren, punkty z dymkiem (wartości pól, zdjęcie, uwagi), wybór
  zapamiętany w koncepcji, pusta koncepcja przybliża mapę do punktów.
- Teren: lista projektów w JSON (`/teren/projekty.json`).
- Dodano `DECISIONS.md` D-073 i 1 test.

## ETAP 68 — 2026-09-29
- Przepisy: „+ Fiszka” przy cytacie odpowiedzi — fiszka z kotwicą w
  PDF-ie aktu (dokładna strona cytatu, podświetlenie), PDF aktu dodawany
  do fiszek raz, link do fiszek po zapisie.
- Fiszki: `fiszki/zewnetrzne.py` (fiszki z innych modułów), tabela
  `pdf_skroty`; naprawiony podgląd PDF — lewy brzeg szerokiej strony był
  niewidoczny.
- Dodano `DECISIONS.md` D-074 i 2 testy.

## ETAP 69 — 2026-09-29
- Teren: **raport do druku** — mapa schematyczna ponumerowanych punktów
  (kolor wg pola, legenda, podziałka, północ), zestawienie pól, tabela
  punktów z dokładnością GPS, dokumentacja fotograficzna z numerami;
  przycisk „Raport do druku” na stronie projektu.
- Dodano `teren/raport.py`, `DECISIONS.md` D-075 i 3 testy.

## ETAP 70 — 2026-09-29
- Teren: pole-skala — opcje listy wyboru od najlepszej do najgorszej,
  kolory od zielonego do czerwonego na mapie projektu i w raporcie;
  zaznaczenie w edytorze pól, we wzorach pola „stan” już jako skala.
- Dodano `DECISIONS.md` D-076 i 1 test.

## ETAP 71 — 2026-09-29
- Aktualizacja jednym poleceniem: `./aktualizuj.sh` (kopia zapasowa w
  `~/warsztat_kopie/`, podmiana plików bez ruszania danych, `.env` i
  `.venv`, usuwanie plików starej wersji, zależności); opis w
  `docs/URUCHOMIENIE.md`.
- Dodano `aktualizacja.py`, `aktualizuj.sh`, `DECISIONS.md` D-077 i 6 testów.

## ETAP 72 — 2026-09-29
- Teren: poprawianie punktów po imporcie — wartości pól, uwagi,
  przesunięcie punktu na mapie przeciąganiem (z odległością w metrach);
  oznaczenie „poprawione ręcznie” w tabeli, dymku, raporcie, GeoJSON i CSV.
- Stare bazy dostają nowe kolumny automatycznie.
- Dodano `DECISIONS.md` D-078 i 2 testy.

## ETAP 73 — 2026-09-29
- Atlas: mapa położenia gminy w Raporcie gminy (gminy województwa,
  wyróżniona gmina, podziałka, północ; przy błędzie PRG — podpis z
  przyczyną).
- Dodano `DECISIONS.md` D-079 i 2 testy.

## ETAP 74 — 2026-09-29
- Fiszki: **fiszki na telefon bez internetu** — plik HTML z wybranymi
  fiszkami (wszystkie, temat, plik), powtórki Leitnera na telefonie
  (umiem / trudne / nie umiem), wyniki w pamięci telefonu, eksport pliku
  wyników, import w Warsztacie (pudełka i statystyki z datami z telefonu,
  bez dublowania, nowsza powtórka z komputera wygrywa).
- Dodano `fiszki/telefon.py`, `fiszki/trasy_telefon.py`,
  `DECISIONS.md` D-080, D-081 i 9 testów.

## ETAP 75 — 2026-09-29
- Osiedle: obszar opracowania z działek ewidencyjnych — identyfikatory
  działek → granice z ULDK → jeden obszar (zastępuje obecny, tereny
  zostają).
- Dodano `DECISIONS.md` D-082 i 1 test.

## ETAP 76 — 2026-09-29
- Atlas: Raport gminy — porównanie z drugą gminą (wartość i miejsce w jej
  województwie, wyróżnione kolumny), eksport CSV (jedna albo dwie gminy).
- Dodano `DECISIONS.md` D-083 i 1 test.

## ETAP 77 — 2026-09-29
- Przepisy: **porównanie wersji aktu** — artykuły dodane, usunięte i
  zmienione (różnice słowo po słowie), liczby zmian, odnośniki do nowej
  wersji.
- Dodano `przepisy/porownanie.py`, `DECISIONS.md` D-084 i 2 testy.

## ETAP 78 — 2026-09-29
- Dostępność: **„Gdzie nowa placówka?”** — 1–5 proponowanych miejsc,
  które obejmą progiem najwięcej mieszkańców poza zasięgiem, znaczniki
  na mapie, zasięg przed i po.
- Dodano `dostepnosc/lokalizacja.py`, `DECISIONS.md` D-085 i 2 testy.

## ETAP 79 — 2026-09-30
- Przegląd po ETAPach 67–78 (bez nowych funkcji): lint i składnia JS
  czyste, logika nowych ścieżek danych bez błędów; wąskie okno (390 px):
  suwak lat w kronice zmian zawija się, tabela symboli i tabela punktów
  raportu z terenu przewijają się w poziomie.
- Dodano `DECISIONS.md` D-086.

## ETAP 80 — 2026-09-30
- MPZP: **karta działki** (dawny raport do druku) — wymiary, współrzędne
  środka w WGS84, PL-1992 i PL-2000, ortofotomapa obecna i najstarsza
  archiwalna z obrysem granicy, linki do kroniki zmian i kalkulatora.
- Dodano `mpzp/karta.py`, `DECISIONS.md` D-087 i 2 testy.

## ETAP 81 — 2026-09-30
- Osiedle: plan miejscowy i działki ewidencyjne (GUGiK) jako nakładki
  pod rysunkiem koncepcji, wybór zapamiętany.
- Dodano `DECISIONS.md` D-088 i 1 test.

## ETAP 82 — 2026-09-30
- Przepisy: **„✦ Fiszki” przy każdym artykule** — propozycje Gemini z
  cytatem sprawdzanym w tekście artykułu i liczbami tylko z przepisu,
  wybór i poprawki, zapis do Fiszek z kotwicą w PDF-ie aktu.
- Dodano `DECISIONS.md` D-089 i 2 testy.

## ETAP 83 — 2026-09-30
- Teren: obszar prac projektu i **mapa offline w formularzu na telefon**
  (ortofotomapa GUGiK obszaru w pliku, zapisane punkty, pozycja GPS z
  dokładnością, podziałka, „Gdzie jestem”).
- Naprawiono: mylący komunikat „Nie udało się ustalić położenia” po
  zapisaniu punktu albo przy stojącym telefonie.
- Dodano `teren/podklad.py`, `dane/ortofoto.obraz_ortofotomapy`,
  `DECISIONS.md` D-090 i 2 testy.

## ETAP 84 — 2026-09-30
- Atlas: **wskaźnik złożony** — składowe z zestawu raportu gminy, kierunek
  (stymulanta / destymulanta) i waga, unitaryzacja zerowana albo
  standaryzacja; ranking gmin województwa, kartogram SVG, CSV z wartościami
  surowymi i po normalizacji.
- Dodano `atlas/zlozony.py`, `atlas/trasy_zlozony.py`, `DECISIONS.md` D-091
  i 3 testy.

## ETAP 85 — 2026-09-30
- Dostępność: **zasięg z punktu** — kliknij miejsce na mapie: okręgi 5, 10
  i 15 minut marszu (szybki model), mieszkańcy w zasięgu i ilu z nich ma
  dziś do wybranej usługi dalej niż próg.
- Dodano `dostepnosc/zasieg.py`, `DECISIONS.md` D-092 i 2 testy.

## ETAP 86 — 2026-09-30
- Strona główna: **kalendarz „Najbliższe terminy”** — egzaminy z Fiszek (z
  postępem nauki) i wyjścia w teren z projektów Terenu.
- Teren: termin wyjścia w teren na stronie projektu.
- Dodano stronę **Pomoc** (menu → Pomoc): krótkie przepisy „jak zrobić…”
  dla każdego modułu, aktualizacja, kopia zapasowa, klucze.
- Dodano `templates/pomoc.html`, `DECISIONS.md` D-093, D-094 i 3 testy.

## ETAP 87 — 2026-09-30
- Dodano `docs/PORTFOLIO.md` — opis Warsztatu do portfolio (po polsku, ze
  streszczeniem po angielsku) i listę zrzutów ekranu do zrobienia.
- Dodano `DECISIONS.md` D-095.

## ETAP 88 — 2026-09-30
- Przepisy: **pobieranie ustaw z Dziennika Ustaw** (API Sejmu, ta sama
  baza co ISAP) — wyszukiwanie po tytule, oznaczone teksty jednolite,
  pobranie jednym kliknięciem zamiast ręcznego ściągania PDF-a.
- Dodano `dane/sejm.py`, `przepisy/static/sejm.js`, `DECISIONS.md` D-096 i 1 test.

## ETAP 89 — 2026-09-30
- MPZP: **plan ogólny gminy** — nakładka stref planistycznych na mapie i
  atrybuty planu ogólnego w miejscu działki (usługa GUGiK, na razie gminy,
  które już uchwaliły plan ogólny). Nakładka także w Osiedlu.
- Dodano `mpzp/uslugi.py`, `DECISIONS.md` D-097 i 2 testy.

## ETAP 90 — 2026-09-30
- MPZP: **ceny transakcyjne** z Rejestru Cen Nieruchomości (bezpłatny od
  2026 r.) — warstwa transakcji na mapie i transakcje obejmujące miejsce
  działki w panelu.
- Naprawiono odczyt tabel HTML z odpowiedzi usług (nagłówek + 2 kolumny).
- Dodano `DECISIONS.md` D-098 i 1 test.

## ETAP 91 — 2026-09-30
- Atlas: **metoda Hellwiga** we wskaźniku złożonym — miara rozwoju jako
  odległość od wzorca (najlepszych wartości składowych), z wagami.
- Dodano `DECISIONS.md` D-099 i 2 testy.

## ETAP 92 — 2026-09-30
- Atlas: **ekstrapolacja trendu** w raporcie gminy — „→ 2028: ~wartość”
  pod wykresem każdego wskaźnika (np. ludności), z oznaczeniem trendu
  niestabilnego (R² < 0,7).
- Dodano `DECISIONS.md` D-100 i 1 test.

## ETAP 93 — 2026-09-30
- Teren: **tryb ankiety** — projekt „ankieta” z formularzem na telefon
  zaczynającym od pytań (miejsce i zdjęcie opcjonalne) i raportem „Wyniki
  ankiety”; wzór „Ankieta: przestrzeń publiczna”.
- Teren: nowy typ pola **wielokrotny wybór**.
- Dodano `DECISIONS.md` D-101 i 3 testy.

## ETAP 94 — 2026-09-30
- Osiedle: **odległości i cień** — odległość terenów zabudowy od granicy
  obszaru (np. działek) i strefa możliwego cienia (równonoc, przesilenia,
  godz. 9–15) z listą terenów mieszkaniowych i zieleni, na które może
  padać cień.
- Dodano `osiedle/cien.py`, `DECISIONS.md` D-102 i 3 testy.

## ETAP 95 — 2026-09-30
- Fiszki: **tematy trafiają do Anki jako tagi**; eksport do Anki jednego
  tematu (link „Anki” przy temacie).
- Dodano `DECISIONS.md` D-103 i 2 testy.

## ETAP 96 — 2026-09-30
- Przegląd kodu ETAPów 79–95 i pomiary wydajności na dużych danych
  (tabela w PROGRESS).
- Przyspieszono „Gdzie nowa placówka” (Dostępność) o ok. 30–35% przy tym
  samym wyniku.
- Dodano `DECISIONS.md` D-104.

## ETAP 97 — 2026-09-30
- **Automatyczna kopia zapasowa** danych przy uruchomieniu — co 7 dni do
  `~/warsztat_kopie`, zostaje 5 najnowszych; data ostatniej kopii na
  stronie głównej.
- Dodano `DECISIONS.md` D-105 i 2 testy.

## ETAP 98 — 2026-09-30
- Pomoc: opisy funkcji dodanych w ETAPach 88–97.
- Dodano `DECISIONS.md` D-106 i 1 test.

## ETAP 99 — 2026-09-30
- Teren: **paski wykresu** w zestawieniu raportu (wyniki ankiety,
  rozkład wartości pól), w kolorach skali dla pól „od najlepszej”.
- Dodano `DECISIONS.md` D-107 i 1 test.

## ETAP 100 — 2026-09-30
- Osiedle: **odległości i cień w raporcie do druku** — strefa cienia i
  numery terenów na szkicu, tabele jak na stronie, wybór dnia.
- Dodano `DECISIONS.md` D-108 i 1 test.

## ETAP 101 — 2026-09-30
- Przepisy: **„Czy jest nowszy tekst?”** — dla ustaw pobranych z Dziennika
  Ustaw szuka nowszego obwieszczenia z tekstem jednolitym i pozwala je
  pobrać.
- Dodano `DECISIONS.md` D-109 i 2 testy.

## ETAP 102 — 2026-09-30
- Strona główna: **„Dodaj do kalendarza (.ics)”** — egzaminy i wyjścia w
  teren do Kalendarza Google, Thunderbirda albo telefonu.
- Naprawiono niezamknięty iterator katalogu w kopii automatycznej.
- Dodano `kalendarz.py`, `DECISIONS.md` D-110 i 2 testy.

## ETAP 103 — 2026-09-30
- **Nowy moduł Ceny**: ceny mieszkań w miastach na prawach powiatu i
  powiatach z GUS BDL — wykres w czasie dla kilku miast, zmiany (rok do
  roku, w 5 lat, od początku, średnio rocznie), ranking w województwie, CSV.
- Klient BDL obsługuje poziom powiatu.
- Dodano `ceny/`, `DECISIONS.md` D-111 i 3 testy.

## ETAP 104 — 2026-09-30
- Ceny: **transakcje z Rejestru Cen Nieruchomości** — import pliku
  GeoPackage powiatu (z katalogu Pobrane), mediana ceny za m² z kwartylami,
  trend co kwartał, rozkład cen, izby, mapa transakcji, filtry i CSV.
- Przeliczenie współrzędnych PL-1992 → WGS84.
- Dodano `ceny/rcn.py`, `ceny/trasy_rcn.py`, `DECISIONS.md` D-112 i 4 testy.

## ETAP 105 — 2026-09-30
- Ceny → Transakcje: obszary rysowane na mapie (do 8), porównanie median
  między obszarami i wobec całego pliku
- Raport cen transakcyjnych do druku / PDF z mapą schematyczną SVG
- Pomoc: opis porównania dzielnic

## ETAP 106 — 2026-09-30
- Ceny → Transakcje: działki z tego samego pliku RCN (przełącznik
  „Mieszkania | Działki”), cena za m² gruntu, filtry przeznaczenia w planie
  i rodzaju nieruchomości, tabela według przeznaczenia, CSV i raport
- Pomoc: opis cen działek

## ETAP 107 — 2026-09-30
- Ceny → Transakcje: podobne transakcje wokół wskazanego miejsca —
  mediana ceny za m² i orientacyjna cena mieszkania lub działki
- Pomoc: opis wyceny porównawczej

## ETAP 108 — 2026-09-30
- Ceny → Transakcje: widok mapy w heksagonach H3 — mediana ceny za m²,
  wybór wielkości heksagonu i minimum transakcji
- Pomoc: opis mapy w heksagonach

## ETAP 109 — 2026-09-30
- MPZP: ceny mieszkań i działek w okolicy działki z zaimportowanego pliku RCN
- Osiedle: karta „Ceny w okolicy” obszaru opracowania
- Pomoc: opis cen w okolicy

## ETAP 110 — 2026-10-01
- Ceny → Transakcje: wykres mediany ceny za m² w latach dla narysowanych
  obszarów, także w raporcie do druku

## ETAP 111 — 2026-10-01
- Ceny → Transakcje: mapa zmiany cen w heksagonach między dwoma okresami
- Pomoc: opis mapy zmian
