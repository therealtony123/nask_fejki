#!/usr/bin/env python3
"""Lekki, cykliczny runner: co zadany interwał zbiera świeże podejrzane strony
i przelicza pipeline KOLEKCJONERA FEJKÓW (bonus "okresowe aktualizowanie informacji").

Jeden cykl = uruchomienie `harvest_urls.py` jako podproces (z `--run-pipeline`,
chyba że podano `--skip-pipeline`) w katalogu projektu. Runner sam nie importuje
`requests`/`kfk` — dzięki temu działa nawet gdy zależności projektu są zepsute,
a błąd jednego cyklu nie zabija pętli.

Użycie:
  .venv/bin/python scripts/scheduler.py                 # co 24 h, źródła: both, 1 strona, max 50
  .venv/bin/python scripts/scheduler.py --once          # jeden cykl i wyjście
  .venv/bin/python scripts/scheduler.py --interval-hours 6 --max 20
  .venv/bin/python scripts/scheduler.py --once --skip-pipeline --source openphish

Uwaga: uruchamiaj tym samym interpreterem, w którym są zależności projektu
(czyli `.venv/bin/python`), bo podproces dostaje `sys.executable`.

Alternatywa (bez trzymania procesu w tle) — crontab (`crontab -e`), co 6 godzin:
  0 */6 * * * cd /home/tymon/kolekcjoner-fejkow && .venv/bin/python harvest_urls.py \
      --source both --pages 1 --max 20 --run-pipeline >> logs/harvest.log 2>&1

Alternatywa — systemd timer (scheduler.service + scheduler.timer, OnUnitActiveSec=24h).
"""
import argparse
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

PROJ = Path(__file__).resolve().parent.parent
HARVEST = PROJ / "harvest_urls.py"


def _ts() -> str:
    """Znacznik czasu do logów."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def log(msg: str) -> None:
    print(f"[{_ts()}] {msg}", flush=True)


def run_cycle(args) -> int:
    """Jeden cykl: harvest (opcjonalnie + pipeline). Zwraca kod wyjścia podprocesu (-1 = błąd)."""
    cmd = [sys.executable, str(HARVEST),
           "--source", args.source,
           "--pages", str(args.pages),
           "--max", str(args.max)]
    if not args.skip_pipeline:
        cmd.append("--run-pipeline")

    log(f"START cyklu: {' '.join(cmd[1:])} (cwd={PROJ})")
    t0 = time.monotonic()
    try:
        rc = subprocess.run(cmd, cwd=str(PROJ)).returncode
    except KeyboardInterrupt:
        raise
    except Exception as e:  # np. brak pliku, brak prawa wykonania
        log(f"BŁĄD uruchomienia podprocesu: {type(e).__name__}: {e}")
        rc = -1
    dt = time.monotonic() - t0
    log(f"KONIEC cyklu: exit={rc}, czas={dt:.1f}s")
    if rc != 0:
        log(f"UWAGA: harvest_urls.py zwrócił {rc} — pętla działa dalej.")
    return rc


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Cykliczny harvester podejrzanych stron + pipeline (bonus: okresowa aktualizacja).",
        epilog="Przykład crona: 0 */6 * * * cd %s && .venv/bin/python harvest_urls.py "
               "--source both --pages 1 --max 20 --run-pipeline" % PROJ)
    ap.add_argument("--interval-hours", type=float, default=24.0,
                    help="Interwał między cyklami w godzinach (domyślnie 24.0)")
    ap.add_argument("--once", action="store_true",
                    help="Wykonaj jeden cykl i wyjdź (bez pętli)")
    ap.add_argument("--source", choices=["openphish", "aa419", "both"], default="both",
                    help="Źródło kandydatów (domyślnie both)")
    ap.add_argument("--pages", type=int, default=1, help="Liczba stron listy AA419 (domyślnie 1)")
    ap.add_argument("--max", type=int, default=50, help="Maks. unikalnych domen na cykl (domyślnie 50)")
    ap.add_argument("--skip-pipeline", action="store_true",
                    help="Tylko zbieranie (bez pipeline.py run)")
    args = ap.parse_args()

    if args.interval_hours <= 0:
        ap.error("--interval-hours musi być > 0")
    if not HARVEST.is_file():
        log(f"BŁĄD: brak {HARVEST}")
        return 2

    if args.once:
        return 0 if run_cycle(args) == 0 else 1

    sleep_s = args.interval_hours * 3600.0
    log(f"Scheduler wystartował: interwał {args.interval_hours:g} h "
        f"(~{sleep_s / 60:.0f} min), źródło={args.source}, pages={args.pages}, "
        f"max={args.max}, pipeline={'NIE' if args.skip_pipeline else 'TAK'}. Ctrl+C kończy.")
    try:
        while True:
            run_cycle(args)
            log(f"Sen {args.interval_hours:g} h do następnego cyklu…")
            time.sleep(sleep_s)
    except KeyboardInterrupt:
        log("Zatrzymano przez użytkownika")
        return 0


if __name__ == "__main__":
    sys.exit(main())
