from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = ROOT_DIR / "src"
sys.path.insert(0, str(SRC_DIR))

from hosoo_agent.naver_place_reviews import (  # noqa: E402
    collect_review_snapshots,
    load_places,
    save_snapshots_csv,
    save_snapshots_json,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect Naver Place review counts.")
    parser.add_argument("--places", default=str(ROOT_DIR / "data" / "places.json"))
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--display", type=int, default=50)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--out-dir", default=str(ROOT_DIR / "snapshots"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    target_date = date.fromisoformat(args.date)
    places = load_places(Path(args.places))

    print(f"Collecting review snapshots for {target_date.isoformat()} ({len(places)} places)")
    snapshots = collect_review_snapshots(
        places=places,
        target_date=target_date,
        display=args.display,
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
    comp_daily = sum(snapshot.daily_reviews or 0 for snapshot in snapshots if snapshot.type == "경쟁사")

    print(f"Saved JSON: {json_path}")
    print(f"Saved CSV: {csv_path}")
    print(f"Our daily reviews: {our_daily}")
    print(f"Competitor daily reviews: {comp_daily}")
    if failures:
        print(f"Failures: {len(failures)}")
        for failure in failures:
            print(f"- {failure.name}: {failure.error}")


if __name__ == "__main__":
    main()
