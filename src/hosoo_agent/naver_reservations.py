from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


BOOKING_URL = "https://new.smartplace.naver.com/bizes/booking/{booking_id}"
BOOKING_LIST_URL = "https://partner.booking.naver.com/bizes/{booking_id}/booking-list-view"


@dataclass(frozen=True)
class ReservationPlace:
    place_id: str
    booking_id: str
    name: str
    short_name: str
    type: str


@dataclass(frozen=True)
class ReservationSnapshot:
    collected_date: str
    collected_at: str
    place_id: str
    booking_id: str
    name: str
    short_name: str
    confirmed_reservations: int | None
    used_reservations: int | None
    error: str | None = None


def load_reservation_places(path: Path) -> list[ReservationPlace]:
    raw_places = json.loads(path.read_text(encoding="utf-8"))
    return [
        ReservationPlace(
            place_id=str(item["place_id"]),
            booking_id=str(item["booking_id"]),
            name=item["name"],
            short_name=item.get("short_name", item["name"]),
            type=item.get("type", "당사"),
        )
        for item in raw_places
    ]


def save_reservation_snapshots(snapshots: list[ReservationSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [snapshot.__dict__ for snapshot in snapshots]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def append_reservation_history(snapshots: list[ReservationSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as file:
        for snapshot in snapshots:
            file.write(json.dumps(snapshot.__dict__, ensure_ascii=False) + "\n")


def _parse_today_count(text: str, label: str) -> int | None:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for index, line in enumerate(lines):
        if line == f"오늘 {label}":
            if index > 0 and lines[index - 1].isdigit():
                return int(lines[index - 1])
            if index + 1 < len(lines) and lines[index + 1].isdigit():
                return int(lines[index + 1])

    compact = re.sub(r"\s+", " ", text).strip()
    patterns = [
        rf"오늘\s*{label}\s*(\d+)",
        rf"(\d+)\s*오늘\s*{label}",
    ]
    for pattern in patterns:
        match = re.search(pattern, compact)
        if match:
            return int(match.group(1))
    return None


def parse_today_confirmed_count(text: str) -> int | None:
    return _parse_today_count(text, "확정")


def parse_today_used_count(text: str) -> int | None:
    return _parse_today_count(text, "이용")


def parse_booking_list_count(text: str) -> int | None:
    compact = re.sub(r"\s+", "", text)
    match = re.search(r"예약(\d+)건", compact)
    if match:
        return int(match.group(1))
    return None


def _booking_list_url(booking_id: str, target_date: date, date_filter: str, status_codes: list[str]) -> str:
    params = [
        *[f"bookingStatusCodes={status_code}" for status_code in status_codes],
        "dateDropdownType=DATE",
        f"dateFilter={date_filter}",
        f"startDateTime={target_date.isoformat()}",
        f"endDateTime={target_date.isoformat()}",
    ]
    return f"{BOOKING_LIST_URL.format(booking_id=booking_id)}?{'&'.join(params)}"


async def collect_today_confirmed_reservations(
    page: Any,
    place: ReservationPlace,
    target_date: date,
    collected_at: str,
    wait_ms: int = 2500,
) -> ReservationSnapshot:
    url = BOOKING_URL.format(booking_id=place.booking_id)
    try:
        await page.goto(url, wait_until="load", timeout=30000)
        await page.wait_for_timeout(wait_ms)
        body_text = await page.locator("body").inner_text(timeout=10000)

        if "네이버 로그인이 필요한 기능" in body_text or "로그인" in body_text and "예약 현황" not in body_text:
            raise RuntimeError("Naver login is required in this browser session.")

        confirmed_count = parse_today_confirmed_count(body_text)
        used_count = parse_today_used_count(body_text)
        if confirmed_count is None:
            raise RuntimeError("Could not find '오늘 확정' count on the booking dashboard.")
        if used_count is None:
            raise RuntimeError("Could not find '오늘 이용' count on the booking dashboard.")

        return ReservationSnapshot(
            collected_date=target_date.isoformat(),
            collected_at=collected_at,
            place_id=place.place_id,
            booking_id=place.booking_id,
            name=place.name,
            short_name=place.short_name,
            confirmed_reservations=confirmed_count,
            used_reservations=used_count,
        )
    except Exception as exc:
        return ReservationSnapshot(
            collected_date=target_date.isoformat(),
            collected_at=collected_at,
            place_id=place.place_id,
            booking_id=place.booking_id,
            name=place.name,
            short_name=place.short_name,
            confirmed_reservations=None,
            used_reservations=None,
            error=str(exc),
        )


async def collect_historical_reservation_metrics(
    page: Any,
    place: ReservationPlace,
    target_date: date,
    collected_at: str,
    wait_ms: int = 2500,
) -> ReservationSnapshot:
    try:
        confirmed_url = _booking_list_url(place.booking_id, target_date, "REGDATE", ["RC03"])
        await page.goto(confirmed_url, wait_until="load", timeout=30000)
        await page.wait_for_timeout(wait_ms)
        confirmed_text = await page.locator("body").inner_text(timeout=10000)
        if "로그인" in confirmed_text and "예약" not in confirmed_text:
            raise RuntimeError("Naver login is required in this browser session.")

        confirmed_count = parse_booking_list_count(confirmed_text)
        if confirmed_count is None:
            raise RuntimeError("Could not find historical confirmed reservation count.")

        used_url = _booking_list_url(place.booking_id, target_date, "USEDATE", ["RC03", "RC08"])
        await page.goto(used_url, wait_until="load", timeout=30000)
        await page.wait_for_timeout(wait_ms)
        used_text = await page.locator("body").inner_text(timeout=10000)
        used_count = parse_booking_list_count(used_text)
        if used_count is None:
            raise RuntimeError("Could not find historical used reservation count.")

        return ReservationSnapshot(
            collected_date=target_date.isoformat(),
            collected_at=collected_at,
            place_id=place.place_id,
            booking_id=place.booking_id,
            name=place.name,
            short_name=place.short_name,
            confirmed_reservations=confirmed_count,
            used_reservations=used_count,
        )
    except Exception as exc:
        return ReservationSnapshot(
            collected_date=target_date.isoformat(),
            collected_at=collected_at,
            place_id=place.place_id,
            booking_id=place.booking_id,
            name=place.name,
            short_name=place.short_name,
            confirmed_reservations=None,
            used_reservations=None,
            error=str(exc),
        )
