# Design Ref: §8.3 — build_v15_message 통합 테스트
"""Phase 1.5 메시지 빌더 테스트.

build_v15_message + _format_v15_quote_line + _format_compact_line + _compress_if_needed.
"""

from __future__ import annotations

from datetime import date

import pytest

import config
from data import Quote
from main import build_v15_message
from signals import compute_signals


def _q(
    ticker: str,
    label: str,
    category: str,
    sector: str | None = None,
    last: float = 100.0,
    prev: float = 100.0,
    last_date_: date = date(2026, 5, 8),
    is_stale: bool = False,
    **kw,
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
        **kw,
    )


# ─────────────────────────────────────────────────────────────
# 기본 메시지 구조
# ─────────────────────────────────────────────────────────────

def test_message_contains_all_section_headers():
    quotes = [
        _q("^IXIC", "나스닥", "index", last=26000, prev=25000),
        _q("ES=F", "S&P 미니", "future", last=7000, prev=6990),
        _q("NVDA", "엔비디아", "stock", "반도체", last=142, prev=140),
        _q("AAPL", "애플", "stock", "빅테크", last=232, prev=230),
        _q("TSLA", "테슬라", "stock", "EV/암호", last=312, prev=300),
        _q("USDKRW=X", "원/달러", "macro", last=1375, prev=1380),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)

    # v7: 섹션 헤더 prefix 이모지 제거 (FR-25)
    assert "[지수]" in msg
    assert "[단타 핵심" in msg
    assert "[반도체]" in msg
    assert "[빅테크]" in msg
    assert "[EV/암호]" in msg
    assert "[거시]" in msg


def test_empty_quotes_raises():
    with pytest.raises(RuntimeError, match="비어있"):
        build_v15_message([], {})


# ─────────────────────────────────────────────────────────────
# 단타 후보 자동 요약
# ─────────────────────────────────────────────────────────────

def test_daytrade_candidate_section_appears_when_2_signals():
    """INTC: 갭 + 거래량 = 2 signals → 단타 후보 (v5/v8 이모지 형식)."""
    quotes = [
        _q("INTC", "인텔", "stock", "반도체",
           last=32.15, prev=28.20,
           open_today=31.59,  # +12% 갭
           volume_today=8_000_000,
           volume_avg_20d=1_000_000,
           high_52w=33.00),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)

    assert "[오늘 단타 후보" in msg
    assert "INTC" in msg
    # v5: 한글 "갭"/"거래량" → 이모지 + 숫자
    assert "🎯" in msg  # 갭
    assert "🔥" in msg  # 거래량


def test_no_candidate_section_when_no_signals():
    quotes = [
        _q("AMD", "AMD", "stock", "반도체", last=100.0, prev=99.5),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "[오늘 단타 후보" not in msg


def test_no_candidate_section_when_only_1_signal():
    """신호 1개만 있으면 후보 섹션 X."""
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),  # 거래량만
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    # 거래량 신호 1개 < 임계 2 → 후보 섹션 없음
    assert "[오늘 단타 후보" not in msg


# ─────────────────────────────────────────────────────────────
# 사상최고 ★ / 신호 마크 표시
# ─────────────────────────────────────────────────────────────

def test_all_time_high_star_displayed():
    quotes = [
        _q("MU", "마이크론", "stock", "반도체",
           last=100.0, prev=95.0, high_52w=100.0),  # ratio = 1.0 → ★
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "★" in msg


def test_volume_spike_emoji_displayed():
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "🔥" in msg


def test_compact_format_for_no_signal_stock():
    """v7 표 형식: code block 안에 컬럼 정렬. 종목명/ticker/변동률 등장 검증."""
    quotes = [
        _q("AMD", "AMD", "stock", "반도체", last=100.5, prev=100.0),  # +0.5%, 신호 없음
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),  # 거래량 spike
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "AMD" in msg
    assert "+0.50%" in msg
    assert "🔥" in msg
    assert "엔비디아" in msg
    assert "NVDA" in msg
    # v7 표 형식 — code block 등장
    assert "```" in msg


# ─────────────────────────────────────────────────────────────
# 길이 한도 (NFR-01)
# ─────────────────────────────────────────────────────────────

def test_message_within_4000_chars_full_quotes():
    """26 quotes 모두 시뮬레이션 → 4000자 이내."""
    quotes: list[Quote] = []
    for ticker, label in config.INDICES:
        quotes.append(_q(ticker, label, "index", last=1000.0, prev=999.0))
    for ticker, label in config.FUTURES:
        quotes.append(_q(ticker, label, "future", last=1000.0, prev=999.0))
    for ticker, label in config.STOCKS:
        sec = config.SECTOR_MAP.get(ticker)
        quotes.append(_q(ticker, label, "stock", sec, last=100.0, prev=99.0))
    for ticker, label, _u in config.MACRO:
        quotes.append(_q(ticker, label, "macro", last=1000.0, prev=999.0))

    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert len(msg) <= config.SLACK_MESSAGE_MAX_CHARS


# ─────────────────────────────────────────────────────────────
# 휴장일
# ─────────────────────────────────────────────────────────────

def test_stale_handling_in_v15():
    """v4 표 형식: 헤더 2줄 분리 후 휴장 표시."""
    quotes = [
        _q("^IXIC", "나스닥", "index",
           last=26000.0, prev=25000.0,
           last_date_=date(2026, 5, 9), is_stale=True),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "(미 증시 휴장)" in msg
    assert "직전 거래일: 2026-05-09" in msg


# ─────────────────────────────────────────────────────────────
# 시간외 섹션
# ─────────────────────────────────────────────────────────────

def test_afterhours_section_appears_when_data_present():
    """AHRS 변동 1%+ 종목은 단타 핵심 섹션에 등장."""
    quotes = [
        _q("ES=F", "S&P 미니", "future", last=7000, prev=6990),
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142.0, prev=140.0,
           afterhours_close=144.5),  # +1.76%
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "AHRS NVDA" in msg
    assert "📊" in msg


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI — news_map 통합 (Design §8.3, +6 케이스)
# Design Ref: Plan NFR-07, FR-04, FR-05, FR-09, FR-10
# ─────────────────────────────────────────────────────────────

from news import NewsSnapshot  # noqa: E402


def _ns(
    ticker: str,
    *,
    headline=None,
    earnings_date=None,
    days_to_earnings=None,
    insider_usd=None,
) -> NewsSnapshot:
    return NewsSnapshot(
        ticker=ticker,
        top_headline=headline,
        next_earnings_date=earnings_date,
        days_to_earnings=days_to_earnings,
        insider_net_buy_usd_7d=insider_usd,
    )


def test_news_map_none_byte_identical_to_phase15():
    """L1-msg-12: news_map=None 시 Phase 1.5와 byte 단위 동일 (Plan NFR-07 회귀 안전)."""
    quotes = [
        _q("^IXIC", "나스닥", "index", last=26000, prev=25000),
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),
    ]
    sigs = compute_signals(quotes)
    msg_phase15 = build_v15_message(quotes, sigs)
    msg_with_none = build_v15_message(quotes, sigs, news_map=None)
    assert msg_phase15 == msg_with_none


def test_daytrade_candidate_shows_headline_indent():
    """L1-msg-13 (v5 갱신): 단타 후보 아래 들여쓰기로 헤드라인 등장 (F1).

    v5: 들여쓰기 2-space + '📰' 형식.
    """
    quotes = [
        _q("INTC", "인텔", "stock", "반도체",
           last=32.15, prev=28.20,
           open_today=31.59,  # 갭 +12%
           volume_today=8_000_000, volume_avg_20d=1_000_000),
    ]
    sigs = compute_signals(quotes)
    news_map = {
        "INTC": _ns(
            "INTC",
            headline=("Intel restructures amid weak demand", "Bloomberg", -0.55),
        ),
    }
    msg = build_v15_message(quotes, sigs, news_map=news_map)
    assert "📰" in msg
    assert "-0.55" in msg
    assert "Intel restructures amid weak demand" in msg
    assert "Bloomberg" in msg
    # v5: 헤드라인이 2 공백으로 시작
    assert "  📰" in msg


def test_earnings_badge_inline_within_7_days():
    """L1-msg-14: days_to_earnings=3 → 📅3d 배지 inline (F2)."""
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),  # 신호 1개 → 풀 표시
    ]
    sigs = compute_signals(quotes)
    news_map = {"NVDA": _ns("NVDA", days_to_earnings=3)}
    msg = build_v15_message(quotes, sigs, news_map=news_map)
    assert "📅3d" in msg


def test_earnings_badge_not_shown_beyond_7_days():
    """L1-msg-15 (v4 갱신): days_to_earnings=8 → 배지 미표시 (Plan FR-04).

    v4 헤더에 📅(캘린더) 이모지 추가됐으므로, 배지 형식 "📅Xd" 구체 검증.
    """
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           volume_today=2_500_000, volume_avg_20d=1_000_000),
    ]
    sigs = compute_signals(quotes)
    news_map = {"NVDA": _ns("NVDA", days_to_earnings=8)}
    msg = build_v15_message(quotes, sigs, news_map=news_map)
    # 배지 형식 (날짜 Xd 포함)이 등장하면 안 됨
    assert "📅8d" not in msg
    assert "📅3d" not in msg
    assert "📅7d" not in msg


def test_insider_section_appears_for_significant_buys():
    """L1-msg-16: 💼 섹션 — 발화 종목 있음, net buy 큰 순 정렬 (Plan FR-05, OQ-4)."""
    quotes = [
        _q("TSLA", "테슬라", "stock", "EV/암호", last=312, prev=300),
        _q("NVDA", "엔비디아", "stock", "반도체", last=142, prev=140),
    ]
    sigs = compute_signals(quotes)
    news_map = {
        "NVDA": _ns("NVDA", insider_usd=1_400_000.0),  # $1.4M
        "TSLA": _ns("TSLA", insider_usd=3_200_000.0),  # $3.2M
    }
    msg = build_v15_message(quotes, sigs, news_map=news_map)
    assert "[내부자 매수 급증 7일 (≥$1M)]" in msg
    assert "+$3.2M" in msg
    assert "+$1.4M" in msg
    # OQ-4: 큰 순 정렬 — TSLA가 NVDA보다 먼저
    assert msg.index("TSLA 테슬라") < msg.index("NVDA 엔비디아")


def test_insider_section_omitted_when_no_significant_buys():
    """L1-msg-17: 발화 종목 0 → 💼 섹션 자체 생략."""
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체", last=142, prev=140),
    ]
    sigs = compute_signals(quotes)
    news_map = {
        "NVDA": _ns("NVDA", insider_usd=500_000.0),  # $0.5M < threshold
    }
    msg = build_v15_message(quotes, sigs, news_map=news_map)
    assert "💼" not in msg
    assert "내부자 매수" not in msg


# ─────────────────────────────────────────────────────────────
# Phase 2-NoAI v3 — UX 개선 (FR-15/16/17/20, +4 케이스)
# 운영 후 추가
# ─────────────────────────────────────────────────────────────

def test_market_mood_line_appears_in_header():
    """L1-msg-18 (FR-15): 시장 동향 한 줄이 헤더 직후 등장 — 상승/하락 카운트 + VIX 라벨."""
    quotes = [
        _q("^VIX", "VIX", "index", last=17.19, prev=17.08),  # 안정 (<20)
        _q("NVDA", "엔비디아", "stock", "반도체", last=142, prev=140),  # 상승
        _q("INTC", "인텔", "stock", "반도체", last=32, prev=33),  # 하락
        _q("AMD", "AMD", "stock", "반도체", last=100, prev=99),  # 상승
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    assert "📊 상승 2 / 하락 1" in msg
    assert "VIX 17.19" in msg
    assert "(안정)" in msg


def test_vix_label_inline_with_thresholds():
    """L1-msg-19 (FR-20): VIX 종목 라인 끝에 (안정/경계/공포) 라벨 inline."""
    # 안정: <20
    quotes_a = [_q("^VIX", "VIX", "index", last=15.0, prev=15.0)]
    msg_a = build_v15_message(quotes_a, compute_signals(quotes_a))
    assert "(안정)" in msg_a
    # 경계: 20-25
    quotes_b = [_q("^VIX", "VIX", "index", last=22.0, prev=22.0)]
    msg_b = build_v15_message(quotes_b, compute_signals(quotes_b))
    assert "(경계)" in msg_b
    # 공포: >=25
    quotes_c = [_q("^VIX", "VIX", "index", last=30.0, prev=30.0)]
    msg_c = build_v15_message(quotes_c, compute_signals(quotes_c))
    assert "(공포)" in msg_c


def test_daytrade_candidates_sorted_by_signal_count_desc():
    """L1-msg-20 (FR-16, v5): 단타 후보 신호 수 내림차순 정렬."""
    quotes = [
        # NVDA: 2 신호 (거래량 + 갭)
        _q("NVDA", "엔비디아", "stock", "반도체",
           last=142, prev=140,
           open_today=142.5,
           volume_today=2_500_000, volume_avg_20d=1_000_000),
        # MU: 4 신호 (거래량 + 갭 + 신고가 + 시간외)
        _q("MU", "마이크론", "stock", "반도체",
           last=746, prev=646,
           open_today=730,
           volume_today=80_000_000, volume_avg_20d=10_000_000,
           high_52w=747,
           afterhours_close=757),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    # v7: "[오늘 단타 후보]" 섹션 헤더 (이모지 제거)
    candidate_section = msg.split("[오늘 단타 후보]")[1]
    mu_pos = candidate_section.index("마이크론 MU")
    nvda_pos = candidate_section.index("엔비디아 NVDA")
    assert mu_pos < nvda_pos


def test_candidate_reasons_show_specific_numbers():
    """L1-msg-21 (FR-17, v5): 단타 후보 사유에 이모지+숫자 압축 형식."""
    quotes = [
        _q("INTC", "인텔", "stock", "반도체",
           last=32.15, prev=28.20,
           open_today=31.59,
           volume_today=8_000_000, volume_avg_20d=1_000_000),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    # v5: "🔥8.0×", "🎯+12.0%" 이모지 + 숫자 한 줄
    assert "🔥8.0×" in msg
    assert "🎯+12.0%" in msg


def test_message_dump_and_width_diagnostics(capsys):
    """L1-msg-23 (FR-23, v6): _print_message_dump + _print_width_diagnostics 동작."""
    from main import _print_message_dump, _print_width_diagnostics

    msg = "📅 2026-05-11\n• 엔비디아 NVDA 142 +1.50% 🔥\n💡 푸터"
    _print_message_dump(msg)
    _print_width_diagnostics(msg)
    out = capsys.readouterr().out
    # marker 등장
    assert "===MSG-DUMP-BEGIN===" in out
    assert "===MSG-DUMP-END===" in out
    assert "===WIDTH-DIAG-BEGIN===" in out
    assert "===WIDTH-DIAG-END===" in out
    # 메시지 본문 포함
    assert "엔비디아 NVDA" in out
    # 폭 진단에 max line width 표시
    assert "max line width:" in out


def test_no_legend_line_in_v8():
    """L1-msg-22 (FR-27, v8): 범례 라인 제거 — 종목 옆 마크로 의미 자명.

    사용자 요청 (v8): "신호 앞에 아이콘 제거" → 💡 신호: ... 라인 자체 제거.
    """
    quotes = [
        _q("NVDA", "엔비디아", "stock", "반도체", last=142, prev=140),
    ]
    sigs = compute_signals(quotes)
    msg = build_v15_message(quotes, sigs)
    # v8: 범례 라인 자체 미등장
    assert "💡 신호:" not in msg
    assert "🔥거래량" not in msg  # 푸터/범례 문자열은 없음
