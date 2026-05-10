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
# Phase 2-NoAI — Design Ref: §3.2
# 객관적 사실 데이터 3종(F1 헤드라인+VADER, F2 어닝스 배지, F3 인사이더 매수)
# ─────────────────────────────────────────────────────────────

# F1: VADER compound |c| ≥ 0.3 만 surface (Plan FR-03)
NEWS_VADER_COMPOUND_THRESHOLD: float = 0.3

# F1: 헤드라인 50자 초과 시 47자 + "..." (OQ-3, v5 50자로 축소 — 모바일 한 줄 가독성)
NEWS_HEADLINE_MAX_CHARS: int = 50

# F2: ≤ 7일 어닝스만 📅 배지 표시 (Plan FR-04)
EARNINGS_LOOKAHEAD_DAYS: int = 7

# F3: 7일 누적 인사이더 순매수 ≥ $1M 만 섹션 표시 (Plan FR-05)
INSIDER_BUY_USD_THRESHOLD: float = 1_000_000.0

# F3: 인사이더 합산 기간 (7일)
INSIDER_LOOKBACK_DAYS: int = 7

# 병렬 호출: 14 stocks × ~1s → ~3-4s (Plan FR-06)
NEWS_THREAD_POOL_WORKERS: int = 8

# per-ticker yfinance 호출 타임아웃
NEWS_FETCH_TIMEOUT_SEC: float = 5.0

# feature flag 환경변수 이름
ENABLE_NEWS_ENV_VAR: str = "ENABLE_NEWS"

# FR-13: F1 헤드라인 한글 번역 (Plan FR-13, 운영 후 추가)
ENABLE_NEWS_TRANSLATION_ENV_VAR: str = "ENABLE_NEWS_TRANSLATION"
NEWS_TRANSLATION_TIMEOUT_SEC: float = 3.0


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI v3 — UX 개선 (FR-14 ~ FR-20)
# 운영 발견: 헤드라인 종목 매칭 부정확 + 좁은 모바일 가독성 + 초보자 진입장벽
# ─────────────────────────────────────────────────────────────

# FR-14: 헤드라인 종목별 매칭 정확도용 영문 회사명 사전
# yfinance.Ticker.news 결과 중 title에 ticker/회사명 포함된 항목 우선 매칭.
COMPANY_NAMES_EN: dict[str, list[str]] = {
    "NVDA":  ["Nvidia", "NVIDIA"],
    "TSLA":  ["Tesla"],
    "MSFT":  ["Microsoft"],
    "AAPL":  ["Apple"],
    "AMZN":  ["Amazon"],
    "AVGO":  ["Broadcom"],
    "INTC":  ["Intel"],
    "MU":    ["Micron"],
    "AMD":   ["AMD", "Advanced Micro"],
    "GOOGL": ["Google", "Alphabet"],
    "META":  ["Meta", "Facebook"],
    "TSM":   ["TSMC", "Taiwan Semiconductor"],
    "ASML":  ["ASML"],
    "COIN":  ["Coinbase"],
}

# FR-20: VIX 컨텍스트 라벨 임계값
# VIX < 20: 안정 / 20–25: 경계 / >= 25: 공포 (CBOE 일반 가이드)
VIX_LABEL_STABLE_MAX: float = 20.0
VIX_LABEL_CAUTION_MAX: float = 25.0

# FR-17: 초보자 가이드 푸터 (메시지 끝 1줄)
FOOTER_BEGINNER_GUIDE: str = (
    "💡 신호: 🔥거래량 🎯갭 🆙신고가 📊시간외 ⚡VIX급등 ★사상최고"
)


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


def is_news_enabled() -> bool:
    """Phase 2-NoAI feature flag 파싱 (OQ-2: default true).

    ENABLE_NEWS=false 면 Phase 1.5 동작과 byte 단위 동일 출력 (NFR-07 안전망).
    """
    return os.environ.get(ENABLE_NEWS_ENV_VAR, "true").strip().lower() == "true"


def is_news_translation_enabled() -> bool:
    """FR-13 한글 번역 feature flag (default true).

    ENABLE_NEWS_TRANSLATION=false 시 영문 헤드라인 원문 표시. deep-translator 비공식
    endpoint 503/rate-limit 회피용 안전망.
    """
    return (
        os.environ.get(ENABLE_NEWS_TRANSLATION_ENV_VAR, "true").strip().lower() == "true"
    )
