#!/usr/bin/env python3
"""Generuje demonstracyjne zrzuty reklam (3 wzorce produkcyjne + delikatny szum).

Kampania A - wzorzec inwestycyjny (czerwony baner, biała karta, złoty przycisk CTA)
Kampania B - wzorzec 'cudowna dieta' (zielony, charakterystyczne koło)
Kampania C - wzorzec 'wycofanie środków' (niebieski, dwa pasy)
Wariant w obrębie kampanii = ten sam szablon + drobne przesunięcia/szum -> podobny dHash.
"""
import json
import random
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent.parent
ADS = ROOT / "data" / "ads"
ADS.mkdir(parents=True, exist_ok=True)


def ad_a(i: int, title: str, sub: str) -> Image.Image:
    img = Image.new("RGB", (640, 360), (245, 240, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 640, 64], fill=(180, 25, 25))
    d.rectangle([20, 90, 620, 200], fill=(255, 255, 255), outline=(60, 60, 60))
    d.text((30 + (i % 3), 100), title, fill=(20, 20, 20))
    d.text((30, 215), sub, fill=(60, 60, 60))
    d.rectangle([20, 260, 300, 320], fill=(255, 190, 0))
    d.ellipse([520, 280, 600, 345], fill=(180, 25, 25))
    return img


def ad_b(i: int, title: str, sub: str) -> Image.Image:
    img = Image.new("RGB", (640, 360), (235, 245, 235))
    d = ImageDraw.Draw(img)
    d.ellipse([40, 20, 220, 200], fill=(30, 140, 60))
    d.ellipse([60, 40 - (i % 2), 200, 180], outline=(255, 255, 255), width=4)
    d.rectangle([240, 60, 620, 110], fill=(255, 255, 255))
    d.text((250, 65), title, fill=(20, 60, 30))
    d.text((250, 130), sub, fill=(40, 80, 50))
    d.rectangle([240, 250, 620, 300], fill=(255, 120, 0))
    return img


def ad_c(i: int, title: str, sub: str) -> Image.Image:
    img = Image.new("RGB", (640, 360), (235, 238, 248))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 120, 640, 180], fill=(20, 60, 180))
    d.rectangle([0, 190, 640, 250], fill=(90, 130, 220))
    d.text((20, 20 + (i % 2) * 5), title, fill=(10, 20, 60))
    d.text((20, 280), sub, fill=(40, 50, 90))
    d.rectangle([480, 20, 620, 90], fill=(255, 200, 0))
    return img


NS_PER_CAMP = {
    "A": ["dns1.cloud-fast.ns", "dns2.cloud-fast.ns"],
    "B": ["ns1.dns-simple.cc", "ns2.dns-simple.cc"],
    "C": ["ns1.dns-cheap.ru", "ns2.dns-cheap.ru"],
}
IP_PREFIX = {"A": "45.12.10", "B": "185.77.9", "C": "91.204.3"}

CAMPAIGNS = [
    # kampania A: fałszywa inwestycja krypto "z wizerunkiem Lewandowskiego"
    dict(rid="A", artist=ad_a, domains=[
        ("a1", "lewandowski-inwestycja.today", "LEWANDOWSKI INWESTUJE?",
         "Sekretny kurs: 5 000 zł zysku już dziś"),
        ("a2", "rl-inwestycja.cyou", "ROBERT LEWANDOWSKI ODKRYL SYSTEM",
         "Kryptowaluta bitcoin zysk 5 000 zł gwarantowany dochód"),
        ("a3", "kurs-lewandowski.buzz", "LEWANDOWSKI: NOWA INWESTYCJA",
         "Webinar kryptowaluta bitcoin bonus wypłata portfel"),
        ("a4", "lewa-inwest.top", "LEWANDOWSKI INWESTUJE W BITCOIN",
         "System kryptowaluta zysk dochód wypłata pierwsza emisja"),
        ("a5", "a-kampania.click", "PREMIUM TARCZA FINANSOWA",  # wariant SZABLONU, inna narracja
         "Zupełnie inna treść, brak słów kluczowych kampanii"),
    ]),
    # kampania B: cudowna dieta / tabletki "z Okafor"
    dict(rid="B", artist=ad_b, domains=[
        ("b1", "dieta-okafor.fit", "CUDOWNA DIETA DOKTOR OKAFOR",
         "Tabletki odchudzanie keto dieta -12 kg w 7 dni"),
        ("b2", "okafor-tabletki.rest", "DIETA OKAFOR: EFEKT PO 7 DNIACH",
         "Suplement odchudzanie cukrzyca tabletki keto detoks"),
        ("b3", "zdrowa-dieta.buzz", "OKAFOR POZIOM CUKRU",
         "Dieta keto suplement nadciśnienie tabletki odchudzanie"),
    ]),
    # kampania C: "wycofanie środków z platformy" (narracja DE/PL)
    dict(rid="C", artist=ad_c, domains=[
        ("c1", "sofy-portfel.verify", "TWOJE SRODKI SA ZABLOKOWANE",
         "Portfel sofy natychmiast wycofanie alpha wypłata"),
        ("c2", "sofy-wallet.check", "WYPLATA SRODKOW TERAZ",
         "Sofy portfel natychmiast wycofanie wypłata dostępne"),
        ("c3", "alpha-balance.sbs", "DATENSCHUTZ MITTEILUNG 1420 EUR",
         "Portfel natychmiast wycofanie alpha auszahlung sofort"),
    ]),
]

LONERS = [
    ("d1", "kredyt-oferta-2025", "Niski kredyt gotówkowy bez bik Sprawdź ofertę emerytura renta"),
    ("d2", "uzywane-samochody", "Używane samochody z Niemiec sprowadzanie galeria pojazdy"),
]


def noise(img: Image.Image, seed: int) -> Image.Image:
    rnd = random.Random(seed)
    px = img.load()
    for _ in range(300):
        x, y = rnd.randrange(img.width), rnd.randrange(img.height)
        r, g, b = px[x, y]
        d = rnd.randint(-14, 14)
        px[x, y] = (max(0, r + d), max(0, g + d), max(0, b + d))
    return img


def main():
    records = []
    for camp in CAMPAIGNS:
        rid = camp["rid"]
        for idx, (mid, dom, title, sub) in enumerate(camp["domains"]):
            p = ADS / f"ad_{mid}.png"
            img = noise(camp["artist"](idx, title, sub), seed=idx * 31 + ord(rid))
            img.save(p)
            records.append(dict(
                id=mid,
                source="dataset",
                url=f"https://{dom}/landing",
                text=f"{title}. {sub}.",
                image=str(p.relative_to(ROOT)),
                redirect_chain=[f"https://tracker-{rid.lower()}-{idx}.net/c",
                                f"https://jump-{rid.lower()}{idx % 2}.top/x"],
                ns=NS_PER_CAMP[rid],
                mx=[f"mail.{rid.lower()}-mail{idx % 2}.pro"],
                ip=f"{IP_PREFIX[rid]}.{(idx * 7) % 200 + 20}",
            ))
    for mid, slug, text in LONERS:
        records.append(dict(
            id=mid, source="manual", url=f"https://example-{slug}.com/ad", text=text,
        ))
    out = ROOT / "data" / "demo_materials.jsonl"
    out.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in records),
                   encoding="utf-8")
    print(f"Zapisano {len(records)} materiałów -> {out}")


if __name__ == "__main__":
    main()
