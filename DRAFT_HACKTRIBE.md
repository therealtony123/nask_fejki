# DRAFT — HackTribe (Kolekcjoner Fejków) — do wklejenia przed 20:00

## 01. Nazwa projektu
Kolekcjoner Fejków — FOLLOW THE FAKE

## 02. Nazwa zespołu
[UZUPEŁNIJ NAZWĘ ZESPOŁU]

## 03. Numer stolika
[UZUPEŁNIJ]

## 04. Krótki opis projektu
Narzędzie łączy pojedyncze podejrzane reklamy w większe kampanie oszustw.
Z każdego materiału (URL, zapisana strona, archiwum HAR, zrzut ekranu, wideo)
automatycznie wyodrębnia cechy z czterech niezależnych widoków: tekst
(tytuł, treść, OCR zrzutów), wizja (perceptual hashe pHash/dHash, kolory
dominujące), infrastruktura (domeny, ID trackerów GA/Pixel/GTM, łańcuchy
przekierowań) oraz struktura (szablon HTML/CSS). Podobieństwo ważone
multi-widok buduje graf incydentów, w którym każda krawędź ma jawne
przesłanki ("identyczny tytuł", "te same trackery", "warianty graficzne").
Klastrowanie Louvain wyznacza kampanie. Demonstrator w Streamlit prowadzi
przez cały proces: od wczytania materiału, przez cechy i porównania, po graf
zależności z uzasadnieniami oraz ocenę nowego materiału względem zbioru
(przypisanie do kampanii lub nowy wzorzec).

## 05. Plan rozwiązania
1. Ingest wielu formatów materiałów (HTML+HAR+zrzuty+wideo+URL).
2. Ekstrakcja cech multi-widok: tekst/OCR, hashe percepcyjne, domeny +
   trackery + przekierowania, szablon HTML.
3. Podobieństwo ważone z wagami normalizowanymi do dostępnych cech
   (odporność na niekompletne dane) i listą przesłanek dla każdej krawędzi.
4. Graf incydentów + klastrowanie Louvain -> kampanie z etykietami.
5. Ocena nowych materiałów (przypisanie do znanej kampanii vs nowy wzorzec).
6. Interfejs Streamlit: raport, graf zależności (pyvis), eksploracja
   incydentów, analiza URL.
7. Konteneryzacja (Docker), README z metodyką; opcjonalnie baza referencyjna
   twarzy podszywanych osób i scheduler skanujący biblioteki reklam.

## 06. Wybrane zadanie partnera
NASK PIB — Kolekcjoner Fejków (FOLLOW THE FAKE)

## 07. Dotychczasowe postępy
- EDA udostępnionego zbioru: 10 incydentów, 362 pliki (strony, HAR, zrzuty,
  wideo), zidentyfikowane sygnały kampanii.
- Działający pipeline v1 (Python): ingest -> cechy -> podobieństwo ->
  graf + Louvain -> kampanie; wyniki zapisywane w SQLite.
- Wykryte powiązania z twardymi przesłankami: ten sam fałszywy artykuł
  ("zamach na Rafała Brzoskę") na wielu domenach + 11 wariantów graficznych
  (score 0.885) oraz wspólny artykuł "37 minut po emisji..." między dwoma
  incydentami (score 0.473, 6 pasujących obrazów).
- Demonstrator Streamlit z grafem zależności i wyjaśnieniami powiązań,
  zakładka "nowy materiał" (porównanie URL ze zbiorem).
- Dockerfile + docker-compose, README z opisem metodyki.

## 08. Link do repozytorium
[UZUPEŁNIJ — np. https://github.com/TWOJLOGIN/kolekcjoner-fejkow]
(można uzupełnić po 20:00 — pole nie jest blokowane)
