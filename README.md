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

## 다음에 붙일 기능

- 네이버 예약건수 수집
- 리뷰/예약 통합 대시보드
- 매일 자동 실행
- 경쟁사 변화 알림
