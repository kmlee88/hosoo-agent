# hosoo-agent

Atelier Hosoo 운영 지표를 매일 모니터링하기 위한 내부 도구입니다.

## 첫 번째 기능: 네이버 플레이스 리뷰 모니터링

기존 `kmlee88/at-review-monitoring` 저장소에서 검증했던 네이버 플레이스 리뷰 수집 로직을 가져와, 이 프로젝트에서는 앱에 붙이기 쉬운 작은 모듈로 정리합니다.

현재 수집하는 값:

- 업체명
- 구분: 당사 또는 경쟁사
- 네이버 플레이스 ID
- 누적 방문자 리뷰 수
- 기준일 신규 리뷰 수
- 기준일 영수증 리뷰 수
- 기준일 리뷰 상세 일부

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python scripts/collect_reviews.py
```

결과는 `snapshots/` 폴더에 JSON과 CSV로 저장됩니다.
기본값은 네이버에 실제 노출되는 최신 리뷰 날짜를 자동으로 찾아 그 날짜 기준으로 집계합니다.
전일비 비교를 위해 전일 스냅샷이 없으면 자동으로 한 번 더 수집합니다.

특정 날짜를 강제로 집계하려면:

```bash
python scripts/collect_reviews.py --date 2026-05-09
```

## 대시보드 실행

추가 패키지 없이 표준 Python 서버로 실행합니다.

```bash
python app.py
```

브라우저에서 `http://127.0.0.1:8000`을 열면 됩니다.
다른 포트로 띄우려면 `PORT=8010 python app.py`처럼 실행합니다.
같은 와이파이에 연결된 모바일에서 보려면 `HOST=0.0.0.0 python app.py`로 실행한 뒤 Mac의 로컬 IP로 접속합니다.

## 전 직원 공유용 배포

전 직원이 다른 네트워크에서 보려면 로컬 실행이 아니라 공개 URL이 있는 서버에 배포해야 합니다.
현재 앱은 Docker/Render 배포를 바로 할 수 있게 준비되어 있습니다.

배포 시 최소 환경변수:

```bash
HOST=0.0.0.0
PORT=8000
DASHBOARD_USER=공유할_아이디
DASHBOARD_PASSWORD=공유할_비밀번호
```

`DASHBOARD_USER`와 `DASHBOARD_PASSWORD`를 넣으면 브라우저에서 로그인 창이 뜹니다.
직원 공유용 링크는 Render, Fly.io, Railway, AWS Lightsail 같은 외부 서버에 올린 URL을 사용합니다.

대시보드는 아래 파일을 읽습니다.

- 리뷰: `snapshots/reviews-YYYY-MM-DD.json`
- 예약 확정/이용건수: `snapshots/reservations-YYYY-MM-DD.json` 또는 `snapshots/reservations-YYYY-MM-DD.csv`
- 예약관리 대상 지점: `data/reservation_places.json`

## 네이버 예약 확정/이용건수 수집

네이버 스마트플레이스 로그인 세션이 필요한 자동화입니다. 최초 1회는 브라우저를 띄워 직접 로그인합니다.

```bash
python scripts/collect_reservations.py --headed
```

로그인 후 같은 프로필(`.browser-profile/naver`)을 재사용하므로 다음 실행부터는 세션이 유지되면 자동으로 수집됩니다.
수집 대상은 `data/reservation_places.json`의 6개 직영점이며, 각 예약관리 대시보드의 `예약현황 > 오늘 확정`, `오늘 이용` 값을 저장합니다.

수집 결과는 두 곳에 저장됩니다.

- `snapshots/reservations-YYYY-MM-DD.json`: 대시보드가 읽는 해당일 최신값
- `snapshots/reservations-history.jsonl`: 1시간 단위 수집 이력 누적

전일비는 해당일 최신값과 전일 마지막으로 저장된 일별 값을 비교합니다.
모든 지점 수집이 실패한 경우에는 기존 일별 파일을 덮어쓰지 않고, 실패 이력만 히스토리에 남깁니다.

예약 스냅샷 JSON 예시:

```json
[
  {
    "collected_date": "2026-05-10",
    "collected_at": "2026-05-10T10:00:00+09:00",
    "place_id": "1638682001",
    "name": "아뜰리에호수 잠실",
    "confirmed_reservations": 12,
    "used_reservations": 17,
    "error": null
  }
]
```

## 다음에 붙일 기능

- 네이버 예약건수 수집
- 리뷰/예약 통합 대시보드
- 매일 자동 실행
- 경쟁사 변화 알림
