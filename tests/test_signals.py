# Design Ref: §8.2 — signals.py 단위 테스트 (모두 단위, integration 없음)
"""Phase 1.5 signals.py 테스트.

5종 신호 + 사상최고 + 섹터 + Signal property — 약 22 케이스.
"""

from __future__ import annotations

from datetime import date

from data import Quote
from signals import Signal, compute_signals, get_sector


def _q(
    ticker: str = "X",
    label: str = "x",
    category: str = "stock",
    sector: str | None = "반도체",
    last: float = 100.0,
    prev: float = 100.0,
    last_date_: date = date(2026, 5, 10),
    is_stale: bool = False,
    open_today: float | None = None,
    volume_today: float | None = None,
    volume_avg_20d: float | None = None,
    high_52w: float | None = None,
    afterhours_close: float | None = None,
) -> Quote:
    return Quote(
        ticker=ticker,
        label=label,
        category=category,  # type: ignore[arg-type]
        sector=sector,
        last_close=last,
        prev_close=prev,
        last_date=last_date_,
        is_stale=is_stale,
        open_today=open_today,
        volume_today=volume_today,
        volume_avg_20d=volume_avg_20d,
        high_52w=high_52w,
        afterhours_close=afterhours_close,
    )


# ─────────────────────────────────────────────────────────────
# 🔥 거래량 spike (임계 2.0)
# ─────────────────────────────────────────────────────────────

def test_volume_spike_above_threshold():
    sigs = compute_signals([_q(ticker="A", volume_today=2_500_000, volume_avg_20d=1_000_000)])
    assert sigs["A"].is_volume_spike is True


def test_volume_spike_at_boundary():
    """vol_ratio = 2.0 (정확히 임계) → True."""
    sigs = compute_signals([_q(ticker="A", volume_today=2_000_000, volume_avg_20d=1_000_000)])
    assert sigs["A"].is_volume_spike is True


def test_volume_spike_below_threshold():
    sigs = compute_signals([_q(ticker="A", volume_today=1_999_000, volume_avg_20d=1_000_000)])
    assert sigs["A"].is_volume_spike is False


def test_volume_spike_no_data():
    sigs = compute_signals([_q(ticker="A", volume_today=None, volume_avg_20d=None)])
    assert sigs["A"].is_volume_spike is False


# ─────────────────────────────────────────────────────────────
# 🎯 갭 (임계 1.5%)
# ─────────────────────────────────────────────────────────────

def test_gap_positive_above_threshold():
    """open=101.6, prev=100 → +1.6%."""
    sigs = compute_signals([_q(ticker="A", open_today=101.6, prev=100.0)])
    assert sigs["A"].is_gap is True


def test_gap_negative_above_threshold():
    """open=98.4, prev=100 → -1.6% (절대값 1.6%)."""
    sigs = compute_signals([_q(ticker="A", open_today=98.4, prev=100.0)])
    assert sigs["A"].is_gap is True


def test_gap_below_threshold():
    """open=101.4, prev=100 → +1.4%."""
    sigs = compute_signals([_q(ticker="A", open_today=101.4, prev=100.0)])
    assert sigs["A"].is_gap is False


def test_gap_no_open_data():
    sigs = compute_signals([_q(ticker="A", open_today=None, prev=100.0)])
    assert sigs["A"].is_gap is False


# ─────────────────────────────────────────────────────────────
# ⚡ VIX 급등 (^VIX ticker만)
# ─────────────────────────────────────────────────────────────

def test_vix_spike_for_vix_ticker():
    """^VIX +6.8% (last=23.5, prev=22) → True."""
    sigs = compute_signals([
        _q(ticker="^VIX", category="index", sector=None, last=23.5, prev=22.0),
    ])
    assert sigs["^VIX"].is_vix_spike is True


def test_vix_spike_at_boundary():
    """^VIX +5.0% (정확히 임계) → True."""
    sigs = compute_signals([
        _q(ticker="^VIX", category="index", sector=None, last=21.0, prev=20.0),
    ])
    assert sigs["^VIX"].is_vix_spike is True


def test_non_vix_doesnt_get_vix_spike():
    """AAPL이 +10% 변동해도 is_vix_spike = False (^VIX 만 적용)."""
    sigs = compute_signals([_q(ticker="AAPL", last=110.0, prev=100.0)])
    assert sigs["AAPL"].is_vix_spike is False


def test_vix_no_quote_no_spike():
    """quotes에 ^VIX 없으면 다른 어떤 ticker도 vix_spike=False."""
    sigs = compute_signals([_q(ticker="AAPL", last=110.0, prev=100.0)])
    assert sigs["AAPL"].is_vix_spike is False


# ─────────────────────────────────────────────────────────────
# 🆙 52주 신고가 / ★ 사상최고
# ─────────────────────────────────────────────────────────────

def test_52w_near_high_at_threshold():
    """ratio = 0.99 (정확히 임계) → True."""
    sigs = compute_signals([_q(ticker="A", last=99.0, high_52w=100.0)])
    assert sigs["A"].is_52w_near_high is True


def test_52w_below_threshold():
    """ratio = 0.98 → False."""
    sigs = compute_signals([_q(ticker="A", last=98.0, high_52w=100.0)])
    assert sigs["A"].is_52w_near_high is False


def test_all_time_high_at_threshold():
    """ratio = 0.999 (정확히 ★ 임계) → True."""
    sigs = compute_signals([_q(ticker="A", last=99.9, high_52w=100.0)])
    assert sigs["A"].is_all_time_high is True


def test_all_time_high_above_52w_high():
    """ratio = 1.0 (역대 신고가) → True."""
    sigs = compute_signals([_q(ticker="A", last=100.0, high_52w=100.0)])
    assert sigs["A"].is_all_time_high is True


def test_52w_high_no_data():
    sigs = compute_signals([_q(ticker="A", last=100.0, high_52w=None)])
    assert sigs["A"].is_52w_near_high is False
    assert sigs["A"].is_all_time_high is False


# ─────────────────────────────────────────────────────────────
# 📊 시간외 (임계 1.0%)
# ─────────────────────────────────────────────────────────────

def test_afterhours_above_threshold():
    """100 → 101.5 = +1.5%."""
    sigs = compute_signals([_q(ticker="A", last=100.0, afterhours_close=101.5)])
    assert sigs["A"].is_afterhours_move is True


def test_afterhours_negative():
    """100 → 98.5 = -1.5% (절대값 1.5%)."""
    sigs = compute_signals([_q(ticker="A", last=100.0, afterhours_close=98.5)])
    assert sigs["A"].is_afterhours_move is True


def test_afterhours_below_threshold():
    sigs = compute_signals([_q(ticker="A", last=100.0, afterhours_close=100.5)])
    assert sigs["A"].is_afterhours_move is False


def test_afterhours_no_data():
    sigs = compute_signals([_q(ticker="A", last=100.0, afterhours_close=None)])
    assert sigs["A"].is_afterhours_move is False


# ─────────────────────────────────────────────────────────────
# 섹터 매핑
# ─────────────────────────────────────────────────────────────

def test_get_sector_known():
    assert get_sector("NVDA") == "반도체"
    assert get_sector("AAPL") == "빅테크"
    assert get_sector("TSLA") == "EV/암호"


def test_get_sector_unknown_returns_none():
    assert get_sector("UNKNOWN_TICKER") is None


# ─────────────────────────────────────────────────────────────
# Signal property
# ─────────────────────────────────────────────────────────────

def test_signal_emoji_marks_order_consistent():
    s = Signal(
        ticker="A",
        is_volume_spike=True,
        is_gap=True,
        is_vix_spike=False,
        is_52w_near_high=True,
        is_all_time_high=False,
        is_afterhours_move=False,
    )
    assert s.emoji_marks == "🔥🎯🆙"


def test_signal_emoji_marks_empty_when_no_signals():
    s = Signal(
        ticker="A",
        is_volume_spike=False,
        is_gap=False,
        is_vix_spike=False,
        is_52w_near_high=False,
        is_all_time_high=False,
        is_afterhours_move=False,
    )
    assert s.emoji_marks == ""


def test_signal_count_excludes_all_time_high():
    """signal_count는 ★(사상최고)를 제외한 5종 단타 신호만 카운트."""
    s = Signal(
        ticker="A",
        is_volume_spike=True,
        is_gap=True,
        is_vix_spike=False,
        is_52w_near_high=True,
        is_all_time_high=True,  # ★는 카운트 제외
        is_afterhours_move=True,
    )
    assert s.signal_count == 4  # volume + gap + 52w_near_high + afterhours


def test_signal_count_zero():
    s = Signal(
        ticker="A",
        is_volume_spike=False,
        is_gap=False,
        is_vix_spike=False,
        is_52w_near_high=False,
        is_all_time_high=False,
        is_afterhours_move=False,
    )
    assert s.signal_count == 0


# ─────────────────────────────────────────────────────────────
# 통합 — 다중 quote
# ─────────────────────────────────────────────────────────────

def test_compute_signals_returns_dict_keyed_by_ticker():
    quotes = [
        _q(ticker="A", last=100.0, prev=99.0),
        _q(ticker="B", last=200.0, prev=199.0),
    ]
    sigs = compute_signals(quotes)
    assert set(sigs.keys()) == {"A", "B"}
    assert isinstance(sigs["A"], Signal)


def test_compute_signals_intel_like_scenario():
    """INTC: 갭 +12% + 거래량 8x → 단타 후보."""
    sigs = compute_signals([
        _q(
            ticker="INTC",
            label="인텔",
            sector="반도체",
            last=32.15,
            prev=28.20,
            open_today=31.59,  # +12% 갭
            volume_today=8_000_000,
            volume_avg_20d=1_000_000,
            high_52w=33.00,
        ),
    ])
    s = sigs["INTC"]
    assert s.is_gap is True
    assert s.is_volume_spike is True
    assert s.signal_count >= 2  # 단타 후보 자격
