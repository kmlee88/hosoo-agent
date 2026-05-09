from __future__ import annotations

import unittest

from hosoo_agent.naver_reservations import (
    parse_booking_list_count,
    parse_today_confirmed_count,
    parse_today_used_count,
)


class NaverReservationsTest(unittest.TestCase):
    def test_parse_today_confirmed_count_from_dashboard_text(self) -> None:
        text = """
        예약 현황
        0
        확정대기
        2
        오늘 확정
        17
        오늘 이용
        1
        오늘 취소
        """

        self.assertEqual(parse_today_confirmed_count(text), 2)
        self.assertEqual(parse_today_used_count(text), 17)

    def test_parse_today_confirmed_count_when_label_comes_first(self) -> None:
        self.assertEqual(parse_today_confirmed_count("예약 현황 오늘 확정 12 오늘 이용 3"), 12)
        self.assertEqual(parse_today_used_count("예약 현황 오늘 확정 12 오늘 이용 3"), 3)

    def test_parse_booking_list_count(self) -> None:
        self.assertEqual(parse_booking_list_count("예약27건내려받기인쇄"), 27)
        self.assertEqual(parse_booking_list_count("예약 0 건"), 0)


if __name__ == "__main__":
    unittest.main()
