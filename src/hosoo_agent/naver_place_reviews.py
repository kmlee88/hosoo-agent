from __future__ import annotations

import csv
import http.cookiejar
import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any

GRAPHQL_URL = "https://pcmap-api.place.naver.com/graphql"
NAVER_HOME_URL = "https://www.naver.com"


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    type: str


@dataclass
class ReviewDetail:
    review_id: str
    created: str
    visited: str
    author: str
    rating: str
    body: str
    tags: list[str]
    origin_type: str


@dataclass
class PlaceReviewSnapshot:
    collected_date: str
    place_id: str
    name: str
    type: str
    total_reviews: int | None
    daily_reviews: int | None
    daily_receipt_reviews: int
    reviews: list[ReviewDetail]
    error: str | None = None


class NaverSession:
    def __init__(self) -> None:
        cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
        self.headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "ko-KR,ko;q=0.9",
        }

    def get(self, url: str, timeout: int = 10) -> bytes:
        request = urllib.request.Request(url, headers=self.headers, method="GET")
        with self.opener.open(request, timeout=timeout) as response:
            return response.read()

    def post_json(
        self,
        url: str,
        payload: Any,
        headers: dict[str, str] | None = None,
        timeout: int = 15,
    ) -> Any:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request_headers = {
            **self.headers,
            "Content-Type": "application/json",
            **(headers or {}),
        }
        request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
        try:
            with self.opener.open(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
        except urllib.error.HTTPError as exc:
            error_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {exc.code}: {error_body[:300]}") from exc
        return json.loads(raw)


def load_places(path: Path) -> list[Place]:
    raw_places = json.loads(path.read_text(encoding="utf-8"))
    return [Place(id=str(item["id"]), name=item["name"], type=item["type"]) for item in raw_places]


def create_naver_session() -> NaverSession:
    session = NaverSession()
    session.get(NAVER_HOME_URL, timeout=10)
    return session


def parse_naver_review_date(value: str, base_year: int | None = None) -> str | None:
    if not value:
        return None

    match = re.match(r"(\d{1,2})\.(\d{1,2})\.", value)
    if not match:
        return None

    year = base_year or datetime.now().year
    month = int(match.group(1))
    day = int(match.group(2))
    if not (1 <= month <= 12 and 1 <= day <= 31):
        return None
    return f"{year}-{month:02d}-{day:02d}"


def fetch_visitor_reviews(
    session: NaverSession,
    place_id: str,
    display: int = 50,
) -> tuple[list[dict[str, Any]], int]:
    payload = [
        {
            "operationName": "getVisitorReviews",
            "variables": {
                "input": {
                    "businessId": place_id,
                    "businessType": "place",
                    "page": 1,
                    "display": display,
                    "isPhotoUsed": False,
                    "item": "0",
                    "bookingBusinessId": None,
                    "order": 0,
                }
            },
            "query": """
                query getVisitorReviews($input: VisitorReviewsInput) {
                    visitorReviews(input: $input) {
                        items {
                            id
                            created
                            visited
                            rating
                            author { nickname }
                            body
                            tags
                            originType
                        }
                        total
                    }
                }
            """,
        }
    ]

    response = session.post_json(
        GRAPHQL_URL,
        payload=payload,
        headers={
            "Referer": f"https://pcmap.place.naver.com/place/{place_id}/review/visitor",
            "Origin": "https://pcmap.place.naver.com",
        },
        timeout=15,
    )

    data = response[0]["data"]["visitorReviews"]
    return data["items"], int(data["total"])


def collect_place_snapshot(
    session: NaverSession,
    place: Place,
    target_date: date,
    display: int = 50,
) -> PlaceReviewSnapshot:
    try:
        items, total = fetch_visitor_reviews(session, place.id, display=display)
    except Exception as exc:
        return PlaceReviewSnapshot(
            collected_date=target_date.isoformat(),
            place_id=place.id,
            name=place.name,
            type=place.type,
            total_reviews=None,
            daily_reviews=None,
            daily_receipt_reviews=0,
            reviews=[],
            error=str(exc),
        )

    details: list[ReviewDetail] = []
    seen_ids: set[str] = set()
    for item in items:
        review_id = item.get("id", "")
        if review_id in seen_ids:
            continue
        seen_ids.add(review_id)

        review_date = parse_naver_review_date(item.get("created", ""), base_year=target_date.year)
        if review_date != target_date.isoformat():
            continue

        details.append(
            ReviewDetail(
                review_id=review_id,
                created=item.get("created", ""),
                visited=item.get("visited", ""),
                author=item.get("author", {}).get("nickname", ""),
                rating=str(item.get("rating", "")),
                body=item.get("body", "") or "",
                tags=item.get("tags", []) or [],
                origin_type=item.get("originType", "") or "",
            )
        )

    receipt_count = sum(1 for detail in details if detail.origin_type == "영수증")
    return PlaceReviewSnapshot(
        collected_date=target_date.isoformat(),
        place_id=place.id,
        name=place.name,
        type=place.type,
        total_reviews=total,
        daily_reviews=len(details),
        daily_receipt_reviews=receipt_count,
        reviews=details,
    )


def collect_review_snapshots(
    places: list[Place],
    target_date: date | None = None,
    display: int = 50,
    delay_seconds: float = 1.0,
) -> list[PlaceReviewSnapshot]:
    run_date = target_date or date.today()
    try:
        session = create_naver_session()
    except Exception as exc:
        return [
            PlaceReviewSnapshot(
                collected_date=run_date.isoformat(),
                place_id=place.id,
                name=place.name,
                type=place.type,
                total_reviews=None,
                daily_reviews=None,
                daily_receipt_reviews=0,
                reviews=[],
                error=f"Failed to initialize Naver session: {exc}",
            )
            for place in places
        ]

    snapshots: list[PlaceReviewSnapshot] = []
    for index, place in enumerate(places):
        snapshots.append(collect_place_snapshot(session, place, run_date, display=display))
        if index < len(places) - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)
    return snapshots


def save_snapshots_json(snapshots: list[PlaceReviewSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [asdict(snapshot) for snapshot in snapshots]
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def save_snapshots_csv(snapshots: list[PlaceReviewSnapshot], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "collected_date",
                "place_id",
                "name",
                "type",
                "total_reviews",
                "daily_reviews",
                "daily_receipt_reviews",
                "error",
            ],
        )
        writer.writeheader()
        for snapshot in snapshots:
            writer.writerow(
                {
                    "collected_date": snapshot.collected_date,
                    "place_id": snapshot.place_id,
                    "name": snapshot.name,
                    "type": snapshot.type,
                    "total_reviews": snapshot.total_reviews,
                    "daily_reviews": snapshot.daily_reviews,
                    "daily_receipt_reviews": snapshot.daily_receipt_reviews,
                    "error": snapshot.error or "",
                }
            )
