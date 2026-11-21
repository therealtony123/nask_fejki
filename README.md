# 🕵️ KOLEKCJONER FEJKÓW — FOLLOW THE FAKE

Narzędzie, które z chaosu pojedynczych podejrzanych reklam wydobywa wspólne ślady
i łączy je w większe **kampanie oszustw**. Rozwiązanie automatycznie analizuje
treść, warstwę wizualną i publicznie dostępne metadane infrastruktury, a następnie
prezentuje podobieństwa i zależności między incydentami w czytelnej formie
(klastry + graf z uzasadnieniem każdego powiązania).

Projekt przygotowany na hackathon **HackNation 2026** — zadanie „Kolekcjoner Fejków"
(NASK PIB).

---

## 1. Pipeline

```
Ingest ──► Cechy ──► Podobieństwo ważone ──► Graf + Louvain ──► Kampanie ──► UI
         (tekst,     (multi-widok z          (krawędzie        (klastry    (Streamlit)
          wizja,      przesłankami)          z dowodami)        z etykietami)
          infra,
          struktura)
```

### 1.1 Ingest

Wejściem jest katalog ze zbiorem (struktura `do_udostępnienia/<id>/*`) lub pojedynczy
URL (zakładka „Nowy materiał"). Każdy katalog to jeden **incydent** i może zawierać
dowolny podzbiór materiałów: zapisane strony HTML (+zasoby), archiwa HAR, zrzuty
ekranu, obrazy, wideo (mp4), pliki metadanych (.info.json z yt-dlp).
Brakujące typy danych nie przerywają analizy — system działa na tym, co jest.

### 1.2 Cechy (pozyskiwanie)

Cztery niezależne widoki cech:

| Widok | Cechy | Skąd |
|---|---|---|
| **tekst** | tytuł (znormalizowany), treść strony, meta description/keywords, tekst z OCR zrzutów ekranu | HTML (BeautifulSoup), OCR (tesseract `pol+eng`) |
| **wizja** | perceptual hashe (DCT-pHash + dHash, 64 bity), kolory dominujące, wymiary | każdy obraz incydentu (PIL+numpy+scipy) |
| **infrastruktura** | domeny (pełne i rejestrowalne), ID trackerów (GA/GTM/Pixel/Clarity), usługi śledzące, łańcuchy przekierowań | HTML (linki, skrypty), HAR (każdy request/response) |
| **wzorce domen** | TLD, segmentacja, słowopodobieństwo, entropia nazwy (np. `słowo-słowo` w nietypowym TLD) — schemat nazewniczy rzadko zmieniany przez operatora | analiza nazw domen rejestrowalnych |
| **struktura** | klasy CSS, skrypty JS, favicon md5 | HTML |

Dodatkowo: md5 plików wideo i metadane z plików `.info.json` (np. ID reklamy
na Facebooku). Wszystkie cechy są jawne i czytelne dla analityka — to fundament
interpretowalności wyniku.

### 1.3 Podobieństwo (ważone, multi-widok)

Każdą parę incydentów porównuje się niezależnie w widokach:

- **tytuł** (waga 0.30) — równość/`difflib` na znormalizowanym tytule;
- **trackery** (waga 0.30) — te same identyfikatory analityki (GA/Pixel/GTM)
  to bardzo silny sygnał wspólnego operatora kampanii;
- **obrazy** (waga 0.25) — odległość Hamminga pHash ≤ 12 lub dHash ≤ 8
  oznacza duplikat/wariant graficzny;
- **infrastruktura** (waga 0.20) — Jaccard zbioru domen rejestrowalnych;
- **treść** (waga 0.15) — cosinus TF-IDF n-gramów znakowych (2–4 znaki;
  odporne na polską fleksję, brak zależności od języka modelu);
- **struktura** (waga 0.10) — Jaccard klas CSS (wspólny szablon produkcyjny);
- **wzorce domen** (waga 0.08) — wspólny schemat nazw domen (TLD + klasy
  nazewnicze + entropia), z pominięciem platform/CDN; słaby sygnał, liczony
  maks. jako 0.5, więc sam nie tworzy krawędzi — pomaga przy łączeniu z innymi.

**Kluczowa własność (niekompletne dane):** wagi są normalizowane wyłącznie do
widoków dostępnych *w obu* porównywanych materiałach. Brakująca cecha nie obniża
sztucznie wyniku i nie psuje porównania.

Krawędź powstaje, gdy suma ważona ≥ **progu** (domyślnie 0.25). Każda krawędź
zapisuje **listę przesłanek** — które konkretnie cechy ją utworzyły („identyczny
tytuł «…»", „te same trackery: G-XXXX", „3 pasujące obrazy, odl. 5", …).
Krawędź jest oznaczana jako **twarda**, gdy zachodzi: identyczny tytuł, wspólne
ID analityki lub co najmniej połowa obrazów jest wariantami.

### 1.4 Klastrowanie

Graf incydentów (węzły = incydenty, krawędzie = udokumentowane podobieństwo)
jest dzielony algorytmem **Louvain** (community detection, `networkx`) — kampanie
nie muszą być klikami, co pozwala łączyć łańcuchy wariantów. Każda kampania
dostaje etykietę zbudowaną z najczęstszych przesłanek.

### 1.5 Nowy materiał vs zbiór

Nowy materiał (URL) przechodzi tę samą ekstrakcję cech, jest porównywany ze
wszystkimi zapisanymi incydentami, po czym:

- jeśli najlepsze dopasowanie ≥ **progu przypisania** (0.30) → materiał
  przypisywany do kampanii najsilniejszego sąsiada (głosowanie ważone),
- w przeciwnym razie → zgłaszany jako **nowy wzorzec działania**.

### 1.6 Eksport dla CSIRT: STIX 2.1 + watchlista IoC

Po klastrowaniu pipeline generuje dwa artefakty wdrożeniowe:

- **pakiet STIX 2.1** (`*.stix.json`): obiekty `campaign` (z opisem przesłanek
  i pierwszą/ostatnią aktywnością), `incident` (z cechami: domeny, ID trackerów),
  `indicator` (pattern `domain-name` dla domen) oraz relacje
  `incident -attributed-to-> campaign`, `indicator -indicates-> campaign`
  i `incident -related-to-> incident` — te ostatnie zawierają **listę przesłanek
  w polu description i poziom ufności (0–100) = ważone podobieństwo**;
- **watchlista IoC** (`*.ioc.csv`): domeny, ID trackerów (GA/GTM/Pixel), hashe
  faviconów i wideo z przypisaniem do kampanii i incydentu źródłowego.

Oba pliki są do pobrania w zakładce „Eksport (STIX/IoC)" demonstratora i mogą
trafić wprost do MISP/OpenCTI.

### 1.7 Interpretowalność w obie strony

Każda para materiałów ma jawne **przesłanki ZA i PRZECIW** połączeniu (zakładka
„Kampanie" → „Dlaczego materiały NIE zostały połączone?"). Brakujące dane są
komunikowane wprost — analityk widzi, że rozdzielenie wynika z dowodów, a nie
z braku informacji.

### 1.8 Bonus: biblioteka reklam

Opcjonalna integracja z **Meta Ad Library API** (zakładka „Biblioteka reklam"):
wyszukiwanie reklam wg słów kluczowych (np. „zarabiaj z domu") i porównywanie
ich treści ze znanymi kampaniami. Wymaga tokena Graph API (instrukcja w
`kfk/adlibrary.py`); bez tokena zakładka działa na zapisanej próbce
`data/meta_ads_sample.json`.

---

## 2. Uruchomienie

### Lokalnie (Python ≥ 3.11)

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# opcjonalnie polski model OCR (bez niego OCR działa po angielsku):
mkdir -p tessdata && curl -sL -o tessdata/pol.traineddata \
  https://github.com/tesseract-ocr/tessdata_fast/raw/main/pol.traineddata

# pipeline (CLI):
TESSDATA_PREFIX="$PWD/tessdata" .venv/bin/python pipeline.py data --db kfk.sqlite

# demonstrator:
TESSDATA_PREFIX="$PWD/tessdata" .venv/bin/streamlit run app.py
```

Otwórz http://localhost:8501 — w panelu bocznym ustaw katalog danych i kliknij
**▶ Uruchom analizę**.

### Docker

```bash
docker compose up --build
```

Dane montowane z `./data`, baza `./kfk.sqlite`. W obrazie jest tesseract z polskim
modelem.

Wymagania systemowe lokalnie: `tesseract-ocr` (dla OCR; opcjonalne).

---

## 3. Zależności i licencje

| Biblioteka | Licencja |
|---|---|
| numpy, scipy, pillow | BSD-3 / BSD |
| networkx | BSD-3 |
| streamlit | Apache-2.0 |
| beautifulsoup4, lxml | MIT / BSD-3 |
| requests | Apache-2.0 |
| pytesseract (opcjonalny) | Apache-2.0 |
| pyvis (wizualizacja grafu) | BSD-3 |

Modele: tesseract `tessdata_fast` (Apache-2.0). Brak zewnętrznych API i kluczy —
całość działa offline na dostarczonych materiałach. Pobieranie URL-i w zakładce
„Nowy materiał" wymaga dostępu do internetu.

## 4. Ograniczenia (świadome)

- **Domena rejestrowalna** liczona naiwnie (ostatnie 2 etykiety) — wystarcza dla
  demonstracji; w wersji produkcyjnej należy użyć Public Suffix List.
- **IP/WHOIS/RDAP** celowo nie wchodzą w pipeline offline (dane mogą być
  niedostępne); rozszerzenie o wzbogacenie RDAP/cert.sh jest przewidziane jako
  plugin po stronie „wzbogacania".
- Klasteryzacja jest deterministyczna (seed), ale zmiana progu zmienia ziarnistość
  kampanii — progi są parametryzowane w UI.
- Dane organizatora nie są częścią tego repozytorium (klauzula o zakazie
  rozpowszechniania).

## 5. Struktura kodu

```
pipeline.py            # CLI: pełny przebieg analizy
app.py                 # demonstrator Streamlit
kfk/
  features.py          # ingest + ekstrakcja cech (tekst/wizja/infra/struktura)
  similarity.py        # TF-IDF + ważone podobieństwo multi-widok + przesłanki
  cluster.py           # graf, Louvain, przypisywanie nowych materiałów
  store.py             # trwałość: SQLite (incydenty, krawędzie, kampanie)
  stix.py              # eksport STIX 2.1 + watchlista IoC + oś czasu
eda.py                 # eksploracyjna analiza zbioru
```