from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from hosoo_agent.naver_place_reviews import (  # noqa: E402
    collect_review_snapshots,
    detect_latest_review_date,
    load_places,
    save_snapshots_csv,
    save_snapshots_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Naver Place review counts.")
    parser.add_argument("--places", default=str(ROOT_DIR / "data" / "places.json"))
    parser.add_argument(
        "--date",
        default="latest",
        help="YYYY-MM-DD, or latest to use the newest review date visible on Naver.",
    )
    parser.add_argument("--display", type=int, default=50)
    parser.add_argument("--max-pages", type=int, default=5)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--out-dir", default=str(ROOT_DIR / "snapshots"))
    parser.add_argument(
        "--skip-previous",
        action="store_true",
        help="Do not backfill the previous day when its snapshot is missing.",
    )
    return parser.parse_args()


def collect_and_save(args: argparse.Namespace, places, target_date: date) -> tuple[int, int, int]:
    print(f"Collecting review snapshots for {target_date.isoformat()} ({len(places)} places)")
    snapshots = collect_review_snapshots(
        places=places,
        target_date=target_date,
        display=args.display,
        max_pages=args.max_pages,
        delay_seconds=args.delay,
    )

    out_dir = Path(args.out_dir)
    stem = f"reviews-{target_date.isoformat()}"
    json_path = out_dir / f"{stem}.json"
    csv_path = out_dir / f"{stem}.csv"

    save_snapshots_json(snapshots, json_path)
    save_snapshots_csv(snapshots, csv_path)

    failures = [snapshot for snapshot in snapshots if snapshot.error]
    our_daily = sum(snapshot.daily_reviews or 0 for snapshot in snapshots if snapshot.type == "당사")
    franchise_daily = sum(snapshot.daily_reviews or 0 for snapshot in snapshots if snapshot.type == "가맹점")
    comp_daily = sum(snapshot.daily_reviews or 0 for snapshot in snapshots if snapshot.type == "경쟁사")

    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV: {csv_path}")
    print(f"Our daily reviews: {our_daily}")
    print(f"Franchise daily reviews: {franchise_daily}")
    print(f"Competitor daily reviews: {comp_daily}")
    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures:
            print(f"- {failure.name}: {failure.error}")
    return our_daily, comp_daily, len(failures)


def main() -> None:
    args = parse_args()
    places = load_places(Path(args.places))
    if args.date == "latest":
        target_date = detect_latest_review_date(places)
    else:
        target_date = date.fromisoformat(args.date)

    out_dir = Path(args.out_dir)
    previous_date = target_date - timedelta(days=1)
    previous_path = out_dir / f"reviews-{previous_date.isoformat()}.json"

    collect_and_save(args, places, target_date)
    if not args.skip_previous and not previous_path.exists():
        print(f"Previous-day snapshot is missing; backfilling {previous_date.isoformat()}")
        collect_and_save(args, places, previous_date)


if __name__ == "__main__":
    main()
