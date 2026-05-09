from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))
os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(ROOT_DIR / ".playwright-browsers"))

from hosoo_agent.naver_reservations import (  # noqa: E402
    append_reservation_history,
    collect_historical_reservation_metrics,
    collect_today_confirmed_reservations,
    load_reservation_places,
    save_reservation_snapshots,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Naver booking confirmed reservations.")
    parser.add_argument("--places", default=str(ROOT_DIR / "data" / "reservation_places.json"))
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--out-dir", default=str(ROOT_DIR / "snapshots"))
    parser.add_argument("--history-file", default=str(ROOT_DIR / "snapshots" / "reservations-history.jsonl"))
    parser.add_argument("--latest-web-file", default=str(ROOT_DIR / "web" / "reservation-latest.json"))
    parser.add_argument("--previous-web-file", default=str(ROOT_DIR / "web" / "reservation-previous.json"))
    parser.add_argument("--profile-dir", default=str(ROOT_DIR / ".browser-profile" / "naver"))
    parser.add_argument(
        "--mode",
        choices=["today", "historical"],
        default="today",
        help="today reads the dashboard cards; historical reads booking list filters for the selected date.",
    )
    parser.add_argument(
        "--backfill-previous",
        action="store_true",
        help="After today's collection, create yesterday's daily snapshot if it is missing.",
    )
    parser.add_argument("--headed", action="store_true", help="Show browser window for login and debugging.")
    parser.add_argument("--slow-mo", type=int, default=0)
    return parser.parse_args()


async def run() -> None:
    args = parse_args()
    target_date = date.fromisoformat(args.date)
    collected_at = datetime.now().astimezone().isoformat(timespec="seconds")
    places = load_reservation_places(Path(args.places))

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise SystemExit("Playwright is required. Install with: pip install playwright && playwright install chromium") from exc

    print(f"Collecting reservation metrics for {target_date.isoformat()} ({len(places)} places, mode={args.mode})")
    async with async_playwright() as playwright:
        context = await playwright.chromium.launch_persistent_context(
            user_data_dir=args.profile_dir,
            headless=not args.headed,
            slow_mo=args.slow_mo,
            viewport={"width": 1440, "height": 1000},
        )
        page = context.pages[0] if context.pages else await context.new_page()

        async def collect_for_date(collection_date: date, mode: str):
            snapshots = []
            for place in places:
                if mode == "historical":
                    snapshot = await collect_historical_reservation_metrics(page, place, collection_date, collected_at)
                else:
                    snapshot = await collect_today_confirmed_reservations(page, place, collection_date, collected_at)
                snapshots.append(snapshot)
                value = "-" if snapshot.confirmed_reservations is None else snapshot.confirmed_reservations
                used_value = "-" if snapshot.used_reservations is None else snapshot.used_reservations
                status = f"ERROR: {snapshot.error}" if snapshot.error else "OK"
                print(f"- {place.short_name}: confirmed {value}, used {used_value} ({status})")
            return snapshots

        snapshots = await collect_for_date(target_date, args.mode)

        previous_snapshots = None
        previous_date = target_date - timedelta(days=1)
        previous_path = Path(args.out_dir) / f"reservations-{previous_date.isoformat()}.json"
        if args.backfill_previous and args.mode == "today" and not previous_path.exists():
            print(f"Previous reservation snapshot is missing; backfilling {previous_date.isoformat()}")
            previous_snapshots = await collect_for_date(previous_date, "historical")

        await context.close()

    append_reservation_history(snapshots, Path(args.history_file))

    total = sum(snapshot.confirmed_reservations or 0 for snapshot in snapshots)
    total_used = sum(snapshot.used_reservations or 0 for snapshot in snapshots)
    failures = [snapshot for snapshot in snapshots if snapshot.error]
    successes = [snapshot for snapshot in snapshots if snapshot.confirmed_reservations is not None and not snapshot.error]
    out_path = Path(args.out_dir) / f"reservations-{target_date.isoformat()}.json"
    if successes:
        save_reservation_snapshots(snapshots, out_path)
        latest_payload = {
            "reservationDate": target_date.isoformat(),
            "collectedAt": collected_at,
            "totalConfirmed": total,
            "totalUsed": total_used,
            "stores": [snapshot.__dict__ for snapshot in snapshots],
        }
        Path(args.latest_web_file).write_text(
            json.dumps(latest_payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"Saved JSON: {out_path}")
        print(f"Saved latest web metadata: {args.latest_web_file}")
    else:
        print(f"Skipped daily JSON update because every place failed: {out_path}")
    print(f"Appended history: {args.history_file}")
    print(f"Total confirmed reservations: {total}")
    print(f"Total used reservations: {total_used}")
    if failures:
        print(f"Failures: {len(failures)}")

    if previous_snapshots is not None:
        previous_total = sum(snapshot.confirmed_reservations or 0 for snapshot in previous_snapshots)
        previous_total_used = sum(snapshot.used_reservations or 0 for snapshot in previous_snapshots)
        previous_failures = [snapshot for snapshot in previous_snapshots if snapshot.error]
        previous_successes = [
            snapshot
            for snapshot in previous_snapshots
            if snapshot.confirmed_reservations is not None and not snapshot.error
        ]
        append_reservation_history(previous_snapshots, Path(args.history_file))
        if previous_successes:
            save_reservation_snapshots(previous_snapshots, previous_path)
            previous_payload = {
                "reservationDate": previous_date.isoformat(),
                "collectedAt": collected_at,
                "totalConfirmed": previous_total,
                "totalUsed": previous_total_used,
                "stores": [snapshot.__dict__ for snapshot in previous_snapshots],
            }
            Path(args.previous_web_file).write_text(
                json.dumps(previous_payload, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            print(f"Saved previous JSON: {previous_path}")
        else:
            print(f"Skipped previous JSON update because every place failed: {previous_path}")
        print(f"Previous confirmed reservations: {previous_total}")
        print(f"Previous used reservations: {previous_total_used}")
        if previous_failures:
            print(f"Previous failures: {len(previous_failures)}")


if __name__ == "__main__":
    asyncio.run(run())
