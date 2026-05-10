---
name: morning-us-index-noai-v2
type: design
version: 0.1.0
status: draft
phase: design
level: dynamic
owner: jooladen
created: 2026-05-11
updated: 2026-05-11
plan: docs/01-plan/features/morning-us-index-noai-v2.plan.md
builds_on: morning-us-index-v15 (Phase 1.5, completed)
architecture: option-c-pragmatic-1-new-module
---

# Design — morning-us-index-noai-v2 (Phase 2-NoAI: 뉴스/어닝스/인사이더 추가, AI 미사용)

> **Summary**: Phase 1.5 코드 경로(Quote/Signal/build_v15_message)를 **변경 0** 유지한 채, 신규 모듈 `news.py` 하나만 추가하고 `build_v15_message` 시그니처에 `news_map=None` 옵션을 더해 객관적 사실 데이터 3종(헤드라인+VADER 감성, 어닝스 임박, 인사이더 매수)을 무료로 통합한다.
>
> **Project**: morning-us-index
> **Version**: 0.2.0 (Phase 2-NoAI)
> **Author**: jooladen
> **Date**: 2026-05-11
> **Status**: Draft
> **Planning Doc**: [morning-us-index-noai-v2.plan.md](../../01-plan/features/morning-us-index-noai-v2.plan.md)

---

## Context Anchor

> Plan 문서 §Context Anchor 그대로 복사. Design→Do 핸드오프에서 전략적 맥락 보존.

| 키 | 값 |
|---|---|
| **WHY** | 단타 후보의 "왜 떴는지" 객관적 단서를 매일 아침 자동 매칭. 지식 미세 조정보다 사실 노출 |
| **WHO** | 준 (단일 사용자, 단타 트레이더). KST 06:00 = 미장 마감 후 1–2시간 |
| **RISK** | yfinance.news 비공식 API 변경 / VADER 30% 오답 / 메시지 4000자 한도 / 인사이더 SEC 지연 |
| **SUCCESS** | 단타 후보에 헤드라인 매칭률 ≥80% / 메시지 ≤4000자 / Phase 1.5 회귀 0 / 운영 ≤30s |
| **SCOPE** | F1(헤드라인+감성) + F2(어닝스 배지) + F3(인사이더 매수). 14 종목 전체 헤드라인 X, 거시 캘린더 X |

---

## 1. Overview

### 1.1 Design Goals

- Phase 1.5의 5종 단타 신호 위에 **객관적 사실 데이터 3종** 통합 (AI/LLM 0)
- Phase 1.5 71 테스트 **회귀 0건**
- 신규 의존성 **1개** (`vaderSentiment>=3.3.2`) 만 추가
- 운영 실행 시간 **≤ 30초** (Phase 1.5의 9.3s + news ~7s)
- 메시지 **≤ 4,000자** 보장 (Slack 한도)
- 신규 단위/통합 테스트 **≥ 22 케이스**

### 1.2 Design Principles

- **Closed for modification, open for extension** — Phase 1.5 함수/dataclass(`Quote`, `Signal`, `fetch_all`, `compute_signals`) 미수정. 신규 모듈 1개 + 기존 시그니처에 default-`None` 인자 추가만으로 확장.
- **Fail-open per ticker** — 한 ticker의 news/earnings/insider 실패가 전체 발송을 막지 않음. 누락 종목은 조용히 skip, 다른 종목은 정상 표시.
- **Confidence over coverage** — VADER `|compound| ≥ 0.3` 임계값으로 모호한 헤드라인 surface 금지. 잘못된 점수보다 미표시가 낫다.
- **Feature flag for runtime override** — `ENABLE_NEWS=false` 시 byte 단위로 Phase 1.5와 동일 메시지 출력 (회귀 안전망).

### 1.3 Plan Open Questions 해소

| Open Q (Plan §11) | Design 결정 | 근거 |
|---|---|---|
| **OQ-1** yfinance.news 스키마 변경 fallback | **Defensive dict access + try/except per ticker.** 헤드라인 누락 시 후보 줄만 표시, 메시지 발송 정상. 별도 fallback 데이터 소스 없음. | 추가 의존성 0 원칙 + 무료. SEC EDGAR fallback은 Phase 2-AI |
| **OQ-2** `ENABLE_NEWS` flag default | **`true` (운영 즉시 활성화).** `os.environ.get("ENABLE_NEWS", "true").lower() == "true"` | Plan 가정 그대로. 안전망은 false override |
| **OQ-3** 헤드라인 길이 truncate | **80자 초과 시 77자 + `...`.** 슬랙 모바일 1줄 ≈ 80자 폭 | 한 줄 가독성. Plan US-1 5초 판단 |
| **OQ-4** 인사이더 섹션 정렬 | **net buy USD 내림차순.** 큰 신호 먼저 | 트레이더 의사결정 최적화 |
| **OQ-5** Phase 1.5 보험 cron 제거 시점 | **Phase 2-NoAI 운영 7일 무사고 후 Report 단계에서 제거.** 본 Design 단계에서는 보험 cron 유지 | 안전 우선 |

---

## 2. Architecture Options

### 2.0 Architecture Comparison

3 옵션을 평가했으며, 사용자의 "막힘없이 진행" 지시에 따라 **Option C — Pragmatic Balance**로 자동 선택. Plan §1 본문이 이미 Option C 방향(`news.py` 신규 + `build_v15_message`에 `news_map=None` 인자)을 가정하고 있음.

| 기준 | Option A: Minimal | Option B: Clean | Option C: Pragmatic ✅ |
|---|:-:|:-:|:-:|
| **접근** | `main.py`에 news 로직 인라인. 함수 3개 추가 | `news/` 패키지 (fetcher/scorer/aggregator 3 파일) + `domain/news_snapshot.py` 분리 | `news.py` 단일 모듈 (1 파일) + `NewsSnapshot` dataclass |
| **신규 파일** | 0 | 4–5 | **2** (news.py + test_news.py) |
| **수정 파일** | 3 (main.py, config.py, requirements.txt, test_v15_message.py) | 3 (동일) | **3** (main.py, config.py, requirements.txt) + test_v15_message.py 추가 케이스 |
| **복잡도** | Low | High | **Medium** |
| **유지보수성** | Medium (main.py 비대화) | High (계층 명확) | **High** (단일 모듈로 관심사 격리) |
| **공수** | Low (반나절) | High (2일) | **Medium** (반나절~하루) |
| **리스크** | main.py 600+ 줄로 비대 → 회귀 위험 ↑ | 과잉 설계 (1 모듈에 3 파일 분할은 YAGNI) | Low — Phase 1.5 코드 미수정, 단일 모듈 격리 |
| **테스트 격리** | main.py 테스트와 혼재 | 각 레이어 단위 테스트 깔끔 | **news.py 단위 테스트 독립** |
| **추천 시점** | 1회성 핫픽스 | 장기 멀티팀 프로젝트 | **1인 + 단일 사이클 + AI 분리** |

**Selected**: **Option C — Pragmatic Balance**
**Rationale**: Phase 1.5 코드 경로(`Quote`, `Signal`, `build_v15_message`, `fetch_all`, `compute_signals`) 미수정 보장 + 단일 모듈 격리로 회귀 위험 0. Option B는 1 사이클짜리 작업에 4 파일 분할은 과잉 설계(YAGNI). Option A는 main.py를 600줄 이상으로 비대화시켜 가독성 저하.

### 2.1 Component Diagram

```
┌──────────────────────────────────────────────────────────────────────┐
│  main.py — orchestrator                                              │
│                                                                      │
│   load_slack_webhook_url()                                           │
│         ↓                                                            │
│   ┌─────────────────┐    ┌─────────────────┐                         │
│   │  data.fetch_all │    │  news.fetch_*   │  (NEW, 병렬 ThreadPool)│
│   │   → list[Quote] │    │  → news_map     │                         │
│   └────────┬────────┘    └────────┬────────┘                         │
│            ↓                      ↓                                  │
│   signals.compute_signals    NewsSnapshot dict[str, NS]              │
│            ↓                      ↓                                  │
│   ┌──────────────────────────────────────────┐                       │
│   │  main.build_v15_message(                 │  (확장: news_map 추가)│
│   │    quotes, signals,                      │                       │
│   │    news_map=None  ←──── default 호환성   │                       │
│   │  )                                       │                       │
│   └──────────────────────┬───────────────────┘                       │
│                          ↓                                           │
│              _compress_if_needed(msg)                                │
│                          ↓                                           │
│              post_slack(url, message)                                │
└──────────────────────────────────────────────────────────────────────┘

           Phase 1.5 (변경 없음)        Phase 2-NoAI (신규)
           ─────────────────────         ────────────────────
           data.py                      news.py          🆕
           signals.py                   tests/test_news.py  🆕
           config.py 일부 추가
           main.py build_v15_message에 news_map 인자만 추가
           requirements.txt 1줄 추가 (vaderSentiment)
```

### 2.2 Data Flow

```
yfinance API (3 종류, 14 stocks)
        │
        │  ThreadPoolExecutor(max_workers=8)
        │  ── 14 ticker × 3 호출 = 42 future ──→ ~3–4s 완료
        ↓
┌─────────────────────────────────────────────────┐
│  per-ticker (parallel)                          │
│    Ticker.news        → top headline + source   │
│    Ticker.earnings_dates → next date / days     │
│    Ticker.insider_purchases → 7d net buy USD    │
└────────────────┬────────────────────────────────┘
                 ↓
┌─────────────────────────────────────────────────┐
│  per-headline (serial, after parallel fetch)    │
│    VADER analyzer.polarity_scores(title)        │
│    → compound score ∈ [-1.0, +1.0]             │
│    Filter: |compound| ≥ 0.3 만 surface          │
└────────────────┬────────────────────────────────┘
                 ↓
        dict[str, NewsSnapshot]
                 ↓
        build_v15_message (news_map 주입)
                 ↓
        ┌─────────────────────────┐
        │  message sections:      │
        │   - 헤더                │
        │   - 📈 [지수]           │
        │   - 🎯 [단타 핵심]      │
        │   - 🏭/📱/🚗 [섹터]     │  ← 📅 어닝스 배지 inline (F2)
        │   - 💰 [거시]           │
        │   - 💼 [내부자 매수]    │  ← 신규 섹션 (F3, 발화 시만)
        │   - 🚨 [오늘 단타 후보] │  ← └ 📰 헤드라인 (F1)
        └─────────────────────────┘
```

### 2.3 Dependencies

| Component | Depends On | Purpose |
|---|---|---|
| `news.py` | `data.Quote` (read-only), `config` 상수, `yfinance.Ticker`, `vaderSentiment.SentimentIntensityAnalyzer` | 종목별 news/earnings/insider 조회 + 감성 점수 |
| `main.build_v15_message` | `news.NewsSnapshot` (optional import) | 메시지에 헤드라인/배지/인사이더 통합 |
| `tests/test_news.py` | `news.py`, `unittest.mock.patch`, fixture data | 단위 테스트 |
| `tests/test_v15_message.py` (확장) | `news.NewsSnapshot` | news_map 통합 케이스 |

**의존성 방향**:
```
main.py ──→ news.py ──→ data.py (read-only: Quote)
   │            │
   │            └──→ config.py
   ↓
signals.py ──→ data.py
```
순환 의존 없음. news.py는 data.py의 Quote에만 의존하며 signals.py와 무관.

---

## 3. Data Model

### 3.1 `NewsSnapshot` dataclass (신규, `news.py`)

```python
from dataclasses import dataclass
from datetime import date

@dataclass(frozen=True)
class NewsSnapshot:
    """종목별 뉴스/어닝스/인사이더 통합 스냅샷.

    어느 필드든 None일 수 있으며 (부분 실패 허용), 모두 None인 NewsSnapshot은
    `is_empty` property로 식별 후 dict에서 생략 가능.
    """
    ticker: str

    # F1: 헤드라인 + VADER compound
    # tuple = (title_truncated, source, vader_compound)
    # |compound| ≥ NEWS_VADER_COMPOUND_THRESHOLD (0.3) 만 채워짐
    top_headline: tuple[str, str, float] | None

    # F2: 어닝스 임박
    next_earnings_date: date | None
    days_to_earnings: int | None       # 0 이상, 7 초과면 메시지 미표시

    # F3: 인사이더 매수
    insider_net_buy_usd_7d: float | None   # 양수 = 순매수. None = 데이터 없음

    @property
    def is_empty(self) -> bool:
        """모든 필드 None → 메시지 통합 시 생략 대상."""
        return (
            self.top_headline is None
            and self.next_earnings_date is None
            and self.insider_net_buy_usd_7d is None
        )

    @property
    def has_earnings_badge(self) -> bool:
        """📅 배지 표시 조건: days_to_earnings ∈ [0, EARNINGS_LOOKAHEAD_DAYS]."""
        return (
            self.days_to_earnings is not None
            and 0 <= self.days_to_earnings <= EARNINGS_LOOKAHEAD_DAYS
        )

    @property
    def has_significant_insider_buy(self) -> bool:
        """💼 섹션 표시 조건: net buy ≥ INSIDER_BUY_USD_THRESHOLD ($1M)."""
        return (
            self.insider_net_buy_usd_7d is not None
            and self.insider_net_buy_usd_7d >= INSIDER_BUY_USD_THRESHOLD
        )
```

**불변성 (frozen=True)**: `Quote`/`Signal`과 동일 패턴 유지. 테스트에서 == 비교, hash 키로 사용 가능.

### 3.2 `config.py` 신규 상수

| 상수 | 값 | 용도 |
|---|---|---|
| `NEWS_VADER_COMPOUND_THRESHOLD` | `0.3` | `\|compound\| ≥ 0.3` 만 surface (Plan FR-03) |
| `NEWS_HEADLINE_MAX_CHARS` | `80` | 80자 초과 시 77자 + "..." (OQ-3) |
| `EARNINGS_LOOKAHEAD_DAYS` | `7` | 📅 배지 표시 임계일 (Plan FR-04) |
| `INSIDER_BUY_USD_THRESHOLD` | `1_000_000.0` | 7일 순매수 ≥ $1M (Plan FR-05) |
| `INSIDER_LOOKBACK_DAYS` | `7` | 인사이더 합산 기간 |
| `NEWS_THREAD_POOL_WORKERS` | `8` | ThreadPoolExecutor max_workers (Plan FR-06) |
| `NEWS_FETCH_TIMEOUT_SEC` | `5.0` | per-ticker yfinance 호출 타임아웃 |
| `ENABLE_NEWS_ENV_VAR` | `"ENABLE_NEWS"` | feature flag 환경변수 이름 |
| `ENABLE_NEWS_TRANSLATION_ENV_VAR` | `"ENABLE_NEWS_TRANSLATION"` | FR-13 한글 번역 feature flag (default true) |
| `NEWS_TRANSLATION_TIMEOUT_SEC` | `3.0` | per-headline 번역 호출 타임아웃 (deep-translator 비공식 endpoint 안전망) |

```python
# Phase 2-NoAI 신규 상수
NEWS_VADER_COMPOUND_THRESHOLD: float = 0.3
NEWS_HEADLINE_MAX_CHARS: int = 80
EARNINGS_LOOKAHEAD_DAYS: int = 7
INSIDER_BUY_USD_THRESHOLD: float = 1_000_000.0
INSIDER_LOOKBACK_DAYS: int = 7
NEWS_THREAD_POOL_WORKERS: int = 8
NEWS_FETCH_TIMEOUT_SEC: float = 5.0
ENABLE_NEWS_ENV_VAR: str = "ENABLE_NEWS"


def is_news_enabled() -> bool:
    """ENABLE_NEWS 환경변수 파싱. default true (OQ-2)."""
    return os.environ.get(ENABLE_NEWS_ENV_VAR, "true").strip().lower() == "true"
```

### 3.3 외부 데이터 스키마 (yfinance)

#### Ticker.news (list[dict])
```python
# yfinance ≥ 0.2.40 결과 (Phase 2-NoAI 작성 시점)
[
    {
        "uuid": "...",
        "title": "Nvidia beats Q3 estimates, raises guidance",  # ← 사용
        "publisher": "Reuters",                                  # ← 사용 (source)
        "link": "https://...",
        "providerPublishTime": 1715432100,  # unix ts
        "type": "STORY",
        ...
    },
    ...
]
```
**Defensive access**: `item.get("title", "").strip()`, `item.get("publisher", "?")`. 키 누락 시 해당 헤드라인 skip.

#### Ticker.earnings_dates (pandas.DataFrame)
```
Index: DatetimeIndex (UTC tz-aware)
Columns: EPS Estimate, Reported EPS, Surprise(%)
```
**처리**: index → date, KST today와 차이(days), 0 이상이고 가장 가까운 미래 날짜만 추출. 과거 날짜는 무시.

#### Ticker.insider_purchases (pandas.DataFrame)
```
Columns: ['Insider Purchases - Last 6m', 'Shares', '...']
```
**처리**: pandas 스키마가 yfinance 버전마다 다름. 보수적으로 **net buy USD 직접 추출이 불안정**하므로:
- 1차: `Ticker.insider_transactions`에서 최근 `INSIDER_LOOKBACK_DAYS`일 + `Transaction == "Purchase"` 필터 + `Value` 합산
- 데이터 부재 시 `insider_net_buy_usd_7d = None`

⚠️ 이 부분은 Do 단계에서 실 데이터로 검증 필요. fail-open 보장.

---

## 4. Module Design

### 4.1 `news.py` (신규)

```python
"""Phase 2-NoAI — 종목별 뉴스/어닝스/인사이더 통합 스냅샷.

Design Ref: §3.1, §3.2
Plan FR-01 ~ FR-07
"""

from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from config import (
    EARNINGS_LOOKAHEAD_DAYS,
    INSIDER_BUY_USD_THRESHOLD,
    INSIDER_LOOKBACK_DAYS,
    NEWS_FETCH_TIMEOUT_SEC,
    NEWS_HEADLINE_MAX_CHARS,
    NEWS_THREAD_POOL_WORKERS,
    NEWS_VADER_COMPOUND_THRESHOLD,
    TIMEZONE_KST,
)
from data import Quote


# ─────────────────────────────────────────────────────────────
# Public Dataclass
# ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class NewsSnapshot:
    """종목별 뉴스/어닝스/인사이더 통합 스냅샷.

    Plan FR-02: top_headline = (title, source, vader_compound)
    """
    ticker: str
    top_headline: tuple[str, str, float] | None
    next_earnings_date: date | None
    days_to_earnings: int | None
    insider_net_buy_usd_7d: float | None

    @property
    def is_empty(self) -> bool: ...
    @property
    def has_earnings_badge(self) -> bool: ...
    @property
    def has_significant_insider_buy(self) -> bool: ...


# ─────────────────────────────────────────────────────────────
# VADER (singleton)
# ─────────────────────────────────────────────────────────────

_VADER_ANALYZER: SentimentIntensityAnalyzer | None = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    """VADER 분석기 lazy 초기화."""
    global _VADER_ANALYZER
    if _VADER_ANALYZER is None:
        _VADER_ANALYZER = SentimentIntensityAnalyzer()
    return _VADER_ANALYZER


def _score_headline(title: str) -> float:
    """제목 → VADER compound score ∈ [-1.0, +1.0]."""
    return _get_analyzer().polarity_scores(title).get("compound", 0.0)


def _truncate(title: str, max_chars: int = NEWS_HEADLINE_MAX_CHARS) -> str:
    """80자 초과 시 77자 + '...' (OQ-3)."""
    title = title.strip()
    return title if len(title) <= max_chars else title[: max_chars - 3].rstrip() + "..."


# ─────────────────────────────────────────────────────────────
# Per-ticker fetchers (각각 fail-open)
# ─────────────────────────────────────────────────────────────

def fetch_news_for_ticker(ticker: str) -> tuple[str, str, float] | None:
    """yfinance.Ticker.news 첫 번째 적합 항목 → (title_truncated, source, compound).

    |compound| < NEWS_VADER_COMPOUND_THRESHOLD 면 None 반환 (Plan FR-03).
    어떤 예외든 None으로 swallow (fail-open).
    """
    try:
        items = yf.Ticker(ticker).news or []
    except Exception as e:
        sys.stderr.write(f"[WARN] news fetch failed for {ticker}: {type(e).__name__}\n")
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        title = (item.get("title") or "").strip()
        if not title:
            continue
        source = item.get("publisher") or "?"
        compound = _score_headline(title)
        if abs(compound) < NEWS_VADER_COMPOUND_THRESHOLD:
            continue  # 다음 헤드라인 시도
        return (_truncate(title), source, compound)

    return None


def fetch_earnings_for_ticker(ticker: str) -> tuple[date | None, int | None]:
    """yfinance.Ticker.earnings_dates → (next_date, days_from_today).

    KST 기준 오늘 ≤ next_date 인 가장 가까운 미래 일자.
    데이터 없거나 미래 일자 없으면 (None, None).
    """
    try:
        df = yf.Ticker(ticker).earnings_dates
    except Exception:
        return (None, None)
    if df is None or df.empty:
        return (None, None)

    today_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()
    try:
        future_dates = sorted(
            d.date()
            for d in df.index.to_pydatetime()
            if d.date() >= today_kst
        )
    except Exception:
        return (None, None)
    if not future_dates:
        return (None, None)

    next_date = future_dates[0]
    days = (next_date - today_kst).days
    return (next_date, days)


def fetch_insider_for_ticker(ticker: str) -> float | None:
    """yfinance.Ticker.insider_transactions 최근 INSIDER_LOOKBACK_DAYS(7)일 net buy USD.

    1차: insider_transactions의 Purchase row Value 합산.
    실패 또는 데이터 부재 시 None.
    """
    try:
        df = yf.Ticker(ticker).insider_transactions
    except Exception:
        return None
    if df is None or df.empty:
        return None

    try:
        today_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()
        # 컬럼명 yfinance 버전마다 다를 수 있어 defensive
        date_col = next(
            (c for c in df.columns if "date" in str(c).lower()), None
        )
        type_col = next(
            (c for c in df.columns
             if "transaction" in str(c).lower() or "type" in str(c).lower()),
            None,
        )
        value_col = next(
            (c for c in df.columns if "value" in str(c).lower()), None
        )
        if not (date_col and type_col and value_col):
            return None

        df = df.copy()
        df["_d"] = df[date_col].apply(
            lambda v: v.date() if hasattr(v, "date") else None
        )
        cutoff = today_kst.toordinal() - INSIDER_LOOKBACK_DAYS
        mask = df["_d"].apply(
            lambda d: d is not None and d.toordinal() >= cutoff
        ) & df[type_col].astype(str).str.contains("Purchase", case=False, na=False)

        total = df.loc[mask, value_col].sum()
        return float(total) if total else None
    except Exception:
        return None


def _build_snapshot(ticker: str) -> NewsSnapshot:
    """단일 ticker의 3 종류 데이터를 합쳐 NewsSnapshot 생성. fail-open."""
    headline = fetch_news_for_ticker(ticker)
    earnings_date, days = fetch_earnings_for_ticker(ticker)
    insider_usd = fetch_insider_for_ticker(ticker)
    return NewsSnapshot(
        ticker=ticker,
        top_headline=headline,
        next_earnings_date=earnings_date,
        days_to_earnings=days,
        insider_net_buy_usd_7d=insider_usd,
    )


# ─────────────────────────────────────────────────────────────
# Parallel fetcher (entry point)
# ─────────────────────────────────────────────────────────────

def fetch_news_all(stocks: Iterable[Quote]) -> dict[str, NewsSnapshot]:
    """모든 stock의 NewsSnapshot을 ThreadPool 병렬 조회.

    Plan FR-06: max_workers=8 (보수적). 14 stocks × 1s/each = 14s → ~3–4s.
    Plan FR-07: per-ticker 실패 허용. 결과 dict에서 누락 (is_empty=True도 포함될 수 있음).

    Args:
        stocks: data.fetch_all() 결과 중 category="stock" 14개.

    Returns:
        dict[ticker, NewsSnapshot]. 예외 발생한 ticker는 누락.
    """
    tickers = [q.ticker for q in stocks if q.category == "stock"]
    if not tickers:
        return {}

    results: dict[str, NewsSnapshot] = {}
    with ThreadPoolExecutor(max_workers=NEWS_THREAD_POOL_WORKERS) as pool:
        futures = {pool.submit(_build_snapshot, t): t for t in tickers}
        for fut in as_completed(futures, timeout=NEWS_FETCH_TIMEOUT_SEC * 4):
            ticker = futures[fut]
            try:
                snapshot = fut.result(timeout=NEWS_FETCH_TIMEOUT_SEC)
                results[ticker] = snapshot
            except Exception as e:
                sys.stderr.write(
                    f"[WARN] news snapshot failed for {ticker}: {type(e).__name__}\n"
                )
                # ticker 결과 누락 (Plan FR-07 fail-open)

    return results
```

### 4.2 `main.py` 변경 (build_v15_message 시그니처 확장)

**변경 범위**: 단 1개 함수 시그니처에 `news_map=None` 추가 + 헤드라인 들여쓰기/배지/인사이더 섹션 합치는 로직 추가. 다른 함수 (`fetch_indices`, `build_message`, `_format_quote_line`, `_format_v15_quote_line`, `_format_compact_line`, `_compress_if_needed`, `post_slack`)는 **미수정**.

```python
# 신규 import (top)
from news import NewsSnapshot

def _format_v15_quote_line_with_earnings(
    q: Quote,
    sig: Signal,
    news: NewsSnapshot | None,
) -> str:
    """기존 _format_v15_quote_line 결과 + 📅Xd 배지 inline."""
    base = _format_v15_quote_line(q, sig)
    if news is not None and news.has_earnings_badge:
        return f"{base} 📅{news.days_to_earnings}d"
    return base


def _format_insider_section(news_map: dict[str, NewsSnapshot], quotes: list[Quote]) -> list[str]:
    """💼 [내부자 매수 급증 7일 (≥$1M)] 섹션 라인 리스트. 발화 종목 없으면 빈 리스트."""
    label_by_ticker = {q.ticker: q.label for q in quotes}
    significant = [
        ns for ns in news_map.values() if ns.has_significant_insider_buy
    ]
    if not significant:
        return []
    # OQ-4: net buy 큰 순 정렬
    significant.sort(key=lambda ns: ns.insider_net_buy_usd_7d or 0.0, reverse=True)

    lines = ["💼 [내부자 매수 급증 7일 (≥$1M)]"]
    for ns in significant:
        label = label_by_ticker.get(ns.ticker, ns.ticker)
        usd = ns.insider_net_buy_usd_7d or 0.0
        usd_m = usd / 1_000_000.0
        lines.append(f"• {ns.ticker} {label}: 임원 +${usd_m:,.1f}M 매수")
    lines.append("")
    return lines


def build_v15_message(
    quotes: list[Quote],
    signals: dict[str, Signal],
    news_map: dict[str, NewsSnapshot] | None = None,  # 🆕 Phase 2-NoAI
) -> str:
    """Phase 1.5 + Phase 2-NoAI 메시지 빌드.

    Plan NFR-07: news_map=None 시 Phase 1.5와 byte 단위 동일 출력 (회귀 안전).
    news_map 주입 시 추가 출력:
      - 종목 줄 끝에 📅Xd 배지 (sector 섹션)
      - 단타 후보 줄 아래 └ 📰 헤드라인 (F1)
      - 💼 인사이더 섹션 (거시 다음, 단타 후보 이전)
    """
    # 기존 로직 유지 — 단, sector 그룹에서 _format_v15_quote_line 호출을
    # _format_v15_quote_line_with_earnings(q, sig, news_map.get(q.ticker))로 교체.
    # 거시 섹션 다음에 _format_insider_section() 호출.
    # 단타 후보 루프에서 news_map.get(q.ticker).top_headline 있으면
    # `  └ 📰 {compound:+.2f} "{title}" ({source})` 들여쓰기 추가.
    ...
```

**핵심 변경점** (Phase 1.5 build_v15_message 대비):

| 위치 | 변경 | 영향 |
|---|---|---|
| 시그니처 | `news_map: dict[str, NewsSnapshot] \| None = None` 추가 | `news_map=None`이면 Phase 1.5와 byte 동일 |
| sector 섹션 stocks 라인 | `_format_v15_quote_line` → `_format_v15_quote_line_with_earnings` | 📅 배지 inline (news_map 있을 때만) |
| 거시 섹션 다음 | `_format_insider_section()` 호출 | 💼 섹션 (발화 시만) |
| 단타 후보 루프 | top_headline 있으면 `  └ 📰 {compound:+.2f} "{title}" ({source})` 추가 | 들여쓰기 줄 |

### 4.3 `main.py` orchestration 변경 (`main()` 함수)

```python
from news import fetch_news_all
from config import is_news_enabled

def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        webhook_url = load_slack_webhook_url()
        quotes = fetch_all()
        signals_map = compute_signals(quotes)

        # 🆕 Phase 2-NoAI: ENABLE_NEWS=true (default)면 news_map fetch
        news_map = None
        if is_news_enabled():
            stocks = [q for q in quotes if q.category == "stock"]
            news_map = fetch_news_all(stocks)

        message = build_v15_message(quotes, signals_map, news_map=news_map)
        post_slack(webhook_url, message)
        print(
            f"[OK] morning-us-index-noai-v2 발송 완료 "
            f"({len(quotes)} quotes, {len(news_map or {})} news snapshots, "
            f"{len(message)} chars)"
        )
        return 0
    except Exception as e:
        # 기존 에러 처리 그대로
        ...
```

### 4.4 `requirements.txt` 변경

```diff
 yfinance>=0.2.40
 requests>=2.31
+vaderSentiment>=3.3.2
+deep-translator>=1.11.4    # FR-13: 한글 번역 (운영 후 추가)
```

### 4.4.1 FR-13 한글 번역 통합 흐름

```
fetch_news_for_ticker(ticker)
   │
   ├─ yf.Ticker(ticker).news → list[dict]
   │
   └─ for item in items:
        title_en = _extract_title(item)
        compound = _score_headline(title_en)        ← VADER는 영문 원문으로 계산
        if abs(compound) < 0.3: continue
        title_display = (
            _translate_to_korean(title_en)          ← 호재/악재 판정 후 번역
            if is_news_translation_enabled()        ← env flag
            else title_en
        )
        return (_truncate(title_display), source, compound)   ← truncate는 표시할 텍스트 기준
```

**핵심 결정**:
- VADER score 계산은 **영문 원문**으로 (한글 lexicon은 VADER에 없음, 번역 오역이 score 오염 가능)
- |compound|≥0.3 통과 후에만 번역 (실패 헤드라인을 굳이 번역 안 함, 호출 비용 ↓)
- truncate는 **번역 후** 텍스트 기준 (한글이 영문보다 짧을 수 있음)
- 번역 실패 시 원문 fallback (fail-open, 사용자 메시지 발송 보장)

### 4.5 메시지 mockup (FR-08, FR-09, FR-10 통합)

```
[2026-05-12 KST 06:00 발송] 직전 거래일: 2026-05-11

📈 [지수]
• 나스닥 ^IXIC: 26,247.08  ▲ +440.88 (+1.71%) 🟢 ★
• S&P 500 ^GSPC: 7,398.93  ▲ +61.82 (+0.84%) 🟢
• 다우 ^DJI: 49,609.16  ▲ +9.92 (+0.02%) 🟢
• 러셀2000 ^RUT: 2,234.50  ▼ -6.71 (-0.30%) 🔴
• VIX ^VIX: 23.50  ▲ +1.16 (+5.20%) 🟢 ⚡

🎯 [단타 핵심: 선물 + 시간외]
• S&P 미니 ES=F: 7,412 ▲ +0.18%
• NQ=F: +0.24%
• YM=F: +0.01%
• AHRS NVDA: +1.2% 📊

🏭 [반도체]
• 엔비디아 NVDA: 142.50  ▲ +2.45 (+1.75%) 🟢 🔥 📅3d         ← F2
• 인텔 INTC: 32.15  ▲ +3.95 (+13.96%) 🟢 🎯🔥
• 마이크론 MU: 95.40  ▲ +12.45 (+15.00%) 🟢 ★ 🆙🔥
• AMD: +0.85%
• ASML: +2.10%
• AVGO: +0.42%
• TSM: +1.80%

📱 [빅테크]
• 애플 AAPL: 232.15  ▲ +4.66 (+2.05%) 🟢
• 마이크로소프트 MSFT: 425.80  ▼ -5.78 (-1.34%) 🔴
• GOOGL: +0.50%
• META: +1.20%
• AMZN: +0.56%

🚗 [EV/암호]
• 테슬라 TSLA: 312.40  ▲ +12.07 (+4.02%) 🟢
• COIN: +2.10%

💰 [거시]
• 원/달러 USDKRW=X: 1,375.20  ▼ -4.13 (-0.30%) 🔴
• WTI CL=F: $95.42  ▲ +0.58 (+0.61%) 🟢
• 금 GC=F: $2,400.10  ▲ +12.00 (+0.50%) 🟢
• 비트코인 BTC-USD: $90,000  ▼ -900 (-1.00%) 🔴

💼 [내부자 매수 급증 7일 (≥$1M)]                              ← F3 (신규 섹션)
• TSLA 테슬라: 임원 +$3.2M 매수
• NVDA 엔비디아: 임원 +$1.4M 매수

🚨 [오늘 단타 후보 (신호 2개 이상)]
• 인텔 INTC — 🎯🔥 (갭 + 거래량)
  └ 📰 -0.12 "Intel reorganization sparks investor concern" (Bloomberg)   ← F1
• 마이크론 MU — 🆙🔥 (52주 신고가 + 거래량)
  └ 📰 +0.65 "Micron memory demand surges on AI capex" (Reuters)
```

---

## 5. UI/UX Design

**N/A** — 백엔드 스크립트. UI는 Slack 메시지 그 자체. §4.5 mockup 참조.

---

## 6. Error Handling

### 6.1 단계별 에러 매트릭스

| 단계 | 실패 종류 | 대응 | 사용자 영향 |
|---|---|---|---|
| `fetch_news_for_ticker` 예외 | yfinance API 변경, 네트워크 | None 반환 + warn 로그 | 해당 종목 헤드라인만 미표시 |
| `fetch_earnings_for_ticker` 예외 | df 스키마 변경, NaT | (None, None) 반환 | 해당 종목 📅 배지 미표시 |
| `fetch_insider_for_ticker` 예외 | df 스키마 변경, 컬럼 부재 | None 반환 | 해당 종목 인사이더 합산 0 처리 |
| `_build_snapshot` 예외 | 알 수 없는 예외 | ThreadPool future.exception catch + warn | dict에서 ticker 누락 |
| `fetch_news_all` ThreadPool timeout (20s) | yfinance 전체 응답 지연 | as_completed timeout 발생, 부분 결과 반환 | 누락된 ticker는 메시지에서 빠짐 |
| `is_news_enabled()=False` (env override) | 사용자 명시 비활성화 | news_map=None → Phase 1.5 동일 동작 | Phase 1.5 메시지 |
| `vaderSentiment` import 실패 | 의존성 미설치 | news.py 모듈 import 시점에 ImportError → main() try/except에서 catch → 에러 슬랙 발송 | 운영 메시지 미발송 (단, 의존성 단계에서 차단) |
| 메시지 4,000자 초과 | 단타 후보 + 인사이더 동시 다발 | `_compress_if_needed` 자동 압축 (기존 로직) | 메시지 잘림 가능, 본문은 도착 |

### 6.2 부분 실패 시 메시지 보장

```
케이스 A: news_map fetch 0건 성공 (모든 ticker 실패)
  → news_map = {} (빈 dict)
  → build_v15_message는 Phase 1.5와 거의 동일 (인사이더/배지/헤드라인 모두 미표시)
  → 메시지 발송 정상

케이스 B: news_map 14중 5개 성공
  → 5개 ticker만 배지/헤드라인 surface
  → 나머지 9개는 Phase 1.5와 동일
  → 메시지 발송 정상

케이스 C: VADER import 실패 (의존성 누락)
  → news.py 모듈 로드 시 ImportError
  → main()에서 catch → 에러 메시지 슬랙 발송
  → 운영자(준)가 즉시 인지 가능
```

### 6.3 로그 정책

- **stderr**: per-ticker 실패는 `[WARN] news fetch failed for {ticker}: {ExcType}` 한 줄. GitHub Actions log에서 확인 가능.
- **stdout**: 성공 시 `[OK] morning-us-index-noai-v2 발송 완료 (N quotes, M news snapshots, X chars)` 1줄.

---

## 7. Configuration & Secrets

| 항목 | 변경 |
|---|---|
| Secrets | **변경 0** (`SLACK_WEBHOOK_URL` 1개만 사용) |
| Env vars (선택) | **신규 1개**: `ENABLE_NEWS` (default `"true"`). false 시 Phase 1.5 동작 |
| `requirements.txt` | `vaderSentiment>=3.3.2` 1줄 추가 |
| `.github/workflows/daily_report.yml` | **변경 0** (cron / Python 3.11 / secrets 동일) |

---

## 8. Test Plan (v2.3.0) — L1 단위/통합 ~22 케이스

> **CRITICAL**: WHAT to test 정의. 실제 테스트 코드는 Do 단계에서 구현.

### 8.1 Test Scope

| Type | Target | Tool | Phase |
|---|---|---|---|
| **L1: Unit** | `news.py` 순수 함수 (VADER scoring, truncate, snapshot build) | pytest + unittest.mock | Do |
| **L1: Unit** | `_format_insider_section`, `build_v15_message` news_map 통합 | pytest | Do |
| **L1: Integration** | 실 yfinance 호출 (integration marker) | pytest -m integration | Do |
| **L2/L3** | N/A (백엔드 스크립트, UI 없음) | — | — |

### 8.2 `tests/test_news.py` 신규 (~22 케이스)

#### 8.2.1 VADER scoring (6 케이스)

| # | 항목 | 입력 | 통과 기준 |
|---|---|---|---|
| L1-news-1 | 긍정 헤드라인 — 명확한 호재 | "Nvidia beats Q3 estimates, raises guidance" | compound ≥ 0.3, surface 됨 |
| L1-news-2 | 부정 헤드라인 — 명확한 악재 | "Company faces major lawsuit" | compound ≤ -0.3, surface 됨 |
| L1-news-3 | 중립 헤드라인 — 무방향 | "Quarterly report scheduled for Tuesday" | \|compound\| < 0.3, None 반환 |
| L1-news-4 | VADER 약점 — 'dwindles' 누락 | "Stock dwindles after disappointing earnings" | \|compound\| < 0.3, None (알려진 한계) |
| L1-news-5 | 강한 부정 — 다중 부정어 | "Stock crashes, plunges, terrible loss" | compound ≤ -0.5 |
| L1-news-6 | 강한 긍정 — 다중 호재어 | "Tesla surges on breakthrough, record profit" | compound ≥ 0.5 |

#### 8.2.2 `_truncate` (2 케이스)

| # | 항목 | 입력 | 통과 기준 |
|---|---|---|---|
| L1-news-7 | 80자 이하 — 그대로 반환 | "Short headline" | 입력 그대로 |
| L1-news-8 | 80자 초과 — 77자 + "..." | 100자 영문 헤드라인 | len(result) == 80, 끝이 "..." |

#### 8.2.3 `fetch_news_for_ticker` mocked (4 케이스)

| # | 항목 | mock 동작 | 통과 기준 |
|---|---|---|---|
| L1-news-9 | 정상 — 첫 항목이 |compound|≥0.3 | yf.Ticker.news = [{"title": "Nvidia beats...", "publisher": "Reuters"}, ...] | (truncated_title, "Reuters", +0.7+) 반환 |
| L1-news-10 | 첫 항목 임계값 미달, 두 번째 통과 | 1번째 \|c\|<0.3, 2번째 \|c\|≥0.3 | 두 번째 반환 |
| L1-news-11 | 모든 항목 임계값 미달 | 모든 항목 \|c\|<0.3 | None |
| L1-news-12 | yf.Ticker.news raises | Exception | None + warn log |

#### 8.2.4 `fetch_earnings_for_ticker` mocked (3 케이스)

| # | 항목 | mock 동작 | 통과 기준 |
|---|---|---|---|
| L1-news-13 | 미래 어닝스 3일 후 | DatetimeIndex with today+3 | (date(...+3), 3) |
| L1-news-14 | 과거 어닝스만 | DatetimeIndex with today-5 | (None, None) |
| L1-news-15 | df 빈 / None | empty DataFrame | (None, None) |

#### 8.2.5 `fetch_insider_for_ticker` mocked (3 케이스)

| # | 항목 | mock 동작 | 통과 기준 |
|---|---|---|---|
| L1-news-16 | 7일 내 Purchase 2건 합산 | df with 2 Purchase rows × $500K | 1_000_000.0 반환 |
| L1-news-17 | 7일 외 Purchase | 10일 전 Purchase | 0 또는 None |
| L1-news-18 | 컬럼 누락 | df without Value column | None (defensive) |

#### 8.2.6 `fetch_news_all` ThreadPool (2 케이스)

| # | 항목 | mock 동작 | 통과 기준 |
|---|---|---|---|
| L1-news-19 | 14 stocks 병렬 fetch | _build_snapshot mock returns NewsSnapshot per ticker | dict size == 14, 모든 ticker 포함 |
| L1-news-20 | 일부 실패 (3건 raise) | 3 tickers raise, 11 returns | dict size == 11, fail-open 검증 |

#### 8.2.7 `NewsSnapshot` properties (2 케이스)

| # | 항목 | 입력 | 통과 기준 |
|---|---|---|---|
| L1-news-21 | `is_empty` — 모두 None | all None | True |
| L1-news-22 | `has_earnings_badge` boundary | days=7 / days=8 | True / False |

**소계: 22 케이스**.

### 8.3 `tests/test_v15_message.py` 확장 (~6 케이스 추가)

| # | 항목 | 통과 기준 |
|---|---|---|
| L1-msg-12 | news_map=None — Phase 1.5와 byte 동일 | 두 결과 비교 == |
| L1-msg-13 | news_map 있음 + 단타 후보에 헤드라인 | "└ 📰" 등장 |
| L1-msg-14 | days_to_earnings=3 — 📅3d 배지 표시 | "📅3d" 등장 |
| L1-msg-15 | days_to_earnings=8 — 배지 미표시 | "📅" 미등장 |
| L1-msg-16 | 💼 [내부자 매수] 섹션 — 발화 종목 있음 | 섹션 헤더 + 금액 라인 |
| L1-msg-17 | 💼 발화 종목 0 — 섹션 자체 생략 | 섹션 헤더 미등장 |

**소계: 6 케이스 추가** → 기존 11 + 6 = **17 케이스**.

### 8.4 Phase 1.5 회귀 (변경 없음)

| 검증 항목 | 방법 | 통과 기준 |
|---|---|---|
| Phase 1.5 71 테스트 회귀 0 | `pytest tests/test_main.py tests/test_data.py tests/test_signals.py tests/test_v15_message.py` | 66 unit pass (`-m "not integration"`) |
| ENABLE_NEWS=false 시 출력 동일 | 통합 테스트로 byte 비교 | Phase 1.5와 동일 |

**총 신규 테스트**: 22 + 6 = **28 케이스** (Plan SC-2N-8 ≥22 충족, +6 마진)
**전체 테스트**: Phase 1.5의 71 + 신규 28 = **99 케이스**

### 8.5 Seed Data Requirements

| Entity | Min Count | Key Fields |
|---|:-:|---|
| Headline fixture | 6 | title (영문, 5종 케이스) |
| Earnings DataFrame fixture | 3 | DatetimeIndex (future/past/empty) |
| Insider DataFrame fixture | 3 | Transaction (Purchase/Sale), Value, Date |

---

## 9. Clean Architecture

이 프로젝트는 단일 Python 스크립트(< 1,000 LOC)라 Next.js 다층 구조 N/A. 대신 **모듈별 책임 분리** 원칙 적용.

### 9.1 모듈별 책임

| 모듈 | 책임 | 의존 |
|---|---|---|
| `config.py` | 상수, env 로딩 | 외부 의존 없음 (frozen) |
| `data.py` | yfinance OHLCV → `Quote` | `config` |
| `signals.py` | `Quote` → `Signal` (5종 단타 신호) | `data`, `config` |
| **`news.py`** 🆕 | yfinance news/earnings/insider → `NewsSnapshot` | `data`, `config`, `vaderSentiment` |
| `main.py` | orchestration + message builder + Slack 발송 | `data`, `signals`, `news`, `config`, `requests` |

### 9.2 의존성 규칙

```
config.py (no external)
   ↑
   ├── data.py
   │     ↑
   │     ├── signals.py
   │     └── news.py  🆕
   ↑     ↑     ↑
   └─────┴─────┴── main.py (orchestrator)
```

- **단방향 의존**: 안쪽(config)에서 바깥쪽(main)으로만 흐름.
- **`news.py` ↮ `signals.py` 독립**: 두 모듈 사이 import 없음. 메시지 빌더에서만 합쳐짐.
- **`news.py` reads `data.Quote` (read-only)**: 타입 사용만, Quote 변경 안 함.

### 9.3 Import 규칙

| From | Can Import | Cannot Import |
|---|---|---|
| `config` | (외부 stdlib만) | data/signals/news/main |
| `data` | `config` | signals/news/main |
| `signals` | `data`, `config` | news/main |
| `news` | `data`, `config`, `vaderSentiment`, `yfinance` | signals/main |
| `main` | `data`, `signals`, `news`, `config` | (해당 없음, 최상위) |

---

## 10. Coding Convention Reference

### 10.1 명명

| 대상 | 규칙 | 예시 |
|---|---|---|
| 모듈 | snake_case.py | `news.py` |
| Dataclass | PascalCase | `NewsSnapshot` |
| 함수 | snake_case | `fetch_news_for_ticker`, `_build_snapshot` |
| 상수 | UPPER_SNAKE_CASE | `NEWS_VADER_COMPOUND_THRESHOLD` |
| Private 함수 | `_` prefix | `_get_analyzer`, `_truncate` |

### 10.2 Import 순서 (PEP 8)

```python
# 1. __future__
from __future__ import annotations

# 2. stdlib
import sys
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime

# 3. third-party
import yfinance as yf
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

# 4. local
from config import (...)
from data import Quote
```

### 10.3 환경변수

| 변수 | 용도 | 범위 | Default |
|---|---|---|---|
| `SLACK_WEBHOOK_URL` | Slack 발송 | Server only | (필수, secret) |
| `ENABLE_NEWS` 🆕 | Phase 2-NoAI 활성화 토글 | Server only | `"true"` |

### 10.4 본 feature 적용 규칙

| 항목 | 적용 |
|---|---|
| Dataclass 생성 | `@dataclass(frozen=True)` 일관 |
| Optional 타입 | `T \| None` (Python 3.10+ syntax, PEP 604) |
| Type hints | 모든 public 함수 + dataclass 필드 |
| Error 처리 | per-ticker try/except + warn log + fail-open |
| Comment | Design Ref 코멘트 (`# Design Ref: §X` 형태) 1개/모듈 |

---

## 11. Implementation Guide

### 11.1 File Structure

```
morning_us_index/
├── main.py                       (확장: build_v15_message news_map 인자 + main() news 흐름)
├── config.py                     (확장: 8개 상수 + is_news_enabled())
├── data.py                       (변경 없음)
├── signals.py                    (변경 없음)
├── news.py                       🆕 (NewsSnapshot + fetch_news_all + VADER + ThreadPool)
├── requirements.txt              (1줄 추가: vaderSentiment)
├── pytest.ini                    (변경 없음)
├── tests/
│   ├── __init__.py               (변경 없음)
│   ├── test_main.py              (변경 없음, Phase 1 17 회귀)
│   ├── test_data.py              (변경 없음, 14 회귀)
│   ├── test_signals.py           (변경 없음, 29 회귀)
│   ├── test_v15_message.py       (+6 케이스: news_map 통합)
│   └── test_news.py              🆕 (22 케이스)
└── .github/workflows/daily_report.yml  (변경 없음)
```

### 11.2 Implementation Order (16 단계 체크리스트)

| # | 항목 | 산출물 | DoD |
|---|---|---|---|
| 1 | `config.py` 확장 — Phase 2-NoAI 상수 8개 + `is_news_enabled()` | 수정 | `pytest -k config` (있다면) 또는 import OK |
| 2 | `requirements.txt` 1줄 추가 (`vaderSentiment>=3.3.2`) + `pip install` | 수정 | `python -c "from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer"` OK |
| 3 | `news.py` 신규 — NewsSnapshot dataclass + property 메소드 | 신규 | import OK, dataclass 동결 확인 |
| 4 | `news.py` — `_score_headline`, `_truncate`, `_get_analyzer` 순수 함수 | 채움 | 수기 호출로 검증 |
| 5 | `news.py` — `fetch_news_for_ticker` (yfinance + VADER 통합) | 채움 | 실 ticker 호출 OK (수기) |
| 6 | `news.py` — `fetch_earnings_for_ticker` | 채움 | 실 NVDA 호출 OK |
| 7 | `news.py` — `fetch_insider_for_ticker` (스키마 defensive) | 채움 | 실 TSLA 호출 OK |
| 8 | `news.py` — `_build_snapshot`, `fetch_news_all` (ThreadPool) | 채움 | 14 stocks 4초 내 완료 |
| 9 | `tests/test_news.py` — 22 케이스 작성 | 신규 | 22 passed (`-m "not integration"`) |
| 10 | `main.py` — import news 추가 + `_format_v15_quote_line_with_earnings`, `_format_insider_section` 헬퍼 | 수정 | 단위 호출 OK |
| 11 | `main.py` — `build_v15_message` 시그니처에 `news_map=None` 추가 + 내부 통합 로직 | 수정 | news_map=None 시 출력 == Phase 1.5 출력 byte 동일 |
| 12 | `main.py` — `main()` 흐름에 `fetch_news_all` 추가 + `ENABLE_NEWS` 분기 | 수정 | 로컬 `python main.py` 슬랙 도착 (헤드라인+배지+인사이더 ≥1) |
| 13 | `tests/test_v15_message.py` — 6 케이스 추가 | 수정 | 17 passed |
| 14 | Phase 1.5 회귀 검증 — `pytest tests/test_main.py tests/test_data.py tests/test_signals.py` | 검증 | 60 passed (-m not integration) |
| 15 | 통합 실행 — 로컬 실 슬랙 발송 + 메시지 ≤4000자 검증 | 검증 | 실 도착, len(msg) ≤ 4000 |
| 16 | git commit + push + `gh workflow run daily_report.yml` 트리거 | 운영 | Actions 통과, 슬랙 메시지 도착 |

### 11.3 Session Guide

#### Module Map

| Module | Scope Key | Description | 11.2 # | Est. Turns |
|---|---|---|---|:-:|
| module-1-config | `module-1-config` | config.py 상수 + is_news_enabled | 1, 2 | 5–8 |
| module-2-news-dataclass | `module-2-news-dataclass` | NewsSnapshot dataclass + property | 3 | 4–6 |
| module-3-news-fetchers | `module-3-news-fetchers` | _score_headline / _truncate / fetch_*_for_ticker 4종 | 4–7 | 12–18 |
| module-4-news-parallel | `module-4-news-parallel` | _build_snapshot + fetch_news_all (ThreadPool) | 8 | 5–8 |
| module-5-news-tests | `module-5-news-tests` | tests/test_news.py 22 케이스 | 9 | 15–20 |
| module-6-message-integration | `module-6-message-integration` | main.py build_v15_message 확장 (news_map 인자 + 헬퍼 2개) | 10, 11 | 10–14 |
| module-7-orchestration | `module-7-orchestration` | main() 흐름 + ENABLE_NEWS 분기 | 12 | 4–6 |
| module-8-message-tests | `module-8-message-tests` | tests/test_v15_message.py 6 케이스 추가 | 13 | 8–10 |
| module-9-regression | `module-9-regression` | Phase 1.5 71 회귀 검증 | 14 | 3–5 |
| module-10-deploy | `module-10-deploy` | 로컬 실행 + git push + workflow_dispatch | 15, 16 | 5–8 |

#### Recommended Session Plan

| 세션 | 범위 | DoD | 추정 시간 | Est. Turns |
|---|---|---|---|:-:|
| **S1 — Foundation** | module-1, 2 | NewsSnapshot import OK, vaderSentiment 설치 | 30분 | 10–14 |
| **S2 — News Fetchers** | module-3, 4 | `python -c "from news import fetch_news_all; print(fetch_news_all([...]))"` 14 ticker 결과 | 60–90분 | 17–26 |
| **S3 — Tests** | module-5 | `pytest tests/test_news.py` 22 passed | 60–90분 | 15–20 |
| **S4 — Integration** | module-6, 7, 8 | 로컬 `python main.py` 슬랙 메시지 1통 (모든 신규 섹션) + 6 테스트 passed | 60–90분 | 22–30 |
| **S5 — Regression & Deploy** | module-9, 10 | Phase 1.5 71 + 신규 28 모두 통과 + 실 슬랙 도착 | 30–45분 | 8–13 |

**호출 예시**:
```bash
# 분할 실행 (권장)
/pdca do morning-us-index-noai-v2 --scope module-1-config,module-2-news-dataclass
/pdca do morning-us-index-noai-v2 --scope module-3-news-fetchers,module-4-news-parallel
/pdca do morning-us-index-noai-v2 --scope module-5-news-tests
/pdca do morning-us-index-noai-v2 --scope module-6-message-integration,module-7-orchestration,module-8-message-tests
/pdca do morning-us-index-noai-v2 --scope module-9-regression,module-10-deploy

# 또는 단일 세션 (반나절 작업이라 가능)
/pdca do morning-us-index-noai-v2
```

> 1인 + 반나절 추정이라 단일 세션도 가능. 단, S2 끝에서 yfinance.news 실 스키마 모양이 확정돼야 S3 테스트 fixture 정확도 ↑. 분할 권장.

---

## 12. Risks Update (Plan §8 보완)

| Plan ID | 위험 | Design 단계 추가 대응 |
|---|---|---|
| **R-1** | yfinance.Ticker.news 비공식 API 스키마 변경 | `item.get("title", "")` defensive access. 각 ticker per try/except. 누락 시 후보 줄만 표시, 메시지 발송 정상 (FR-07) |
| **R-2** | VADER 30% 오답 ("dwindles" 등) | `\|compound\| ≥ 0.3` 임계값 (FR-03) + 22 테스트 중 6개를 VADER 정확도 검증에 할애 |
| **R-3** | 4000자 초과 | 기존 `_compress_if_needed` 재사용 + 신규 섹션 추가 순서 = 거시(있음) → 인사이더(신규) → 단타 후보(헤드라인 포함). 압축 시 단타 후보 헤드라인 들여쓰기 줄을 먼저 drop하는 정책 추가 |
| **R-4** | 인사이더 SEC 지연 1–2일 | 허용 (KST 06:00 = 미장 마감 후). 7일 윈도로 최신 데이터까지 캡쳐. NFR-08 충족 |
| **R-5** | Phase 1.5 회귀 | `news_map=None` default + try/except fail-open + `tests/test_v15_message.py` L1-msg-12 byte 동일 검증 |
| **R-6** | ThreadPoolExecutor rate limit | `max_workers=8` (보수적) + `as_completed timeout=20s` + per-future timeout 5s. 부분 실패 허용 (FR-07) |
| **R-7** | earnings_dates NaT | `df.index.to_pydatetime()` + try/except로 swallow, None 처리 |
| **R-8** | 인사이더 빈 데이터 | 정상 동작 (해당 종목 0 → `has_significant_insider_buy=False` → 섹션 생략) |
| **R-9 (신규)** | yfinance 버전마다 `insider_transactions` 컬럼명 변경 | `next((c for c in df.columns if "value" in str(c).lower()), None)` defensive 매칭. 없으면 None 반환 |
| **R-10 (신규)** | `vaderSentiment` import 실패 (의존성 미설치) | main() try/except에서 catch → 에러 메시지 슬랙 발송. requirements.txt 변경 시 GitHub Actions가 자동 재설치 |
| **R-11 (신규)** | VADER 분석기 매 호출 재초기화로 성능 저하 | `_VADER_ANALYZER` 모듈 레벨 singleton + `_get_analyzer()` lazy 초기화 |

---

## 13. Out of Scope (재확인)

(Plan §3.2, §9 그대로)

- ❌ AI/LLM API (Phase 2-AI 분리, `/pdca pm morning-us-index-ai`)
- ❌ 14 종목 전체 헤드라인 (signal-to-noise 붕괴)
- ❌ 거시 이벤트 캘린더 (FOMC/CPI) — 하드코딩 부패 위험
- ❌ Reddit/WSB 트렌딩 (유료화 → ROI 낮음)
- ❌ News API / Finnhub / Polygon (Phase 2-AI 검토)
- ❌ 한국 시장 통합 (Phase 3)
- ❌ 멀티 채널 / 차트 이미지 (Phase 3)
- ❌ 실시간 알림 (Phase 4)

---

## 14. Deployment

`.github/workflows/daily_report.yml` **변경 없음**.

| 항목 | Phase 1.5 | Phase 2-NoAI |
|---|---|---|
| Cron | `'0 21 * * *'` + 보험 `'30 21 * * *'` | **동일** (OQ-5: 운영 7일 후 보험 제거 — Report 단계) |
| Python | 3.11 | **동일** |
| Secrets | `SLACK_WEBHOOK_URL` | **동일** (추가 0) |
| Env vars | 없음 | `ENABLE_NEWS` (선택, default true. Actions에서 미설정 시 자연스럽게 true) |
| `pip install -r requirements.txt` | yfinance + requests | **+ vaderSentiment** (자동 설치) |
| Timeout | 5분 | **동일** (Phase 2-NoAI ~16s 예상, 충분 마진) |

---

## 15. References

- Plan: `docs/01-plan/features/morning-us-index-noai-v2.plan.md`
- Phase 1 Plan: `docs/01-plan/features/morning-us-index.plan.md`
- Phase 1 Design: `docs/02-design/features/morning-us-index.design.md`
- Phase 1.5 Plan: `docs/01-plan/features/morning-us-index-v15.plan.md`
- Phase 1.5 Design: `docs/02-design/features/morning-us-index-v15.design.md`
- Phase 1.5 Analysis: `docs/03-analysis/morning-us-index-v15.analysis.md`
- **Proposal docs**: `docs/proposal/phase2-noai/{beginner,developer}.md`
- yfinance Ticker API: https://github.com/ranaroussi/yfinance
- yfinance Ticker.news: https://github.com/ranaroussi/yfinance/blob/main/yfinance/scrapers/quote.py
- vaderSentiment: https://github.com/cjhutto/vaderSentiment
- VADER 금융 정확도 연구: https://jds-online.org/journal/JDS/article/1441/info
- SEC Form 4 (insider transactions): https://www.sec.gov/forms/SECFormsList/form-4
- Python ThreadPoolExecutor: https://docs.python.org/3/library/concurrent.futures.html

---

## Version History

| Version | Date | Changes | Author |
|---|---|---|---|
| 0.1 | 2026-05-11 | Initial draft. Option C(Pragmatic) 자동 선택 (사용자 무중단 요청). Plan OQ-1~OQ-5 5개 모두 해소. 22+6=28 신규 테스트 케이스 정의. | jooladen (with Ally) |

---

**다음 단계**: `/pdca do morning-us-index-noai-v2 --scope module-1-config,module-2-news-dataclass` (S1)
또는 단일 세션: `/pdca do morning-us-index-noai-v2`
