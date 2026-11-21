# 🕵️ Kolekcjoner fejków

Demonstrator do zadania **„Kolekcjoner fejków”** (HackNation 2026, wyzwanie NASK PIB):
narzędzie, które z chaosu pojedynczych podejrzanych reklam **wydobywa wspólne ślady
i łączy je w kampanie oszustw** — automatycznie, z czytelnym uzasadnieniem każdego
powiązania.

```
materiały (URL / tekst / zrzut ekranu / zbiór JSON)
        │  ingest + publiczne metadane (DNS, RDAP)
        ▼
zestaw cech (tekst, obraz, domena, infrastruktura, osoby)
        │  podobieństwo ważone + twarde sygnały
        ▼
graf krawędzi z przesłankami → union-find → KAMPANIE
        │
        ▼
GUI: klastry • graf zależności • cechy • analiza nowego materiału
```

## Szybki start

```bash
python3 scripts/make_demo.py    # (opcjonalnie) wygeneruj zbiór demo 13 materiałów
streamlit run app.py           # demonstrator: http://localhost:8501
```

Zbiór demo jest już wygenerowany w `data/demo_materials.jsonl` (ładuje się automatycznie).

### Docker (preferowane przez organizatora)

```bash
docker build -t kolekcjoner-fejkow .
docker run -p 8501:8501 kolekcjoner-fejkow
```

### Zależności

`streamlit`, `pillow`, `numpy`, `requests` (Zależność | licencja):
streamlit — Apache-2.0, Pillow — HPND (MIT-CMU), numpy — BSD-3, requests — Apache-2.0.
Bez kluczy API — całość działa offline (z wyszukiwaniem RDAP jako best-effort).

## Metodyka (jak to działa)

### 1. Ingest materiałów
- **URL** — pobranie treści (HTML→tekst) + pełny łańcuch przekierowań HTTP;
  **DNS**: adres IP hosta; **RDAP** (`rdap.org`, m.in. NASK dla .pl): serwery NS,
  rejestrator, data rejestracji. Strona martwa / brak sieci ⇒ materiał jest
  analizowany na pozostałych modaliowościach.
- **Tekst**, **zrzut ekranu / kreatyw** (PNG/JPG), **zbiór JSONL** — pola:
  `id, url, text, image, redirect_chain, ns, mx, ip`.
- Tolerancja na dane niekompletne jest projektowa: każda cecha jest opcjonalna.

### 2. Ekstrakcja cech
| Modaliwość | Cechy | Metoda |
|---|---|---|
| tekst/semantyka | n-gramy słowne (3), leksykon narracji scam (PL/EN), wzorce kwot (`5 000 zł`, `300%`), wizerunki osób (mała baza referencyjna) | normalizacja (NFKD, stopwordy PL), funkcje haszujące słowne, regex |
| wizualia | dHash 64-bit obrazu | czysta implementacja PIL+numpy (odległość Hamminga) |
| domena | domena rejestrowa (uproszczony PSL), tokeny subdomen, TLD | `registrable()` |
| infrastruktura | domeny z przekierowań, zbiory NS/MX, IP | RDAP/DNS + logi/rekordy wejściowe |

### 3. Podobieństwo ważone (z renormalizacją wag)
Dla pary materiałów liczymy składowe podobieństwa: `text` (0.75·Jaccard-n-gramów +
0.25·Jaccard-słów kluczowych), `image` (1−Hamming/64), `domain`, `infra`, `persona`.
Wynik ważony liczony jest **tylko po modaliowościach dostępnych dla obu materiałów**
(wagi renormalizowane), a `confidence` = dostępna część wagi — brakujące dane nie
fałszują porównania. Wagi konfigurowalne w GUI (suwaki), próg domyślny 0.45.

### 4. Twarde sygnały (niezależne od progu — anty-duplikatowo)
- identyczna domena rejestrowa,
- near-duplikat obrazu: Hamming(dHash) ≤ 6,
- duplikat/wariant tekstu: Jaccard n-gramów ≥ 0.8.

### 5. Grupowanie w kampanie
Krawędzią jest para powyżej progu **albo** z twardym sygnałem. Kampania = komponent
spójności grafu (**union-find**). Każda krawędź przechowuje listę przesłanek
(`Evidence`: modaliwość, opis, składowy wynik, waga) — pełna interpretowalność.

### 6. Analiza nowego materiału
Nowy materiał porównujemy ze wszystkimi wcześniejszymi; przypisujemy do klastru
najbliżej powiązanego przypadku, gdy krawędź przekracza próg lub daje twardy sygnał;
w przeciwnym razie komunikat: **nowa kampania**. GUI pokazuje top-N podobieństw
z przesłankami niezależnie od decyzji.

## Struktura

```
app.py                       # demonstrator Streamlit (end-to-end)
kolekcjoner/
  model.py                   # Material, Features, Evidence, Link, Cluster
  extract.py                 # ekstrakcja cech: tekst/dHash/domeny/DNS/RDAP
  similarity.py              # podobieństwo ważone + twarde sygnały
  cluster.py                # union-find, przypisywanie nowego materiału
  ingest.py                  # URL/tekst/obraz/JSONL → Material
scripts/make_demo.py         # generator zbioru demo (3 kampanie + 2 samotne)
data/demo_materials.jsonl    # zbiór demo, data/ads/*.png — zrzuty
tests/smoke.py               # test end-to-end rdzenia (bez GUI)
Dockerfile                   # środowisko skonteneryzowane
```

## Testy

```bash
python3 tests/smoke.py   # ingest → cechy → klastry → nowy materiał; asercje grupowania
```

## Ograniczenia / dalszy rozwój
- NS/MX obecnie z RDAP (dla domen, gdzie RDAP odpowiada) lub z danych wejściowych
  (log/rekord) — łatwo dorzucić zapytania DNS typu NS/MX.
- Wyszukiwanie reklam w bibliotekach reklam (Google Ad Transparency API) — punkt wejścia
  `ingest.from_url` + słowa kluczowe z `extract.SCAM_LEXICON` są gotowe do podłączenia.
- Skalowanie: porównania par O(n²) — dla dużych zbiorów zastąpić LSH/MinHashem
  po n-gramach i dHashach (struktura modułowa to umożliwia bez zmian GUI).
