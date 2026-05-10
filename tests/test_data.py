# Design Ref: §8.1 — data.py 단위 + 통합 테스트
"""Phase 1.5 data.py 테스트.

단위(9개): _build_ticker_map, Quote dataclass
통합(4개): fetch_all() — yfinance 실 호출 (network 필요)
"""

from __future__ import annotations

from datetime import date

import pytest

import config
from data import Quote, _build_ticker_map, fetch_all


# ─────────────────────────────────────────────────────────────
# 단위 — Quote dataclass / ticker map
# ─────────────────────────────────────────────────────────────

def test_build_ticker_map_includes_all_categories():
    m = _build_ticker_map()
    indices = [t for t, v in m.items() if v[1] == "index"]
    futures = [t for t, v in m.items() if v[1] == "future"]
    stocks = [t for t, v in m.items() if v[1] == "stock"]
    macros = [t for t, v in m.items() if v[1] == "macro"]
    assert len(indices) == len(config.INDICES)
    assert len(futures) == len(config.FUTURES)
    assert len(stocks) == len(config.STOCKS)
    assert len(macros) == len(config.MACRO)


def test_build_ticker_map_total_count():
    m = _build_ticker_map()
    assert len(m) == 5 + 3 + 14 + 4  # 26


def test_build_ticker_map_stocks_have_sector():
    m = _build_ticker_map()
    nvda = m.get("NVDA")
    assert nvda is not None
    assert nvda[1] == "stock"
    assert nvda[2] == "반도체"


def test_build_ticker_map_indices_no_sector():
    m = _build_ticker_map()
    ixic = m.get("^IXIC")
    assert ixic is not None
    assert ixic[1] == "index"
    assert ixic[2] is None


def test_build_ticker_map_macro_label():
    m = _build_ticker_map()
    usdkrw = m.get("USDKRW=X")
    assert usdkrw is not None
    assert usdkrw[0] == "원/달러"
    assert usdkrw[1] == "macro"


def test_quote_dataclass_required_fields():
    q = Quote(
        ticker="NVDA",
        label="엔비디아",
        category="stock",
        sector="반도체",
        last_close=142.5,
        prev_close=140.0,
        last_date=date(2026, 5, 8),
        is_stale=False,
    )
    assert q.last_close == 142.5
    assert q.afterhours_close is None  # default


def test_quote_optional_fields_default_none():
    q = Quote(
        ticker="X",
        label="x",
        category="stock",
        sector=None,
        last_close=1.0,
        prev_close=1.0,
        last_date=date(2026, 1, 1),
        is_stale=False,
    )
    assert q.open_today is None
    assert q.volume_today is None
    assert q.volume_avg_20d is None
    assert q.high_52w is None
    assert q.afterhours_close is None


def test_quote_is_frozen():
    q = Quote(
        ticker="X",
        label="x",
        category="index",
        sector=None,
        last_close=1.0,
        prev_close=1.0,
        last_date=date(2026, 1, 1),
        is_stale=False,
    )
    with pytest.raises(Exception):
        q.last_close = 999.0  # type: ignore[misc]


def test_quote_with_signals_data():
    q = Quote(
        ticker="NVDA",
        label="엔비디아",
        category="stock",
        sector="반도체",
        last_close=142.5,
        prev_close=140.0,
        last_date=date(2026, 5, 8),
        is_stale=False,
        open_today=141.0,
        volume_today=2_500_000,
        volume_avg_20d=1_000_000,
        high_52w=143.0,
        afterhours_close=143.5,
    )
    assert q.open_today == 141.0
    assert q.volume_today == 2_500_000
    assert q.volume_avg_20d == 1_000_000
    assert q.high_52w == 143.0
    assert q.afterhours_close == 143.5


# ─────────────────────────────────────────────────────────────
# 통합 — 실제 yfinance 호출
# ─────────────────────────────────────────────────────────────

@pytest.mark.integration
def test_fetch_all_real_returns_quotes():
    """L1-data-1: yfinance 실 호출로 Quote list 반환."""
    quotes = fetch_all()
    assert len(quotes) >= 15  # 부분 실패 허용, 최소 15개
    for q in quotes:
        assert q.last_close > 0
        assert q.prev_close > 0
        assert q.category in ("index", "future", "stock", "macro")


@pytest.mark.integration
def test_fetch_all_includes_indices():
    """L1-data-2: INDICES 카테고리 ≥ 3개 (5개 중 일부 실패 허용)."""
    quotes = fetch_all()
    idx_quotes = [q for q in quotes if q.category == "index"]
    assert len(idx_quotes) >= 3


@pytest.mark.integration
def test_fetch_all_stocks_have_sector():
    """L1-data-4: stock 카테고리는 sector 채워짐."""
    quotes = fetch_all()
    nvda = next((q for q in quotes if q.ticker == "NVDA"), None)
    if nvda is not None:
        assert nvda.category == "stock"
        assert nvda.sector == "반도체"


@pytest.mark.integration
def test_fetch_all_has_volume_avg_for_some_stocks():
    """L1-data-8: 거래량 평균 계산 (대부분의 stock에 있어야)."""
    quotes = fetch_all()
    stocks_with_vol = [
        q for q in quotes
        if q.category == "stock" and q.volume_avg_20d is not None
    ]
    assert len(stocks_with_vol) >= 5


@pytest.mark.integration
def test_fetch_all_has_52w_high():
    """L1-data-7: 52주 고가 (대부분 종목에 있어야)."""
    quotes = fetch_all()
    with_52w = [q for q in quotes if q.high_52w is not None]
    assert len(with_52w) >= 10
