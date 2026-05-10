# Design Ref: §7 — 환경변수 + 상수만 분리, 비즈니스 로직 무관 (Option C)
"""morning-us-index 설정값.

비밀값은 GitHub Secrets/환경변수로만 주입. 본 모듈은 상수와 로더만 노출한다.
"""

import os

TICKERS: list[tuple[str, str]] = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
]

TIMEZONE_KST = "Asia/Seoul"

YFINANCE_PERIOD = "5d"

HTTP_CONNECT_TIMEOUT_SEC = 5
HTTP_READ_TIMEOUT_SEC = 15

RETRY_ATTEMPTS = 3
RETRY_BACKOFF_SEC: list[int] = [30, 60, 120]

STALE_THRESHOLD_DAYS = 2


def load_slack_webhook_url() -> str:
    """SLACK_WEBHOOK_URL 환경변수를 읽어 반환.

    Raises:
        RuntimeError: 환경변수 미설정 또는 빈 문자열.
    """
    url = os.environ.get("SLACK_WEBHOOK_URL", "").strip()
    if not url:
        raise RuntimeError(
            "SLACK_WEBHOOK_URL 환경변수가 설정되지 않았습니다. "
            "GitHub Secrets 또는 로컬 환경변수에 등록하세요."
        )
    return url
