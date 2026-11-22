# Wzorce kampanii oszukańczych — opis zbioru (NASK „Kolekcjoner fejków")

Dokument opisuje wzorce kampanii oszukańczych wykryte automatycznie w zbiorze 103 incydentów,
a następnie zweryfikowane przeglądem materiałów, dowodów krawędzi i metadanych infrastruktury.
Stanowi część zgłoszenia hackathonowego — realizuje wymaganie „wzbogacony i uporządkowany zbiór
danych, opis zidentyfikowanych wzorców kampanii oszukańczych".

Zasada minimalizacji danych: cytujemy wyłącznie krótkie tytuły, nazwy domen (zwykły tekst, bez
protokołu i klikalnych odnośników) oraz identyfikatory kampanii. Nie publikujemy pełnych treści
stron ani danych osobowych osób trzecich; nazwiska osób publicznych to wyłącznie kontekst analizy.

## 1. Metoda — jak powstał ten opis

Pipeline **KOLEKCJONER FEJKÓW** przetwarza materiały w czterech krokach:

1. **Cechy** — dla każdego incydentu wyliczane są widoki: tytuł i treść (znormalizowane), obrazy
   (hashe percepcyjne pHash/dHash), infrastruktura (domeny, RDAP, redirecty, trackery), struktura
   HTML (klasy CSS, skrypty, favicon) oraz twarze (baza referencyjna znanych osób).
2. **Podobieństwo ważone z przesłankami** — każda para incydentów jest porównywana na 9 widokach
   z wagami: tytuł 0.30, trackery 0.30, twarze 0.30, obrazy 0.25, infrastruktura 0.20, treść 0.15,
   narracja scam 0.10 (wspólne frazy leksykonu oszustw i wzorce kwot), struktura 0.10, wzorzec
   nazw domen 0.08. Wagi są normalizowane do widoków dostępnych w obu
   materiałach, więc braki danych (brak tytułu, brak RDAP) nie blokują porównania. Każda krawędź
   niesie listę przesłanek (dowodów) — np. „identyczny tytuł", „5 pasujących obrazów",
   „te same trackery", „wspólny szablon HTML (jaccard klas CSS: 1.00)".
3. **Graf** — krawędzie powstają powyżej progu podobieństwa **0.25**. Krawędź jest **twarda**,
   gdy spełniona jest co najmniej jedna twarda przesłanka: ten sam tytuł, te same identyfikatory
   analityki (GA/Pixel/GTM), co najmniej połowa obrazów w wariantach graficznych lub ta sama osoba
   na zdjęciach.
4. **Klastrowanie Louvain** (networkx, `louvain_communities`, waga = score, seed 42) — podział
   grafu na kampanie z etykietą z najsilniejszych przesłanek i osią czasu. Artefakty: baza
   `kfk.sqlite`, graf `kfk.graph.json`, pakiet STIX 2.1 `kfk.stix.json`, lista IoC `kfk.ioc.csv`.

**Liczby zbioru** (wyliczone z plików wyjściowych):

| Metryka | Wartość |
|---|---|
| Incydenty | 103 |
| Krawędzie (pary podobne) | 166 — w tym 155 twardych, 11 miękkich |
| Kampanie (klastry Louvain) | 45 — w tym 31 wieloelementowych i 14 singletonów |
| Próg krawędzi / minimalny score / średni score | 0.25 / 0.2621 / 0.672 |
| Krawędzie o score 1.0 / z treścią cos=1.00 | 19 / 20 (w 16 kampaniach) |
| Obiekty STIX 2.1 | 692 (103 incident, 45 campaign, 411 relationship, 132 indicator, 1 identity) |
| Wiersze IoC (CSV) | 391 + nagłówek |
| Zakres czasowy zbioru | 2026-08-12 → 2026-11-21 |

## 2. Kategorie wzorców

Kategorie wyznaczono z danych: przejrzano etykiety i członków kampanii wieloelementowych
(`clusters` w grafie), dowody krawędzi (`edges` w bazie) oraz cechy incydentów (tytuły, domeny,
RDAP, trackery, twarze). Kategorie **nie są rozłączne** — jedna kampania może realizować kilka
wzorców naraz (np. K08 łączy infrastrukturę i platformy inwestycyjne, K26 jest jednocześnie
phishingiem logowania i kampanią infrastrukturalną).

### 2.1 Phishing logowania na znane marki

Strony udające ekrany logowania do znanych serwisów. **Co je łączy:** identyczny lub prawie
identyczny tytuł (w 39 krawędziach tytuł jest identyczny, w 1 niemal identyczny), klony
wizualne logotypów i formularzy, a często wspólny host (darmowe buildery stron: editmysite.com,
flazio.com, gitbook.io, jimdo.com). **Typowe sygnały:** tytuł z nazwą marki + „Log in"/„Sign in",
strona hostowana poza domeną marki, świeża domena rejestracyjna, formularz zbierający dane.
**Jak analityk ją rozpoznaje:** porównanie domeny strony z oficjalną domeną marki, wiek domeny
z RDAP oraz sprawdzenie, czy trackerzy/piksele należą do marki.

Przykłady z danych (kampania — tytuły — domeny):

- K12 — „Instagram" (2 kopie, treść cos=1.00, 5 pasujących obrazów, szablon CSS 1.00),
- K25 — „BBVA | Log in" (identyczny tytuł + szablon CSS 1.00),
- K28 — „KuCōin @Login" (klon na kuciuonlogen.gitbook.io — podszywanie się przez GitBook),
- K41 — „Verify You're Human" (2 kopie, szablon CSS 1.00),
- K30 — „Sign in to your account" (asocjacje z domenami microsoft.com),
- K23 — „WhatsApp", K13 — „Facebook Password Page", K11 — „Сообщество Steam",
- K14 — „Çrypto.com** !Login : SignIn with Ease" (nawiązania do crypto.com), K16 — „Outlook
   for Business | Microsoft 365", K29 — „Mise à jour Bluewin - Swisscom Login",
- K26 — „home - Votre compte CPAM" (francuski ubezpieczyciel; hosting flazio.com/flazio.org),
- K33 — „SEUR: Envío y transporte de paquetería y mensajería | SEUR", K10 — „Flybuys – Sign In",
- K45 — „PORTAL - Mail Authentication" (singleton).

Liczebność: **15 kampanii, 29 incydentów** (14 par klonów + 1 singleton).

### 2.2 Warianty i duplikaty stron (klony 1:1)

Najmocniejszy i najczęstszy wzorzec: te same materiały zebrane w różnych momentach lub z różnych
źródeł (np. dwukrotnie z feedu phishingowego) łączą się w pary z treścią **cos=1.00**,
identycznymi obrazami (odległość hashy = 0) i szablonem CSS o jaccardzie 1.00. W zbiorze jest
**20 krawędzi z cos=1.00** (19 o score 1.0) w **16 kampaniach**, np. K12 (Instagram), K01
(dwie kopie tego samego artykułu), K17 (cztery kopie „Downloading Document" + dwie kopie
CENTRE POINT MARKETS), K33, K18, K27, K30.

Przypadek graniczny — **K21**: cztery materiały bez tytułów, połączone wyłącznie identycznym
szablonem HTML (CSS jaccard 1.00). To krawędzie **miękkie** (hard=0): sam szablon bez drugiej
przesłanki nie jest traktowany jako dowód pewny — dobra ilustracja działania progów ufności.

### 2.3 Kampanie łączone wspólną domeną / infrastrukturą

Klastry, w których siłą spajającą jest współdzielona infrastruktura lub ten sam zestaw grafik.

- **K08 (6 materiałów, 15 twardych krawędzi)** — „kit" używany w kilku oszustwach naraz: dwie
  strony „Roblox 10.000 Robux" na www9.0zz0.com, dwie kopie platformy tradingowej „Home |
  avextrade.com" (avextrade.com) oraz dwa fałszywe banki „Personal Banking | Home Loans | Business
  Banking" — CrystalFin (crystalfinbn.live) i Exos Credit Savings (exoscredsavings.top). Łącznik:
  wspólny zestaw grafik (img_00.gif ≈ img_03.png, odl. 6); pary wewnątrz to klony 1:1 (cos=1.00,
  14 pasujących obrazów). Wniosek: jeden zestaw szablonów obsługuje różne pionki oszustwa.
- **K19 (14 materiałów, 91 twardych krawędzi)** — strony z doświadczeniami Roblox
  (dXEBEC, Ukaon, MOKS i in.) łączone domenami roblox.com/rbxcdn.com oraz tymi samymi
  identyfikatorami Google Analytics **UA-26810151-2** i **UA-486632-1**. Uwaga: to materiały
  zebrane w celach porównawczych (referencyjnych) — pokazują, jak silnie wspólne domeny
  i trackery grupują materiały.
- **K09** — 4 strony na cdn3.editmysite.com (m.in. „Login | Screen"), szablon CSS 1.00, 6
  krawędzi (tylko 1 twarda); **K26** — flazio.com/flazio.org (patrz 2.1); **K32** — framer.com / framerusercontent.com („My Framer Site").

Liczebność: **5 kampanii (K08, K09, K19, K26, K32), 28 incydentów**.

### 2.4 Fałszywe artykuły sensacyjne z wizerunkami celebrytów

Artykuły udające doniesienia medialne, promowane reklamami w Meta Ads i prowadzące do landingów
(„suplementów", „inwestycji"). **Co je łączy:** identyczny sensacyjny tytuł, ten sam piksel
Facebooka (identyfikator FB_…), te same wizerunki osób publicznych w bazie twarzy oraz świeże
domeny rejestrowane tuż przed publikacją.

- **K01** — false-news z deepfake wizerunkiem znanego przedsiębiorcy (kampania „wiem, kto strzelał”):
  dwie wersje www (civicdaybook.live oraz acrosscommunities.live + crimsonbase.pro +
  healthlinkq.pro). Treść cos=1.00 między wersjami www; wspólny piksel FB_2012165449475163
  (facebook-pixel); wizerunek Mateusza Morawieckiego.
- **K02** — landing „Metabo RX" (bf1.clickline.org i in.) i artykuł o „próbowali mnie zniszczyć…":
  krawędź oparta na treści (cos=0.41) i **tej samej osobie** — Monika Olejnik (twarda przesłanka
  „ta sama osoba", score 0.26 — najsłabsza krawędź zbioru).
- **K07** — „37 minut po emisji wyprowadzono go w kajdankach…": wersja www (novumfy.com,
  oceanicbay.info) oraz zrzut reklamy Meta (incydent 61, glowpixel.org); wizerunki Kuby
  Wojewódzkiego, Mateusza Morawieckiego, Krzysztofa Ibisza; tracker AW-18463917747.

Singletony z tej samej rodziny (same reklamy Meta bez dopasowanej wersji www): **K04** —
„App Store – Słodka Bonanza" (incydent 10), **K05** — „Poland Invest
Summit 2026" (incydent 36, meroporepufulo.life), **K06** — „Uromexil Forte" (incydent 47,
shryxla-mynx.icu).

Liczebność: **3 kampanie wieloelementowe (6 incydentów) + 3 pokrewne singletony**.

**Daty utworzenia domen** (RDAP, dni względem pierwszego zrzutu): civicdaybook.live
— +57 dni (Dynadot Inc), acrosscommunities.live — +57 dni (Dynadot Inc), healthlinkq.pro — +57 dni
(NICENIC), novumfy.com — +76 dni (NameSilo, LLC), oceanicbay.info — +70 dni (Sav.com, LLC),
ineptsolidoval.top — −10 dni (Namecheap Inc.), crimsonbase.pro — +29 dni (Dynadot Inc).

### 2.5 Platformy inwestycyjne i fałszywe banki

Strony imitujące platformy tradingowe i banki (część materiałów z list AA419). **Co je łączy:**
ten sam szablon wizualny (koszyk obrazów: wykresy, awatary, certyfikaty), zbliżona treść
(cos 0.94–0.97), profesjonalne tytuły z nazwą „instytucji", domeny w tanich rejestratorach.

- **K17** — wzorzec bramki: 4 kopie „Downloading Document" (szablon CSS 1.00) prowadzące do
  2 kopii platformy „CENTRE POINT MARKETS • Home" (centrepointmarkets.com). Bramka i platforma
  łączą się wspólną grafiką.
- **K08 (część)** — avextrade.com, CrystalFin (crystalfinbn.live),
  Exos Credit Savings (exoscredsavings.top, utworzona 2026-10-31, NameSilo).
- **K38** — trzy bliźniacze banki: „Home - Grand Allied Trust" (grandalliedtrust.com, utworzona
  2026-08-10, Global Domain Group LLC), „Home - United Commercial" (unitedcob.live),
  „Home - WellTrue Credit" (welltruecred.com); treść cos=0.97, 6 wspólnych obrazów.
- Singletony: K35 „Equity Meb — Trade Apple, NVIDIA, Tesla…", K37 „FintPrime — Funded Stock
  Trading", K40 „Lennox Credit Union", K43 „Standard Credit Savings Bank", K44 „Trust Swinci
  Bank".

Liczebność: **8 kampanii, 18 incydentów** (K08 liczony częściowo — 4 materiały).

### 2.6 Pozostałe zaobserwowane wzorce

- **Fałszywi kurierzy / logistyka** — K36: ExpatMova, „Flash Exoress Delivery" [pisownia
  oryginalna], Kwik Logistics Hub, Nektas Parcel (treść cos=0.94–0.96, 28–32 wspólnych obrazów);
  K42: SPEEDEX LOGISTICS (speedexlogisticscompany.com).
- **Hazard / bukmacherka** — K27: „ManBetX(万博体育)…" (cn.wfyyacvv.com:9587), K04: „App Store –
  Słodka Bonanza" (shop-77vault.xyz; wizerunek Jeffa Bezosa). **Inne pary duplikatów** — K18
  „RFP Invitation", K31 „Viewer", K24 „Artist Against 419".
- **Materiały referencyjne** (do kalibracji pipeline'u, niebędące oszustwami) — K19 (strony
  roblox.com), K39 (strona IRS z domenami digitalgov.gov / treasury.gov), K20 („Simple
  Blur"), K22 („Home", weebly.com). Służą jako test, czy detektor nie skleja materiałów przez
  wspólne CDN-y.

## 3. Statystyki zbioru

**Kampanie wg kategorii** (kategorie nierozłączne — K26 i K08 zaliczone do dwóch):

| Kategoria | Kampanie | Incydenty |
|---|---|---|
| 2.1 Phishing logowania na marki | 15 | 29 |
| 2.2 Duplikaty 1:1 (przekrojowo) | 16 (z krawędzią cos=1.00) | 20 krawędzi |
| 2.3 Wspólna infrastruktura | 5 | 28 |
| 2.4 Artykuły sensacyjne z celebrytami | 3 (+3 pokrewne singletony) | 6 (+3) |
| 2.5 Platformy inwestycyjne / fałszywe banki | 8 | 18 |
| 2.6 Pozostałe (kurierzy, hazard, referencyjne) | 14 | 26 |

**Rejestratorzy** (245 rekordów RDAP; 181 to nieudane zapytania — 177 HTTP 429 i 4 HTTP 404,
bez danych rejestratora): MarkMonitor Inc. 18, GoDaddy.com 8, NameSilo 6, get.gov 5, NameCheap 5,
Tucows 4, Dynadot Inc 3, NICENIC 2, Nominet UK 2, CSC Corporate Domains 2. Dominacja MarkMonitor
to efekt domen marek i CDN-ów ładowanych przez strony;
wśród domen **oszukanych** powtarzają się tanio i szybko rejestrowane: NameSilo, Dynadot,
NameCheap, NICENIC, Global Domain Group, Sav.com.

**Domeny** — 168 odrębnych, 356 wystąpień. Najczęstsze to infrastruktura K19 (js.rbxcdn.com 14,
roblox.com 12, images.rbxcdn.com 10, www.roblox.com 9, tr.rbxcdn.com 7) oraz hostingi builderów
(cdn3.editmysite.com 4, cdn.tailwindcss.com 4). TLD rejestrowalnych domen: com 205, org 9, me 7,
gov 7, io 5, live 4, net 4, ms 4, pro 3, top 2.

**Trackery** — 41 wystąpień identyfikatorów: UA-26810151-2 ×14 i UA-486632-1 ×14 (kampania K19),
FB_2012165449475163 ×2 (K01), UA-119765380-3 ×2, GTM-WDBL3P ×2, pozostałe pojedynczo (m.in.
AW-18463917747 w K07). Rozpoznane usługi: facebook-pixel 4, google-analytics 1 (36 wystąpień bez
etykiety usługi). Ta sama para ID analityki odpowiada za 94 twarde krawędzie.

**Świeżość domen** — 62 rekordy RDAP mają datę utworzenia (40 odrębnych domen). **3 odrębne
domeny powstały ≤30 dni od pierwszego zrzutu** (od +20 do +30 dni), 24 są starsze niż rok
(domeny marek i CDN-ów). Świeże domeny to wyłącznie domeny kampanii
oszukańczych:
puuuuuush-king.org +20d, crimsonbase.pro +29d, glowpixel.org +30d.

**Wizerunki osób** (baza referencyjna): Mateusz Morawiecki ×3, Monika Olejnik ×3, Krzysztof
Ibisz ×2, Jeff Bezos ×1, Kuba Wojewódzki ×1; przesłanka „ta sama osoba" zbudowała 2 krawędzie.

**Przesłanki na krawędziach** (166 krawędzi): obrazy 98, struktura CSS 145, wzorzec domen 115,
wspólne domeny 114, treść 98, trackery 94, tytuł 40 (39 identycznych + 1 prawie identyczny),
twarze 2. Wśród 155 twardych krawędzi przesłanki twarde rozkładają się: warianty graficzne 97,
te same ID analityki 94, ten sam tytuł 39, ta sama osoba 2 (krawędź może mieć kilka przesłanek).

## 4. Lekcje dla detekcji i dalszy rozwój

**Które cechy najsilniej łączą.** Najpewniejsze przesłanki: identyczny tytuł (39 krawędzi),
te same ID analityki (94) i warianty graficzne (97) — one czynią krawędź twardą. Struktura CSS
i wzorce nazw domen są użyteczne, ale same potrafią przeszacować (K21: CSS 1.00 przy pustych
tytułach daje krawędzie miękkie; wspólny szablon to często boilerplate frameworków). Treść jest
wiarygodna dopiero od cos>0.30 przy tekstach ≥200 znaków.

**Próg krawędzi.** Próg 0.25 z wagami normalizowanymi do dostępnych widoków daje gęsty, ale
czytelny graf: min score 0.2621 (para K02 oparta na tekście i twarzy), średnia 0.672. Krawędzie
w paśmie 0.25–0.50 (39) to hipotezy do weryfikacji, twarde przesłanki — automatyczny pewnik.

**Odporność na niekompletność.** 181 z 245 rekordów RDAP nie ma rejestratora, część materiałów
nie ma tytułu ani domen — mimo to pipeline nie gubi powiązań: każdy widok działa niezależnie,
a wagi normalizują się do tego, co dostępne. Dla niepołączonych par liczone są też przesłanki
*przeciwko* (negatywne) — pokazują, dlaczego materiały pozostały rozdzielone.

**Rekomendacje detekcyjne** (wprost z danych): (1) świeża domena (≤30 dni, tani rejestrator)
plus tytuł z nazwą marki i „log in" to silny sygnał phishingu; (2) ta sama para ID GA/Pixel/GTM
na różnych domenach wskazuje jednego operatora; (3) ten sam zestaw grafik („kit") łączy różne
pionki oszustwa (K08); (4) reklamy Meta i wersje www kampanii mają identyczny tytuł i piksel —
warto korelować feed reklam z harvestem stron (K01, K07); (5) twarze z bazy referencyjnej
łapią kampanie o różnych tekstach (K02).

**Jak rozszerzać zbiór.** Nowe materiały wchodzą przez upload, adres URL lub harvest z feedów
(OpenPhish, lista fałszywych banków AA419): przekroczenie progu przypisuje materiał do kampanii,
w przeciwnym razie powstaje nowy klaster. Nowe wzorce oszustw pojawiają się więc naturalnie jako
nowe kampanie z własną etykietą przesłanek; kategorie z sekcji 2 można rozbudowywać (np.
fałszywi kurierzy i hazard, już widoczne w zbiorze).

## 5. Pliki źródłowe

- `kfk.sqlite` — 103 incydentów (cechy: tytuły, obrazy, infra/RDAP, trackery, twarze), 166
  krawędzi z dowodami, 45 klastrów; `kfk.graph.json` — graf dla UI;
- `kfk.stix.json` — pakiet STIX 2.1 (692 obiekty), `kfk.ioc.csv` — 391 wierszy IoC;
- `data/do_udostępnienia/` — 103 katalogi materiałów źródłowych;
- `kfk/similarity.py` — wagi widoków i przesłanki, `kfk/cluster.py` — Louvain.
