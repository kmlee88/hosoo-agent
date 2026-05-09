from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

OWNED_PLACE_LABELS = [
    ("잠실점", ("잠실",)),
    ("홍대점", ("홍대",)),
    ("혜화점", ("혜화", "대학로")),
    ("성수점", ("성수연무장", "연무장"), ("성수",)),
    ("연무장", ("성수연무장", "연무장")),
    ("제주점", ("제주",)),
]
FRANCHISE_PLACE_ORDER = [
    "수원행궁",
    "광안리",
    "광주",
    "부산",
    "분당",
    "수원인계",
    "부천",
    "안양",
    "전주한옥마을",
    "의정부",
    "송도트리플",
    "대구",
    "대전",
    "부평",
    "울산",
    "안산",
    "천안",
]


@dataclass(frozen=True)
class ReservationSnapshot:
    collected_date: str
    collected_at: str | None
    place_id: str
    name: str
    confirmed_reservations: int
    used_reservations: int
    used_month_to_date: int | None = None
    error: str | None = None


def _read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def list_snapshot_dates(snapshots_dir: Path, prefix: str) -> list[str]:
    dates: list[str] = []
    for path in snapshots_dir.glob(f"{prefix}-*.json"):
        stem = path.stem
        value = stem.replace(f"{prefix}-", "", 1)
        if value:
            dates.append(value)
    return sorted(set(dates), reverse=True)


def _shift_date(value: str, days: int) -> str:
    return (datetime.strptime(value, "%Y-%m-%d").date() + timedelta(days=days)).isoformat()


def list_report_dates(snapshots_dir: Path) -> list[str]:
    reservation_dates = set(list_snapshot_dates(snapshots_dir, "reservations"))
    review_report_dates = {
        _shift_date(snapshot_date, 1)
        for snapshot_date in list_snapshot_dates(snapshots_dir, "reviews")
        if has_successful_review_data(load_review_snapshots(snapshots_dir, snapshot_date))
    }
    return sorted(reservation_dates | review_report_dates, reverse=True)


def latest_snapshot_date(snapshots_dir: Path, prefix: str) -> str | None:
    dates = list_snapshot_dates(snapshots_dir, prefix)
    return dates[0] if dates else None


def load_review_snapshots(snapshots_dir: Path, target_date: str | None = None) -> list[dict[str, Any]]:
    selected_date = target_date or latest_snapshot_date(snapshots_dir, "reviews")
    if not selected_date:
        return []

    path = snapshots_dir / f"reviews-{selected_date}.json"
    if not path.exists():
        return []
    raw = _read_json(path)
    return raw if isinstance(raw, list) else []


def has_successful_review_data(snapshots: list[dict[str, Any]]) -> bool:
    return any(snapshot.get("total_reviews") is not None and not snapshot.get("error") for snapshot in snapshots)


def latest_successful_review_date(snapshots_dir: Path) -> str | None:
    for snapshot_date in list_snapshot_dates(snapshots_dir, "reviews"):
        if has_successful_review_data(load_review_snapshots(snapshots_dir, snapshot_date)):
            return snapshot_date
    return None


def previous_successful_review_date(snapshots_dir: Path, selected_date: str) -> str | None:
    dates = [snapshot_date for snapshot_date in list_snapshot_dates(snapshots_dir, "reviews") if snapshot_date < selected_date]
    for snapshot_date in dates:
        if has_successful_review_data(load_review_snapshots(snapshots_dir, snapshot_date)):
            return snapshot_date
    return None


def load_reservation_snapshots(snapshots_dir: Path, target_date: str | None = None) -> list[ReservationSnapshot]:
    selected_date = target_date or latest_snapshot_date(snapshots_dir, "reservations")
    if not selected_date:
        return []

    json_path = snapshots_dir / f"reservations-{selected_date}.json"
    csv_path = snapshots_dir / f"reservations-{selected_date}.csv"
    if json_path.exists():
        raw = _read_json(json_path)
        rows = raw if isinstance(raw, list) else []
    elif csv_path.exists():
        with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
            rows = list(csv.DictReader(file))
    else:
        return []

    snapshots: list[ReservationSnapshot] = []
    for row in rows:
        snapshots.append(
            ReservationSnapshot(
                collected_date=str(row.get("collected_date") or selected_date),
                collected_at=str(row.get("collected_at") or "") or None,
                place_id=str(row.get("place_id") or ""),
                name=str(row.get("short_name") or row.get("name") or ""),
                confirmed_reservations=_safe_int(
                    row.get("confirmed_reservations", row.get("confirmed_count", 0))
                ),
                used_reservations=_safe_int(row.get("used_reservations", row.get("used_count", 0))),
                used_month_to_date=(
                    _safe_int(row.get("used_month_to_date", row.get("usedMonthToDate")))
                    if row.get("used_month_to_date", row.get("usedMonthToDate")) is not None
                    else None
                ),
                error=str(row.get("error") or "") or None,
            )
        )
    return snapshots


def previous_reservation_date(snapshots_dir: Path, selected_date: str) -> str | None:
    dates = [snapshot_date for snapshot_date in list_snapshot_dates(snapshots_dir, "reservations") if snapshot_date < selected_date]
    return dates[0] if dates else None


def save_reservation_snapshots(snapshots: list[ReservationSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [
        {
            key: value
            for key, value in snapshot.__dict__.items()
            if value is not None
        }
        for snapshot in snapshots
    ]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _snapshot_key(snapshot: dict[str, Any]) -> str:
    return str(snapshot.get("place_id") or snapshot.get("name") or "")


def _owned_place_display_name(name: str) -> str:
    for label, *alias_groups in OWNED_PLACE_LABELS:
        include_aliases = alias_groups[-1]
        exclude_aliases = alias_groups[0] if len(alias_groups) > 1 else ()
        if any(alias in name for alias in include_aliases) and not any(alias in name for alias in exclude_aliases):
            return label
    return name


def _owned_place_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    name = str(row.get("name") or "")
    for index, (label, *_) in enumerate(OWNED_PLACE_LABELS):
        if _owned_place_display_name(name) == label:
            return index, name
    return len(OWNED_PLACE_LABELS), name


def _franchise_place_sort_key(row: dict[str, Any]) -> tuple[int, str]:
    name = str(row.get("name") or "")
    for index, label in enumerate(FRANCHISE_PLACE_ORDER):
        if label in name:
            return index, name
    return len(FRANCHISE_PLACE_ORDER), name


def summarize_reviews(
    snapshots: list[dict[str, Any]],
    previous_snapshots: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    totals_by_type: dict[str, int] = defaultdict(int)
    receipt_by_type: dict[str, int] = defaultdict(int)
    total_reviews_by_type: dict[str, int] = defaultdict(int)
    error_count = 0
    review_rows: list[dict[str, Any]] = []
    word_counter: Counter[str] = Counter()
    has_previous_snapshots = previous_snapshots is not None
    previous_by_key = {
        _snapshot_key(snapshot): _safe_int(snapshot.get("daily_reviews"))
        for snapshot in previous_snapshots or []
    }
    previous_totals_by_type: dict[str, int] = defaultdict(int)
    for snapshot in previous_snapshots or []:
        previous_totals_by_type[str(snapshot.get("type") or "기타")] += _safe_int(snapshot.get("daily_reviews"))

    for snapshot in snapshots:
        place_type = str(snapshot.get("type") or "기타")
        daily_reviews = _safe_int(snapshot.get("daily_reviews"))
        receipt_reviews = _safe_int(snapshot.get("daily_receipt_reviews"))
        total_reviews = snapshot.get("total_reviews")
        previous_daily_reviews = previous_by_key.get(_snapshot_key(snapshot))
        if snapshot.get("error"):
            error_count += 1

        totals_by_type[place_type] += daily_reviews
        receipt_by_type[place_type] += receipt_reviews
        if total_reviews is not None:
            total_reviews_by_type[place_type] += _safe_int(total_reviews)

        review_rows.append(
            {
                "placeId": snapshot.get("place_id"),
                "name": _owned_place_display_name(str(snapshot.get("name") or ""))
                if place_type == "당사"
                else snapshot.get("name"),
                "type": place_type,
                "dailyReviews": daily_reviews,
                "dailyDelta": None
                if previous_daily_reviews is None
                else daily_reviews - previous_daily_reviews,
                "previousDailyReviews": previous_daily_reviews,
                "receiptReviews": receipt_reviews,
                "totalReviews": total_reviews,
                "error": snapshot.get("error"),
            }
        )

        for review in snapshot.get("reviews") or []:
            body = str(review.get("body") or "")
            tags = review.get("tags") or []
            for token in [*tags, *body.split()]:
                cleaned = token.strip("#.,!?()[]{}\"'“”‘’").lower()
                if len(cleaned) >= 2:
                    word_counter[cleaned] += 1

    own_places = [row for row in review_rows if row["type"] == "당사"]
    franchise_places = [row for row in review_rows if row["type"] == "가맹점"]
    competitor_places = [row for row in review_rows if row["type"] == "경쟁사"]
    own_places = sorted(own_places, key=_owned_place_sort_key)
    franchise_places = sorted(franchise_places, key=_franchise_place_sort_key)
    competitor_places = sorted(
        competitor_places,
        key=lambda row: (row["dailyReviews"], row["name"]),
        reverse=True,
    )
    if has_previous_snapshots:
        total_deltas_by_type = {
            place_type: totals_by_type[place_type] - previous_totals_by_type[place_type]
            for place_type in set(totals_by_type) | set(previous_totals_by_type)
        }
    else:
        total_deltas_by_type = {place_type: None for place_type in totals_by_type}

    current_our = totals_by_type.get("당사", 0)
    current_competitor = totals_by_type.get("경쟁사", 0)
    previous_our = previous_totals_by_type.get("당사", 0)
    previous_competitor = previous_totals_by_type.get("경쟁사", 0)
    current_denominator = current_our + current_competitor
    previous_denominator = previous_our + previous_competitor
    market_share = (current_our / current_denominator * 100) if current_denominator else 0
    previous_market_share = (
        previous_our / previous_denominator * 100
        if has_previous_snapshots and previous_denominator
        else None
    )

    return {
        "totalsByType": dict(totals_by_type),
        "totalDeltasByType": total_deltas_by_type,
        "marketShare": market_share,
        "marketShareDelta": None
        if previous_market_share is None
        else market_share - previous_market_share,
        "receiptByType": dict(receipt_by_type),
        "totalReviewsByType": dict(total_reviews_by_type),
        "errorCount": error_count,
        "places": own_places + franchise_places + competitor_places,
        "ourPlaces": own_places,
        "franchisePlaces": franchise_places,
        "competitorPlaces": competitor_places,
        "keywords": [
            {"keyword": keyword, "count": count}
            for keyword, count in word_counter.most_common(12)
        ],
    }


def summarize_reservations(
    snapshots: list[ReservationSnapshot],
    previous_snapshots: list[ReservationSnapshot] | None = None,
) -> dict[str, Any]:
    previous_by_place = {
        snapshot.place_id: snapshot.confirmed_reservations
        for snapshot in previous_snapshots or []
    }
    previous_used_by_place = {
        snapshot.place_id: snapshot.used_reservations
        for snapshot in previous_snapshots or []
    }
    has_previous_snapshots = previous_snapshots is not None
    total = sum(snapshot.confirmed_reservations for snapshot in snapshots)
    total_used = sum(snapshot.used_reservations for snapshot in snapshots)
    previous_total = sum(snapshot.confirmed_reservations for snapshot in previous_snapshots or [])
    previous_total_used = sum(snapshot.used_reservations for snapshot in previous_snapshots or [])
    month_used_by_place = {
        snapshot.place_id: snapshot.used_month_to_date
        for snapshot in snapshots
        if snapshot.used_month_to_date is not None
    }
    rows = [
        {
            "placeId": snapshot.place_id,
            "name": _owned_place_display_name(snapshot.name),
            "confirmedReservations": snapshot.confirmed_reservations,
            "usedReservations": snapshot.used_reservations,
            "usedMonthToDate": month_used_by_place.get(snapshot.place_id),
            "dailyDelta": None
            if snapshot.place_id not in previous_by_place
            else snapshot.confirmed_reservations - previous_by_place[snapshot.place_id],
            "usedDelta": None
            if snapshot.place_id not in previous_used_by_place
            else snapshot.used_reservations - previous_used_by_place[snapshot.place_id],
            "error": snapshot.error,
        }
        for snapshot in snapshots
    ]
    collected_at_values = [snapshot.collected_at for snapshot in snapshots if snapshot.collected_at]
    return {
        "totalConfirmed": total,
        "totalUsed": total_used,
        "totalUsedMonthToDate": sum(month_used_by_place.values()) if month_used_by_place else None,
        "totalDelta": None if not has_previous_snapshots else total - previous_total,
        "totalUsedDelta": None if not has_previous_snapshots else total_used - previous_total_used,
        "collectedAt": max(collected_at_values) if collected_at_values else None,
        "stores": sorted(rows, key=_owned_place_sort_key),
        "errorCount": sum(1 for snapshot in snapshots if snapshot.error),
    }


def build_dashboard_payload(root_dir: Path, target_date: str | None = None) -> dict[str, Any]:
    snapshots_dir = root_dir / "snapshots"
    report_date = (
        target_date
        or latest_snapshot_date(snapshots_dir, "reservations")
        or (_shift_date(latest_successful_review_date(snapshots_dir), 1) if latest_successful_review_date(snapshots_dir) else None)
        or date.today().isoformat()
    )
    review_date = _shift_date(report_date, -1)
    reviews = load_review_snapshots(snapshots_dir, review_date)
    previous_review_date = previous_successful_review_date(snapshots_dir, review_date)
    previous_reviews = load_review_snapshots(snapshots_dir, previous_review_date) if previous_review_date else None
    reservation_date = report_date
    reservations = load_reservation_snapshots(snapshots_dir, reservation_date)
    previous_reservation_snapshot_date = previous_reservation_date(snapshots_dir, reservation_date)
    previous_reservations = (
        load_reservation_snapshots(snapshots_dir, previous_reservation_snapshot_date)
        if previous_reservation_snapshot_date
        else None
    )

    return {
        "date": report_date,
        "reviewDate": review_date,
        "previousReviewDate": previous_review_date,
        "reservationDate": reservation_date,
        "previousReservationDate": previous_reservation_snapshot_date,
        "availableDates": list_report_dates(snapshots_dir),
        "reviews": summarize_reviews(reviews, previous_reviews),
        "reservations": summarize_reservations(reservations, previous_reservations),
        "dataStatus": {
            "hasReviews": bool(reviews),
            "hasReservations": bool(reservations),
        },
    }
