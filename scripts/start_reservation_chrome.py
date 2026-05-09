from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
PROFILE_DIR = ROOT_DIR / ".browser-profile" / "naver-chrome"
DEFAULT_CDP_PORT = 9222
SMARTPLACE_URL = "https://new.smartplace.naver.com/bizes"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start Chrome for Naver SmartPlace reservation collection.")
    parser.add_argument(
        "--chrome-path",
        default=os.environ.get("RESERVATION_CHROME_PATH"),
        help="Chrome executable path. Defaults to common macOS Chrome locations.",
    )
    parser.add_argument("--port", type=int, default=int(os.environ.get("RESERVATION_CDP_PORT", DEFAULT_CDP_PORT)))
    parser.add_argument("--profile-dir", default=str(PROFILE_DIR))
    parser.add_argument("--url", default=SMARTPLACE_URL)
    return parser.parse_args()


def chrome_candidates() -> list[Path]:
    candidates = [
        Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
        Path.home() / "Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        Path("/Applications/Chromium.app/Contents/MacOS/Chromium"),
        Path.home() / "Applications/Chromium.app/Contents/MacOS/Chromium",
        Path("/Applications/Naver Whale.app/Contents/MacOS/Naver Whale"),
        Path.home() / "Applications/Naver Whale.app/Contents/MacOS/Naver Whale",
        Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge"),
        Path.home() / "Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    ]
    for command in ("google-chrome", "chromium", "chromium-browser", "msedge"):
        if resolved := shutil.which(command):
            candidates.append(Path(resolved))
    return candidates


def find_chrome(chrome_path: str | None) -> Path | None:
    if chrome_path:
        path = Path(chrome_path).expanduser()
        return path if path.exists() else None
    for path in chrome_candidates():
        if path.exists():
            return path
    return None


def is_chrome_ready(cdp_url: str) -> bool:
    try:
        with urllib.request.urlopen(cdp_url, timeout=1) as response:
            return response.status == 200
    except (OSError, urllib.error.URLError):
        return False


def main() -> int:
    args = parse_args()
    cdp_url = f"http://127.0.0.1:{args.port}/json/version"
    profile_dir = Path(args.profile_dir).expanduser()

    if is_chrome_ready(cdp_url):
        print("예약 수집용 Chrome이 이미 실행 중입니다.")
        return 0

    chrome = find_chrome(args.chrome_path)
    if chrome is None:
        print(
            "Chrome 실행 파일을 찾지 못했습니다. Google Chrome을 설치했는지 확인하거나 "
            "RESERVATION_CHROME_PATH에 Chrome 실행 파일 경로를 지정해 주세요.",
            file=sys.stderr,
        )
        return 1

    profile_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [
            str(chrome),
            "--no-first-run",
            "--no-default-browser-check",
            "--disable-crash-reporter",
            "--disable-crashpad",
            f"--remote-debugging-port={args.port}",
            f"--user-data-dir={profile_dir}",
            args.url,
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    for _ in range(20):
        if is_chrome_ready(cdp_url):
            print("예약 수집용 Chrome을 열었습니다.")
            print("이 창에서 네이버 스마트플레이스에 로그인한 뒤 PC를 잠자기 상태로 두지 마세요.")
            return 0
        time.sleep(0.5)

    print("Chrome을 열었지만 자동화 연결 준비를 확인하지 못했습니다.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
