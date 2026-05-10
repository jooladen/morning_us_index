# Design Ref: §8.2 — Phase 2-NoAI news.py 단위 테스트 22 케이스
"""Phase 2-NoAI news.py 테스트.

22 케이스 구성:
    - VADER scoring: 6
    - _truncate: 2
    - fetch_news_for_ticker mocked: 4
    - fetch_earnings_for_ticker mocked: 3
    - fetch_insider_for_ticker mocked: 3
    - fetch_news_all ThreadPool: 2
    - NewsSnapshot properties: 2
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from config import TIMEZONE_KST
from data import Quote
from news import (
    NewsSnapshot,
    _build_snapshot,
    _score_headline,
    _truncate,
    fetch_earnings_for_ticker,
    fetch_insider_for_ticker,
    fetch_news_all,
    fetch_news_for_ticker,
)


# ═════════════════════════════════════════════════════════════
# 8.2.1 VADER scoring (6 케이스)
# ─────────────────────────────────────────────────────────────
# 실측 VADER lexicon 값 기준 (proposal 추정치가 아닌 실제값).
# ═════════════════════════════════════════════════════════════

def test_vader_strong_positive():
    """L1-news-1: 강한 긍정 (다중 호재어)."""
    score = _score_headline("Tesla surges on breakthrough, record profit")
    assert score >= 0.3, f"expected >= 0.3, got {score}"


def test_vader_strong_negative():
    """L1-news-2: 강한 부정 (다중 부정어)."""
    score = _score_headline("Stock crashes, plunges, terrible loss")
    assert score <= -0.3, f"expected <= -0.3, got {score}"


def test_vader_neutral():
    """L1-news-3: 중립 헤드라인 — surface 안 됨."""
    score = _score_headline("Quarterly report scheduled for Tuesday")
    assert abs(score) < 0.3, f"expected |score| < 0.3, got {score}"


def test_vader_known_limit_nvidia_beats():
    """L1-news-4: VADER 알려진 한계 — 금융 컨텍스트 'beats/raises' 미인식.

    Plan R-2: VADER 30% 오답 사례. compound=0.0 → surface 안 됨.
    임계값 0.3이 이런 모호한 케이스를 자연스럽게 걸러냄.
    """
    score = _score_headline("Nvidia beats Q3 estimates, raises guidance")
    assert abs(score) < 0.3, f"VADER known limit: expected |score| < 0.3, got {score}"


def test_vader_below_threshold_just_under():
    """L1-news-5: 임계값 0.3 직전 (~0.29) — surface 안 됨.

    'Tesla shares surge on AI breakthrough' = +0.296 (실측).
    """
    score = _score_headline("Tesla shares surge on AI breakthrough")
    assert 0.0 < score < 0.3, f"boundary case expected ~0.29, got {score}"


def test_vader_dwindles_disappointing_caught():
    """L1-news-6: VADER가 'disappointing'을 강하게 잡음 → surface 됨.

    Plan/proposal에선 'dwindles' 한 단어로 약하다고 예측했지만,
    'disappointing'이 함께 있으면 compound ≤ -0.3 보장.
    """
    score = _score_headline("Stock dwindles after disappointing earnings")
    assert score <= -0.3, f"expected <= -0.3, got {score}"


# ═════════════════════════════════════════════════════════════
# 8.2.2 _truncate (2 케이스)
# ═════════════════════════════════════════════════════════════

def test_truncate_short_returns_as_is():
    """L1-news-7: 80자 이하 — 그대로 반환."""
    s = "Short headline under 80 chars"
    assert _truncate(s) == s


def test_truncate_long_adds_ellipsis():
    """L1-news-8: 80자 초과 — 77자 + '...' 정확히 80자 (OQ-3)."""
    s = "A" * 100
    result = _truncate(s)
    assert len(result) == 80
    assert result.endswith("...")


# ═════════════════════════════════════════════════════════════
# 8.2.3 fetch_news_for_ticker mocked (4 케이스)
# ═════════════════════════════════════════════════════════════

class _FakeTickerNews:
    """yf.Ticker mock — .news 만 stub."""
    def __init__(self, news_list):
        self.news = news_list


def test_fetch_news_first_item_passes_threshold():
    """L1-news-9: 첫 헤드라인 |compound|≥0.3 → surface."""
    items = [
        {"title": "Stock crashes, plunges, terrible loss", "publisher": "Reuters"},
    ]
    with patch("news.yf.Ticker", return_value=_FakeTickerNews(items)):
        result = fetch_news_for_ticker("NVDA")
    assert result is not None
    title, source, compound = result
    assert "crashes" in title
    assert source == "Reuters"
    assert compound <= -0.3


def test_fetch_news_skips_below_threshold_until_match():
    """L1-news-10: 첫 항목 임계값 미달, 두 번째 통과."""
    items = [
        {"title": "Quarterly report scheduled for Tuesday", "publisher": "AP"},  # 중립
        {"title": "Tesla surges on breakthrough, record profit", "publisher": "Bloomberg"},
    ]
    with patch("news.yf.Ticker", return_value=_FakeTickerNews(items)):
        result = fetch_news_for_ticker("TSLA")
    assert result is not None
    title, source, compound = result
    assert "Tesla" in title
    assert source == "Bloomberg"
    assert compound >= 0.3


def test_fetch_news_all_items_below_threshold_returns_none():
    """L1-news-11: 모든 항목 임계값 미달 → None."""
    items = [
        {"title": "Quarterly report scheduled for Tuesday", "publisher": "AP"},
        {"title": "Nvidia beats Q3 estimates, raises guidance", "publisher": "Reuters"},
    ]
    with patch("news.yf.Ticker", return_value=_FakeTickerNews(items)):
        result = fetch_news_for_ticker("NVDA")
    assert result is None


def test_fetch_news_exception_returns_none():
    """L1-news-12: yfinance 예외 → None (fail-open) + warn 로그."""
    class _RaisingTicker:
        @property
        def news(self):
            raise RuntimeError("yfinance broken")

    with patch("news.yf.Ticker", return_value=_RaisingTicker()):
        result = fetch_news_for_ticker("BAD")
    assert result is None


# ═════════════════════════════════════════════════════════════
# 8.2.4 fetch_earnings_for_ticker mocked (3 케이스)
# ═════════════════════════════════════════════════════════════

class _FakeTickerEarnings:
    """yf.Ticker mock — .earnings_dates 만 stub."""
    def __init__(self, df):
        self.earnings_dates = df


def _today_kst() -> date:
    return datetime.now(ZoneInfo(TIMEZONE_KST)).date()


def test_fetch_earnings_future_returns_date_and_days():
    """L1-news-13: 미래 어닝스 3일 후."""
    today = _today_kst()
    future = today + timedelta(days=3)
    df = pd.DataFrame(
        {"EPS Estimate": [1.5]},
        index=pd.DatetimeIndex([pd.Timestamp(future)]),
    )
    with patch("news.yf.Ticker", return_value=_FakeTickerEarnings(df)):
        next_date, days = fetch_earnings_for_ticker("NVDA")
    assert next_date == future
    assert days == 3


def test_fetch_earnings_only_past_returns_none():
    """L1-news-14: 과거 어닝스만 있음 → (None, None)."""
    today = _today_kst()
    past = today - timedelta(days=5)
    df = pd.DataFrame(
        {"EPS Estimate": [1.0]},
        index=pd.DatetimeIndex([pd.Timestamp(past)]),
    )
    with patch("news.yf.Ticker", return_value=_FakeTickerEarnings(df)):
        next_date, days = fetch_earnings_for_ticker("NVDA")
    assert next_date is None
    assert days is None


def test_fetch_earnings_empty_df_returns_none():
    """L1-news-15: 빈 DataFrame → (None, None)."""
    empty_df = pd.DataFrame()
    with patch("news.yf.Ticker", return_value=_FakeTickerEarnings(empty_df)):
        next_date, days = fetch_earnings_for_ticker("UNKNOWN")
    assert next_date is None
    assert days is None


# ═════════════════════════════════════════════════════════════
# 8.2.5 fetch_insider_for_ticker mocked (3 케이스)
# ═════════════════════════════════════════════════════════════

class _FakeTickerInsider:
    """yf.Ticker mock — .insider_transactions 만 stub."""
    def __init__(self, df):
        self.insider_transactions = df


def test_fetch_insider_recent_purchases_sum():
    """L1-news-16: 7일 내 Purchase 2건 합산 → $1M."""
    today = _today_kst()
    recent_1 = today - timedelta(days=2)
    recent_2 = today - timedelta(days=5)
    df = pd.DataFrame({
        "Start Date": [pd.Timestamp(recent_1), pd.Timestamp(recent_2)],
        "Transaction": ["Purchase", "Purchase"],
        "Value": [500_000.0, 500_000.0],
    })
    with patch("news.yf.Ticker", return_value=_FakeTickerInsider(df)):
        total = fetch_insider_for_ticker("TSLA")
    assert total == 1_000_000.0


def test_fetch_insider_old_purchases_excluded():
    """L1-news-17: 7일 외 Purchase는 합산에서 제외."""
    today = _today_kst()
    old = today - timedelta(days=10)
    df = pd.DataFrame({
        "Start Date": [pd.Timestamp(old)],
        "Transaction": ["Purchase"],
        "Value": [500_000.0],
    })
    with patch("news.yf.Ticker", return_value=_FakeTickerInsider(df)):
        total = fetch_insider_for_ticker("TSLA")
    assert total is None  # 7일 외라 총합 0 → None


def test_fetch_insider_missing_columns_returns_none():
    """L1-news-18: 컬럼 누락 → None (defensive 매칭 실패)."""
    df = pd.DataFrame({"Foo": [1], "Bar": [2]})
    with patch("news.yf.Ticker", return_value=_FakeTickerInsider(df)):
        total = fetch_insider_for_ticker("X")
    assert total is None


# ═════════════════════════════════════════════════════════════
# 8.2.6 fetch_news_all ThreadPool (2 케이스)
# ═════════════════════════════════════════════════════════════

def _stock_quote(ticker: str) -> Quote:
    """간단한 stock Quote fixture."""
    return Quote(
        ticker=ticker,
        label=ticker,
        category="stock",
        sector="반도체",
        last_close=100.0,
        prev_close=99.0,
        last_date=date(2026, 5, 8),
        is_stale=False,
    )


def test_fetch_news_all_parallel_14_stocks():
    """L1-news-19: 14 stocks 병렬 fetch — 모든 ticker가 dict에 포함."""
    tickers = ["A1", "A2", "A3", "A4", "A5", "A6", "A7",
               "B1", "B2", "B3", "B4", "B5", "B6", "B7"]
    stocks = [_stock_quote(t) for t in tickers]

    def fake_build(ticker):
        return NewsSnapshot(
            ticker=ticker,
            top_headline=None,
            next_earnings_date=None,
            days_to_earnings=None,
            insider_net_buy_usd_7d=None,
        )

    with patch("news._build_snapshot", side_effect=fake_build):
        result = fetch_news_all(stocks)
    assert len(result) == 14
    assert set(result.keys()) == set(tickers)


def test_fetch_news_all_partial_failure_returns_remaining():
    """L1-news-20: 3 ticker 실패, 11 성공 → dict size 11 (Plan FR-07)."""
    tickers = [f"T{i}" for i in range(14)]
    stocks = [_stock_quote(t) for t in tickers]

    fail_set = {"T0", "T5", "T10"}

    def fake_build(ticker):
        if ticker in fail_set:
            raise RuntimeError(f"simulated failure for {ticker}")
        return NewsSnapshot(
            ticker=ticker,
            top_headline=None,
            next_earnings_date=None,
            days_to_earnings=None,
            insider_net_buy_usd_7d=None,
        )

    with patch("news._build_snapshot", side_effect=fake_build):
        result = fetch_news_all(stocks)
    assert len(result) == 11
    assert not (fail_set & set(result.keys()))


# ═════════════════════════════════════════════════════════════
# 8.2.7 NewsSnapshot properties (2 케이스)
# ═════════════════════════════════════════════════════════════

def test_news_snapshot_is_empty_when_all_none():
    """L1-news-21: 모든 필드 None → is_empty=True."""
    ns = NewsSnapshot(
        ticker="X",
        top_headline=None,
        next_earnings_date=None,
        days_to_earnings=None,
        insider_net_buy_usd_7d=None,
    )
    assert ns.is_empty is True
    assert ns.has_earnings_badge is False
    assert ns.has_significant_insider_buy is False


def test_news_snapshot_earnings_badge_boundary():
    """L1-news-22: has_earnings_badge boundary — 7일 ✅, 8일 ❌."""
    base = dict(
        top_headline=None,
        next_earnings_date=date(2026, 5, 18),
        insider_net_buy_usd_7d=None,
    )
    ns_7 = NewsSnapshot(ticker="A", days_to_earnings=7, **base)
    ns_8 = NewsSnapshot(ticker="B", days_to_earnings=8, **base)
    assert ns_7.has_earnings_badge is True
    assert ns_8.has_earnings_badge is False
