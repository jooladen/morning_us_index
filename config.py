# Design Ref: §7 — 환경변수 + 상수만 분리, 비즈니스 로직 무관 (Option C)
"""morning-us-index 설정값.

비밀값은 GitHub Secrets/환경변수로만 주입. 본 모듈은 상수와 로더만 노출한다.
"""

import os

# ─────────────────────────────────────────────────────────────
# Phase 1 (호환 유지) — fetch_indices, build_message가 의존
# ─────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────
# Phase 1.5 (v15) — Design Ref: §4.1
# ─────────────────────────────────────────────────────────────

# Plan FR-01: 5 지수 (^IXIC, ^GSPC + 다우/러셀/VIX)
INDICES: list[tuple[str, str]] = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
    ("^DJI",  "다우"),
    ("^RUT",  "러셀2000"),
    ("^VIX",  "VIX"),
]

# Plan FR-02: 3 선물 (한국 새벽 다음장 전망 1순위)
FUTURES: list[tuple[str, str]] = [
    ("ES=F", "S&P 미니"),
    ("NQ=F", "나스닥 미니"),
    ("YM=F", "다우 미니"),
]

# Plan FR-03: 14 종목 (11 기본 + TSM/ASML/COIN)
# TSMC의 ADR 티커는 "TSM" (Yahoo Finance)
STOCKS: list[tuple[str, str]] = [
    ("NVDA",  "엔비디아"),
    ("TSLA",  "테슬라"),
    ("MSFT",  "마이크로소프트"),
    ("AAPL",  "애플"),
    ("AMZN",  "아마존"),
    ("AVGO",  "브로드컴"),
    ("INTC",  "인텔"),
    ("MU",    "마이크론"),
    ("AMD",   "AMD"),
    ("GOOGL", "구글"),
    ("META",  "메타"),
    ("TSM",   "TSMC"),
    ("ASML",  "ASML"),
    ("COIN",  "코인베이스"),
]

# Plan FR-04: 4 거시 (ticker, label, unit prefix)
MACRO: list[tuple[str, str, str]] = [
    ("USDKRW=X", "원/달러", ""),
    ("CL=F",     "WTI",     "$"),
    ("GC=F",     "금",       "$"),
    ("BTC-USD",  "비트코인", "$"),
]

# Plan FR-05: 수동 섹터 매핑 (Ticker.info 자동 사용 X)
SECTOR_MAP: dict[str, str] = {
    # 반도체
    "NVDA": "반도체", "AMD":  "반도체", "AVGO": "반도체", "INTC": "반도체",
    "MU":   "반도체", "TSM":  "반도체", "ASML": "반도체",
    # 빅테크
    "AAPL":  "빅테크", "MSFT": "빅테크", "GOOGL": "빅테크",
    "META":  "빅테크", "AMZN": "빅테크",
    # EV / 암호
    "TSLA":  "EV/암호", "COIN": "EV/암호",
}

# Plan FR-06: 단타 신호 5종 임계값
SIGNAL_VOLUME_RATIO_THRESHOLD: float    = 2.0    # 🔥 거래량 / 20일 평균
SIGNAL_GAP_THRESHOLD_PCT: float         = 1.5    # 🎯 갭 (open - prev_close) / prev_close
SIGNAL_VIX_CHANGE_THRESHOLD_PCT: float  = 5.0    # ⚡ VIX 일중 변동
SIGNAL_52W_HIGH_THRESHOLD_RATIO: float  = 0.99   # 🆙 52주 신고가 근접
SIGNAL_52W_HIGH_STAR_RATIO: float       = 0.999  # ★ 사상최고
SIGNAL_AFTERHOURS_THRESHOLD_PCT: float  = 1.0    # 📊 시간외 변동

# 메시지 길이 한도 (Slack)
SLACK_MESSAGE_MAX_CHARS: int = 4000

# 단타 후보 요약 — 최소 신호 수 (OQ-4 결정: 2개 이상)
DAYTRADE_CANDIDATE_MIN_SIGNALS: int = 2


# ─────────────────────────────────────────────────────────────

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
