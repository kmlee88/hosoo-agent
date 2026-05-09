from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from hosoo_agent.dashboard_data import (
    ReservationSnapshot,
    build_dashboard_payload,
    save_reservation_snapshots,
    summarize_reviews,
)


class DashboardDataTest(unittest.TestCase):
    def test_summarize_reviews_groups_our_and_competitor_counts(self) -> None:
        summary = summarize_reviews(
            [
                {
                    "type": "당사",
                    "name": "A",
                    "place_id": "1",
                    "daily_reviews": 2,
                    "daily_receipt_reviews": 1,
                    "total_reviews": 10,
                    "reviews": [{"body": "친절하고 좋아요", "tags": ["친절"]}],
                },
                {
                    "type": "경쟁사",
                    "name": "B",
                    "place_id": "2",
                    "daily_reviews": 3,
                    "daily_receipt_reviews": 2,
                    "total_reviews": 20,
                    "reviews": [],
                },
            ]
        )

        self.assertEqual(summary["totalsByType"]["당사"], 2)
        self.assertEqual(summary["totalsByType"]["경쟁사"], 3)
        self.assertEqual(summary["receiptByType"]["당사"], 1)
        self.assertEqual(summary["keywords"][0], {"keyword": "친절", "count": 1})

    def test_build_dashboard_payload_reads_reservations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            save_reservation_snapshots(
                [
                    ReservationSnapshot(
                        collected_date="2026-05-10",
                        collected_at=None,
                        place_id="1",
                        name="아뜰리에호수 잠실",
                        confirmed_reservations=7,
                        used_reservations=5,
                    )
                ],
                snapshots / "reservations-2026-05-10.json",
            )

            payload = build_dashboard_payload(root, target_date="2026-05-10")

        self.assertEqual(payload["reservations"]["totalConfirmed"], 7)
        self.assertEqual(payload["reservations"]["totalUsed"], 5)
        self.assertEqual(payload["reservations"]["stores"][0]["name"], "잠실점")

    def test_build_dashboard_payload_uses_reservation_short_name(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / "reservations-2026-05-10.json").write_text(
                """
                [
                  {
                    "collected_date": "2026-05-10",
                    "place_id": "1477059571",
                    "booking_id": "1103452",
                    "name": "아뜰리에호수 혜화",
                    "short_name": "혜화",
                    "confirmed_reservations": 4,
                    "used_reservations": 6,
                    "error": null
                  }
                ]
                """,
                encoding="utf-8",
            )

            payload = build_dashboard_payload(root, target_date="2026-05-10")

        self.assertEqual(payload["reservations"]["stores"][0]["name"], "혜화점")

    def test_reservation_payload_keeps_store_order_and_compares_previous_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / "reservations-2026-05-09.json").write_text(
                """
                [
                  {"collected_date":"2026-05-09","place_id":"hongdae","name":"홍대","confirmed_reservations":3,"used_reservations":2},
                  {"collected_date":"2026-05-09","place_id":"yeonmujang","name":"성수연무장","confirmed_reservations":5,"used_reservations":1}
                ]
                """,
                encoding="utf-8",
            )
            (snapshots / "reservations-2026-05-10.json").write_text(
                """
                [
                  {"collected_date":"2026-05-10","place_id":"hongdae","name":"홍대","confirmed_reservations":7,"used_reservations":4},
                  {"collected_date":"2026-05-10","place_id":"yeonmujang","name":"성수연무장","confirmed_reservations":4,"used_reservations":3}
                ]
                """,
                encoding="utf-8",
            )

            payload = build_dashboard_payload(root, target_date="2026-05-10")

        self.assertEqual([row["name"] for row in payload["reservations"]["stores"]], ["홍대점", "연무장"])
        self.assertEqual(payload["reservations"]["totalConfirmed"], 11)
        self.assertEqual(payload["reservations"]["totalUsed"], 7)
        self.assertEqual(payload["reservations"]["totalDelta"], 3)
        self.assertEqual(payload["reservations"]["totalUsedDelta"], 4)
        self.assertEqual(payload["reservations"]["stores"][1]["dailyDelta"], -1)
        self.assertEqual(payload["reservations"]["stores"][1]["usedDelta"], 2)

    def test_reservation_payload_reports_latest_collected_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / "reservations-2026-05-10.json").write_text(
                """
                [
                  {"collected_date":"2026-05-10","collected_at":"2026-05-10T09:00:00+09:00","place_id":"jamsil","name":"잠실","confirmed_reservations":2,"used_reservations":1},
                  {"collected_date":"2026-05-10","collected_at":"2026-05-10T10:00:00+09:00","place_id":"hongdae","name":"홍대","confirmed_reservations":3,"used_reservations":2}
                ]
                """,
                encoding="utf-8",
            )

            payload = build_dashboard_payload(root, target_date="2026-05-10")

        self.assertEqual(payload["reservations"]["collectedAt"], "2026-05-10T10:00:00+09:00")

    def test_build_dashboard_payload_prefers_latest_successful_review_date(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / "reviews-2026-05-10.json").write_text(
                '[{"collected_date":"2026-05-10","total_reviews":null,"error":"network"}]',
                encoding="utf-8",
            )
            (snapshots / "reviews-2026-05-09.json").write_text(
                '[{"collected_date":"2026-05-09","type":"당사","name":"A","place_id":"1","total_reviews":10,"daily_reviews":2,"daily_receipt_reviews":0,"reviews":[],"error":null}]',
                encoding="utf-8",
            )

            payload = build_dashboard_payload(root)

        self.assertEqual(payload["date"], "2026-05-09")
        self.assertEqual(payload["reviews"]["totalsByType"]["당사"], 2)

    def test_review_payload_sorts_groups_and_compares_to_previous_day(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            snapshots = root / "snapshots"
            snapshots.mkdir()
            (snapshots / "reviews-2026-05-08.json").write_text(
                """
                [
                  {"collected_date":"2026-05-08","type":"당사","name":"아뜰리에호수 홍대","place_id":"hongdae","total_reviews":10,"daily_reviews":2,"daily_receipt_reviews":0,"reviews":[],"error":null},
                  {"collected_date":"2026-05-08","type":"당사","name":"아뜰리에호수 잠실","place_id":"jamsil","total_reviews":20,"daily_reviews":5,"daily_receipt_reviews":0,"reviews":[],"error":null},
                  {"collected_date":"2026-05-08","type":"경쟁사","name":"B","place_id":"b","total_reviews":30,"daily_reviews":1,"daily_receipt_reviews":0,"reviews":[],"error":null}
                ]
                """,
                encoding="utf-8",
            )
            (snapshots / "reviews-2026-05-09.json").write_text(
                """
                [
                  {"collected_date":"2026-05-09","type":"당사","name":"아뜰리에호수 홍대","place_id":"hongdae","total_reviews":13,"daily_reviews":3,"daily_receipt_reviews":0,"reviews":[],"error":null},
                  {"collected_date":"2026-05-09","type":"당사","name":"아뜰리에호수 잠실","place_id":"jamsil","total_reviews":26,"daily_reviews":6,"daily_receipt_reviews":0,"reviews":[],"error":null},
                  {"collected_date":"2026-05-09","type":"경쟁사","name":"A","place_id":"a","total_reviews":40,"daily_reviews":8,"daily_receipt_reviews":0,"reviews":[],"error":null},
                  {"collected_date":"2026-05-09","type":"경쟁사","name":"B","place_id":"b","total_reviews":32,"daily_reviews":2,"daily_receipt_reviews":0,"reviews":[],"error":null}
                ]
                """,
                encoding="utf-8",
            )

            payload = build_dashboard_payload(root, target_date="2026-05-09")

        self.assertEqual([row["name"] for row in payload["reviews"]["ourPlaces"]], ["잠실점", "홍대점"])
        self.assertEqual([row["name"] for row in payload["reviews"]["competitorPlaces"]], ["A", "B"])
        self.assertEqual(payload["reviews"]["ourPlaces"][0]["dailyDelta"], 1)
        self.assertEqual(payload["reviews"]["totalDeltasByType"]["당사"], 2)
        self.assertAlmostEqual(payload["reviews"]["marketShare"], 9 / 19 * 100)
        self.assertAlmostEqual(payload["reviews"]["marketShareDelta"], (9 / 19 * 100) - (7 / 8 * 100))


if __name__ == "__main__":
    unittest.main()
