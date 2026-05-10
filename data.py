# Design Ref: §4.2 — Phase 1.5 데이터 수집 모듈 (yfinance 일괄 호출)
"""morning-us-index-v15 데이터 계층.

- ``Quote`` dataclass: 모든 카테고리(index/future/stock/macro) 통합
- ``fetch_all()``: ``yf.download`` 일괄 호출 2회 (regular + prepost)
- 부분 실패 허용: 일부 ticker 데이터 없으면 list에서 빠짐 (warning log)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from zoneinfo import ZoneInfo

import yfinance as yf

from config import (
    FUTURES,
    INDICES,
    MACRO,
    SECTOR_MAP,
    STALE_THRESHOLD_DAYS,
    STOCKS,
    TIMEZONE_KST,
)


@dataclass(frozen=True)
class Quote:
    """모든 카테고리(index/future/stock/macro) 통합 dataclass.

    Plan SC-1.5-1: 26 데이터 포인트 표준 모델.
    Phase 1의 ``IndexQuote``는 그대로 유지하여 회귀 위험 0 (Plan NFR-05).
    """

    ticker: str
    label: str
    category: Literal["index", "future", "stock", "macro"]
    sector: str | None  # stock일 때만 채워짐

    last_close: float
    prev_close: float
    last_date: date
    is_stale: bool

    # 단타 신호 계산용 (없을 수 있음 — 부분 실패 허용)
    open_today: float | None = None
    volume_today: float | None = None
    volume_avg_20d: float | None = None
    high_52w: float | None = None
    afterhours_close: float | None = None


# ─────────────────────────────────────────────────────────────

def _build_ticker_map() -> dict[str, tuple[str, str, str | None]]:
    """ticker -> (label, category, sector)."""
    m: dict[str, tuple[str, str, str | None]] = {}
    for t, label in INDICES:
        m[t] = (label, "index", None)
    for t, label in FUTURES:
        m[t] = (label, "future", None)
    for t, label in STOCKS:
        m[t] = (label, "stock", SECTOR_MAP.get(t))
    for t, label, _unit in MACRO:
        m[t] = (label, "macro", None)
    return m


def _extract_quote(
    ticker: str,
    df_main,
    df_prepost,
    ticker_map: dict[str, tuple[str, str, str | None]],
    now_kst: date,
) -> Quote | None:
    """단일 ticker의 데이터에서 ``Quote`` 생성. 데이터 부족 시 ``None``."""
    if df_main is None or df_main.empty:
        return None

    # multi-ticker download은 columns가 MultiIndex (ticker, OHLCV)
    try:
        if hasattr(df_main.columns, "get_level_values"):
            tickers_in_df = df_main.columns.get_level_values(0).unique().tolist()
            if ticker not in tickers_in_df:
                return None
            sub = df_main[ticker]
        else:
            # single ticker fallback
            sub = df_main
    except Exception:
        return None

    if sub.empty or "Close" not in sub.columns:
        return None

    sub = sub.dropna(subset=["Close"])
    if len(sub) < 2:
        return None

    last_close = float(sub["Close"].iloc[-1])
    prev_close = float(sub["Close"].iloc[-2])
    last_date_value = sub.index[-1].date()

    open_today = (
        float(sub["Open"].iloc[-1])
        if "Open" in sub.columns and sub["Open"].iloc[-1] == sub["Open"].iloc[-1]
        else None
    )
    volume_today = (
        float(sub["Volume"].iloc[-1])
        if "Volume" in sub.columns and sub["Volume"].iloc[-1] == sub["Volume"].iloc[-1]
        else None
    )

    # 20일 평균 거래량 (마지막 거래일 제외, 그 직전 20일)
    volume_avg_20d: float | None = None
    if "Volume" in sub.columns and len(sub) >= 21:
        try:
            vol_series = sub["Volume"].iloc[-21:-1].dropna()
            if len(vol_series) >= 10:
                volume_avg_20d = float(vol_series.mean())
        except Exception:
            volume_avg_20d = None

    # 52주 고가
    high_52w: float | None = None
    if "High" in sub.columns:
        try:
            high_52w = float(sub["High"].dropna().max())
        except Exception:
            high_52w = None

    # 시간외 종가 (stocks만, 데이터 있을 때만)
    afterhours_close: float | None = None
    if df_prepost is not None and not df_prepost.empty:
        try:
            if hasattr(df_prepost.columns, "get_level_values"):
                ah_tickers = df_prepost.columns.get_level_values(0).unique().tolist()
                if ticker in ah_tickers:
                    ah_sub = df_prepost[ticker].dropna(subset=["Close"])
                    if not ah_sub.empty:
                        afterhours_close = float(ah_sub["Close"].iloc[-1])
        except Exception:
            afterhours_close = None

    is_stale = (now_kst - last_date_value).days >= STALE_THRESHOLD_DAYS
    label, category, sector = ticker_map[ticker]

    return Quote(
        ticker=ticker,
        label=label,
        category=category,  # type: ignore[arg-type]
        sector=sector,
        last_close=last_close,
        prev_close=prev_close,
        last_date=last_date_value,
        is_stale=is_stale,
        open_today=open_today,
        volume_today=volume_today,
        volume_avg_20d=volume_avg_20d,
        high_52w=high_52w,
        afterhours_close=afterhours_close,
    )


def fetch_all() -> list[Quote]:
    """INDICES + FUTURES + STOCKS + MACRO 일괄 조회.

    Plan SC-1.5-1: 26 데이터 포인트 (5+3+14+4)
    Plan NFR-02: ≤ 60초

    호출:
        - ``yf.download(all=26, period=1y)`` 1회 — 52주 고가 + 거래량 평균 계산용
        - ``yf.download(stocks=14, prepost=True, interval=1m)`` 1회 — 시간외

    부분 실패 허용:
        일부 ticker 데이터 없으면 list에서 빠짐. 모두 실패하면 RuntimeError.

    Raises:
        RuntimeError: 모든 ticker 조회 실패 (yfinance 전체 장애).
    """
    ticker_map = _build_ticker_map()
    all_tickers = list(ticker_map.keys())
    stock_tickers = [t for t, _ in STOCKS]

    now_kst = datetime.now(ZoneInfo(TIMEZONE_KST)).date()

    # 1차: regular OHLCV (1년치)
    try:
        df_main = yf.download(
            all_tickers,
            period="1y",
            group_by="ticker",
            auto_adjust=True,
            actions=False,
            progress=False,
            threads=True,
        )
    except Exception as e:
        raise RuntimeError(
            f"yfinance 일괄 조회 실패 (regular): {type(e).__name__}: {e}"
        ) from e

    # 2차: prepost (시간외) — 실패해도 진행
    df_prepost = None
    try:
        df_prepost = yf.download(
            stock_tickers,
            period="2d",
            interval="1m",
            group_by="ticker",
            prepost=True,
            progress=False,
            threads=True,
        )
    except Exception as e:
        sys.stderr.write(
            f"[WARN] yfinance prepost 조회 실패 (continuing without afterhours): "
            f"{type(e).__name__}: {e}\n"
        )
        df_prepost = None

    quotes: list[Quote] = []
    missing: list[str] = []

    for ticker in all_tickers:
        try:
            q = _extract_quote(ticker, df_main, df_prepost, ticker_map, now_kst)
            if q is None:
                missing.append(ticker)
            else:
                quotes.append(q)
        except Exception as e:
            sys.stderr.write(
                f"[WARN] {ticker} 처리 중 예외 (skipping): {type(e).__name__}: {e}\n"
            )
            missing.append(ticker)

    if not quotes:
        raise RuntimeError(
            "yfinance 데이터 부족: 모든 ticker 조회 실패 (Yahoo 전체 장애 가능)"
        )

    if missing:
        sys.stderr.write(
            f"[WARN] {len(missing)} ticker 데이터 누락 (skipped): {', '.join(missing)}\n"
        )

    return quotes
