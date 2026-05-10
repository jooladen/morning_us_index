# Design Ref: §4.1 — Phase 2-NoAI 객관적 사실 데이터 3종 통합 모듈
"""morning-us-index-noai-v2 news/earnings/insider 통합 스냅샷.

Plan FR-01 ~ FR-07, FR-11.

3 종류 데이터 (모두 yfinance + 무료):
    F1: Top 1 headline + VADER compound (|c| ≥ 0.3 surface)
    F2: 어닝스 임박 (≤ 7일이면 📅 배지)
    F3: 인사이더 7일 누적 net buy USD (≥ $1M)

Phase 1.5 코드 경로 미수정 보장. data.Quote(read-only)에만 의존.
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

    Plan FR-02: ``top_headline`` = (title_truncated, source, vader_compound).
    어느 필드든 None일 수 있음 (Plan FR-07 부분 실패 허용).
    """

    ticker: str

    # F1: 헤드라인 + VADER compound (|c| ≥ 0.3 만 채워짐)
    top_headline: tuple[str, str, float] | None

    # F2: 어닝스 임박
    next_earnings_date: date | None
    days_to_earnings: int | None  # 음수면 과거 (있을 수 없음), 0+ 만 의미

    # F3: 인사이더 7일 누적 net buy USD (양수 = 순매수)
    insider_net_buy_usd_7d: float | None

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
        """📅 배지 표시 조건 (Design OQ-1: ≤ EARNINGS_LOOKAHEAD_DAYS)."""
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


# ─────────────────────────────────────────────────────────────
# VADER analyzer (lazy singleton)
# ─────────────────────────────────────────────────────────────

_VADER_ANALYZER: SentimentIntensityAnalyzer | None = None


def _get_analyzer() -> SentimentIntensityAnalyzer:
    """VADER 분석기 lazy 초기화. 모듈 import 시점이 아닌 첫 호출 시 생성."""
    global _VADER_ANALYZER
    if _VADER_ANALYZER is None:
        _VADER_ANALYZER = SentimentIntensityAnalyzer()
    return _VADER_ANALYZER


def _score_headline(title: str) -> float:
    """제목 → VADER compound score ∈ [-1.0, +1.0]."""
    return _get_analyzer().polarity_scores(title).get("compound", 0.0)


def _truncate(title: str, max_chars: int = NEWS_HEADLINE_MAX_CHARS) -> str:
    """80자 초과 시 77자 + '...' (Design OQ-3)."""
    title = title.strip()
    if len(title) <= max_chars:
        return title
    return title[: max_chars - 3].rstrip() + "..."


# ─────────────────────────────────────────────────────────────
# Per-ticker fetchers (각각 fail-open)
# ─────────────────────────────────────────────────────────────

def fetch_news_for_ticker(ticker: str) -> tuple[str, str, float] | None:
    """yfinance.Ticker.news 첫 번째 적합 항목 → (title_truncated, source, compound).

    Plan FR-03: ``|compound| < NEWS_VADER_COMPOUND_THRESHOLD`` 면 surface 안 함.
    Plan FR-07: 어떤 예외든 None으로 swallow.

    Returns:
        (truncated_title, publisher, compound) or None.
    """
    try:
        items = yf.Ticker(ticker).news or []
    except Exception as e:
        sys.stderr.write(f"[WARN] news fetch failed for {ticker}: {type(e).__name__}\n")
        return None

    for item in items:
        if not isinstance(item, dict):
            continue
        # yfinance ≥ 0.2.40: 항목이 {'content': {'title': ..., 'provider': {'displayName': ...}}}로 중첩될 수도 있음
        title = _extract_title(item)
        if not title:
            continue
        source = _extract_source(item)
        compound = _score_headline(title)
        if abs(compound) < NEWS_VADER_COMPOUND_THRESHOLD:
            continue  # 다음 헤드라인 시도
        return (_truncate(title), source, compound)

    return None


def _extract_title(item: dict) -> str:
    """yfinance.news 항목에서 title 안전하게 추출 (스키마 변화 대응)."""
    # 1차: 평탄 구조 (구버전)
    title = (item.get("title") or "").strip()
    if title:
        return title
    # 2차: content 중첩 (신버전)
    content = item.get("content")
    if isinstance(content, dict):
        title = (content.get("title") or "").strip()
        if title:
            return title
    return ""


def _extract_source(item: dict) -> str:
    """yfinance.news 항목에서 publisher 안전하게 추출."""
    pub = item.get("publisher")
    if isinstance(pub, str) and pub:
        return pub
    content = item.get("content")
    if isinstance(content, dict):
        provider = content.get("provider")
        if isinstance(provider, dict):
            name = provider.get("displayName") or provider.get("name")
            if isinstance(name, str) and name:
                return name
    return "?"


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
        future_dates: list[date] = []
        for idx in df.index:
            d = idx.date() if hasattr(idx, "date") else None
            if d is not None and d >= today_kst:
                future_dates.append(d)
    except Exception:
        return (None, None)
    if not future_dates:
        return (None, None)

    next_date = min(future_dates)
    days = (next_date - today_kst).days
    return (next_date, days)


def fetch_insider_for_ticker(ticker: str) -> float | None:
    """yfinance.Ticker.insider_transactions 최근 7일 net buy USD.

    Plan FR-05: 7일 누적 Purchase Value 합산.
    스키마 변경 방어: 컬럼명을 lowercase contains로 매칭.

    Returns:
        net buy USD (양수) or None (데이터 없음/스키마 불일치).
    """
    try:
        df = yf.Ticker(ticker).insider_transactions
    except Exception:
        return None
    if df is None or df.empty:
        return None

    try:
        # 컬럼명 yfinance 버전마다 다름 → defensive 매칭
        date_col = next(
            (c for c in df.columns if "date" in str(c).lower()), None
        )
        type_col = next(
            (c for c in df.columns
             if "transaction" in str(c).lower() or str(c).lower() == "type"),
            None,
        )
        value_col = next(
            (c for c in df.columns if "value" in str(c).lower()), None
        )
        if not (date_col and type_col and value_col):
            return None

        today_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()
        cutoff_ord = today_kst.toordinal() - INSIDER_LOOKBACK_DAYS

        total = 0.0
        for _, row in df.iterrows():
            try:
                d_val = row[date_col]
                d = d_val.date() if hasattr(d_val, "date") else None
                if d is None or d.toordinal() < cutoff_ord:
                    continue
                t_val = str(row[type_col]).lower()
                if "purchase" not in t_val:
                    continue
                v = row[value_col]
                if v is None:
                    continue
                # NaN check
                if v != v:  # noqa: PLR0124
                    continue
                total += float(v)
            except Exception:
                continue

        return total if total > 0 else None
    except Exception:
        return None


def _build_snapshot(ticker: str) -> NewsSnapshot:
    """단일 ticker의 3 종류 데이터를 합쳐 NewsSnapshot 생성 (fail-open).

    각 fetcher가 None을 반환할 수 있으며, 모두 None이면 ``is_empty=True``.
    """
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

    Plan FR-06: ``max_workers=8`` (보수적). 14 stocks × 1s/each → ~3–4s.
    Plan FR-07: per-ticker 실패 허용. 결과 dict에서 누락.

    Args:
        stocks: ``data.fetch_all()`` 결과 중 ``category="stock"`` 14개.

    Returns:
        ``dict[ticker, NewsSnapshot]``. 예외 발생한 ticker는 누락.
    """
    tickers = [q.ticker for q in stocks if q.category == "stock"]
    if not tickers:
        return {}

    results: dict[str, NewsSnapshot] = {}
    # as_completed 전체 timeout: per-ticker 5s × 4 마진 = 20s
    overall_timeout = NEWS_FETCH_TIMEOUT_SEC * 4

    with ThreadPoolExecutor(max_workers=NEWS_THREAD_POOL_WORKERS) as pool:
        futures = {pool.submit(_build_snapshot, t): t for t in tickers}
        try:
            for fut in as_completed(futures, timeout=overall_timeout):
                ticker = futures[fut]
                try:
                    snapshot = fut.result(timeout=NEWS_FETCH_TIMEOUT_SEC)
                    results[ticker] = snapshot
                except Exception as e:
                    sys.stderr.write(
                        f"[WARN] news snapshot failed for {ticker}: "
                        f"{type(e).__name__}\n"
                    )
                    # Plan FR-07: ticker 결과 누락
        except TimeoutError:
            sys.stderr.write(
                f"[WARN] fetch_news_all overall timeout {overall_timeout}s — "
                f"returning partial results ({len(results)}/{len(tickers)})\n"
            )

    return results
