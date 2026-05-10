---
name: morning-us-index-v15
type: design
version: 0.1.0
status: draft
phase: design
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/morning-us-index-v15.plan.md
architecture: option-c-pragmatic-2-modules
---

# Design — morning-us-index-v15 (Phase 1.5)

## Context Anchor

| 키 | 값 |
|---|---|
| **WHY** | 단타(상한가 눌림목) 진입 후보를 매일 아침 자동 스크리닝 |
| **WHO** | 준 (단일 사용자, 단타 트레이더) |
| **RISK** | yfinance N+1 호출 지연 / 시간외 데이터 정확도 / 메시지 4000자 한도 / 부분 미반환 |
| **SUCCESS** | 26 데이터 포인트 + 신호 정확도 ≥ 95% / ≤ 4000자 / ≤ 60초 / Phase 1 회귀 0 |
| **SCOPE** | yfinance 단독. AI/뉴스 = Phase 2 |

## 1. Overview

Phase 1 코드(`main.py` + `config.py` + tests)에 **신규 모듈 2개**(`signals.py`, `data.py`)를 추가하여 26 데이터 포인트 + 단타 신호 5종을 자동 마크하는 슬랙 메시지로 확장. **Phase 1 코드 경로(IndexQuote, fetch_indices, build_message)는 그대로 보존**하여 회귀 위험 0을 달성하고, `main()`만 신규 흐름으로 전환.

## 2. Goals & Non-Goals (요약, Plan §3 참조)

이 문서에서 새로 결정하는 것 — **Plan Open Questions 해소**:

| Open Q | 결정 |
|---|---|
| **OQ-1** 메시지 4,000자 초과 정책 | **압축 정책**: 신호 없는 종목은 1줄(라벨 + 변동률만), 신호 있는 종목은 풀 표시. 그래도 초과하면 거시 섹션 자동 제거 (warn 로그) |
| **OQ-2** yfinance 호출 전략 | **`yf.download(tickers, period="60d")` 일괄** 1회 + **`yf.download(stocks, period="2d", prepost=True)` 1회** = 총 2 HTTP 호출. ThreadPool 불필요 |
| **OQ-3** `Ticker.info` 사용 여부 | **사용 X**. 52주 고가/평균 거래량은 `history(period="1y")` 결과에서 자체 계산 (info는 호출당 1초+ 느림) |
| **OQ-4** 단타 후보 최소 신호 수 | **2개 이상** (신호 1개는 일반적, 2개 이상이 진짜 후보) |
| **OQ-5** 시간외 데이터 정책 | **있을 때만 📊 마크**. 데이터 없으면 조용히 skip (별도 알림 X). 일부 종목만 prepost 잘 잡힘 |

## 3. Architecture Overview (Option C)

```
morning_us_index/
├── main.py                  ← 흐름 변경: fetch_all → compute_signals → build_v15_message → post_slack
├── config.py                ← INDICES/FUTURES/STOCKS/MACRO 분리 + SECTOR_MAP + 임계값
├── data.py                  🆕 yfinance 일괄 호출 + Quote dataclass
├── signals.py               🆕 5종 단타 신호 + 사상최고 + 섹터 분류
├── requirements.txt         (변경 없음 — yfinance, requests)
├── pytest.ini               (변경 없음)
├── tests/
│   ├── test_main.py         (Phase 1, 17 케이스 — 그대로)
│   ├── test_data.py         🆕 fetch_all + Quote 테스트
│   ├── test_signals.py      🆕 5종 신호 + 사상최고 테스트 (~25 케이스)
│   └── test_v15_message.py  🆕 build_v15_message 통합 (~8 케이스)
└── .github/workflows/daily_report.yml  (변경 없음)
```

### 3.1 Phase 1 코드 보존 전략

| Phase 1 자산 | Phase 1.5 처리 |
|---|---|
| `IndexQuote` dataclass | 그대로 (Phase 1 테스트가 의존) |
| `fetch_indices()` | 그대로 (호출 안 함, 테스트만 호출) |
| `build_message()` | 그대로 (호출 안 함, 테스트만 호출) |
| `_format_quote_line()` | 그대로 (build_message 내부에서만 사용) |
| `post_slack()` | **그대로** (build_v15_message 결과를 동일 함수로 발송) |
| `main()` | **흐름 변경** — fetch_all → compute_signals → build_v15_message → post_slack |
| 17 단위 테스트 | 모두 통과 유지 (NFR-05 SC-1.5-6) |

→ Phase 1 회귀 위험 거의 0. 신규 코드는 새 모듈 + 새 함수만 추가.

## 4. Module Design

### 4.1 `config.py` 확장

```python
# 카테고리별 분리 (구 TICKERS는 호환을 위해 유지하되 deprecated)
INDICES: list[tuple[str, str]] = [
    ("^IXIC", "나스닥"),
    ("^GSPC", "S&P 500"),
    ("^DJI",  "다우"),
    ("^RUT",  "러셀2000"),
    ("^VIX",  "VIX"),
]

FUTURES: list[tuple[str, str]] = [
    ("ES=F", "S&P 미니"),
    ("NQ=F", "나스닥 미니"),
    ("YM=F", "다우 미니"),
]

STOCKS: list[tuple[str, str]] = [
    ("NVDA",  "엔비디아"),  ("TSLA", "테슬라"),    ("MSFT", "마이크로소프트"),
    ("AAPL",  "애플"),      ("AMZN", "아마존"),    ("AVGO", "브로드컴"),
    ("INTC",  "인텔"),      ("MU",   "마이크론"),  ("AMD",  "AMD"),
    ("GOOGL", "구글"),      ("META", "메타"),
    ("TSMC",  "TSMC"),      ("ASML", "ASML"),      ("COIN", "코인베이스"),
]

MACRO: list[tuple[str, str, str]] = [   # (ticker, label, unit)
    ("USDKRW=X", "원/달러", ""),
    ("CL=F",     "WTI",     "$"),
    ("GC=F",     "금",       "$"),
    ("BTC-USD",  "비트코인", "$"),
]

SECTOR_MAP: dict[str, str] = {
    # 반도체
    "NVDA": "반도체", "AMD": "반도체", "AVGO": "반도체", "INTC": "반도체",
    "MU":   "반도체", "TSMC": "반도체", "ASML": "반도체",
    # 빅테크
    "AAPL":  "빅테크", "MSFT": "빅테크", "GOOGL": "빅테크",
    "META":  "빅테크", "AMZN": "빅테크",
    # EV/암호
    "TSLA":  "EV/암호", "COIN": "EV/암호",
}

# Phase 1.5 단타 신호 임계값 (Plan FR-06)
SIGNAL_VOLUME_RATIO_THRESHOLD: float    = 2.0   # 🔥
SIGNAL_GAP_THRESHOLD_PCT: float          = 1.5   # 🎯
SIGNAL_VIX_CHANGE_THRESHOLD_PCT: float   = 5.0   # ⚡
SIGNAL_52W_HIGH_THRESHOLD_RATIO: float   = 0.99  # 🆙
SIGNAL_52W_HIGH_STAR_RATIO: float        = 0.999 # ★ (사상최고)
SIGNAL_AFTERHOURS_THRESHOLD_PCT: float   = 1.0   # 📊

# 메시지 길이 한도 (Slack)
SLACK_MESSAGE_MAX_CHARS: int = 4000

# 단타 후보 요약 — 최소 신호 수
DAYTRADE_CANDIDATE_MIN_SIGNALS: int = 2
```

### 4.2 `data.py` (신규)

```python
from dataclasses import dataclass
from datetime import date
from typing import Literal

@dataclass(frozen=True)
class Quote:
    """Phase 1.5 통합 dataclass — 모든 카테고리(index/future/stock/macro)."""
    ticker: str
    label: str
    category: Literal["index", "future", "stock", "macro"]
    sector: str | None              # stock일 때만 채워짐, 그 외 None

    last_close: float
    prev_close: float
    last_date: date
    is_stale: bool                  # KST 기준 last_date가 2일 이상 과거

    # 단타 신호 계산용 (없을 수 있음)
    open_today: float | None = None
    volume_today: float | None = None
    volume_avg_20d: float | None = None
    high_52w: float | None = None
    afterhours_close: float | None = None  # 시간외 종가 (regular close 후)


def fetch_all() -> list[Quote]:
    """
    INDICES + FUTURES + STOCKS + MACRO를 yf.download 일괄 호출로 조회.

    호출 횟수: 2 (regular history 1회 + prepost history 1회)
    예상 시간: 5–15초

    Raises:
        RuntimeError: 모든 ticker 데이터 조회 실패 시.
                       부분 실패는 RuntimeError가 아닌 partial_quotes 반환 + 경고 로그.
    """
```

### 4.3 `signals.py` (신규)

```python
from dataclasses import dataclass
from data import Quote

@dataclass(frozen=True)
class Signal:
    """단타 신호 + 사상최고 결과."""
    ticker: str
    is_volume_spike: bool       # 🔥 거래량 ≥ 2x 평균
    is_gap: bool                # 🎯 갭 ≥ 1.5%
    is_vix_spike: bool          # ⚡ VIX 일중 변동 ≥ 5% (VIX ticker만)
    is_52w_near_high: bool      # 🆙 종가 ≥ 52w high × 0.99
    is_all_time_high: bool      # ★ 종가 ≥ 52w high × 0.999
    is_afterhours_move: bool    # 📊 시간외 변동 ≥ 1%

    @property
    def emoji_marks(self) -> str:
        """메시지 라인에 부착될 이모지 문자열 (예: '🔥🎯🆙')."""

    @property
    def signal_count(self) -> int:
        """발생한 신호 수 (사상최고/52w-high는 둘 중 하나로 카운트)."""


def compute_signals(quotes: list[Quote]) -> dict[str, Signal]:
    """
    각 Quote에 대해 5종 단타 신호를 계산.
    Returns: {ticker: Signal}
    """


def get_sector(ticker: str) -> str | None:
    """SECTOR_MAP 조회. 매핑 없으면 None."""
```

### 4.4 `main.py` 변경

기존 함수들은 그대로 두고 **새 함수 추가** + `main()` 흐름만 교체:

```python
# 신규 함수
def build_v15_message(
    quotes: list[Quote],
    signals: dict[str, Signal],
) -> str:
    """Phase 1.5 슬랙 메시지 빌드. 섹션 그룹화 + 신호 마크 + 단타 후보 요약."""


def main() -> int:
    # 변경된 흐름
    try:
        webhook_url = load_slack_webhook_url()
        quotes = fetch_all()                         # 🆕 data.py
        signals = compute_signals(quotes)            # 🆕 signals.py
        message = build_v15_message(quotes, signals) # 🆕 main.py
        post_slack(webhook_url, message)             # 기존 그대로
        ...
```

### 4.5 메시지 포맷 샘플 (FR-08)

```
[2026-05-11 KST 06:00 발송] 직전 거래일: 2026-05-08 (미 증시 휴장 / 마지막 거래일)

📈 [지수]
• 다우 ^DJI: 49,609.16  ▲ +9.92 (+0.02%) 🟢
• S&P 500 ^GSPC: 7,398.93  ▲ +61.82 (+0.84%) 🟢 ★
• 나스닥 ^IXIC: 26,247.08  ▲ +440.88 (+1.71%) 🟢 ★
• 러셀 ^RUT: 2,234.50  ▼ -6.71 (-0.30%) 🔴
• VIX ^VIX: 23.50  ▲ +1.16 (+5.20%) 🟢 ⚡

🎯 [단타 핵심: 선물 + 시간외]
• ES=F (S&P 미니): 7,412 ▲ +0.18%
• NQ=F (나스닥 미니): 26,310 ▲ +0.24%
• YM=F (다우 미니): 49,615 ▲ +0.01%
• AHRS NVDA: +1.2% 📊
• AHRS AAPL: -0.5% 📊

🏭 [반도체]
• NVDA 엔비디아: 142.50  ▲ +2.45 (+1.75%) 🟢 🔥
• AVGO 브로드컴: 234.10  ▲ +9.50 (+4.23%) 🟢 🆙
• INTC 인텔: 32.15  ▲ +3.95 (+14.00%) 🟢 🎯🔥
• MU 마이크론: 95.40  ▲ +12.45 (+15.00%) 🟢 🆙🔥 ★
• AMD: +0.85%
• ASML: +2.10%
• TSMC: +1.80%

📱 [빅테크]
• AAPL 애플: 232.15  ▲ +4.66 (+2.05%) 🟢
• MSFT 마이크로소프트: 425.80  ▼ -5.78 (-1.34%) 🔴
• GOOGL: +0.50%
• META: +1.20%
• AMZN: +0.56%

🚗 [EV/암호]
• TSLA 테슬라: 312.40  ▲ +12.07 (+4.02%) 🟢
• COIN 코인베이스: +2.10%

💰 [거시]
• 원/달러 USDKRW=X: 1,375.20  ▼ -4.13 (-0.30%) 🔴
• WTI CL=F: $95.42  ▲ +0.58 (+0.61%) 🟢
• 금 GC=F: $2,400.10  ▲ +12.00 (+0.50%) 🟢
• 비트코인 BTC-USD: $90,000  ▼ -900 (-1.00%) 🔴

🚨 [오늘 단타 후보 (신호 2개 이상)]
• INTC 인텔 — 🎯🔥 (갭 +12% + 거래량 8x)
• MU 마이크론 — 🆙🔥 (52주 신고가 + 거래량)
```

### 4.6 압축 정책 (4000자 초과 시)

```python
def _compress_if_needed(message: str) -> str:
    if len(message) <= SLACK_MESSAGE_MAX_CHARS:
        return message
    # 1차: 신호 없는 종목 1줄 압축 (예: "AMD: +0.85%")
    # 2차: 거시 섹션 제거
    # 3차: 시간외 섹션 제거
    # warn log
```

## 5. Data Model

### 5.1 yfinance 호출 패턴

```python
import yfinance as yf

# Call 1: regular OHLCV for all tickers (60d for 52w high + 20d avg volume)
all_tickers = [t for t, _ in INDICES + FUTURES + STOCKS] + [t for t, _, _ in MACRO]
df_main = yf.download(
    all_tickers,
    period="1y",         # 52주 고가 계산용
    group_by="ticker",
    auto_adjust=True,
    actions=False,
    progress=False,
)
# df_main['NVDA']['Close'].iloc[-1] = 직전 거래일 종가
# df_main['NVDA']['Close'].iloc[-2] = 그 이전 거래일
# df_main['NVDA']['Close'].iloc[-252:].max() = 52주 고가
# df_main['NVDA']['Volume'].iloc[-20:].mean() = 20일 평균 거래량

# Call 2: prepost only for stocks (시간외)
stock_tickers = [t for t, _ in STOCKS]
df_prepost = yf.download(
    stock_tickers,
    period="2d",
    interval="1m",
    group_by="ticker",
    prepost=True,
    progress=False,
)
# 일중 1분봉 → regular session 마감 후 시간대만 추출 → afterhours_close
```

### 5.2 신호 계산 알고리즘

```python
def compute_signals(quotes: list[Quote]) -> dict[str, Signal]:
    signals = {}
    vix_quote = next((q for q in quotes if q.ticker == "^VIX"), None)
    vix_pct = abs((vix_quote.last_close - vix_quote.prev_close) / vix_quote.prev_close * 100) if vix_quote else 0

    for q in quotes:
        gap_pct = (
            abs((q.open_today - q.prev_close) / q.prev_close * 100)
            if q.open_today and q.prev_close
            else 0
        )
        vol_ratio = (
            q.volume_today / q.volume_avg_20d
            if q.volume_today and q.volume_avg_20d
            else 0
        )
        ah_pct = (
            abs((q.afterhours_close - q.last_close) / q.last_close * 100)
            if q.afterhours_close and q.last_close
            else 0
        )
        ratio_to_52w = q.last_close / q.high_52w if q.high_52w else 0

        signals[q.ticker] = Signal(
            ticker=q.ticker,
            is_volume_spike=vol_ratio >= SIGNAL_VOLUME_RATIO_THRESHOLD,
            is_gap=gap_pct >= SIGNAL_GAP_THRESHOLD_PCT,
            is_vix_spike=(q.ticker == "^VIX" and vix_pct >= SIGNAL_VIX_CHANGE_THRESHOLD_PCT),
            is_52w_near_high=ratio_to_52w >= SIGNAL_52W_HIGH_THRESHOLD_RATIO,
            is_all_time_high=ratio_to_52w >= SIGNAL_52W_HIGH_STAR_RATIO,
            is_afterhours_move=ah_pct >= SIGNAL_AFTERHOURS_THRESHOLD_PCT,
        )
    return signals
```

## 6. Data Flow / Sequence

```
[Cron 21:00 UTC]
      ↓
[Runner: ubuntu-latest]
      ↓
[python main.py]
      ↓
  ┌──────────────────────────────────────────────┐
  │ main()                                        │
  │   ├─ load_slack_webhook_url()                │
  │   ├─ data.fetch_all()                        │
  │   │     ├─ yf.download(all=26, period=1y)   │ ← 1차 HTTP
  │   │     ├─ yf.download(stocks=14, prepost) │ ← 2차 HTTP
  │   │     └─ list[Quote] (26개)              │
  │   ├─ signals.compute_signals(quotes)        │
  │   │     └─ dict[str, Signal] (26개)        │
  │   ├─ build_v15_message(quotes, signals)     │
  │   │     ├─ format header                    │
  │   │     ├─ format [지수] section            │
  │   │     ├─ format [단타 핵심]               │
  │   │     ├─ format [반도체] / [빅테크] / ... │
  │   │     ├─ format [거시]                   │
  │   │     ├─ format [오늘 단타 후보]          │
  │   │     │   (signal_count >= 2)            │
  │   │     └─ _compress_if_needed()           │
  │   └─ post_slack(url, message)               │ ← 기존 그대로
  └──────────────────────────────────────────────┘
      ↓
[exit 0/1 → GitHub Actions success/fail]
```

## 7. Configuration & Secrets

Phase 1과 동일. **추가/변경 0**.
- `SLACK_WEBHOOK_URL` 1개만 사용
- 환경변수 추가 없음

## 8. Test Plan (L1 — 30+ 케이스)

이 프로젝트는 백엔드 스크립트라 L2/L3 N/A. L1 단위 + 통합 위주.

### 8.1 `test_data.py` (신규, ~10 케이스)

| ID | 항목 | 통과 기준 |
|---|---|---|
| L1-data-1 | fetch_all() — 정상 호출 (integration) | 26개 Quote 반환, 모두 last_close > 0 |
| L1-data-2 | fetch_all() — INDICES 5개 포함 | category="index" 5개 |
| L1-data-3 | fetch_all() — FUTURES 3개 포함 | category="future" 3개 |
| L1-data-4 | fetch_all() — STOCKS 14개 포함 | category="stock" 14개, sector 채워짐 |
| L1-data-5 | fetch_all() — MACRO 4개 포함 | category="macro" 4개 |
| L1-data-6 | Quote.is_stale 계산 | 월요일 케이스 stale=True |
| L1-data-7 | Quote.high_52w 계산 | history(period="1y").max() == high_52w |
| L1-data-8 | Quote.volume_avg_20d 계산 | history(period="60d").iloc[-20:].mean() |
| L1-data-9 | 일부 ticker 데이터 미반환 — 부분 실패 허용 | 다른 종목은 정상 반환, 누락은 빠짐 |
| L1-data-10 | prepost 데이터 없는 종목 — afterhours_close=None | 조용히 None |

### 8.2 `test_signals.py` (신규, ~12 케이스)

| ID | 항목 | 통과 기준 |
|---|---|---|
| L1-sig-1 | 🔥 거래량 spike (vol/avg = 2.5) | is_volume_spike=True |
| L1-sig-2 | 🔥 boundary (vol/avg = 2.0) | is_volume_spike=True |
| L1-sig-3 | 🔥 (vol/avg = 1.99) | False |
| L1-sig-4 | 🎯 갭 +1.6% | is_gap=True |
| L1-sig-5 | 🎯 갭 -1.6% (음수) | is_gap=True |
| L1-sig-6 | 🎯 갭 +1.4% | False |
| L1-sig-7 | ⚡ VIX +5.5% (^VIX ticker만) | is_vix_spike=True |
| L1-sig-8 | ⚡ AAPL +5.5% (VIX 아님) | is_vix_spike=False |
| L1-sig-9 | 🆙 종가 = 52w high × 0.995 | is_52w_near_high=True |
| L1-sig-10 | ★ 종가 = 52w high × 0.9995 | is_all_time_high=True |
| L1-sig-11 | 📊 시간외 +1.5% | is_afterhours_move=True |
| L1-sig-12 | 📊 afterhours_close=None | is_afterhours_move=False |
| L1-sig-13 | get_sector("NVDA") | "반도체" |
| L1-sig-14 | get_sector("UNKNOWN") | None |
| L1-sig-15 | Signal.signal_count (3개 신호) | 3 |
| L1-sig-16 | Signal.emoji_marks 순서 | "🔥🎯🆙" 일관 |

### 8.3 `test_v15_message.py` (신규, ~8 케이스)

| ID | 항목 | 통과 기준 |
|---|---|---|
| L1-msg-1 | build_v15_message — 모든 섹션 포함 | 7 섹션 헤더 모두 등장 |
| L1-msg-2 | 단타 후보 자동 요약 (신호 2개+) | 종목 + 마크 한 줄 등장 |
| L1-msg-3 | 신호 0개 종목 — 단타 후보 섹션에 없음 | not in 단타 후보 |
| L1-msg-4 | 사상최고 ★ 표시 | "★" 등장 |
| L1-msg-5 | 거래량 🔥 마크 | "🔥" 등장 |
| L1-msg-6 | 메시지 ≤ 4000자 | len(msg) ≤ 4000 |
| L1-msg-7 | 압축 정책 — 신호 없는 종목 1줄 | "AMD: +0.85%" 형태 |
| L1-msg-8 | 휴장일 처리 | "(미 증시 휴장 / 마지막 거래일)" 등장 |

### 8.4 Phase 1 회귀 (test_main.py 17 케이스 — 변경 없음)

| 보장 | 방법 |
|---|---|
| `IndexQuote` 시그니처 그대로 | dataclass 미수정 |
| `fetch_indices` 동작 그대로 | 함수 미수정 |
| `build_message(quotes)` 동작 그대로 | 함수 미수정 |
| `post_slack` 동작 그대로 | 함수 미수정 |
| 17 단위 테스트 통과 | `pytest tests/test_main.py` ≥ 16 (integration deselected 포함 17) |

**총 신규 테스트: 30+ (10 + 12 + 8 = 30)**, Phase 1 17 그대로 = **47 테스트** 운영.

## 9. Error Handling & Retry

| 단계 | 에러 | 대응 |
|---|---|---|
| `data.fetch_all` 전체 실패 (Yahoo down) | RuntimeError → main() catch → 슬랙 에러 메시지 | 기존 Phase 1 패턴 |
| `data.fetch_all` 일부 ticker 미반환 | 누락 ticker는 list에서 빠짐, warning log | 메시지엔 누락 종목 표시 X |
| `signals.compute_signals` 데이터 부족 | 해당 신호 False, 다른 신호는 정상 계산 | 부분 실패 허용 |
| `build_v15_message` 메시지 4000자 초과 | 압축 정책 자동 적용 + warn log | NFR-01 보장 |
| `post_slack` (Phase 1과 동일) | 5xx/429 3회 재시도, 4xx 즉시 실패 | 변경 없음 |

## 10. Deployment

`.github/workflows/daily_report.yml` **변경 없음**. 동일 cron(`'0 21 * * *'` + 보험 `'30 21 * * *'`), 동일 secrets, 동일 Python 3.11.

## 11. Implementation Guide

### 11.1 구현 순서 체크리스트

| # | 항목 | 산출물 | DoD |
|---|---|---|---|
| 1 | `config.py` 확장 — INDICES/FUTURES/STOCKS/MACRO/SECTOR_MAP/임계값 | 수정 | import 가능, 상수값 명시 |
| 2 | `data.py` 신규 — Quote dataclass + fetch_all 골격 | 신규 | import OK, fetch_all() 호출 가능 |
| 3 | `data.py` — yf.download 통합 (1차 호출, 1년치) | 채움 | INDICES/FUTURES/STOCKS/MACRO 26개 Quote 반환 |
| 4 | `data.py` — prepost 호출 추가 | 채움 | 14 stock 중 일부의 afterhours_close 채워짐 |
| 5 | `data.py` — 부분 실패 허용 | 채움 | 누락 ticker는 list에서 빠짐 |
| 6 | `tests/test_data.py` 작성 (10 케이스) | 신규 | 9 unit + 1 integration 통과 |
| 7 | `signals.py` 신규 — Signal dataclass + compute_signals 골격 | 신규 | import OK |
| 8 | `signals.py` — 5종 신호 + 사상최고 + 섹터 분류 | 채움 | 단위 테스트 통과 |
| 9 | `tests/test_signals.py` 작성 (16 케이스) | 신규 | 통과 |
| 10 | `main.py` — `build_v15_message()` 신규 함수 | 추가 | 더미 데이터로 호출 OK, 7 섹션 모두 출력 |
| 11 | `main.py` — `_compress_if_needed()` | 추가 | 가짜 5,000자 메시지 → 4,000 이하 압축 |
| 12 | `main.py` — `main()` 흐름 변경 | 수정 | 로컬 `python main.py` 슬랙 도착 |
| 13 | `tests/test_v15_message.py` 작성 (8 케이스) | 신규 | 통과 |
| 14 | 회귀 테스트 — Phase 1 17 케이스 모두 통과 | 검증 | `pytest tests/test_main.py` 16 passed |
| 15 | 통합 실행 — 로컬 실 슬랙 발송 1회 | 검증 | 실 메시지 도착, 26 데이터 확인 |
| 16 | git commit + push | 운영 | `gh workflow run`로 검증 |

### 11.2 의존성 설치

추가 의존성 없음 (Phase 1 그대로 — yfinance, requests).

### 11.3 Session Guide (Module Map + 권장 세션)

#### Module Map

| Module Key | 설명 | 파일 | 11.1 # |
|---|---|---|---|
| **module-1-config** | TICKERS 분리 + SECTOR_MAP + 임계값 | `config.py` | 1 |
| **module-2-data** | Quote dataclass + fetch_all() | `data.py` | 2–5 |
| **module-3-data-tests** | data 단위/통합 테스트 | `tests/test_data.py` | 6 |
| **module-4-signals** | Signal + compute_signals + sector | `signals.py` | 7–8 |
| **module-5-signals-tests** | signals 단위 테스트 | `tests/test_signals.py` | 9 |
| **module-6-message** | build_v15_message + 압축 정책 | `main.py` (확장) | 10–11 |
| **module-7-orchestration** | main() 흐름 변경 | `main.py` (수정) | 12 |
| **module-8-message-tests** | message 통합 테스트 | `tests/test_v15_message.py` | 13 |
| **module-9-regression** | Phase 1 회귀 검증 | (실행) | 14 |
| **module-10-deploy** | 운영 검증 | (실행) | 15–16 |

#### Recommended Session Plan

| 세션 | 범위 | DoD | 시간 |
|---|---|---|---|
| **S1 — Data** | module-1, 2, 3 | 로컬 `data.fetch_all()` 26 Quote 반환 + 10 테스트 통과 | 60–90분 |
| **S2 — Signals** | module-4, 5 | 더미 입력 → 5종 신호 정상 출력 + 16 테스트 통과 | 60분 |
| **S3 — Message** | module-6, 7, 8 | 로컬 `python main.py` → 슬랙 메시지 1통 (모든 섹션) + 8 테스트 통과 | 60–90분 |
| **S4 — Regression & Deploy** | module-9, 10 | Phase 1 17 + 신규 30+ 모두 통과 + 슬랙 도착 | 30분 |

**호출 예시**:
```bash
/pdca do morning-us-index-v15 --scope module-1-config,module-2-data,module-3-data-tests
/pdca do morning-us-index-v15 --scope module-4-signals,module-5-signals-tests
/pdca do morning-us-index-v15 --scope module-6-message,module-7-orchestration,module-8-message-tests
/pdca do morning-us-index-v15 --scope module-9-regression,module-10-deploy
```

또는 단일 세션:
```bash
/pdca do morning-us-index-v15
```

> 1인 + 4시간 추정이라 단일 세션도 가능하지만, S1 끝에서 데이터 모양이 확정돼야 S2/S3 진행이 깔끔. 분할 권장.

## 12. Risks Update (Plan §8 보완)

| Plan ID | Design 단계 추가 대응 |
|---|---|
| R-1 (yfinance 지연) | `yf.download()` 일괄 1회 + prepost 1회 = 총 2 HTTP, ~5–15초. NFR-02(60초) 충분 마진 |
| R-2 (시간외 정확도) | 1분봉 + prepost=True로 가져오되 데이터 없으면 조용히 None. 일부 종목만 잡혀도 OK |
| R-3 (4000자 초과) | `_compress_if_needed()` 자동 압축: 신호 없는 종목 1줄 → 거시 제거 → 시간외 제거 순 |
| R-4 (부분 미반환) | data.fetch_all()이 부분 실패 허용. 누락 ticker는 list에서 빠짐, warning log |
| R-5 (사상최고 boundary) | 임계값 0.999 명시 + 단위 테스트 boundary 케이스 (0.9995 / 0.998) |
| R-6 (Phase 1 회귀) | 함수/dataclass 미변경, main()만 수정. 17 테스트 그대로 통과 |
| R-7 (한국 ADR — TSMC/ASML/COIN) | 통합 테스트 시 검증, 문제 시 STOCKS에서 제외 옵션 |

## 13. Out of Scope (재확인)

- Phase 2: AI/뉴스
- Phase 3: 한국 시장, 멀티 채널, 차트 이미지
- Phase 4: 실시간 알림, self-hosted

## 14. References

- yfinance download (multi-ticker): https://github.com/ranaroussi/yfinance
- Slack message limits: https://api.slack.com/changelog/2018-04-truncating-really-long-messages
- Phase 1 Plan: `docs/01-plan/features/morning-us-index.plan.md`
- Phase 1.5 Plan: `docs/01-plan/features/morning-us-index-v15.plan.md`
- 사용자 요구 형태: `prompt/slack_output.md`

---

**다음 단계**: `/pdca do morning-us-index-v15` (단일) 또는 `/pdca do morning-us-index-v15 --scope module-1-config,module-2-data,module-3-data-tests` (S1만)
